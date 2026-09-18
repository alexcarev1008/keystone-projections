# KEYSTONE — Fable context pack

generated: 2026-09-18T22:20:29+00:00 · artifacts window_end: 2026 · projection_season: 2027 · production_tier: H=marcel P=marcel

## 1. What KEYSTONE is (one paragraph)

Bayesian component-based MLB player projection system: seven binomial stages per PA'
chain (k, bb, hbp, hr, hit_bip, xbh, triple for hitters; the first five for pitchers).
Marcel is Tier 1; a non-centred hierarchical state-space model per (role, stage) is
Tier 2 (aging g[age], talent-drift tau, park effects on batted-ball stages); Statcast
contact-quality indicators plug into three stages as Tier 3. Stages are fitted
independently and combined index-by-index into derived stats via a verified formula
shared by actuals, projections and simulations. Frontend is React + Recharts served
read-only by FastAPI over parquet + JSON artifacts.

## 2. Model equations (MANUAL.md §5.3, reproduced)

```
theta[i, first] = lam * z(log PA'_first) + sigma_pop * e
theta[i, t]     = theta[i, t-1] + g[age[i, t]] + tau * e
y[i, t]         ~ Binomial(n[i, t], invlogit(mu_league[t] + theta[i, t] + X_park . phi))
```
Priors: tau ~ HalfNormal(.3), sigma_pop ~ HalfNormal(1), lam ~ N(0, .5),
        g0 ~ N(0, .1), g_step_sd ~ HalfNormal(.02), park_sd ~ HalfNormal(.1),
        phi ~ N(0, 1) * park_sd. Non-centred parameterisation, nutpie sampler.
Tier 3 adds a second Binomial on the same theta with (barrels/BBE, ev95plus/BBE).
Projections park-neutral, conditional on playing (no attrition model).

## 3. Production tier and gate results

| role | tier | wins | of | need | cov80_mean | vs | pass |
|---|---|---:|---:|---:|---:|---|---|
| H | tier2 | 2 | 4 | 3 | 0.819 | marcel | FAIL |
| P | tier2 | 1 | 4 | 3 | 0.761 | marcel | FAIL |

Gate rule (§6): key stat is wOBA (H) / FIP (P). Tier 2 ships if RMSE <= Marcel in
3 of 4 dev targets AND mean 80% coverage in [0.75, 0.85]. Tier 3 ships if it clears
the same bar vs Tier 2. If Tier 2 fails, production is **Marcel points + Tier 2
bands** and the Methodology page says so plainly. Holdout 2025 is unspent (deferred
until after M2b — see STATUS.md).

## 4. Data coverage

| season | H rows | P rows | H PA' total | P BF' total |
|---:|---:|---:|---:|---:|
| 2015 | 635 | 712 | 175,997 | 181,319 |
| 2016 | 630 | 720 | 177,011 | 182,472 |
| 2017 | 621 | 732 | 178,228 | 183,189 |
| 2018 | 621 | 752 | 177,697 | 183,032 |
| 2019 | 630 | 775 | 179,452 | 184,475 |
| 2020 | 573 | 709 | 65,839 | 66,003 |
| 2021 | 654 | 850 | 174,847 | 179,923 |
| 2022 | 685 | 807 | 180,549 | 180,464 |
| 2023 | 650 | 804 | 183,021 | 182,495 |
| 2024 | 649 | 802 | 181,386 | 180,939 |
| 2025 | 667 | 803 | 181,717 | 180,946 |
| 2026 | 656 | 800 | 171,877 | 171,100 |

## 5. Known findings and open questions

- **Hitter HR% is where Tier 2 loses.** RMSE .0155 vs Marcel .0124 (worst stat),
  cov80 .71. wHR = 2.05 is the largest wOBA weight, so hitter HR% alone plausibly
  explains the wOBA gap. Two candidate causes are laid out for Fable M1 in STATUS.md:
  (a) park-neutral scoring while Marcel is park-blind but inherits parks implicitly;
  (b) over-shrinkage from a fitting population dominated by part-timers.
- **H/hit_bip divergence concentration.** 181 of 313 total dev divergences at
  target_accept 0.9 come from this one stage. The verified simulation had 0
  divergences at the same scale, so it is real-data structure the non-centred
  parameterisation does not absorb — most likely a funnel where sigma_pop = 0.091 is small next to binomial noise. Tier 3
  target_accept 0.95 collapsed this to ~4 divergences per fit.
- **DIPS falls out of the fit.** sigma_pop for hit_bip: H 0.091
  vs P 0.047 (~ 2x wider talent spread for hitters).
