# Cloudflare Security Audit Methodology & Multi-Phase Adversarial Protocol

## 1. Overview & Purpose
The Cloudflare Security Audit Framework (`security-audit`) transforms the agent into an adversarial 6-phase security audit team. It enforces a strict separation of concerns where **no agent is ever allowed to validate or approve its own findings**.

## 2. The 6 Audit Phases
1. **Phase 1: Reconnaissance (Architecture & Ledger):**
   - Maps trust boundaries, untrusted input surfaces, lower-trust entrypoints, and sensitive sinks.
   - Establishes a deterministic `coverage-ledger.json` and architectural attack surface map.
2. **Phase 2: Coverage-Led Hunting:**
   - Dispatches isolated hunter subagents (`invoke_subagent` with role `Security Hunter`) focused on specific ledger units and attack classes.
   - Hunters record exact traces and proposed findings.
3. **Phase 3: Adversarial Candidate Validation (The Disprover / Refutation Agent):**
   - **The Golden Rule:** Every candidate finding discovered by a hunter is assigned to a *fresh, independent verifier subagent* that did not write or hunt it.
   - **Mandate:** The verifier's sole objective is to **refute and disprove** the candidate. It attempts to find existing boundary validations, framework protections, sanitization, or prerequisite failures that invalidate the claim.
   - Only findings that withstand rigorous attempts at refutation can advance.
4. **Phase 4: Structured Output & Schema Validation:**
   - Categorizes outcomes into `confirmed`, `needs_validation` (specific external blocker), or `rejected`.
   - Validates data against `report-schema.json`.
5. **Phase 5: Independent Record Verification:**
   - Independent validation agents verify line numbers, positive code paths, and boundary impacts.
6. **Phase 6: Target-Neutral Reporting:**
   - Derives actionable reports (`REPORT.md`, `FINDINGS-DETAIL.md`, `NEEDS-VALIDATION.md`).

## 3. Specialized Attack Class Domains
The audit utilizes specialized domain hunting rules located in `.agents/skills/security-audit/`:
- `AI-AND-LLM.md`: Prompt injection, tool boundary escape, unvalidated agent outputs, secret exfiltration.
- `WEB-PROTOCOL-AND-AUTH.md`: API authentication, session token handling, CORS, header injection.
- `MEMORY-SAFETY-AND-BINARY.md`: Buffer management, race conditions, native binary/MQL5 boundary risks.
- `CLOUD-AND-DEPLOYMENT.md`: Environment secrets, permission leaks, configuration exposure.
- `RESOURCE-EXHAUSTION-AND-AVAILABILITY.md`: Rate-limiting, unbounded loops, algorithmic DoS.

## 4. Operational Safety & Bounded Execution
- Audits are defensive, static source-first inspections.
- Probing deployed production infrastructure or external endpoints is strictly forbidden.
- Target execution occurs strictly within isolated local boundaries using dummy fixtures and data.
