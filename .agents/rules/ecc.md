# ECC (Everything Claude Code) Framework & Agent Governance

## 1. Overview
ECC provides an enterprise performance optimization system for AI coding agents, featuring:
- **71 Specialized Domain Agents** (`.agents/agents/*.md`)
- **314 Advanced Skills** (`.agents/skills/`)
- **Continuous Learning Engine v2.1** (Instinct-based memory and prioritized pattern injection)
- **AgentShield Security Scanner** (MCP, prompt injection, and permission defense)

## 2. Specialized Agents Directory (`.agents/agents/`)
Whenever a task requires deep domain expertise, dispatch a specialized agent via `invoke_subagent` using the corresponding specification in `.agents/agents/`:
- **Architecture & Design:** `architect`, `code-architect`, `code-explorer`, `code-simplifier`
- **Code Review & Quality:** `code-reviewer`, `commit-reviewer`, `database-reviewer`, `fastapi-reviewer`
- **Security & Hardening:** `security-reviewer`, `security-auditor`
- **Debugging & Resolution:** `build-error-resolver`, `conversation-analyzer`
- **Testing & Validation:** `e2e-runner`, `test-runner`

## 3. Continuous Learning & The Instinct Model (v2.1)
- **Atomic Instincts:** Captured lessons, user corrections, and successful recurring patterns are stored in `.agents/instincts/` with confidence scores ($0.3$ to $0.9$).
- **Context Budget Protection:** Instincts are injected selectively by priority and domain relevance, preventing context window saturation.
- **Evolution Pipeline:** Repeated, validated instincts evolve into formal skills, workflows, or global guidelines.

## 4. AgentShield Security Scanner
- Regularly verify MCP tools, prompts, and credentials using AgentShield:
  `npx ecc-agentshield scan .`
- Enforce prompt injection defense, least-privilege MCP tool boundaries, and zero secret leakage.

## 5. Integration with Superpowers & Project Architecture
- **Superpowers:** Controls the execution process (Brainstorming spec -> 2-5 min tasks -> Red-Green-Refactor TDD with the Iron Law).
- **ECC:** Provides the execution muscle (71 agents, 314 skills, Continuous Learning, AgentShield).
- **Quant Constitution (`.antigravityrules` & `AGENTS.md`):** Maintains quantitative integrity, deterministic math in `quant_core/`, and all regression tests green.
