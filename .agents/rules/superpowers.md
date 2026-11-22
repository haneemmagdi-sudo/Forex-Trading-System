# Superpowers Development Methodology & Rules

## 1. The Core Law: Discipline Before Code
- **Never jump straight into writing code** upon receiving a user request.
- If a skill applies to the current task, you MUST invoke and follow that skill.
- Before entering implementation or plan mode, extract and confirm specifications with the user first (`brainstorming`).

## 2. Specification Extraction & Sizing
- Tease out the real requirements and architectural constraints before proposing solutions.
- Present design and trade-offs in short, digestible sections (chunks) rather than walls of text.
- Confirm understanding and obtain user sign-off on the design before touching code.

## 3. Granular Implementation Plans (2-5 Minutes per Task)
- When requirements are agreed, break down the work into bite-sized tasks (each estimated at 2 to 5 minutes).
- Every task must clearly specify:
  - Exact file paths: `Create:`, `Modify:`, and `Test:`
  - Exact test command and expected failing output (RED step)
  - Minimal implementation snippet (GREEN step)
  - Refactoring instructions (REFACTOR step)
- Tasks must end with an independently verifiable deliverable.

## 4. Subagent-Driven Execution
- Dispatch a fresh, dedicated subagent for each task (`invoke_subagent` with `TypeName: "self"` or `"research"`).
- Keep each subagent's prompt focused and self-contained with exact instructions and file targets to prevent context pollution.
- Conduct a task review (spec compliance + code quality) upon task completion.

## 5. Strict Test-Driven Development (TDD) — The Iron Law
```
NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST
```
- **RED:** Write a clear, focused test reproducing the bug or specifying the new feature. Run it and verify it fails for the exact intended reason.
- **GREEN:** Write only the minimal production code necessary to turn the test green.
- **REFACTOR:** Clean and streamline the implementation while keeping all tests passing.
- **AUTOMATIC DELETION:** If any production code is written before its corresponding failing test, IT MUST BE DELETED IMMEDIATELY. Do not keep it as reference; do not adapt it; delete and start fresh from the test.

## 6. Workspace Quality & Integrity Safeguards
- All changes must respect existing project architecture (`.antigravityrules` & `AGENTS.md`).
- Run the project's regression test suite before concluding any development cycle:
  - `PYTHONPATH=. %PY% tests/test_system_integrity.py`
  - `PYTHONPATH=. %PY% tests/test_institutional_mas.py`
  - `PYTHONPATH=. %PY% tests/test_code_healing_agent.py`
- All changes must be surgical and verified.
