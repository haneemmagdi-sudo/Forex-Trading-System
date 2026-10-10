"""
==============================================================================
ml_models/train_pipeline.py — Quantum FSM Pro V4.2 Elite
==============================================================================
Module  : QuantumDQNTrainer — Deep Q-Network Training Pipeline with PRM
Author  : Principal Quantitative AI Architect
Version : 4.2.1
Inspired: Chapter 13 — DQN with Process Reward Models & Experience Replay
          (The Hitchhiker's Guide to Agentic AI: From Foundations to Systems)

Overview
--------
Implements QuantumDQNTrainer — the complete PyTorch-based DQN training
orchestration pipeline that hooks the QuantumPRMEnv into a full Deep
Q-Network training loop.

This module demonstrates how Process Rewards from QuantumPRMEnv are:
    1. Collected during environment interaction at each bar close step.
    2. Aggregated into a Prioritized-compatible Experience Replay Buffer.
    3. Sampled to form mini-batches for Q-function optimization.
    4. Used to compute Bellman TD targets for the Huber loss.
    5. Propagated through the QNetwork via the Adam optimizer.
    6. Used to update the soft target network via Polyak averaging.

DQN Architecture
----------------
The QNetwork is a 3-layer MLP with the following topology:

    Input  : state vector  shape (18,)
    Layer 1: Linear(18 -> 256)   + LayerNorm(256) + LeakyReLU(0.01)
    Layer 2: Linear(256 -> 128)  + LayerNorm(128) + LeakyReLU(0.01)
    Layer 3: Linear(128 -> 4)    (output: Q-values for each action, no activation)

Layer normalization is used instead of batch normalization because:
    - Trading sequences have highly non-stationary statistics.
    - Small batch sizes are common in RL replay (32-64 samples).
    - LayerNorm normalizes per-sample, eliminating batch size sensitivity.

Training Loop Architecture
--------------------------
For each training episode:
    1. Reset environment → get initial observation.
    2. For each step in the episode:
        a. Select action via epsilon-greedy (AdaptiveEpsilonController).
        b. Execute action in QuantumPRMEnv → get (obs_next, PRM_reward, done, info).
        c. Store Transition(state, action, PRM_reward, next_state, done) in ReplayBuffer.
        d. If buffer >= batch_size:
            i.  Sample random mini-batch of Transitions.
            ii. Compute Bellman TD targets:
                    y = r + gamma * max_a Q_target(s', a) * (1 - done)
            iii. Compute Huber loss:
                    L = SmoothL1Loss(Q_online(s, a), y)
            iv. Backpropagate L through Q_online.
            v.  Soft update Q_target parameters:
                    theta_target = tau * theta_online + (1 - tau) * theta_target
    3. Log episode metrics (reward, loss, epsilon, step count).

Key Hyperparameters
-------------------
    batch_size    : 64      Mini-batch size for experience replay sampling.
    gamma         : 0.99    Discount factor for future rewards.
    tau           : 0.005   Polyak soft target update rate.
    lr            : 1e-4    Adam learning rate.
    buffer_capacity: 50000  Maximum experience replay buffer capacity.
    train_freq    : 4       Steps between gradient updates.
    target_update : 100     Hard target sync (fallback, used alongside Polyak).

Bellman Equation (with PRM rewards)
------------------------------------
The Bellman optimality equation is applied using PROCESS rewards r_t
(the dense PRM composite reward) instead of sparse terminal rewards:

    Q*(s_t, a_t) = r_t + gamma * max_a Q*(s_{t+1}, a)   [if not terminal]
    Q*(s_t, a_t) = r_t                                    [if terminal]

Using PRM r_t (which ranges roughly in [-0.75, +0.35] per step instead of
{-1, 0, +1} at terminal only) produces much tighter TD error distributions,
stabilizing training significantly. The Huber loss (SmoothL1) is used to
further clip large TD errors that would otherwise cause divergence.

Experience Replay Buffer Design
---------------------------------
The UniformReplayBuffer stores Transition objects (validated by Pydantic v2)
in a circular numpy-backed array for memory efficiency. Sampling is O(1)
via random indexing rather than list shuffling.

In production, this can be replaced with a Prioritized Experience Replay (PER)
buffer by adding priority weights to the Transition schema and using
weighted random sampling based on TD error magnitude.
"""

from __future__ import annotations

import logging
import math
import os
import time
import uuid
from collections import deque
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from pydantic import BaseModel, Field, field_validator

# PyTorch imports
try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    from torch.optim import Adam
    from torch.optim.lr_scheduler import StepLR
    _TORCH_AVAILABLE: bool = True
except ImportError:
    _TORCH_AVAILABLE: bool = False
    raise ImportError(
        "PyTorch is required for QuantumDQNTrainer. "
        "Install with: pip install torch"
    )

# TensorBoard support (optional but recommended for production monitoring)
try:
    from torch.utils.tensorboard import SummaryWriter
    _TENSORBOARD_AVAILABLE: bool = True
except ImportError:
    _TENSORBOARD_AVAILABLE: bool = False
    SummaryWriter = None  # type: ignore[assignment]

# Internal imports
from ml_models.dqn_prm_env import (
    N_ACTIONS,
    STATE_DIM,
    QuantumPRMEnv,
    AdaptiveEpsilonController,
    MarketObservation,
    AccountTelemetry,
)

logger = logging.getLogger("quantum_fsm.train_pipeline")


# ===========================================================================
# Hyperparameter Defaults
# ===========================================================================

BATCH_SIZE:       int   = 64
GAMMA:            float = 0.99
TAU:              float = 0.005
LEARNING_RATE:    float = 1e-4
BUFFER_CAPACITY:  int   = 50_000
TRAIN_FREQ:       int   = 4         # gradient updates every N steps
TARGET_SYNC_FREQ: int   = 100       # hard target sync (fallback alongside Polyak)
GRAD_CLIP_NORM:   float = 10.0      # gradient norm clipping threshold


