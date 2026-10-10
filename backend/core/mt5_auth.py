"""
==============================================================
backend/core/mt5_auth.py — Antigravity MT5 Authentication Layer
==============================================================
Production-grade MetaTrader 5 connection initialiser.

Responsibilities
----------------
* Load MT5 credentials **exclusively** from environment variables
  (never hard-coded). Uses ``python-dotenv`` to populate the process
  environment from the project-root ``.env`` file before reading vars.
* Attempt an optional terminal-path launch so the MT5 terminal can be
  started programmatically when ``MT5_TERMINAL_PATH`` is provided.
* Perform a structured authentication sequence:
    1. ``mt5.initialize()``   — start the MT5 API bridge.
    2. ``mt5.login()``        — authenticate with the broker server.
    3. Verify the returned ``AccountInfo`` and log the result.
* Expose a lightweight ``MT5AuthResult`` dataclass so callers can
  inspect every field of the connection outcome without relying on
  module-level globals.
* Provide a ``teardown()`` helper that cleanly shuts down the MT5 bridge.

Security notes
--------------
* ``MT5_PASSWORD`` is never written to any log sink.  The ``SecureStr``
  wrapper ensures accidental ``str(password)`` calls produce only ``***``.
* All credential validation happens **before** the first MT5 API call
  so the system fails fast if the environment is mis-configured.

Usage
-----
    from backend.core.mt5_auth import MT5AuthManager

    auth = MT5AuthManager()
    result = auth.connect()
    if result.success:
        print(result.account_info)
    ...
    auth.teardown()
"""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from loguru import logger

# ── Project-root .env injection (idempotent — safe to call multiple times) ──
_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"
if _ENV_FILE.is_file():
    try:
        from dotenv import load_dotenv  # type: ignore
        load_dotenv(dotenv_path=_ENV_FILE, override=False)
    except ImportError:
        logger.warning(
            "python-dotenv not installed; relying on shell-exported env vars."
        )

# ── Optional MetaTrader5 import (Windows-only native library) ───────────────
try:
    import MetaTrader5 as mt5  # type: ignore

    _MT5_AVAILABLE: bool = True
