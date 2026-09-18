# M1 — Statistical red team (Fable, 2026-09-17)

Audit scope (FABLE_MISSIONS §M1): leakage, stage math/denominators, age convention, traded-player
aggregation, two-way handling, 2020, prior sensitivity, sampler health, Marcel fairness.
One code-level root cause found and fixed (F1); the rest of the audit came back clean or produced
findings for M2 (F2–F5). Findings ranked by impact on the conclusions.

## Pre-registered experiment (written BEFORE the validation run)

**E1 — park-aware backtest scoring.**
- *Change:* Tier 2/3 park-stage projections in the backtest are scored in the player's T−1 park
  (`park_exposure_map`: 0.5 × window_end venue shares, leakage-safe) instead of park-neutral.
  The fit is untouched; same seed, so any delta is pure scoring.
- *Hypothesis:* Marcel inherits each player's park implicitly through his raw rates; scoring Tier 2
  park-neutral against park-inflected actuals handicaps only Tier 2. Arithmetic: H/hr park_sd 0.351,
  home exposure 0.5 ⇒ an omitted term with sd ≈ 0.175 logit ≈ .008 in HR/contact rate;
  √(.0124² + .008²) ≈ .0147 ≈ the observed Tier 2 RMSE .0155. P/hr park_sd 0.120 ⇒ ≈ .002,
  negligible — which is why the same model *wins* pitcher HR%.
- *Expectation:* on `backtest --quick` (2024, H, stages k+hr, seed 1): stage_k RMSE unchanged
  (not a park stage); tier2 stage_hr RMSE falls vs the park-neutral run.
- *Decides:* stage_hr RMSE lower ⇒ park-aware stays the default; the gates are re-decided only by
  Daniel's full `make backtest` re-run (commands in STATUS.md). No 2025 involvement.
- **Result (quick run, identical fits): tier2 stage_hr RMSE .0202 → .0172 (Marcel .0169);
  stage_k .0341 → .0341. Accepted.** The pre-registered magnitude (~.003 of orthogonal error on
  the HR stage) matches. Full-sample effect on wOBA/FIP gates: decided by Daniel's re-run.

## F1 — Park-neutral scoring handicapped Tier 2 on park stages [HIGH — fixed]

**Severity:** drives the headline conclusion. Hitter HR% was Tier 2's worst stat (.0155 vs Marcel
.0124, cov80 .71) and wHR = 2.05 is the largest wOBA weight, so this alone plausibly flips the
H wOBA gate story.

**Cause, not symptom:** §5.3 fits venue effects phi and *removes* them from theta, then §6 scored the
park-neutral projection against what the player did in his real park. Marcel never learns parks, so
his raw rates keep them — only Tier 2 paid the neutrality penalty. The H-vs-P asymmetry confirms it:
park_sd H/hr 0.351 (penalty ≈ .008 rate-sd) vs P/hr 0.120 (≈ .002), and Tier 2 *won* pitcher HR%.
Coverage is hit the same way — an omitted .175-logit term reads as intervals-too-narrow (cov80 .71).

**Fix (shipped):** `eval/backtest.py` now projects park stages into the player's T−1 park via
`park_exposure_map` (T−1 venue shares only — leakage-safe; no T−1 row ⇒ neutral). Default ON;
`--park-neutral` CLI flag restores old behaviour; `backtest.json` records `park_aware_scoring`.
Tests: `tests/test_park_aware.py` (exposure map uses window_end only + 0.5·share; `SS.project`
applies x·phi with the right sign/magnitude). Suite 31/31.

**Prediction for the full re-run (recorded before it):** H/hr RMSE falls toward ~.0135 and its cov80
rises toward .80; H wOBA gap to Marcel narrows or closes; pitcher rows nearly unchanged; BABIP/XBH
move slightly (park_sd .058/.092). Gates re-decided by the run, not by me.

## F2 — "Over-shrinkage from a part-timer-dominated fit population" is REFUTED [evidence, closed]