# ===========================================================================
# Pydantic v2 Schemas
# ===========================================================================


class Transition(BaseModel):
    """
    A single experience transition stored in the replay buffer.

    Validated by Pydantic v2 to prevent corrupt transitions from entering
    the buffer and producing invalid TD error calculations.

    Attributes
    ----------
    state       : list[float]   Current state observation. Shape: (STATE_DIM,).
    action      : int           Action taken by the agent.
    reward      : float         PRM process reward received after action.
    next_state  : list[float]   Next state observation. Shape: (STATE_DIM,).
    done        : bool          Whether this transition ended the episode.
    episode_id  : str           UUID hex identifier of the source episode.
    step_index  : int           Bar index within the episode.
    r_drawdown  : float         R_drawdown component (for diagnostics).
    r_grid_eff  : float         R_grid_efficiency component (for diagnostics).
    r_smc_align : float         R_smc_alignment component (for diagnostics).
    """
    state:       List[float]
    action:      int = Field(ge=0, lt=N_ACTIONS)
    reward:      float
    next_state:  List[float]
    done:        bool
    episode_id:  str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    step_index:  int = Field(default=0, ge=0)
    r_drawdown:  float = 0.0
    r_grid_eff:  float = 0.0
    r_smc_align: float = 0.0

    model_config = {"frozen": True}

    @field_validator("state", "next_state", mode="before")
    @classmethod
    def _validate_state_dim(cls, v: List[float]) -> List[float]:
        """Ensure state vectors have exactly STATE_DIM dimensions."""
        if len(v) != STATE_DIM:
            raise ValueError(
                f"State dimension mismatch: expected {STATE_DIM}, got {len(v)}."
            )
        # Sanitize NaN/Inf
        return [0.0 if (math.isnan(x) or math.isinf(x)) else x for x in v]


class TrainingConfig(BaseModel):
    """
    Validated training hyperparameter configuration.

    Attributes
    ----------
    batch_size       : int    Mini-batch size for replay buffer sampling.
    gamma            : float  Reward discount factor.
    tau              : float  Polyak soft target update rate.
    learning_rate    : float  Adam optimizer learning rate.
    buffer_capacity  : int    Maximum replay buffer capacity.
    train_freq       : int    Steps between gradient updates.
    target_sync_freq : int    Steps between hard target network syncs.
    grad_clip_norm   : float  Gradient norm clipping threshold.
    n_episodes       : int    Total training episodes.
    log_every        : int    Logging frequency in episodes.
    save_every       : int    Checkpoint save frequency in episodes.
    checkpoint_dir   : str    Directory for model checkpoints.
    tensorboard_dir  : str    Directory for TensorBoard logs.
    device           : str    PyTorch device string ("cpu", "cuda", "mps").
    seed             : int    Random seed for reproducibility.
    """
    batch_size:       int   = Field(default=BATCH_SIZE, ge=8, le=1024)
    gamma:            float = Field(default=GAMMA, gt=0.0, lt=1.0)
    tau:              float = Field(default=TAU, gt=0.0, lt=1.0)
    learning_rate:    float = Field(default=LEARNING_RATE, gt=0.0, lt=1.0)
    buffer_capacity:  int   = Field(default=BUFFER_CAPACITY, ge=1000)
    train_freq:       int   = Field(default=TRAIN_FREQ, ge=1)
    target_sync_freq: int   = Field(default=TARGET_SYNC_FREQ, ge=1)
    grad_clip_norm:   float = Field(default=GRAD_CLIP_NORM, gt=0.0)
    n_episodes:       int   = Field(default=500, ge=1)
    log_every:        int   = Field(default=10, ge=1)
    save_every:       int   = Field(default=50, ge=1)
    checkpoint_dir:   str   = Field(default="checkpoints/dqn_prm")
    tensorboard_dir:  str   = Field(default="runs/dqn_prm")
    device:           str   = Field(default="cpu")
    seed:             int   = Field(default=42, ge=0)

    model_config = {"frozen": False}

    @field_validator("device", mode="before")
    @classmethod
    def _validate_device(cls, v: str) -> str:
        """Auto-select GPU if available when device='auto'."""
        if v == "auto":
            if torch.cuda.is_available():
                return "cuda"
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                return "mps"
            else:
                return "cpu"
        return v


class EpisodeMetrics(BaseModel):
    """
    Per-episode training metrics emitted by the training loop.

    Attributes
    ----------
    episode         : int    Episode number.
    total_steps     : int    Total environment steps this episode.
    total_reward    : float  Cumulative PRM reward for this episode.
    mean_loss       : float  Mean TD Huber loss over gradient updates.
    max_loss        : float  Maximum TD loss step (spike detection).
    epsilon         : float  Epsilon at episode end.
    mean_q_value    : float  Mean max Q-value over the episode (policy quality).
    elapsed_sec     : float  Wall-clock time for this episode in seconds.
    grad_updates    : int    Number of gradient updates performed.
    buffer_size     : int    Current replay buffer fill level.
    boost_active    : bool   Whether PRM boost was active this episode.
    """
    episode:       int
    total_steps:   int
    total_reward:  float
    mean_loss:     float
    max_loss:      float
    epsilon:       float
    mean_q_value:  float
    elapsed_sec:   float
    grad_updates:  int
    buffer_size:   int
    boost_active:  bool

    model_config = {"frozen": True}

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()

    def log_str(self) -> str:
        """Format metrics as a concise log line."""
        return (
            f"[Ep {self.episode:04d}] "
            f"steps={self.total_steps:4d} | "
            f"reward={self.total_reward:+8.4f} | "
            f"loss={self.mean_loss:.5f} | "
            f"Q_mean={self.mean_q_value:.4f} | "
            f"eps={self.epsilon:.4f} | "
            f"buf={self.buffer_size:5d} | "
            f"t={self.elapsed_sec:.1f}s"
        )


# ===========================================================================
# QNetwork — Deep Q-Network PyTorch Module
# ===========================================================================

