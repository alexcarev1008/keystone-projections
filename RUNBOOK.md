# KEYSTONE — Runbook (Daniel's checklist)

Keep this open. Two Terminal tabs the whole time:
- **Tab A — agent:** `cd ~/Desktop/keystone-projections && claude`
- **Tab B — you:** `cd ~/Desktop/keystone-projections` (long `make` jobs, git, checks)

Pick the model inside Claude Code with `/model` (Opus for Stage A/C, Fable for Stage B).

---

## Step 0 — One-time setup (~20 min, no AI)
Tab B:
```bash
python3.12 --version || brew install python@3.12      # or install from python.org
node --version                                         # need ≥ 20.19; else: brew install node
xcode-select -p || xcode-select --install              # provides make + git
make setup && make test                                # expect: 7 passed
git init && git add -A && git commit -m "phase 0: manual + verified reference"
```
If you only have Python 3.13, use `make setup PY=python3.13`.

Then fill in **fg_guts.csv**: on FanGraphs → Guts! → wOBA and FIP constants, copy rows 2015–2026 into a spreadsheet →
save as `data/external/fg_guts.csv` with the header in `data/external/README.md`.

---

## Stage A — Opus builds (model: **Opus**)
For each phase: `/model` → Opus, `/clear`, paste the prompt, let it work, run any long command it lists in Tab B,
paste back the ≤ 30-line summary.

**Prompt (change N):**
> You are building KEYSTONE. Read `CLAUDE.md`, then `STATUS.md`, then MANUAL.md §0–§3 and **Phase N** in §10 plus
> only the spec sections that phase lists. Do Phase N only. Follow the §2 token rules exactly. When the acceptance
> checks pass (or you're blocked), update STATUS.md, commit, and stop.

| # | Phase | Your long job in Tab B |
|---|---|---|
| 1 | Data layer | `make data` (~5–10 min) |
| 2 | Backtest harness | `make backtest` (~1–2 h), then `make holdout` **only after the gates are recorded** |
| 3 | Projection artifacts | `make project` (~20–40 min) |
| 4 | API | — |
| 5 | Frontend | `make api` (Tab B) + `make web` (Tab C) → open http://localhost:5173, check it, then save screenshots (Cmd+Shift+4) of Home, a hitter, a pitcher, Ohtani, and Methodology into `docs/screenshots/` |
| 6 | Statcast data + Tier 3 plumbing | `make statcast`, `make backtest TIER=3` |
| 6.5 | Fable context pack | `make diagnostics` |

Skip Phase 7 for now; it runs after Fable's M4.
**Stage A is done when** the app runs locally and `docs/fable_context/CONTEXT.md` exists. Commit.

Tip: while Opus runs a phase, stop it early if it starts exploring files unrelated to that phase.

---

## Stage B — Fable missions (model: **Fable**, $100 cap)
Rules: **one Claude Code session per mission — don't `/clear` mid-mission.** After each session, check your credit
balance and add the spend to the "Fable ledger" in STATUS.md.

**Mission prompt (change n and $):**
> You are Fable on KEYSTONE. Read `FABLE_MISSIONS.md` §1, §4, and **Mission Mn** only, then
> `docs/fable_context/CONTEXT.md` and the files that mission lists. Budget: $X. Do the mission. Send mechanical
> work to `docs/fable/HANDOFF.md`. Finish with the deliverable, a STATUS.md update and a commit.

**Resume after your long job (same session):**
> Results of `<command>`: `<paste ≤ 30 lines>`. Continue Mn.

**Wire handoff (switch to Opus, `/clear` first):**
> Read `docs/fable/HANDOFF.md`. Implement every unchecked item exactly as specified, run the listed checks, tick the
> items, update STATUS.md, commit `handoff: <mission>`. Don't change modelling decisions — ask in STATUS.md instead.

| Order | Who | What | Budget |
|---|---|---|---|
| 1 | Fable | **M1** red team | $15 |
| 2 | Opus | wire handoff → you: `make backtest` → `make diagnostics` | — |
| 3 | Fable | **M2a** diagnose + build → gives you backtest commands | $22 |
| 4 | You | run those backtests; paste results into the **same** M2 session | — |
| 5 | Fable | **M2b** judge + iterate → you: `make holdout` once → paste | $18 |
| 6 | Opus | wire handoff → you: `make project diagnostics` | — |
| 7 | Fable | **M3** playing time (**skip if M1+M2 > $65**) | $15 |
| 8 | Opus | wire handoff → you: `make project diagnostics` | — |
| 9 | Fable | **M4** research memo | $20 |
| 10 | Opus | wire handoff (Methodology page) + **Phase 7** README → you: new screenshots | — |
| 11 | Fable | **M5** hiring-manager review + interview prep | $10 |
| 12 | Opus | wire handoff (fixes) | — |

If Fable reaches budget + 30%, paste:
> You're at the mission budget. Stop new work now: write what's done and what's left to the deliverable and HANDOFF, update STATUS.md, commit.

---

## Stage C — Finish (Opus)
- Opus: `/clear`, "Read STATUS.md and HANDOFF.md; finish anything open, run `make test` and `npm run build`, commit."
- You: create a GitHub repo and push; put the link, `docs/research_memo.md` and screenshots in the application.
- After the 2026 regular season ends: `make data project diagnostics` and commit (projections then use full 2026 data).
- Study `docs/interview_prep.md`.

## If something goes wrong
- The same error twice → the agent writes a blocker in STATUS.md and stops. Bring the blocker to Opus first (it's cheap); only escalate to Fable if it's a modelling or statistical problem.
- A long job crashes → paste the last 30 lines of the error to Opus.
- Never paste whole data files or full logs into Fable.
