# KEYSTONE — Fable Missions

Budget: **$100 of Fable** (Daniel holds $110; $10 is reserve). Written 2026-09-17.

> **Fable, read this first.** You are not the build agent. By the time you're called, Opus has already built a
> working product: data, Marcel, the Bayesian model, backtests, API, frontend (MANUAL.md Stage A). Your job is
> the work where a stronger model changes the outcome: finding root causes, statistical judgment, model research,
> and analyst-grade writing. **If a task is mechanical (wiring, UI, formatting, data fetching, refactoring,
> boilerplate tests), don't do it. Write it as a spec item in `docs/fable/HANDOFF.md` and Opus will do it.**

---

## §1 Why this split

Fable costs $10 per million input tokens and $50 per million output tokens. Re-reading cached context costs only
$0.25 per million on Fable 5.1. So:

- **Reading is cheap and writing is expensive.** Fable gets a rich, pre-built context pack (§3) and spends its
  tokens on thinking and on dense, high-value output — not on exploring the repo or typing boilerplate.
- **Opus does everything a strong model can do reliably:** plumbing, data, API, UI, re-runs, wiring changes.
- **Fable does what its positioning says it's best at:** fixing root causes instead of symptoms, code review,
  long autonomous research, and deep analysis that ends in finished deliverables.

## §2 Workflow at a glance

```
STAGE A — Opus builds (MANUAL.md §10)       $0 Fable
  P0 setup → P1 data → P2 backtests → P3 artifacts → P4 API → P5 frontend → P6 Statcast data → P6.5 context pack
                                  │
STAGE B — Fable missions (this file)          $100 Fable
  M1 Statistical red team ($15)
     └─ Opus wires the handoff · Daniel re-runs backtests · Opus refreshes the context pack
  M2a Model research: diagnose + build ($22)
     └─ Daniel runs full backtests
  M2b Model research: judge + second iteration ($18)
     └─ Opus wires the handoff · Daniel runs `make project` · Opus refreshes the context pack
  M3 Playing time + attrition model ($15)
     └─ Opus wires it into artifacts/API/UI · Daniel re-runs
  M4 Research memo + "what the model learned" ($20)
     └─ Opus builds the Methodology page + README from the memo (Phase 7) · Daniel takes screenshots
  M5 Hiring-manager review + interview prep ($10)
     └─ Opus fixes the listed issues
STAGE C — Opus final polish                    $0 Fable
```