class QNetwork(nn.Module):
    """
    Deep Q-Network: 3-layer MLP with LayerNorm + LeakyReLU.

    Architecture
    ------------
    Input  : state vector  shape (state_dim,)  [default: 18]
    Layer 1: Linear(state_dim -> hidden1)  + LayerNorm + LeakyReLU(0.01)
    Layer 2: Linear(hidden1   -> hidden2)  + LayerNorm + LeakyReLU(0.01)
    Output : Linear(hidden2   -> n_actions)  (raw Q-values, no activation)

    Design Choices
    --------------
    1. LayerNorm (not BatchNorm): Trading features are non-stationary.
       LayerNorm normalizes each sample independently, making it robust
       to variable batch sizes and distribution shifts across trading sessions.

    2. LeakyReLU (negative_slope=0.01): Prevents dead neurons that are
       common with ReLU in RL training due to the all-negative reward
       regions that can occur with the PRM R_drawdown penalty (-0.75).

    3. No output activation: Q-values are unbounded scalars representing
       expected cumulative discounted returns. Sigmoid/Tanh would incorrectly
       constrain the Q-value range.

    Parameters
    ----------
    state_dim  : int   Input state dimension. Default: STATE_DIM (18).
    n_actions  : int   Number of discrete actions. Default: N_ACTIONS (4).
    hidden1    : int   First hidden layer width. Default: 256.
    hidden2    : int   Second hidden layer width. Default: 128.

    Example
    -------
    >>> net = QNetwork(state_dim=18, n_actions=4)
    >>> x = torch.randn(64, 18)   # batch of 64 states
    >>> q_vals = net(x)           # shape: (64, 4)
    """

    def __init__(
        self,
        state_dim: int = STATE_DIM,
        n_actions: int = N_ACTIONS,
        hidden1:   int = 256,
        hidden2:   int = 128,
    ) -> None:
        super().__init__()

        if state_dim <= 0:
            raise ValueError(f"state_dim must be > 0; received {state_dim}.")
        if n_actions <= 0:
            raise ValueError(f"n_actions must be > 0; received {n_actions}.")

        self.state_dim = state_dim
        self.n_actions = n_actions

        # Layer 1: input -> hidden1
        self.fc1   = nn.Linear(state_dim, hidden1)
        self.ln1   = nn.LayerNorm(hidden1)
        self.act1  = nn.LeakyReLU(negative_slope=0.01)

        # Layer 2: hidden1 -> hidden2
        self.fc2   = nn.Linear(hidden1, hidden2)
        self.ln2   = nn.LayerNorm(hidden2)
        self.act2  = nn.LeakyReLU(negative_slope=0.01)

        # Output layer: hidden2 -> Q-values (no activation)
        self.fc_out = nn.Linear(hidden2, n_actions)

        # Xavier (Glorot) initialization for stable gradient flow
        self._initialize_weights()

        total_params = sum(p.numel() for p in self.parameters())
        logger.info(
            "[QNetwork] Initialized | arch=%d->%d->%d->%d | "
            "total_params=%d",
            state_dim, hidden1, hidden2, n_actions,
            total_params,
        )

    def _initialize_weights(self) -> None:
        """Apply Xavier uniform initialization to all linear layers."""
        for module in [self.fc1, self.fc2, self.fc_out]:
            nn.init.xavier_uniform_(module.weight)
            nn.init.constant_(module.bias, 0.0)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass through the Q-network.

        Parameters
        ----------
        x : torch.Tensor  Input state tensor. Shape: (batch_size, state_dim).

        Returns
        -------
        torch.Tensor  Q-value estimates. Shape: (batch_size, n_actions).
        """
        x = self.act1(self.ln1(self.fc1(x)))
        x = self.act2(self.ln2(self.fc2(x)))
        return self.fc_out(x)


# ===========================================================================
# Experience Replay Buffer
# ===========================================================================

class UniformReplayBuffer:
    """
    Circular uniform experience replay buffer backed by pre-allocated numpy arrays.

    Stores Transition objects (validated by Pydantic v2) and provides
    O(1) insertion and O(batch_size) sampling via random index selection.

    The buffer operates in circular-overwrite mode: when capacity is reached,
    the oldest transitions are overwritten. This mirrors the standard DQN
    replay buffer design from DeepMind (Mnih et al., 2015).

    Parameters
    ----------
    capacity  : int  Maximum number of transitions to store.
    state_dim : int  Dimensionality of state/next_state vectors.

    Example
    -------
    >>> buf = UniformReplayBuffer(capacity=10000, state_dim=18)
    >>> buf.push(Transition(state=[0.1]*18, action=1, reward=0.1,
    ...                     next_state=[0.2]*18, done=False))
    >>> batch = buf.sample(64)
    """

    def __init__(
        self,
        capacity:  int = BUFFER_CAPACITY,
        state_dim: int = STATE_DIM,
    ) -> None:
        if capacity <= 0:
            raise ValueError(f"capacity must be > 0; received {capacity}.")

        self._capacity:  int = capacity
        self._state_dim: int = state_dim
        self._write_idx: int = 0
        self._size:      int = 0

        # Pre-allocate numpy arrays for memory efficiency
        self._states:      np.ndarray = np.zeros((capacity, state_dim), dtype=np.float32)
        self._actions:     np.ndarray = np.zeros(capacity, dtype=np.int64)
        self._rewards:     np.ndarray = np.zeros(capacity, dtype=np.float32)
        self._next_states: np.ndarray = np.zeros((capacity, state_dim), dtype=np.float32)
        self._dones:       np.ndarray = np.zeros(capacity, dtype=np.float32)

        # PRM component arrays for diagnostics
        self._r_drawdown:  np.ndarray = np.zeros(capacity, dtype=np.float32)
        self._r_grid_eff:  np.ndarray = np.zeros(capacity, dtype=np.float32)
        self._r_smc_align: np.ndarray = np.zeros(capacity, dtype=np.float32)

        logger.info(
            "[ReplayBuffer] Initialized | capacity=%d | state_dim=%d | "
            "memory_MB=%.1f",
            capacity,
            state_dim,
            (2 * capacity * state_dim * 4 + capacity * (4 + 4 + 4 + 3 * 4)) / 1e6,
        )

    def push(self, transition: Transition) -> None:
        """
        Add a validated Transition to the buffer.

        Overwrites the oldest entry when the buffer is full (circular).

        Parameters
        ----------
        transition : Transition  A Pydantic-validated experience tuple.
        """
        idx = self._write_idx

        self._states[idx]      = np.array(transition.state, dtype=np.float32)
        self._actions[idx]     = transition.action
        self._rewards[idx]     = transition.reward
        self._next_states[idx] = np.array(transition.next_state, dtype=np.float32)
        self._dones[idx]       = float(transition.done)
        self._r_drawdown[idx]  = transition.r_drawdown
        self._r_grid_eff[idx]  = transition.r_grid_eff
        self._r_smc_align[idx] = transition.r_smc_align

        self._write_idx = (idx + 1) % self._capacity
        self._size = min(self._size + 1, self._capacity)

    def sample(
        self,
        batch_size: int,
        device:     str = "cpu",
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        Sample a random mini-batch of transitions.

        Parameters
        ----------
        batch_size : int  Number of transitions to sample.
        device     : str  PyTorch device string for tensor allocation.

        Returns
        -------
        Tuple of:
            states      : torch.Tensor  shape (batch_size, state_dim), float32
            actions     : torch.Tensor  shape (batch_size,), int64
            rewards     : torch.Tensor  shape (batch_size,), float32
            next_states : torch.Tensor  shape (batch_size, state_dim), float32
            dones       : torch.Tensor  shape (batch_size,), float32
        """
        if batch_size > self._size:
            raise ValueError(
                f"Cannot sample {batch_size} transitions from buffer "
                f"of size {self._size}."
            )

        indices = np.random.randint(0, self._size, size=batch_size)

        states      = torch.tensor(self._states[indices],      dtype=torch.float32).to(device)
        actions     = torch.tensor(self._actions[indices],     dtype=torch.int64).to(device)
        rewards     = torch.tensor(self._rewards[indices],     dtype=torch.float32).to(device)
        next_states = torch.tensor(self._next_states[indices], dtype=torch.float32).to(device)
        dones       = torch.tensor(self._dones[indices],       dtype=torch.float32).to(device)

        return states, actions, rewards, next_states, dones

    def __len__(self) -> int:
        return self._size

    @property
    def is_ready(self) -> bool:
        """True when the buffer has at least BATCH_SIZE transitions."""
        return self._size >= BATCH_SIZE

    def __repr__(self) -> str:
        return (
            f"UniformReplayBuffer("
            f"size={self._size}/{self._capacity}, "
            f"write_idx={self._write_idx})"
        )