except ImportError:
    mt5 = None  # type: ignore
    _MT5_AVAILABLE = False
    logger.warning(
        "MetaTrader5 library not found — MT5Auth will operate in UNAVAILABLE mode."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────


class _SecureStr:
    """
    Thin wrapper that prevents a secret string from appearing in logs,
    repr(), or str() output.

    Attributes
    ----------
    _value : str
        The underlying plaintext secret. Access via ``.reveal()``.
    """

    __slots__ = ("_value",)

    def __init__(self, value: str) -> None:
        self._value = value

    def reveal(self) -> str:
        """Return the actual plaintext value — use sparingly."""
        return self._value

    def __repr__(self) -> str:
        return "***"

    def __str__(self) -> str:
        return "***"


def _require_env(key: str) -> str:
    """
    Read a mandatory environment variable, raising ``EnvironmentError``
    with a clear human-readable message if it is absent or empty.

    Parameters
    ----------
    key : str
        Name of the environment variable to read.

    Returns
    -------
    str
        The non-empty variable value.

    Raises
    ------
    EnvironmentError
        If the variable is missing or blank.
    """
    value = os.environ.get(key, "").strip()
    if not value:
        raise EnvironmentError(
            f"Required environment variable '{key}' is not set. "
            f"Add it to your .env file or export it in the shell before "
            f"starting the process."
        )
    return value


def _optional_env(key: str, default: str = "") -> str:
    """
    Read an optional environment variable.

    Parameters
    ----------
    key : str
        Name of the environment variable.
    default : str
        Value to return when the variable is absent.

    Returns
    -------
    str
        The variable value or ``default``.
    """
    return os.environ.get(key, default).strip()


# ─────────────────────────────────────────────────────────────────────────────
# Public data structures
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class MT5Credentials:
    """
    Validated MT5 login credentials loaded from environment variables.

    Environment Variables Expected
    ------------------------------
    MT5_LOGIN          : Broker account number (integer).
    MT5_PASSWORD       : Broker account password (wrapped in _SecureStr).
    MT5_SERVER         : Broker server name, e.g. ``ICMarketsSC-Demo``.
    MT5_TERMINAL_PATH  : (Optional) Absolute path to ``terminal64.exe``.
    MT5_TIMEOUT_MS     : (Optional) API timeout in milliseconds (default 10 000).
    MT5_PORTABLE       : (Optional) ``"true"`` to enable portable mode.
    """

    login: int
    password: _SecureStr
    server: str
    terminal_path: Optional[Path]
    timeout_ms: int
    portable: bool

    @classmethod
    def from_env(cls) -> "MT5Credentials":
        """
        Instantiate credentials by reading exclusively from the process
        environment.  Fails fast with descriptive errors if mandatory
        variables are missing or malformed.

        Returns
        -------
        MT5Credentials
            Fully validated credential object.

        Raises
        ------
        EnvironmentError
            When ``MT5_LOGIN``, ``MT5_PASSWORD``, or ``MT5_SERVER`` are absent.
        ValueError
            When ``MT5_LOGIN`` cannot be parsed as a positive integer.
        """
        raw_login = _require_env("MT5_LOGIN")
        try:
            login_int = int(raw_login)
            if login_int <= 0:
                raise ValueError("Login must be a positive integer.")
        except ValueError as exc:
            raise ValueError(
                f"MT5_LOGIN='{raw_login}' is not a valid positive integer. "
                f"Set it to your numeric broker account number."
            ) from exc

        raw_password = _require_env("MT5_PASSWORD")
        server = _require_env("MT5_SERVER")

        # Optional terminal path — validated only if supplied
        raw_path = _optional_env("MT5_TERMINAL_PATH")
        terminal_path: Optional[Path] = None
        if raw_path:
            terminal_path = Path(raw_path)
            if not terminal_path.is_file():
                logger.warning(
                    f"MT5_TERMINAL_PATH='{terminal_path}' does not exist on disk. "
                    f"Auto-launch will be skipped; MT5 must be running manually."
                )
                terminal_path = None

        # Optional timeout (default: 10 000 ms)
        raw_timeout = _optional_env("MT5_TIMEOUT_MS", "10000")
        try:
            timeout_ms = max(1000, int(raw_timeout))
        except ValueError:
            logger.warning(
                f"MT5_TIMEOUT_MS='{raw_timeout}' is not a valid integer; "
                f"defaulting to 10 000 ms."
            )
            timeout_ms = 10_000

        portable = _optional_env("MT5_PORTABLE", "false").lower() == "true"

        return cls(
            login=login_int,
            password=_SecureStr(raw_password),
            server=server,
            terminal_path=terminal_path,
            timeout_ms=timeout_ms,
            portable=portable,
        )


@dataclass
class MT5AccountSnapshot:
    """
    Immutable snapshot of the MT5 account state captured at login time.

    All monetary values are in the account's base currency.
    """

    login: int
    server: str
    broker: str
    currency: str
    leverage: int
    balance: float
    equity: float
    margin: float
    free_margin: float
    margin_level_pct: float
    trade_allowed: bool
    captured_at: float = field(default_factory=time.time)

    @property
    def drawdown_pct(self) -> float:
        """Live drawdown percentage relative to balance."""
        if self.balance <= 0:
            return 0.0
        return max(0.0, round((self.balance - self.equity) / self.balance * 100, 4))

    def to_dict(self) -> dict:
        """Serialise to a plain dict suitable for JSON/log output."""
        return {
            "login": self.login,
            "server": self.server,
            "broker": self.broker,
            "currency": self.currency,
            "leverage": self.leverage,
            "balance": self.balance,
            "equity": self.equity,
            "margin": self.margin,
            "free_margin": self.free_margin,
            "margin_level_pct": self.margin_level_pct,
            "drawdown_pct": self.drawdown_pct,
            "trade_allowed": self.trade_allowed,
            "captured_at_unix": self.captured_at,
        }


@dataclass
class MT5AuthResult:
    """
    Structured result returned by ``MT5AuthManager.connect()``.

    Attributes
    ----------
    success : bool
        ``True`` if MT5 is initialised, authenticated, and the account
        info was successfully read.
    account_info : MT5AccountSnapshot | None
        Populated only when ``success=True``.
    error_code : int | None
        Raw MT5 error code on failure (from ``mt5.last_error()``).
    error_message : str
        Human-readable failure description.
    mt5_available : bool
        Whether the ``MetaTrader5`` library could be imported at all.
    """

    success: bool
    account_info: Optional[MT5AccountSnapshot] = None
    error_code: Optional[int] = None
    error_message: str = ""
    mt5_available: bool = _MT5_AVAILABLE

    @property
    def is_live(self) -> bool:
        """``True`` when connected AND trade execution is enabled."""
        return (
            self.success
            and self.account_info is not None
            and self.account_info.trade_allowed
        )


# ─────────────────────────────────────────────────────────────────────────────
# Main manager class
# ─────────────────────────────────────────────────────────────────────────────


class MT5AuthManager:
    """
    Production-grade MetaTrader 5 authentication manager.

    This class separates the *authentication concern* from the rest of the
    trading system.  It does not place orders or read market data — it only
    handles connecting, validating, and disconnecting from the MT5 terminal.

    Typical lifecycle
    -----------------
    1. Instantiate once per process: ``auth = MT5AuthManager()``.
    2. Call ``auth.connect()`` → inspect ``MT5AuthResult``.
    3. Use the returned ``account_info`` to seed the rest of the system.
    4. Call ``auth.teardown()`` on process exit (or use as a context manager).

    Thread-safety
    -------------
    The MetaTrader5 C-extension uses a global singleton internally, so
    only one ``MT5AuthManager`` should exist per process.  Multiple
    instances calling ``mt5.initialize()`` concurrently is unsupported.

    Parameters
    ----------
    max_retries : int
        Number of connection attempts before giving up (default 3).
    retry_delay_sec : float
        Seconds to wait between retries (default 2.0).
    """

    def __init__(
        self,
        max_retries: int = 3,
        retry_delay_sec: float = 2.0,
    ) -> None:
        self._max_retries = max(1, max_retries)
        self._retry_delay = max(0.5, retry_delay_sec)
        self._credentials: Optional[MT5Credentials] = None
        self._connected: bool = False
        logger.debug(
            f"MT5AuthManager initialised | "
            f"mt5_available={_MT5_AVAILABLE} | "
            f"max_retries={self._max_retries}"
        )

    # ── Public API ────────────────────────────────────────────────────────────

    def connect(self) -> MT5AuthResult:
        """
        Load credentials from environment variables and establish the MT5
        connection with automatic retry logic.

        The method:
        1. Validates credentials via ``MT5Credentials.from_env()``.
        2. Calls ``_initialise_terminal()`` (respects ``MT5_TERMINAL_PATH``).
        3. Calls ``_authenticate()`` to perform the broker login.
        4. Fetches and validates ``mt5.account_info()``.

        Returns
        -------
        MT5AuthResult
            A fully populated result object (success or failure).
        """
        if not _MT5_AVAILABLE:
            msg = (
                "MetaTrader5 package is not installed. "
                "Install it with: pip install MetaTrader5"
            )
            logger.error(msg)
            return MT5AuthResult(success=False, error_message=msg)

        # ── Step 1: Load & validate credentials ──────────────────────────
        try:
            self._credentials = MT5Credentials.from_env()
        except (EnvironmentError, ValueError) as exc:
            logger.error(f"Credential validation failed: {exc}")
            return MT5AuthResult(success=False, error_message=str(exc))

        logger.info(
            f"Connecting to MT5 | login={self._credentials.login} | "
            f"server={self._credentials.server}"
        )

        # ── Step 2 + 3: Initialise terminal + authenticate with retries ──
        for attempt in range(1, self._max_retries + 1):
            result = self._attempt_connection()
            if result.success:
                self._connected = True
                logger.success(
                    f"MT5 authenticated ✓ | "
                    f"login={result.account_info.login} | "
                    f"server={result.account_info.server} | "
                    f"balance={result.account_info.balance:,.2f} "
                    f"{result.account_info.currency} | "
                    f"leverage=1:{result.account_info.leverage}"
                )
                return result

            logger.warning(
                f"Connection attempt {attempt}/{self._max_retries} failed: "
                f"[{result.error_code}] {result.error_message}"
            )
            if attempt < self._max_retries:
                logger.info(f"Retrying in {self._retry_delay:.1f}s …")
                time.sleep(self._retry_delay)

        logger.error("All MT5 connection attempts exhausted.")
        return result  # last failed result

    def teardown(self) -> None:
        """
        Gracefully shut down the MT5 terminal bridge.

        Safe to call even if ``connect()`` was never called or failed.
        """
        if not _MT5_AVAILABLE:
            return
        try:
            mt5.shutdown()
            self._connected = False
            logger.info("MT5 terminal bridge shut down cleanly.")
        except Exception as exc:
            logger.warning(f"MT5 shutdown raised an unexpected error: {exc}")

    @property
    def is_connected(self) -> bool:
        """``True`` if the last ``connect()`` call succeeded."""
        return self._connected

    # ── Context manager protocol ──────────────────────────────────────────────

    def __enter__(self) -> "MT5AuthManager":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.teardown()

    # ── Private helpers ───────────────────────────────────────────────────────

    def _attempt_connection(self) -> MT5AuthResult:
        """Single end-to-end connection attempt (no retry logic here)."""
        assert self._credentials is not None  # guaranteed by connect()

        # ── 2a: Initialise MT5 terminal bridge ────────────────────────────
        init_ok = self._initialise_terminal()
        if not init_ok:
            code, msg = mt5.last_error()
            return MT5AuthResult(
                success=False,
                error_code=code,
                error_message=f"mt5.initialize() failed: [{code}] {msg}",
            )

        # ── 2b: Broker authentication ─────────────────────────────────────
        auth_ok = self._authenticate()
        if not auth_ok:
            code, msg = mt5.last_error()
            mt5.shutdown()
            return MT5AuthResult(
                success=False,
                error_code=code,
                error_message=f"mt5.login() failed: [{code}] {msg}",
            )

        # ── 2c: Fetch & validate account info ─────────────────────────────
        account = mt5.account_info()
        if account is None:
            code, msg = mt5.last_error()
            mt5.shutdown()
            return MT5AuthResult(
                success=False,
                error_code=code,
                error_message=f"mt5.account_info() returned None: [{code}] {msg}",
            )

        snapshot = MT5AccountSnapshot(
            login=account.login,
            server=account.server,
            broker=account.company,
            currency=account.currency,
            leverage=account.leverage,
            balance=account.balance,
            equity=account.equity,
            margin=account.margin,
            free_margin=account.margin_free,
            margin_level_pct=account.margin_level,
            trade_allowed=bool(account.trade_allowed),
        )
        return MT5AuthResult(success=True, account_info=snapshot)

    def _initialise_terminal(self) -> bool:
        """
        Call ``mt5.initialize()``, optionally providing the path to the
        terminal executable when ``MT5_TERMINAL_PATH`` was configured.

        Returns
        -------
        bool
            ``True`` if initialisation succeeded.
        """
        creds = self._credentials
        kwargs: dict = {
            "timeout": creds.timeout_ms,
            "portable": creds.portable,
        }
        if creds.terminal_path is not None:
            kwargs["path"] = str(creds.terminal_path)
            logger.debug(f"MT5 terminal path: {creds.terminal_path}")

        return mt5.initialize(**kwargs)

    def _authenticate(self) -> bool:
        """
        Call ``mt5.login()`` using the loaded credentials.

        The password is revealed only for the API call and never stored
        in any mutable variable after this scope exits.

        Returns
        -------
        bool
            ``True`` if the broker accepted the credentials.
        """
        creds = self._credentials
        return mt5.login(
            login=creds.login,
            password=creds.password.reveal(),  # plaintext only here, not logged
            server=creds.server,
            timeout=creds.timeout_ms,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Module-level convenience singleton (lazy — created on first import usage)
# ─────────────────────────────────────────────────────────────────────────────

_auth_manager: Optional[MT5AuthManager] = None


def get_auth_manager(
    max_retries: int = 3,
    retry_delay_sec: float = 2.0,
) -> MT5AuthManager:
    """
    Return the process-level singleton ``MT5AuthManager``.

    Parameters
    ----------
    max_retries : int
        Forwarded to ``MT5AuthManager.__init__`` on first call only.
    retry_delay_sec : float
        Forwarded to ``MT5AuthManager.__init__`` on first call only.

    Returns
    -------
    MT5AuthManager
        The singleton instance.
    """
    global _auth_manager
    if _auth_manager is None:
        _auth_manager = MT5AuthManager(
            max_retries=max_retries,
            retry_delay_sec=retry_delay_sec,
        )
    return _auth_manager


# ─────────────────────────────────────────────────────────────────────────────
# CLI smoke-test entrypoint
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    """
    Quick standalone smoke-test.

    Run from project root:
        python -m backend.core.mt5_auth

    Expected output on success:
        ✅  MT5 authenticated
        login=XXXXXXXX | server=... | balance=...
    """
    import json

    auth = MT5AuthManager(max_retries=2, retry_delay_sec=1.5)
    result = auth.connect()

    if result.success and result.account_info:
        print("\n✅  MT5 authenticated")
        print(json.dumps(result.account_info.to_dict(), indent=2))
    else:
        print(f"\n❌  Connection failed: {result.error_message}")
        sys.exit(1)

    auth.teardown()
