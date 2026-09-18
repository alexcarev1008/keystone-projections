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
  M2a Model research: diagnose + build ($20)
     └─ Daniel runs full backtests
  M2b Model research: judge + second iteration ($20)
     └─ Daniel runs full backtests
  M2c Model research: correlated stages / sampler geometry, lock the configuration + holdout ($15)
     └─ Opus wires the handoff · Daniel runs `make project` · Opus refreshes the context pack
  M3 Playing time + attrition model ($20)
     └─ Opus wires it into artifacts/API/UI · Daniel re-runs
  M4 ML challenger + formal model comparison ($10)
     └─ Opus wires whatever ships · Opus writes the research memo and README (Phase 7) from the context pack
  (Daniel reviews the screenshots and the finished app himself; Opus drafts the memo — no Fable budget for either.)
STAGE C — Opus final polish                    $0 Fable
```

**Budget ledger:** after every Fable session, Daniel writes the spend in STATUS.md → "Fable ledger". Rules:
- If a mission reaches **its budget + 30%**, Fable stops and writes the handoff.
- If M1 + M2 together go over $95, **skip M3** (move "playing-time model" to the README's "What I'd do next").
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

## M2 — Model research (three sessions: M2a $20, M2b $20, M2c $15)

**Why Fable:** open-ended, multi-step research with judgment calls — which failure matters, which fix is principled,
when to stop. This is the part of the project a projections team actually evaluates.

**Goal:** a production model that beats Marcel on wOBA (H) and FIP (P) in ≥ 3 of 4 dev targets, with 80% coverage
in [0.75, 0.85] — and a documented story of *why* each change helped or didn't.

**Known state going in** (from the Stage A backtests, see STATUS.md):
- Tier 2 loses to Marcel on the key stats; hitter HR% is the worst stat (.0155 vs .0124, cov80 .71) and carries the
  largest wOBA weight. Tier 2 wins where shrinkage is the whole job: K%, BABIP (both roles), pitcher HR%.
- Tier 3 (barrels/BBE, ev95plus) is fitted; its gate result is in `backtest.json`. Sampling got far cleaner with the
  indicator (H/hit_bip divergences 181 → ~1 per target), which is itself a finding about the Tier 2 geometry.
- Sampling is still not clean: several fits above r_hat 1.05, worst H/triple ≈ 1.23.

**M2a — diagnose + build. Read:** refreshed context pack (after M1), M1_audit.md, `models/state_space.py`, `eval/backtest.py`.
1. Write a diagnosis: where and why the production tier loses to Marcel or is miscalibrated (by stage, age, PA, history length).
2. Rank candidate upgrades by (expected gain × confidence) ÷ complexity. Fable decides; the menu is a starting point:
   park-aware scoring; a fitting population that isn't dominated by part-timers; heavy-tailed talent innovations;
   age- or PA-dependent innovation scale; more Statcast indicators; pitcher role (SP/RP) effects; a better
   league-environment projection than a 3-year mean.
3. Implement **up to 3** upgrades behind flags, each with a pre-registered hypothesis in
   `docs/fable/M2_experiments.md`, each validated with `--quick`. Put the full-run commands in STATUS.md and stop.

**M2b — judge + iterate. Read:** Daniel's pasted results, M2_experiments.md.
1. Accept or reject each experiment against its pre-registered metric (the §6 gates). No moving the goalposts.
2. One more round of at most 2 changes where the evidence points somewhere clear.

**M2c — correlated stages, sampler geometry, lock in. Read:** the M2b results.
1. Attempt the structural upgrade the earlier sessions couldn't fit into a single change: correlated talent across
   stages (a multivariate random walk or a shared latent factor), and/or a reparameterisation that fixes the fits
   still above r_hat 1.05. Both are judged by the same gates — ship only what wins.
2. Lock the production configuration. Then `make holdout` (Daniel) → record the 2025 result honestly, good or bad.
3. HANDOFF: everything Opus needs to carry the chosen configuration into artifacts, the waterfall steps, the API and the UI.

**Deliverable:** `docs/fable/M2_experiments.md` (hypothesis → change → result → decision for each experiment, plus
the final configuration and the holdout result).

## M3 — Playing time + attrition ($20; the first thing cut if over budget)

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

## M4 — ML challenger + formal model comparison ($10)

**Why Fable:** deciding whether a flexible learner actually beats a structured Bayesian model — and being willing to
report that it doesn't — is a judgment call, and the comparison has to be statistically honest to be worth anything.

**Read:** the final context pack, M2_experiments.md, `eval/backtest.py`.
**Do:**
1. Build a gradient-boosted challenger for the same target (the derived key stat, or the stage rates): features from
   the same information set the Bayesian model uses — nothing from season T. Same rolling-origin design, same
   evaluation population, same weighting. Any hyperparameter choice is made inside the training years only.
2. Compare on PA-weighted RMSE **and** on distributional scores (CRPS, log score) — a point-only learner has to be
   given an honest interval method (for example quantile regression or residual-based intervals) or be scored only
   where a point metric is fair, and the write-up must say which.
3. Test the obvious hybrid: does the Bayesian projection plus a learned residual correction beat either alone?
4. Report the verdict plainly, including "the hierarchical model wins and here is why" if that's what the numbers say.
   Ship the challenger only if it passes the §6 gates.

**Deliverable:** `docs/fable/M4_ml_challenger.md` — design, leakage controls, results table, verdict, and the two or
three sentences the README should say about it. Opus wires anything that ships and writes the research memo itself.

## §5 Kickoff prompts (paste into a new Fable session)

**Mission start:**
> You are Fable on KEYSTONE. Read `FABLE_MISSIONS.md` §1, §4, and **Mission M<n>** only, then
> `docs/fable_context/CONTEXT.md` and the files that mission lists. Budget: $<x>. Do the mission. Send mechanical
> work to `docs/fable/HANDOFF.md`. Finish with the deliverable, a STATUS.md update and a commit.

**Resuming after Daniel's run (same session if possible):**
> Results of `<command>`: `<paste ≤ 30 lines>`. Continue M<n>.

**Budget stop:**
> You're at the mission budget. Stop new work now: write what's done and what's left to the deliverable and HANDOFF, update STATUS.md, commit.
