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
  guard, hurdle math, simulation rolling, signal recovery, talent sign/shrinkage + talent
  leakage guard (8 tests).
- Wiring into artifacts/API/UI: HANDOFF items (Opus).

## 7. Follow-up T1 — talent covariate (pre-registered 2026-09-18, before any run)

Opus's wiring check (STATUS.md "Questions for Fable") found the gap: the hurdle sees only PT
history and age, so a star coming off a short season is treated like any fading veteran
(Judge, 285 PA in 2026 after 679: h1 p_play .78, 258 expected PA vs Marcel 410). Teams give
good players playing time; talent belongs in X. Judge is a symptom, not the target — nothing
below is tuned on his case.

**Change (flag `talent=True` on `build_pt_table`/`training_table`/`fit_pt`).** One new
feature per role, from seasons ≤ T−1 only:

- per player-season deviation: H `dev_s = wOBA_s − league wOBA_s` (guts weights + guts league
  value); P `dev_s = leagueFIPcore_s − FIPcore_s` where FIPcore = (13·HR + 3·(BB+HBP) − 2·K)/IP
  (cFIP cancels in the difference; league core from the season's aggregate counts). Sign:
  higher = better for both roles.
- `talent_raw(T) = (w1·dev1 + w2·dev2) / (w1 + w2 + K)` over seasons T−1, T−2 with w = PA or
  IP (0 if absent), ballast K = one full season: **K_H = 600 PA, K_P = 180 IP** — fixed, not
  tuned. 2020 rates enter as-is (rates are season-length-invariant; low PT self-shrinks).
- scaled to unit-ish range: `talent = talent_raw / 0.05` (H), `/ 0.5` (P). Fixed constants.
- `simulate_horizons` holds talent fixed across horizons (aging is already carried by agec;
  decaying talent would be a second new modelling choice, not made here).

**Pre-registered expectations.**
1. Mechanism: `beta_talent > 0` (play equation) and `gamma_talent > 0` (PT-given-play), each
   ≥ 2 posterior sd from 0, both roles.
2. **Gate (same rule style as §2): the covariate ships only if expected-PT RMSE with talent
   < the shipped hurdle's RMSE in ≥ 3 of 4 dev targets, per role.** Registered risk, stated
   now: population RMSE is dominated by fringe players whose talent estimate is heavily
   shrunk, so the RMSE gain may be too small to clear 3/4 even if the mechanism is real. If
   so, the covariate is rejected under the gate as written — no goalpost move.
3. Subgroup (reported, not gating): among age ≥ 33 players in the top talent quartile,
   signed bias moves toward 0 vs the shipped hurdle.
4. Both variants still beat Marcel 8/8 (sanity).

**Quick validation (pre-registered).** Single H 2024 fit: samples cleanly (divergences ≤ 5),
beta_talent and gamma_talent both > 0 at ≥ 2 sd.

**Decides.** Fresh dev backtest 2021–2024, both variants, same population/actuals/seed as §3.
2025 is not touched.

### T1 results (run 2026-09-18, seed 1) — ACCEPT

Every pre-registered check passed; `/tmp/m3_followup_preds.csv` has the per-player table.

| role | target | Marcel | hurdle (§3) | hurdle+talent |
|---|---:|---:|---:|---:|
| H | 2021 | 190.5 | 156.8 | **154.1** |
| H | 2022 | 190.7 | 141.5 | **135.7** |
| H | 2023 | 205.0 | 144.0 | **138.2** |
| H | 2024 | 201.9 | 142.7 | **139.1** |
| P | 2021 | 37.2 | 35.1 | **34.9** |
| P | 2022 | 41.1 | 35.7 | **34.9** |
| P | 2023 | 42.1 | 34.7 | **33.6** |
| P | 2024 | 44.0 | 36.9 | **36.6** |

1. Gate: talent RMSE < shipped hurdle in **8/8** (needed ≥ 3/4 per role) ✓; both variants
   still beat Marcel 8/8 ✓.
2. Mechanism: beta_talent +1.06..+1.60 (≥ 4.8 sd from 0), gamma_talent +0.13..+0.40
   (≥ 5.9 sd), every fit, both roles ✓. 0 divergences in all 16 fits ✓.
3. Subgroup (age ≥ 33, top talent quartile, pooled roles): signed bias moved toward 0 in
   4/4 targets — base −29/−33/−24/−31 PA-or-IP → talent −9/−14/−1/−13 (Marcel: −14/+21/+51/+34) ✓.

**Decision: the talent covariate ships.** Production configuration is now the hurdle with
`talent=True` (guts-based wOBA / FIP-core deviation, K = 600 PA / 180 IP, scale .05 / .5).

**Judge symptom check** (592450, projection 2027, age 35, 285 PA in 2026 after 679 — computed
after the decision, reported not gating): h1 p_play .78 → **.96**, pt_expected 258 → **545**
(Marcel 410); p_play at h2–h4 .52/.28/.17 → .95/.94/.94. Direction as the finding demanded —
teams give good players playing time. One honest artifact: his pt_expected *rises* h1→h4
(545 → 646) because the simulation replaces the depressed observed s1 (285 PA) with simulated
healthy seasons while talent stays fixed and aging is only the mild agec quadratic. The h1
number is dev-validated; h2–h4 remain model-implied extrapolation (§5.2) and now lean
optimistic for old stars rather than pessimistic. Not patched — noted for the Methodology
label and re-examined when a season of new data arrives.

## 8. Follow-up finding 2 — regulars ~11% under Marcel: verdict

Opus measured median pt_expected = 0.89× Marcel for 44 hitters with ≥ 600 PA in 2025 and
≥ 550 in 2026 and asked whether Marcel's +126 PA over-projection means the lower number is
right. **Verdict: no — for hitter regulars the base hurdle was genuinely biased low, and the
talent covariate removes most of it.** The per-bucket table from the dev backtest (regulars
= PT ≥ 600 in T−2 and ≥ 550 in T−1 for H, ≥ 160/≥ 140 IP for P; only 2023–24 targets can
qualify because 2020 caps T−2):

| role | n | mean actual | Marcel bias | base-hurdle bias | talent bias |
|---|---:|---:|---:|---:|---:|
| H | 82 | 589 PA | **+4.0** | −65.1 | −18.1 |
| P | 53 | 140 IP | +27.5 | −5.6 | **−0.2** |

Marcel's +126 PA over-projection is a *fringe-and-veteran* phenomenon (§1: the 34+/<150-PA
bucket is +217); for hitter regulars Marcel is nearly unbiased, so it was the right yardstick
in exactly the bucket Opus checked. The base hurdle sat 11% low there because regulars are
disproportionately talented and the model had no talent term — same root cause as finding 1,
one fix for both. Residual −18 PA (~3%): plausibly the partial-2026 features plus remaining
talent shrinkage; re-check after the season ends as already queued. For pitchers the story
inverts: Marcel over-projects regular IP (+27) and the hurdle was right all along. The model
was not changed to match Marcel anywhere — T1 was accepted on its own pre-registered gate.