# ===========================================================================
# QuantumDQNTrainer — Full Training Orchestrator
# ===========================================================================

class QuantumDQNTrainer:
    """
    Full DQN training orchestration pipeline for QuantumPRMEnv.

    Hooks the QuantumPRMEnv into a PyTorch Deep Q-Network training loop
    that uses Process Reward Model (PRM) signals for dense gradient supervision.

    The trainer maintains two Q-networks (online and target) and performs
    soft Polyak averaging updates to the target network at each gradient step.

    Architecture Summary
    --------------------
    Q_online  : Learned Q-network (gradient updates via Adam + Huber loss)
    Q_target  : Soft-updated target network (Polyak averaging, tau=0.005)

    Training Loop (per episode):
        env.reset()
        while not done:
            action = eps_greedy(Q_online(state))
            next_state, r_process, done, info = env.step(action)
            buffer.push(Transition(...))
            if buffer.is_ready and step % train_freq == 0:
                batch = buffer.sample(batch_size)
                y = r + gamma * max_a Q_target(s') * (1 - done)
                loss = SmoothL1Loss(Q_online(s, a), y)
                optimizer.step(loss)
                polyak_update(Q_online, Q_target, tau)

    Parameters
    ----------
    env       : QuantumPRMEnv   The process reward environment.
    config    : TrainingConfig  Hyperparameters and training configuration.
    run_id    : str | None      Optional run identifier for logging namespacing.

    Example
    -------
    >>> from ml_models.dqn_prm_env import QuantumPRMEnv
    >>> from ml_models.train_pipeline import QuantumDQNTrainer, TrainingConfig
    >>>
    >>> # Build environment (with your market data)
    >>> env = QuantumPRMEnv(data=market_data_list)
    >>>
    >>> # Configure training
    >>> config = TrainingConfig(n_episodes=500, batch_size=64, device="auto")
    >>>
    >>> # Initialize and run trainer
    >>> trainer = QuantumDQNTrainer(env=env, config=config)
    >>> trainer.train()
    """

    def __init__(
        self,
        env:    QuantumPRMEnv,
        config: Optional[TrainingConfig] = None,
        run_id: Optional[str] = None,
    ) -> None:
        if not isinstance(env, QuantumPRMEnv):
            raise TypeError(
                f"env must be a QuantumPRMEnv; received {type(env).__name__}."
            )

        self._env:    QuantumPRMEnv   = env
        self._config: TrainingConfig  = config or TrainingConfig()
        self._run_id: str             = run_id or uuid.uuid4().hex[:8]
        self._device: torch.device    = torch.device(self._config.device)

        # Seed everything for reproducibility
        torch.manual_seed(self._config.seed)
        np.random.seed(self._config.seed)

        # ---------------------------------------------------------------
        # Q-Networks: online (trained) + target (soft-updated)
        # ---------------------------------------------------------------
        self._q_online: QNetwork = QNetwork(
            state_dim=STATE_DIM,
            n_actions=N_ACTIONS,
        ).to(self._device)

        self._q_target: QNetwork = QNetwork(
            state_dim=STATE_DIM,
            n_actions=N_ACTIONS,
        ).to(self._device)

        # Initialize target = online (full copy)
        self._hard_sync_target()
        self._q_target.eval()   # target never trains, eval mode only

        # ---------------------------------------------------------------
        # Optimizer, Loss, Scheduler
        # ---------------------------------------------------------------
        self._optimizer: Adam = Adam(
            self._q_online.parameters(),
            lr=self._config.learning_rate,
            weight_decay=1e-5,    # L2 regularization for policy stability
        )

        # Huber (SmoothL1) loss — robust to large TD errors
        self._loss_fn: nn.SmoothL1Loss = nn.SmoothL1Loss(reduction="mean")

        # Step LR decay: halve learning rate every 100 episodes
        self._lr_scheduler: StepLR = StepLR(
            self._optimizer,
            step_size=100,
            gamma=0.5,
        )

        # ---------------------------------------------------------------
        # Replay Buffer
        # ---------------------------------------------------------------
        self._replay_buffer: UniformReplayBuffer = UniformReplayBuffer(
            capacity=self._config.buffer_capacity,
            state_dim=STATE_DIM,
        )

        # ---------------------------------------------------------------
        # Training State Counters
        # ---------------------------------------------------------------
        self._global_step:   int = 0   # Total environment steps across all episodes
        self._grad_updates:  int = 0   # Total gradient update steps

        # ---------------------------------------------------------------
        # TensorBoard Writer (optional)
        # ---------------------------------------------------------------
        self._writer: Optional[Any] = None
        if _TENSORBOARD_AVAILABLE and SummaryWriter is not None:
            tb_dir = os.path.join(
                self._config.tensorboard_dir,
                f"run_{self._run_id}",
            )
            os.makedirs(tb_dir, exist_ok=True)
            self._writer = SummaryWriter(log_dir=tb_dir)
            logger.info(
                "[DQNTrainer] TensorBoard logging enabled at %s", tb_dir
            )
        else:
            logger.info(
                "[DQNTrainer] TensorBoard not available — using console logging only."
            )

        logger.info(
            "[QuantumDQNTrainer] Initialized | run_id=%s | device=%s | "
            "episodes=%d | batch=%d | gamma=%.3f | tau=%.4f | lr=%.2e",
            self._run_id,
            self._device,
            self._config.n_episodes,
            self._config.batch_size,
            self._config.gamma,
            self._config.tau,
            self._config.learning_rate,
        )

    # -----------------------------------------------------------------------
    # Main Training Entrypoint
    # -----------------------------------------------------------------------

    def train(self) -> List[EpisodeMetrics]:
        """
        Execute the full DQN training loop across all configured episodes.

        At each episode:
            1. Reset environment.
            2. Collect experience step-by-step using epsilon-greedy policy.
            3. Push transitions (with PRM rewards) into the replay buffer.
            4. Perform gradient updates every train_freq steps.
            5. Soft-update the target network via Polyak averaging.
            6. Log episode metrics to TensorBoard and console.
            7. Save checkpoints every save_every episodes.

        Returns
        -------
        list[EpisodeMetrics]
            Ordered list of per-episode training metrics for analysis.
        """
        all_metrics: List[EpisodeMetrics] = []
        episode_id = uuid.uuid4().hex[:8]

        logger.info(
            "[DQNTrainer] === Training START | run_id=%s | "
            "episodes=%d | device=%s ===",
            self._run_id,
            self._config.n_episodes,
            self._device,
        )

        for episode in range(1, self._config.n_episodes + 1):
            episode_start = time.perf_counter()
            episode_id    = uuid.uuid4().hex[:8]

            # Per-episode metrics accumulators
            episode_losses:   List[float] = []
            episode_q_values: List[float] = []
            episode_steps:    int         = 0
            episode_reward:   float       = 0.0
            episode_grad_upd: int         = 0

            # ---------------------------------------------------------------
            # 1. Reset environment
            # ---------------------------------------------------------------
            obs, reset_info = self._env.reset()
            done: bool = False

            # ---------------------------------------------------------------
            # 2. Episode interaction loop
            # ---------------------------------------------------------------
            while not done:
                self._global_step += 1
                episode_steps     += 1

                # ─── 2a. Select action via epsilon-greedy ───────────────
                state_tensor = torch.tensor(
                    obs, dtype=torch.float32
                ).unsqueeze(0).to(self._device)

                with torch.no_grad():
                    q_values = self._q_online(state_tensor).squeeze(0).cpu().numpy()

                action = self._env.epsilon_controller.select_action(q_values)

                episode_q_values.append(float(np.max(q_values)))

                # ─── 2b. Step environment ────────────────────────────────
                obs_next, r_process, terminated, truncated, step_info = (
                    self._env.step(action)
                )
                done = terminated or truncated
                episode_reward += r_process

                # ─── 2c. Push transition to replay buffer ─────────────────
                transition = Transition(
                    state=obs.tolist(),
                    action=action,
                    reward=float(r_process),
                    next_state=obs_next.tolist(),
                    done=done,
                    episode_id=episode_id,
                    step_index=episode_steps,
                    r_drawdown=float(step_info.get("r_drawdown",  0.0)),
                    r_grid_eff=float(step_info.get("r_grid_efficiency", 0.0)),
                    r_smc_align=float(step_info.get("r_smc_alignment", 0.0)),
                )
                self._replay_buffer.push(transition)

                # ─── 2d. Gradient update every train_freq steps ──────────
                if (
                    self._replay_buffer.is_ready
                    and self._global_step % self._config.train_freq == 0
                ):
                    loss_val = self._gradient_update()
                    episode_losses.append(loss_val)
                    episode_grad_upd += 1
                    self._grad_updates += 1

                    # Hard sync target network periodically (fallback safety)
                    if self._grad_updates % self._config.target_sync_freq == 0:
                        self._hard_sync_target()
                        logger.debug(
                            "[DQNTrainer] Hard target sync at grad_update=%d",
                            self._grad_updates,
                        )

                obs = obs_next

            # ---------------------------------------------------------------
            # 3. Update LR scheduler at episode boundary
            # ---------------------------------------------------------------
            self._lr_scheduler.step()

            # ---------------------------------------------------------------
            # 4. Compile episode metrics
            # ---------------------------------------------------------------
            elapsed_sec  = time.perf_counter() - episode_start
            mean_loss    = float(np.mean(episode_losses))    if episode_losses   else 0.0
            max_loss     = float(np.max(episode_losses))     if episode_losses   else 0.0
            mean_q_value = float(np.mean(episode_q_values))  if episode_q_values else 0.0
            eps_ctrl     = self._env.epsilon_controller

            metrics = EpisodeMetrics(
                episode=episode,
                total_steps=episode_steps,
                total_reward=episode_reward,
                mean_loss=mean_loss,
                max_loss=max_loss,
                epsilon=eps_ctrl.epsilon,
                mean_q_value=mean_q_value,
                elapsed_sec=elapsed_sec,
                grad_updates=episode_grad_upd,
                buffer_size=len(self._replay_buffer),
                boost_active=(
                    eps_ctrl.boosts_applied > 0
                    and episode == eps_ctrl.episodes_elapsed
                ),
            )
            all_metrics.append(metrics)

            # ---------------------------------------------------------------
            # 5. Logging
            # ---------------------------------------------------------------
            if episode % self._config.log_every == 0 or episode == 1:
                logger.info(metrics.log_str())
                self._log_to_tensorboard(metrics)

            # ---------------------------------------------------------------
            # 6. Checkpoint saving
            # ---------------------------------------------------------------
            if episode % self._config.save_every == 0:
                self._save_checkpoint(episode)

        # Final checkpoint
        self._save_checkpoint(self._config.n_episodes, suffix="final")

        if self._writer is not None:
            self._writer.close()

        logger.info(
            "[DQNTrainer] === Training COMPLETE | run_id=%s | "
            "total_steps=%d | total_grad_updates=%d | final_eps=%.4f ===",
            self._run_id,
            self._global_step,
            self._grad_updates,
            self._env.epsilon_controller.epsilon,
        )

        return all_metrics

    # -----------------------------------------------------------------------
    # Gradient Update Step
    # -----------------------------------------------------------------------

    def _gradient_update(self) -> float:
        """
        Perform a single gradient update step on the online Q-network.

        Implements the full DQN Bellman update with:
            1. Mini-batch sampling from the replay buffer.
            2. Bellman TD target computation via the target Q-network.
            3. Huber (SmoothL1) loss between online Q and TD targets.
            4. Gradient clipping to prevent exploding gradients.
            5. Polyak soft-update of the target network.

        Bellman TD Target Computation
        ------------------------------
        For a sampled transition (s, a, r, s', done):

            # Q-values from target network for next states
            Q_target_next = Q_target(s').max(dim=1)    # shape: (batch,)

            # TD target (Bellman equation with PRM reward r_process):
            y = r + gamma * Q_target_next * (1 - done)

            # Current Q-value for the taken action:
            Q_current = Q_online(s).gather(1, a)       # shape: (batch, 1)

            # Huber loss:
            loss = SmoothL1Loss(Q_current, y)

        The done mask (1 - done) ensures that terminal transitions have
        no bootstrapped future value — only the immediate PRM reward r.

        Polyak Soft Update
        ------------------
        After each gradient step, the target network parameters are
        updated toward the online network parameters:

            theta_target <- tau * theta_online + (1 - tau) * theta_target

        With tau=0.005, the target network tracks the online network very
        slowly (approximately 0.5% of the online parameters per step),
        providing stable TD targets across consecutive gradient updates.

        Returns
        -------
        float  The scalar Huber loss value for this update step.
        """
        # 1. Sample mini-batch from replay buffer
        states, actions, rewards, next_states, dones = self._replay_buffer.sample(
            batch_size=self._config.batch_size,
            device=str(self._device),
        )

        # 2. Compute TD targets with target network (no gradients)
        with torch.no_grad():
            # Q-values for next states from target network: shape (batch, n_actions)
            q_next_all: torch.Tensor = self._q_target(next_states)

            # Double DQN: use online network to SELECT action, target to EVALUATE
            # This reduces overestimation bias in Q-value estimates
            q_next_select: torch.Tensor = self._q_online(next_states)
            best_actions: torch.Tensor  = q_next_select.argmax(dim=1, keepdim=True)

            # Evaluate selected actions using target network
            q_next_best: torch.Tensor = q_next_all.gather(1, best_actions).squeeze(1)

            # Bellman target: r + gamma * max Q_target(s') * (1 - done)
            td_targets: torch.Tensor = (
                rewards + self._config.gamma * q_next_best * (1.0 - dones)
            )
            # Shape: (batch,)

        # 3. Compute online Q-values for the actions actually taken
        q_online_all: torch.Tensor = self._q_online(states)
        # Gather Q-values for the specific action taken: shape (batch, 1) -> (batch,)
        q_online_taken: torch.Tensor = q_online_all.gather(
            1, actions.unsqueeze(1)
        ).squeeze(1)

        # 4. Compute Huber loss between online Q and TD targets
        loss: torch.Tensor = self._loss_fn(q_online_taken, td_targets)

        # 5. Backpropagation
        self._optimizer.zero_grad()
        loss.backward()

        # 6. Gradient norm clipping (prevent exploding gradients)
        nn.utils.clip_grad_norm_(
            self._q_online.parameters(),
            max_norm=self._config.grad_clip_norm,
        )

        # 7. Optimizer step
        self._optimizer.step()

        # 8. Polyak soft-update of target network
        # theta_target <- tau * theta_online + (1 - tau) * theta_target
        self._polyak_update()

        loss_value = float(loss.item())

        logger.debug(
            "[DQNTrainer] Gradient update %d | loss=%.5f | lr=%.2e",
            self._grad_updates,
            loss_value,
            self._optimizer.param_groups[0]["lr"],
        )

        return loss_value

    # -----------------------------------------------------------------------
    # Target Network Update Methods
    # -----------------------------------------------------------------------

    def _polyak_update(self) -> None:
        """
        Apply Polyak (exponential moving average) soft update to target network.

        For each parameter pair (online_param, target_param):
            target_param <- tau * online_param + (1 - tau) * target_param

        With tau=0.005, this provides extremely slow, stable target updates
        that prevent oscillation in the Bellman targets during training.

        This is mathematically equivalent to an EMA with alpha=tau, tracking
        the online network with a lag of approximately 1/tau = 200 gradient steps.
        """
        tau = self._config.tau
        with torch.no_grad():
            for online_param, target_param in zip(
                self._q_online.parameters(),
                self._q_target.parameters(),
            ):
                target_param.data.mul_(1.0 - tau)
                target_param.data.add_(tau * online_param.data)

    def _hard_sync_target(self) -> None:
        """
        Perform a complete hard copy of online network weights to target network.

        Used for:
            1. Initial parameter synchronization (target = online at episode 0).
            2. Periodic hard sync as a safety fallback (every target_sync_freq updates).
        """
        self._q_target.load_state_dict(self._q_online.state_dict())

    # -----------------------------------------------------------------------
    # Checkpointing
    # -----------------------------------------------------------------------

    def _save_checkpoint(self, episode: int, suffix: str = "") -> None:
        """
        Save the online Q-network state dict and training metadata to disk.

        Parameters
        ----------
        episode : int   Current episode number.
        suffix  : str   Optional suffix for the checkpoint filename.
        """
        os.makedirs(self._config.checkpoint_dir, exist_ok=True)

        fname = (
            f"dqn_prm_{self._run_id}_ep{episode:04d}"
            f"{'_' + suffix if suffix else ''}.pt"
        )
        fpath = os.path.join(self._config.checkpoint_dir, fname)

        checkpoint = {
            "episode":         episode,
            "run_id":          self._run_id,
            "global_step":     self._global_step,
            "grad_updates":    self._grad_updates,
            "q_online_state":  self._q_online.state_dict(),
            "q_target_state":  self._q_target.state_dict(),
            "optimizer_state": self._optimizer.state_dict(),
            "epsilon":         self._env.epsilon_controller.epsilon,
            "config":          self._config.model_dump(),
        }

        torch.save(checkpoint, fpath)
        logger.info(
            "[DQNTrainer] Checkpoint saved: %s (episode=%d, steps=%d)",
            fname,
            episode,
            self._global_step,
        )

    def load_checkpoint(self, checkpoint_path: str) -> int:
        """
        Restore a previously saved training checkpoint.

        Loads Q-network weights, target network weights, optimizer state,
        and epsilon from the checkpoint file, enabling training to resume
        from where it was interrupted.

        Parameters
        ----------
        checkpoint_path : str  Full path to the .pt checkpoint file.

        Returns
        -------
        int  Episode number at which the checkpoint was saved.
        """
        if not os.path.exists(checkpoint_path):
            raise FileNotFoundError(
                f"Checkpoint not found: {checkpoint_path}"
            )

        checkpoint = torch.load(checkpoint_path, map_location=self._device)

        self._q_online.load_state_dict(checkpoint["q_online_state"])
        self._q_target.load_state_dict(checkpoint["q_target_state"])
        self._optimizer.load_state_dict(checkpoint["optimizer_state"])
        self._global_step  = checkpoint.get("global_step", 0)
        self._grad_updates = checkpoint.get("grad_updates", 0)

        # Restore epsilon in the controller
        restored_eps = checkpoint.get("epsilon", self._env.epsilon_controller.epsilon)
        self._env.epsilon_controller.epsilon = restored_eps

        episode = checkpoint.get("episode", 0)
        logger.info(
            "[DQNTrainer] Checkpoint loaded: %s | "
            "episode=%d | global_step=%d | epsilon=%.4f",
            os.path.basename(checkpoint_path),
            episode,
            self._global_step,
            restored_eps,
        )

        return episode

    # -----------------------------------------------------------------------
    # TensorBoard Logging
    # -----------------------------------------------------------------------

    def _log_to_tensorboard(self, metrics: EpisodeMetrics) -> None:
        """
        Log episode metrics to TensorBoard for visualization and monitoring.

        Parameters
        ----------
        metrics : EpisodeMetrics  Per-episode training metrics.
        """
        if self._writer is None:
            return

        ep = metrics.episode
        self._writer.add_scalar("reward/episode_total", metrics.total_reward, ep)
        self._writer.add_scalar("reward/episode_mean_per_step",
                                metrics.total_reward / max(metrics.total_steps, 1), ep)
        self._writer.add_scalar("loss/mean_huber", metrics.mean_loss, ep)
        self._writer.add_scalar("loss/max_huber",  metrics.max_loss,  ep)
        self._writer.add_scalar("policy/epsilon",  metrics.epsilon,   ep)
        self._writer.add_scalar("policy/mean_q_value", metrics.mean_q_value, ep)
        self._writer.add_scalar("training/grad_updates", metrics.grad_updates, ep)
        self._writer.add_scalar("training/buffer_size",  metrics.buffer_size,  ep)
        self._writer.add_scalar("training/episode_steps", metrics.total_steps,  ep)
        self._writer.add_scalar("training/elapsed_sec",   metrics.elapsed_sec,  ep)
        self._writer.add_scalar("training/lr",
                                self._optimizer.param_groups[0]["lr"], ep)

    # -----------------------------------------------------------------------
    # Inference
    # -----------------------------------------------------------------------

    def predict(
        self,
        state: np.ndarray,
        deterministic: bool = True,
    ) -> Tuple[int, np.ndarray]:
        """
        Predict the best action for a given state using the trained online Q-network.

        Parameters
        ----------
        state         : np.ndarray  State observation. Shape: (STATE_DIM,).
        deterministic : bool        If True, always select argmax Q. If False,
                                    use current epsilon-greedy policy.

        Returns
        -------
        action   : int          Best action index.
        q_values : np.ndarray   Q-values for all actions. Shape: (N_ACTIONS,).
        """
        self._q_online.eval()
        with torch.no_grad():
            state_tensor = torch.tensor(
                state, dtype=torch.float32
            ).unsqueeze(0).to(self._device)
            q_values = self._q_online(state_tensor).squeeze(0).cpu().numpy()

        if deterministic:
            action = int(np.argmax(q_values))
        else:
            action = self._env.epsilon_controller.select_action(q_values)

        self._q_online.train()
        return action, q_values

    # -----------------------------------------------------------------------
    # Properties
    # -----------------------------------------------------------------------

    @property
    def q_online(self) -> QNetwork:
        """Reference to the trained online Q-network."""
        return self._q_online

    @property
    def q_target(self) -> QNetwork:
        """Reference to the soft-updated target Q-network."""
        return self._q_target

    @property
    def global_step(self) -> int:
        """Total environment steps processed across all episodes."""
        return self._global_step

    @property
    def total_grad_updates(self) -> int:
        """Total gradient update steps performed."""
        return self._grad_updates

    def __repr__(self) -> str:
        return (
            f"QuantumDQNTrainer("
            f"run_id={self._run_id}, "
            f"device={self._device}, "
            f"episodes={self._config.n_episodes}, "
            f"buffer={len(self._replay_buffer)}/{self._config.buffer_capacity})"
        )