**Budget ledger:** after every Fable session, Daniel writes the spend in STATUS.md → "Fable ledger". Rules:
- If a mission reaches **its budget + 30%**, Fable stops and writes the handoff.
- If M1 + M2 together go over $65, **skip M3** (move "playing-time model" to the README's "What I'd do next").
- The $10 reserve is only for fixing a mistake Fable made itself.

## §3 Context pack (built by Opus in Phase 6.5, refreshed after every handoff)

`docs/fable_context/`:
| file | contents |
|---|---|
| `CONTEXT.md` (≤ 400 lines) | the project in one page; the model equations (from MANUAL §5); data coverage by season; current production tier; known limitations; pointers to the files below |
| `backtest_summary.csv` | backtest.json rows (target, role, tier, stat, n, rmse, mae, cov50, cov80) |
| `residuals_by_bucket.csv` | for each tier × role × stat × target, split by age bucket (≤24, 25–27, 28–30, 31–33, ≥34), PA/BF bucket in T−1 (<150, 150–400, >400), and years of history (1, 2, 3+): n, mean error (bias), RMSE, cov80 |
| `pit_histograms.csv` | posterior-predictive PIT values, binned into 10 bins, per role × stat × tier |
| `posterior_summaries.csv` | per role × stage × target: tau, sigma_pop, lam, park_sd, sigma_age (mean, sd, r_hat, ess_bulk); divergences |
| `aging_curves.csv` | G(age) per role × stage (mean, q10, q90) |
| `park_effects.csv` | venue name × stage: phi mean, sd |
| `biggest_misses.csv` | the 40 largest absolute wOBA/FIP errors per tier over the dev targets: player, target, age, prior PA, projection, actual, q10, q90 |
| `stage_correlations.csv` | correlation of posterior-mean talent across stages (within role, last window) |
| `pt_summary.csv` | Marcel PT vs actual PA/IP errors, by age and prior-PT bucket; the share of projected players with 0 PA next year |
| `code_map.md` | one line per backend file: purpose + key functions (so Fable opens only what it needs) |

## §4 Rules for every Fable mission

1. **Start with** `docs/fable_context/CONTEXT.md` → your mission section below → only the files your mission lists.
2. **One session per mission.** Don't clear or restart mid-mission; cached context is what makes long sessions cheap.
3. **Think as deeply as the problem needs, but write compactly.** Make code changes as targeted edits, not file
   rewrites. No narration, no restating files, no printing data.
4. **Long compute belongs to Daniel.** Use `--quick` runs (under 5 min) to validate. Put full runs in STATUS.md as commands.
5. **No tuning on the 2025 holdout. No hand-picked results.** Pre-register each hypothesis (what you change, what
   you expect, which metric decides) *before* the run.
6. **Mechanical work → `docs/fable/HANDOFF.md`**, one checkbox per item: file, change, acceptance check.
7. **End every mission** with its deliverable file, a HANDOFF update, a STATUS.md update (including a self-estimated
   token use), and a commit `fable M<n>: <summary>`.

---

## M1 — Statistical red team ($15)

**Why Fable:** subtle statistical bugs (leakage, wrong denominators, mis-specified priors, a miscalibration that
has a *cause*) are the most expensive kind of error in a portfolio project and the hardest to see. Fixing root
causes is exactly what Fable is for.

**Read:** CONTEXT.md, backtest_summary, residuals_by_bucket, pit_histograms, posterior_summaries, code_map; then
open only the code you need (expected: `components.py`, `league.py`, `models/*`, `eval/backtest.py`, `project.py`).

**Do:**
1. Audit for: leakage (including league constants and park exposures), stage math and denominators, age convention,
   the traded-player aggregation, two-way handling, 2020 handling, prior sensitivity, sampler health, and whether
   Marcel is implemented fairly (a strawman baseline would be a credibility problem).
2. For each miscalibration or bias pattern in the residuals, find the **cause**, not a patch.
3. Fix the top ≤ 5 issues directly (with a test each). Anything else goes in HANDOFF or the findings file.

**Deliverable:** `docs/fable/M1_audit.md` — findings ranked by impact on the conclusions (severity, evidence, fix,
status). ✔ `make test` passes. The re-run commands are in STATUS.md.

## M2 — Model research (two sessions: M2a $22, M2b $18)

**Why Fable:** open-ended, multi-step research with judgment calls — which failure matters, which fix is principled,
when to stop. This is the part of the project a projections team actually evaluates.

**Goal:** a production model that beats Marcel on wOBA (H) and FIP (P) in ≥ 3 of 4 dev targets, with 80% coverage
in [0.75, 0.85] — and a documented story of *why* each change helped or didn't.

**M2a — diagnose + build. Read:** refreshed context pack (after M1), M1_audit.md, `models/state_space.py`, `eval/backtest.py`.
1. Write a diagnosis: where and why the current production tier loses to Marcel or is miscalibrated (by stage, age, PA, history length).
2. Rank candidate upgrades by (expected gain × confidence) ÷ complexity. Fable decides; the menu is only a starting point:
   - Statcast indicators (Tier 3) for more stages (whiff/chase-type indicators, if the Phase 6 data supports them)
   - correlated talent across stages (a multivariate random walk, or a shared latent factor)
   - heavy-tailed talent innovations (real breakouts and collapses)
   - innovation scale and prior mean that depend on age or on PA (not only in the first season)
   - pitcher role effects (starter vs reliever)
   - a better league-environment projection than a 3-year mean
3. Implement **up to 3** upgrades behind flags, each with a pre-registered hypothesis in
   `docs/fable/M2_experiments.md`, each validated with `--quick`. Put the full-run commands in STATUS.md and stop.

**M2b — judge + iterate. Read:** Daniel's pasted results, M2_experiments.md.
1. Accept or reject each experiment against its pre-registered metric (the §6 gates). No moving the goalposts.
2. One more iteration (at most 2 changes) if the evidence points somewhere clear; otherwise lock in the production configuration.
3. Once the configuration is locked: `make holdout` (Daniel) → record the 2025 result honestly, good or bad.
4. HANDOFF: everything Opus needs to carry the chosen configuration into artifacts, the waterfall steps, the API and the UI.

**Deliverable:** `docs/fable/M2_experiments.md` (hypothesis → change → result → decision for each experiment, plus
the final configuration and the holdout result).

## M3 — Playing time + attrition ($15; the first thing cut if over budget)

**Why Fable:** Marcel playing time plus "conditional on playing" is the model's biggest real-world weakness, and a
club makes free-agent and trade decisions on *expected* production. This needs careful modelling judgment
(zero-inflation, injuries, age, role), not plumbing.

**Read:** pt_summary.csv, CONTEXT.md, `models/marcel.py` (the playing-time function), the projection code.
**Do:** design and implement a Bayesian playing-time model: probability of playing at all (a hurdle), times PA/IP
given that he plays, using age, recent PT, role and a missed-time proxy (a big PT drop vs. the prior year).
Backtest it against Marcel PT. If it wins, define the multi-year outlook as *expected* seasons (probability of
playing × production) alongside the conditional ones. HANDOFF: the artifact columns and the UI changes (for
example, "chance he's still an MLB regular in 2029").
**Deliverable:** `docs/fable/M3_playing_time.md` + code + tests.

## M4 — Research memo ($20)

**Why Fable:** this is the document a Nationals reviewer actually reads. Turning posteriors and backtests into
correct, persuasive baseball insight is deep analysis plus a finished deliverable — Fable's strongest use.

**Read:** the final context pack (refreshed after M2/M3), the M1–M3 documents. Open code only to check a claim.
**Write** `docs/research_memo.md` (≤ 2,500 words, in Daniel's voice, first person, no hype):
1. The question and approach, in plain language (1 paragraph).
2. The model, in words plus equations; why components; why a state-space model.
3. **What the model learned**, with numbers and honest uncertainty: how fast each stat's talent changes (tau) and
   what that means for how much recent seasons should count; the pitcher-vs-hitter BABIP talent spread (DIPS);
   component aging curves (which skills peak early, which decline late); park effects (does the model recover the
   parks everyone knows?); the playing-time finding.
4. Validation: vs Marcel, calibration, where it still loses, and the 2025 holdout.
5. Three case studies from the 2027 projections: a player the model likes more than his surface stats suggest, a
   regression candidate, and **one current Nationals player** — each explained through the waterfall.
6. Limitations and next steps.

Also write `docs/fable/methodology_content.json` (section → paragraphs, plus the key numbers) and a HANDOFF item for
Opus to render it on the Methodology page. ✔ Every number in the memo traces to a file in the context pack; list
those sources in an appendix table.

## M5 — Hiring-manager review + interview prep ($10)

**Why Fable:** a critical, expert read of the whole thing — including the rendered charts, using vision — from
the point of view of the person making the hiring decision.

**Read:** `docs/screenshots/*`, `docs/research_memo.md`, `README.md`, CONTEXT.md.
**Do:** role-play the Nationals' Player Projections lead reviewing this application.
1. The top 10 weaknesses a reviewer would notice (statistical, baseball, visual/communication), ranked. Fix the
   memo/README wording yourself; send everything else to HANDOFF.
2. Check every chart in the screenshots: are the bands, scales, labels and colors honest and readable?
3. `docs/interview_prep.md`: 20 hard questions a projections team would ask about this project (methodology,
   baseball, "why not X", failure cases), each with a strong answer grounded in this repo, plus 5 questions Daniel
   should ask them.

**Deliverable:** `docs/fable/M5_review.md`, `docs/interview_prep.md`.

---

## §5 Kickoff prompts (paste into a new Fable session)

**Mission start:**
> You are Fable on KEYSTONE. Read `FABLE_MISSIONS.md` §1, §4, and **Mission M<n>** only, then
> `docs/fable_context/CONTEXT.md` and the files that mission lists. Budget: $<x>. Do the mission. Send mechanical
> work to `docs/fable/HANDOFF.md`. Finish with the deliverable, a STATUS.md update and a commit.

**Resuming after Daniel's run (same session if possible):**
> Results of `<command>`: `<paste ≤ 30 lines>`. Continue M<n>.

**Budget stop:**
> You're at the mission budget. Stop new work now: write what's done and what's left to the deliverable and HANDOFF, update STATUS.md, commit.
