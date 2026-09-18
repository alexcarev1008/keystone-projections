# M3 — Playing time + attrition (hurdle model)

Fable, 2026-09-18. Budget $20.

## 1. Why Marcel PT fails (the evidence)

From `pt_summary.csv` (target 2025, Marcel population = anyone with PT in T−1 ∪ T−2):

- **H overall: mean error +126 PA, RMSE 204, 29.3% of projected players had 0 actual PA.**
- **P overall: mean error +21.6 IP, RMSE 43.6, 36.2% zero-actual.**
- The bias is worst exactly where a club cares: H 34+/<150-PA bucket has **85.9% zero-actual**
  while Marcel projects 228 PA (mean error +217). The 31–33/<150 bucket: 74.6% zero, +193.
- Marcel's rule (`.5·PA1 + .1·PA2 + 200`) has no zero mass and a 200-PA floor for anyone who
  ever appeared; it cannot represent attrition at all. The only bucket it under-projects is
  ≤24 (young players breaking out: −83 and −64).

So the target structure is a point mass at zero (retirement/injury/demotion) plus a
right-skewed positive part — a textbook hurdle.

## 2. Pre-registered design (written before any backtest run)

**Model** (per role, Bayesian, PyMC + nutpie, fitted on training seasons only):

```
played_i          ~ Bernoulli(invlogit(X_i · beta))
sqrt(pt_i)/scale  | played ~ Normal(X_i · gamma, sigma)      scale: H=10, P=5
E[pt_i] = p_play_i × scale² × (mu_i² + sigma²)
```

**Features X** (all from seasons ≤ T−1; 2020 PT scaled ×162/60 when used as a feature):
intercept; s1, s2 = scaled √PT in T−1, T−2 (0 if absent); played1, played2 indicators;
agec = (age−29)/5 and agec²; **missed-time proxy** drop = max(0, s2 − s1) (a big PT fall vs
the prior year predicts further attrition); P only: SP share in T−1 (GS/G).

**Training population**: for each outcome season s in {2017..T−1}, every player with PT in
s−1 ∪ s−2; outcome = actual PT in s (0 if no row). Outcome season 2020 is **dropped** from
training (a 60-game season is not a draw from the same PT distribution); 2020 enters only
as a scaled feature. Priors: beta, gamma ~ N(0, 1.5); sigma ~ HalfNormal(1). These are weak
on standardized features and are not tuned per target.

**Backtest** (rolling-origin, `train_slice` leakage discipline, dev targets 2021–2024 only;
2025 is not touched — the holdout is spent and stays spent):
- Evaluation population: Marcel's own (any PT in T−1 ∪ T−2), actual = 0 for non-players.
- Baseline: `marcel_playing_time` exactly as production uses it.
- **Decision metric (registered): the hurdle ships if expected-PT RMSE < Marcel PT RMSE in
  ≥ 3 of 4 dev targets, per role.** Secondary (reported, not gating): MAE, mean bias,
  Brier score of p_play vs a played-base-rate baseline, p_play decile calibration.

**Expectation**: the hurdle wins ≥3/4 for both roles, driven by the ~30% zero mass and the
+126 PA / +22 IP bias that Marcel structurally cannot remove. If it loses, that is the
result and Marcel PT stays.

**Multi-year outlook (only if the hurdle wins)**: simulate h = 1..4 per player from the
posterior: each year draw played, then PT; roll features forward (s2←s1, s1←√pt, played
indicators, age+1, drop recomputed; SP share held fixed). Report per horizon:
`p_play` (chance of any MLB time), `pt_expected` = E[PT] including the zero branch, and
`p_regular` = P(PT ≥ 300 PA / 100 IP). Expected production at h = pt_expected × conditional
rate stats. Re-entry after a missed season is allowed by the simulation (played1=0, pt2>0
still yields p_play > 0).

## 3. Results (dev targets 2021–2024, run 2026-09-18, seed 1)

**The hurdle wins the registered gate 8 of 8** (needed ≥3/4 per role). Same population and
actuals for both models; `/tmp/m3_pt_backtest.csv` has the raw table.

| role | target | n | Marcel RMSE | hurdle RMSE | Marcel bias | hurdle bias | Brier (base) |
|---|---:|---:|---:|---:|---:|---:|---|
| H | 2021 | 724 | 190.5 | **156.8** | +41.5 | +1.3 | .12 (.19) |
| H | 2022 | 735 | 190.7 | **141.6** | +108.7 | +6.7 | .12 (.21) |
| H | 2023 | 830 | 205.0 | **144.0** | +127.0 | +2.7 | .12 (.23) |
| H | 2024 | 809 | 201.9 | **142.7** | +125.7 | +2.6 | .11 (.23) |
| P | 2021 | 942 | 37.2 | **35.2** | +5.6 | −0.6 | .16 (.22) |
| P | 2022 | 980 | 41.1 | **35.7** | +18.9 | +0.7 | .17 (.23) |
| P | 2023 | 1055 | 42.1 | **34.7** | +22.3 | +1.1 | .16 (.24) |
| P | 2024 | 1024 | 44.0 | **36.9** | +21.6 | +0.5 | .16 (.24) |

