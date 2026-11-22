# TradingAgents Multi-Agent Framework Integration & Human-in-the-Loop Page Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate the Tauric Research `TradingAgents` LangGraph multi-agent framework into the project with a dedicated UI page, support for Stocks/Forex/Crypto/Indices, strict Anti-Lookahead protection, simulated multi-agent debate and risk analysis, and an explicit Human-in-the-Loop user approval gate before executing any orders on MetaTrader 5.

**Architecture:** 
1. A backend adapter (`backend/agents/tradingagents_bridge.py`) wraps `TradingAgentsGraph` and unifies symbol normalization across assets (Stocks, Forex, Crypto, Indices), controls Anti-Lookahead dates, and formats outputs.
2. FastAPI endpoints in `backend/main.py` handle `/api/tradingagents/analyze`, `/api/tradingagents/history`, and `/api/tradingagents/execute` (user-confirmed MT5 execution).
3. A React 19 + Tailwind CSS dedicated page (`src/components/tradingagents/TradingAgentsPage.tsx`) provides an institutional interface with interactive workflow stages, Bull vs Bear debate transcript, risk management reports, final verdict card, and a user approval modal/gate for MT5 execution.

**Tech Stack:** Python 3.11, LangGraph, LangChain, FastAPI, React 19, TypeScript, Tailwind CSS 4, MetaTrader 5 (MT5Connector), yfinance.

**Spec:** User request specifying Tauric Research TradingAgents, multi-agent firm workflow (Technical, Fundamental, News, Sentiment -> Bull/Bear debate -> Risk management -> Portfolio Manager -> Anti-Lookahead protection -> Advisory-first analysis -> Explicit user confirmation to execute on MT5).

## Global Constraints
- Every number must be measured or simulated honestly; no fake hardcoded decisions.
- Default to simulation/advisory mode; orders MUST NOT be sent to MT5 without explicit user approval.
- Preserve existing system integrity; all 16 existing regression tests must pass.
- `.env` must not be tracked; new configuration options documented in `backend/config.py` and `.env.example`.
- Frontend must support Arabic RTL and follow the established purple/slate glassmorphism aesthetic.

## Review Focus
1. Symbol mapping: "EURUSD" vs "EURUSD=X" (yfinance) vs "EURUSD" (MT5).
2. Missing fundamentals gracefully handled for Forex/Crypto (SEC EDGAR only applies to US stocks).
3. Anti-Lookahead enforcement: rejecting future dates and constraining data access to the target date.
4. Human approval gate: MT5 `open_trade` is strictly triggered by explicit user POST request with confirmation.
5. Fallback resiliency: If LLM API keys are unconfigured or rate-limited, system falls back gracefully without crashing.

---

### Task 1: Backend Bridge & Symbol Adapter
**Files:**
- Create: `backend/agents/tradingagents_bridge.py`
- Test: `tests/test_tradingagents_bridge.py`

- [ ] Write tests in `tests/test_tradingagents_bridge.py` testing:
  - Symbol normalization for Forex (`EURUSD` -> `EURUSD=X`), Crypto (`BTCUSD` -> `BTC-USD`), Stocks (`AAPL`), and Indices (`^GSPC`).
  - Anti-Lookahead validation rejecting future dates.
  - Bridge execution structure returning analyst reports, debate history, risk assessment, and pending approval verdict.
- [ ] Implement `backend/agents/tradingagents_bridge.py`:
  - `normalize_symbol(symbol: str, asset_type: str = "auto") -> tuple[str, str, str]`
  - `TradingAgentsBridge` class with `analyze(...)` method invoking `TradingAgentsGraph` or resilient fallback.
  - Settle memory and enforce Anti-Lookahead constraints.
- [ ] Run `tests/test_tradingagents_bridge.py` to verify all tests pass.

---

### Task 2: FastAPI Endpoints & MT5 Human Approval Execution
**Files:**
- Modify: `backend/main.py`
- Test: `tests/test_tradingagents_api.py`

- [ ] Write tests in `tests/test_tradingagents_api.py` for:
  - `POST /api/tradingagents/analyze`
  - `GET /api/tradingagents/history`
  - `POST /api/tradingagents/execute` (verifying MT5 call with user parameters)
- [ ] Add endpoints to `backend/main.py`:
  - `POST /api/tradingagents/analyze`: triggers analysis via bridge and stores result in cache/history.
  - `GET /api/tradingagents/history`: retrieves previous analysis runs.
  - `POST /api/tradingagents/execute`: verifies user confirmation payload (`symbol`, `direction`, `lot_size`, `sl`, `tp`), calls `mt5.open_trade()`, and records execution.
- [ ] Run `tests/test_tradingagents_api.py` and ensure pass.

---

### Task 3: Frontend Dedicated Page Component
**Files:**
- Create: `src/components/tradingagents/TradingAgentsPage.tsx`
- Create: `src/components/tradingagents/types.ts`

- [ ] Create `src/components/tradingagents/types.ts` defining state and report models.
- [ ] Implement `src/components/tradingagents/TradingAgentsPage.tsx`:
  - Institutional header with TradingAgents branding & status.
  - Asset input bar with quick chips (`EUR/USD`, `GBP/USD`, `AAPL`, `NVDA`, `BTC/USD`, `Gold`, `S&P 500`).
  - Date selector with `🛡️ Anti-Lookahead Active` guarantee badge.
  - Dynamic workflow stepper indicating progress of each agent stage.
  - Hero Verdict Card: BUY/SELL/HOLD decision badge, confidence meter, target & stop loss, investment thesis.
  - **Human-in-the-Loop Confirmation Modal**:
    - Appears when user chooses to act on a BUY/SELL decision.
    - Allows user to review and adjust Lot Size, SL, and TP.
    - Prominent action buttons: "✅ موافقة وتنفيذ الأمر على منصة MT5" & "❌ إلغاء".
    - Execution receipt showing MT5 ticket number upon approval.
  - Multi-tab detailed view:
    - Tab 1: 🐂 vs 🐻 مناظرة الباحثين (Bull vs Bear Debate).
    - Tab 2: 🛡️ إدارة المخاطر (Risk Management: Conservative, Neutral, Aggressive).
    - Tab 3: 📊 تقارير المحللين الأربعة (Technical, Fundamental, News, Sentiment).
    - Tab 4: 📜 الأرشيف وسجل التحليلات السابقة.

---

### Task 4: Navigation Integration
**Files:**
- Modify: `src/App-Advanced.tsx`

- [ ] Import `TradingAgentsPage` in `src/App-Advanced.tsx`.
- [ ] Add navigation tab in `TAB_GROUPS` under a dedicated or AI agents group:
  `{ id: 'tradingAgents', label: 'شركة TradingAgents (Tauric)', icon: '🏛️', isNew: true }`.
- [ ] Add case in `renderContent()` for `tradingAgents` tab.

---

### Task 5: Full Regression Testing & Verification
**Files:**
- All modified/created files

- [ ] Run frontend build (`npm run build`) to ensure zero TypeScript or bundling errors.
- [ ] Run backend test suite (`test_system_integrity.py`, `test_institutional_mas.py`, `test_code_healing_agent.py`, `test_tradingagents_bridge.py`, `test_tradingagents_api.py`).
- [ ] Verify clean execution and confirm complete feature delivery.