STATUS Q1(b) proposed sigma_pop is depressed by the ~54% of H/hr rows with <150 contact PAs.
Measured (2019–2024, delta-method logit variance minus binomial noise): talent sd among regulars
(n ≥ 400) = **0.541**; among 150–399 = 0.560. Model: √(sigma_pop² + (0.5·park_sd)²) =
√(0.478² + 0.175²) = **0.509** — within ~6% of the observed spread, and the part-timer and regular
spreads match each other. The hierarchy is weighting small samples correctly; the fitting population
is not the problem. **M2a should not spend a change on re-selecting the fit population for
sigma_pop reasons** (dynamics/tau is a separate question, see F4).

## F3 — Marcel (and Tier 2) project everyone high: stale league environment [M2a menu]

Marcel wOBA bias is +.0085 *uniform across every age bucket* (25–27: +.0089, ≥34: +.0086) and FIP
bias +.07..+.18 — so it is environment drift plus entry/exit selection, not aging. Tier 2 shares
the disease: `projection_logit` = unweighted 3-season mean logit (2020 counted as a full season).
Neither tier is advantaged, so this is not a fairness bug — it is the "better league-environment
projection" item on the M2a menu, and one honest paragraph in the memo (STATUS Q3). Marcel's
missing rebaselining step would not fix drift either (it rebaselines to the same stale mean).

## F4 — BB%: the loss doesn't fit the shrinkage story; tau looks inflated [M2a]

H/bb loses .0204 vs .0199 despite walks being the stablest skill — where a hierarchical model
should win most. Fitted tau H/bb = 0.135 and H/k = 0.123 imply ~13% year-over-year relative talent
swings in the two most stable skills, which reads as tau absorbing mis-modelled structure (player
trends the single g(age) walk can't express, or environment residue) rather than real drift. High
tau ⇒ the model over-weights T−1 ⇒ Marcel's 5/4/3 wins on stable stats. H/bb is also the
second-largest divergence cluster (47). Hypothesis for M2a: age- or PA-dependent innovation scale,
or heavier-tailed innovations; judged by the §6 gates.

## F5 — Sampler geometry: the H/hit_bip funnel has a cause [M2c]

sigma_pop 0.092 and tau 0.017 for H/hit_bip are tiny next to binomial noise (a 400-BIP season has
logit-scale noise sd ≈ 0.11 > the entire population spread). The parameterisation is non-centred in
each e, but theta is a *cumulative sum*: when tau → 0, all of a player's states collapse onto one
value and the ~6.4k e's become jointly unidentified along the chain — a funnel the per-element
non-centring cannot absorb (181 of 313 dev divergences; the simulation, with tau 0.12, had 0).
Consistent with Tier 3's observation that adding an indicator (more information per state) collapsed
divergences 181 → ~1. M2c candidates: marginalise or integrate the chain for low-tau stages,
non-centre on cumulative innovations, or model hit_bip with player-constant talent + small AR term.
Also check then: sigma_age HalfNormal(0.02) is tight enough that the aging curve may be
prior-dominated — verify against the posteriors sidecar when it lands.

## Checks that came back clean

- **Leakage:** `train_slice` cuts season ≥ T everywhere (ps/exp/lg/guts); Tier 3 indicators stripped
  at `season < target`; `scoring_env` (target wOBA weights, kappa, cFIP, actual PA/IP) is identical
  for every tier; the end-to-end perturbation test stands. New park exposure uses T−1 only.
- **Stage math:** chain denominators consistent in all three directions (stage_counts,
  per_pa_from_stage_rates, to_stage_probs); wOBA/FIP reproduce FanGraphs to machine precision;
  every tier scored through one function.
- **Age convention:** June 30 (season_age) used identically by Marcel and the state model; the state
  chain increments age exactly 1/season; projection indexes g at age+h correctly. 0 NaN ages.
- **Traded players / two-way:** bulk season totals + per-team splits (Chisholm fix) verified;
  exposures sum to share 1; TWP handled by the pos filters on both sides.
- **2020:** self-downweights via w·PA (Marcel) and binomial n (Tier 2). Equal weight in the 3-yr
  league mean is a (minor) shared limitation, folded into F3.
- **Marcel fairness:** faithful Tango implementation (5/4/3 & 3/2/1, 1200 regression, own-mix league
  rates, June-30 age adjustment). Not a strawman — it is currently the production tier.
- **Metrics:** PA-weighted RMSE with per-tier finite masks; coverage from posterior-predictive
  simulation at actual PA/BF. Point predictions use posterior-mean stage probs (Jensen gap
  negligible at these curvatures).