- RMSE improvement: H −25% on average, P −11%. MAE: H −36%, P −24%.
- **Bias is the headline.** Marcel over-projects by 42–127 PA / 6–22 IP per player-season;
  the hurdle is within ±7 PA / ±1.1 IP on every target. 2021 is Marcel's least-bad year
  because its features come from scaled-2020 PT.
- p_play beats the base-rate Brier on every target. Decile calibration (2024): P is clean
  throughout (worst decile .97 pred vs .92 actual). H over-predicts play probability in
  deciles 1–2 (.22 vs .12, .43 vs .28) and slightly under-predicts mid-range (.85 vs .90) —
  fringe veterans leave MLB more often than the covariates say. The direction of any residual
  error is conservative (it keeps marginal players' expected PT slightly too high). Not
  re-tuned; recorded as measured.
- Fitted coefficients say what you'd expect: play probability loads on last-year PT
  (β_s1 ≈ +1.9) and falls with age (β_agec ≈ −1.3); the missed-time proxy adds little once
  s1 and s2 are both in the model (β_drop ≈ +0.1) — the two PT levels already encode the
  drop. Kept as registered.

**Decision: the hurdle model ships (per the pre-registered gate) and the multi-year outlook
becomes expected production.**

## 4. Multi-year outlook: definition

For each player, `simulate_horizons` runs the fitted hurdle forward h = 1..4 with features
rolled each simulated year (s2←s1, s1←√pt, played flags, age+1, drop recomputed; SP share
held at T−1). Re-entry after a missed year is possible, so `p_play(h)` is P(any MLB time in
year h), not survival-to-h. Per (player, horizon) the model reports:

- `p_play` — chance of any MLB playing time that year;
- `pt_expected` — E[PA or IP] including the zero branch;
- `p_regular` — P(PT ≥ 300 PA / 100 IP), the "still an MLB regular in 2029" number.

**Expected production at horizon h = pt_expected(h) × conditional rate stats(h)** (the
existing Tier 2 bands), shown alongside the conditional line, which keeps its meaning of
"if he plays". Counting stats scale by pt_expected; rate stats are unchanged. The
independence assumption (PT ⊥ rate | covariates) is wrong in detail — players who lose PT
are usually declining — so expected *counting* production is still slightly optimistic for
decliners; stated on the Methodology page, not patched.

## 5. Is the multi-year outlook trustworthy? (the band-widening question)

Verdict: **yes for the conditional rates as calibrated distributions, and M3 closes the
biggest real gap — but the h2–h4 rates are unvalidated extrapolation and must be labelled
as such.** Specifics:

1. Opus's artifact check A (STATUS.md 2026-09-18) shows the non-widening bands are not a
   bug: per-stage **logit** sd widens h1→h4 for 96–100% of players; where **rate-space**
   bands narrow, the cause is aging pulling HR/XBH levels down (a band at p scales with
   p·(1−p), so a falling level shrinks the band faster than τ√h grows it). That is a
   coherent statement, not a defect. The h1 band is not materially inflated: obs-noise and
   env-shock together are ~12–17% of h1 variance for the stages checked, and dropping them
   would barely change the h4/h1 ratio.
2. The h1 calibration claim is *holdout-validated* (2025: cov80 in [.75,.85] on 9 of 10
   stat rows). Nothing validates h2–h4 rate calibration — the backtest scores h=1 only.
   Small taus (hit_bip .0105, xbh .0198) mean the model claims talent barely drifts for
   those stages; if that is wrong, multi-year bands are too narrow. Honest label: "beyond
   year 1, intervals are model-implied, not backtested".
3. Before M3, the dominant multi-year error was not the rate bands at all: it was showing
   conditional-on-playing numbers for players with a 50–86% chance of zero PA. That error
   is 100–200 PA of expectation per fringe/old player (§1) — an order of magnitude larger
   than any plausible band miscalibration. With pt_expected multiplied in, the outlook is
   fit for its stated purpose (expected value of a contract-year), with the two caveats
   above stated plainly.

## 6. Files

- `backend/keystone/models/playing_time.py` — model, prediction, simulation, backtest.
- `backend/tests/test_playing_time.py` — population/outcome rules, 2020 scaling, leakage
  guard, hurdle math, simulation rolling, signal recovery (6 tests).
- Wiring into artifacts/API/UI: HANDOFF items (Opus).