# ===========================================================================
# Convenience Factory / Entrypoint
# ===========================================================================

def train_dqn_agent(
    market_data: List[Tuple[MarketObservation, AccountTelemetry]],
    n_episodes:  int   = 500,
    device:      str   = "auto",
    batch_size:  int   = 64,
    gamma:       float = 0.99,
    tau:         float = 0.005,
    seed:        int   = 42,
    checkpoint_dir: str = "checkpoints/dqn_prm",
    tensorboard_dir: str = "runs/dqn_prm",
) -> Tuple[QuantumDQNTrainer, List[EpisodeMetrics]]:
    """
    Convenience factory function: build and train a DQN agent on market data.

    This function wires together the full pipeline:
        1. Constructs the QuantumPRMEnv with the provided market data.
        2. Configures training hyperparameters.
        3. Initializes and runs the QuantumDQNTrainer.
        4. Returns the trainer (with the trained Q-network) and all metrics.

    Parameters
    ----------
    market_data     : list  Bar-level replay data (MarketObservation + AccountTelemetry).
    n_episodes      : int   Total training episodes. Default: 500.
    device          : str   PyTorch device ("cpu", "cuda", "mps", "auto"). Default: "auto".
    batch_size      : int   Replay buffer mini-batch size. Default: 64.
    gamma           : float Discount factor. Default: 0.99.
    tau             : float Polyak soft update rate. Default: 0.005.
    seed            : int   Random seed. Default: 42.
    checkpoint_dir  : str   Directory to save model checkpoints.
    tensorboard_dir : str   Directory to save TensorBoard logs.

    Returns
    -------
    trainer : QuantumDQNTrainer   Trained agent (use trainer.predict() for inference).
    metrics : list[EpisodeMetrics] Per-episode training metrics.

    Example
    -------
    >>> from ml_models.dqn_prm_env import MarketObservation, AccountTelemetry
    >>> from ml_models.train_pipeline import train_dqn_agent
    >>>
    >>> # Build your market data list
    >>> market_data = [(MarketObservation(), AccountTelemetry(
    ...     balance=10000, equity=10000, free_margin=9000,
    ...     margin_used=1000, floating_pnl=0, open_position_count=0,
    ...     drawdown_pct=0.0
    ... )) for _ in range(1000)]
    >>>
    >>> trainer, metrics = train_dqn_agent(
    ...     market_data=market_data,
    ...     n_episodes=300,
    ...     device="auto",
    ... )
    >>>
    >>> # Inference: predict action for live state
    >>> import numpy as np
    >>> live_state = np.zeros(18, dtype=np.float32)
    >>> action, q_values = trainer.predict(live_state, deterministic=True)
    >>> print(f"Best action: {action} | Q-values: {q_values}")
    """
    logger.info(
        "[train_dqn_agent] Starting DQN training | "
        "data_bars=%d | episodes=%d | device=%s | seed=%d",
        len(market_data),
        n_episodes,
        device,
        seed,
    )

    # 1. Build environment
    env = QuantumPRMEnv(
        data=market_data,
        dd_safety_threshold=DD_SAFETY_THRESHOLD,
        max_episode_steps=MAX_EPISODE_STEPS,
        seed=seed,
    )

    # 2. Configure training
    config = TrainingConfig(
        n_episodes=n_episodes,
        batch_size=batch_size,
        gamma=gamma,
        tau=tau,
        device=device,
        seed=seed,
        checkpoint_dir=checkpoint_dir,
        tensorboard_dir=tensorboard_dir,
    )

    # 3. Initialize trainer
    trainer = QuantumDQNTrainer(env=env, config=config)

    # 4. Run training
    metrics = trainer.train()

    logger.info(
        "[train_dqn_agent] Training complete | "
        "final_eps=%.4f | total_steps=%d | episodes=%d",
        trainer.q_online.training,  # will just confirm it's in train mode
        trainer.global_step,
        n_episodes,
    )

    return trainer, metrics


# Make key constants importable
from ml_models.dqn_prm_env import (
    DD_SAFETY_THRESHOLD,
    MAX_EPISODE_STEPS,
)

__all__ = [
    "QNetwork",
    "UniformReplayBuffer",
    "Transition",
    "TrainingConfig",
    "EpisodeMetrics",
    "QuantumDQNTrainer",
    "train_dqn_agent",
]
