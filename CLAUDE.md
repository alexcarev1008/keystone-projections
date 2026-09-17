# KEYSTONE — agent bootstrap (keep this short)

**Which model are you?**
- **Opus (build agent):** the spec is `MANUAL.md`. Read §0–§3, then ONLY your assigned phase in §10 and the sections
  it lists. When asked to "wire a handoff", do the unchecked items in `docs/fable/HANDOFF.md`.
- **Fable (research agent):** don't read MANUAL.md end to end. Read `FABLE_MISSIONS.md` §1, §4 and your mission,
  then `docs/fable_context/CONTEXT.md`. Send mechanical work to `docs/fable/HANDOFF.md`.

Both:
1. Progress, decisions, blockers, the Fable ledger and commands for Daniel live in `STATUS.md`. Read it at the start, update it at the end.
2. Verified reference modules (import, don't rewrite without cause): `backend/keystone/components.py`, `league.py`,
   `models/marcel.py`, `models/state_space.py`, `data/mlb_api.py`.
3. Python: `.venv/bin/python` from the repo root; tests: `make test`. Frontend: `frontend/`, `npm run build`.
4. Token rules: no dumping DataFrames/JSON/files; long jobs → hand to Daniel via STATUS.md;
   same error twice → write a blocker and stop; commit at session end.