- **HR park effects, H stage.** park_sd_mean 0.358
  (~35% logit swing between top and bottom parks); see park_effects.csv.
- **Sampling health at production.** max r_hat 1.1603, total
  divergences 89 across 12 fits (better than dev; still
  P/k 1.11 and P/hr 1.10 above the 1.05 line).

## 6. Population parameters (window_end fits from meta.json)

| role/stage | tau_mean | sigma_pop_mean | park_sd_mean | max_rhat | divergences |
|---|---:|---:|---:|---:|---:|
| H/k | 0.1043 | 0.3587 | - | 1.1603 | 3 |
| H/bb | 0.0891 | 0.3349 | - | 1.0186 | 3 |
| H/hbp | 0.0831 | 0.5613 | - | 1.0801 | 1 |
| H/hr | 0.0955 | 0.4730 | 0.3577 | 1.059 | 2 |
| H/hit_bip | 0.0105 | 0.0912 | 0.0583 | 1.0444 | 6 |
| H/xbh | 0.0198 | 0.1605 | 0.0918 | 1.0418 | 1 |
| H/triple | 0.0794 | 0.5653 | 0.2500 | 1.1383 | 0 |
| P/k | 0.0872 | 0.2439 | - | 1.0582 | 1 |
| P/bb | 0.0623 | 0.2901 | - | 1.0419 | 69 |
| P/hbp | 0.0846 | 0.4499 | - | 1.1122 | 0 |
| P/hr | 0.0388 | 0.1706 | 0.1221 | 1.0758 | 0 |
| P/hit_bip | 0.0235 | 0.0467 | 0.0841 | 1.0375 | 3 |

## 7. What is in this pack (and what is not)

Each CSV is capped at 2,000 rows; this file is capped at 400 lines.

| file | rows | source | notes |
|---|---:|---|---|
| backtest_summary.csv | 200 | data/artifacts/backtest.json | complete |
| posterior_summaries.csv | 72 | meta.json + backtest diag rows + sidecar (M1) | sidecar present |
| aging_curves.csv | 462 | data/artifacts/aging.parquet | mean only; q10/q90 need per-draw sidecar |
| park_effects.csv | 16 | meta.json top/bottom_hr_parks | phi_sd null; only top/bottom 3 for hr; other park stages absent |
| residuals_by_bucket.csv | 2750 | Marcel vs actuals + sidecar Tier 2/3 (M1) | sidecar present |
| pit_histograms.csv | 200 | Marcel normal approx + sidecar piecewise Tier 2/3 (M1) | sidecar present |
| biggest_misses.csv | 640 | Marcel + sidecar Tier 2/3 key-stat errors (M1) | sidecar present |
| stage_correlations.csv | 74 | observed residual rates in last window | proxy for talent correlation; not from posteriors |
| pt_summary.csv | 26 | Marcel PT vs actual for target=2025 | includes share_zero_actual |
| code_map.md | 1 per file | walk of backend/keystone/ | |

### Sidecar (M1)

`backtest_predictions.parquet` (target, role, tier, mlbam_id, stat, pred_mean, q10, q50,
q90) and `backtest_posteriors.parquet` (target, role, tier, stage, tau_mean, tau_sd,
sigma_pop_*, lam_*, sigma_age_*, park_sd_*, ess_bulk_min, max_rhat, divergences) are
written next to backtest.json on every `make backtest`. Current status: **present**.
When present, the sidecar fills the Tier 2/3 columns of the tables above; when absent,
diagnostics falls back to Marcel-only rows so `make diagnostics` never fails.

## 8. Pointers into the code

- Stage math & derivations: `backend/keystone/components.py` (verified reference)
- Marcel: `backend/keystone/models/marcel.py`
- Tier 2/3 model + projection: `backend/keystone/models/state_space.py`
- League environment: `backend/keystone/league.py`
- Backtest harness + gates: `backend/keystone/eval/backtest.py`
- Production artifacts: `backend/keystone/project.py`
- Statcast indicators: `backend/keystone/data/statcast.py`
- CLI: `backend/keystone/pipeline.py`
- Full file map: see `code_map.md` in this directory.

## 9. Rules of the road (from FABLE_MISSIONS.md §4)

- One session per mission; don't clear mid-mission.
- Think deep, write compact. Targeted edits, not file rewrites. No printing dataframes.
- Long compute belongs to Daniel; validate with `--quick`, put full runs in STATUS.md.
- No tuning on 2025. Pre-register every hypothesis before Daniel's run.
- Mechanical work → docs/fable/HANDOFF.md, one checkbox each with file + change + check.
