# M4 — ML challenger + formal model comparison (Fable)

Written 2026-09-18. §1–§4 (design, information set, scoring, accept/reject rules) were
written and committed to this file BEFORE any challenger number was computed. Results in
§5–§7 were appended after. Budget $10; this is the last Fable mission.

## §1 The challenger

`sklearn.ensemble.HistGradientBoostingRegressor` (sklearn 1.9.1; per Daniel: no
lightgbm/xgboost), one model per (role, stage, target T) — the same per-stage decomposition
as Tier 2, so stage predictions combine into wOBA/FIP through the identical verified
`stats_from_stage_probs` path, same scoring env, same actual-PA′/IP FIP re-basing, same
PA′-weighted metrics, same eval population (`eval_population`: PA′ ≥ 200 in T + history in
T−3..T−1).

**Regression target:** per training row (player i, label season s), the logit-scale
deviation of the observed stage rate from that season's league rate:
`z = logit((y+0.5)/(n+1)) − mu_league_logit(s)`, sample weight = n (stage trials).
**Prediction for T:** `prob = invlogit(projection_logit(lg_train, stage, T−1) + ẑ)` — the
identical 1/1/1 environment point forecast the locked Tier 2 (E5+E6) uses for mu_proj.

**Training rows:** label seasons 2016 ≤ s ≤ T−1 (data starts 2015; features need s−1),
players from the same `player_season_{role}` table, via the same `stage_counts` /
`pa_prime` frame `_stage_long` feeds the state-space model. Rolling origin: everything is
computed inside `train_slice(bundle, T)` — nothing at or after season T exists in the
frame, by the same guard the backtest uses.

## §2 Information set (exact columns and lags)

All features derive from `train_slice(b, T)`; no column uses season s or later (age is
known pre-season from birth date, like every tier). NaN = "no such season"; HGBR handles
NaN natively. No Statcast (locked Tier 2 doesn't use it). Park handling: park-implicit
through raw historical rates, exactly like Marcel; scored park-aware like every tier.

| feature | source frame | lag |
|---|---|---|
| dev_lag1..3 — target-stage logit dev from league, `logit((y+.5)/(n+1)) − lg.logit` | `stage_counts` + `lg[role]` | s−1, s−2, s−3 |
| n_lag1..3 — target-stage trials | `stage_counts` | s−1..s−3 |
| xdev_<stage>_lag1 — same dev for every *other* stage of the role | `stage_counts` | s−1 |
| pa_lag1..3 — PA′ | `pa_prime(ps)` | s−1..s−3 |
| age — seasonal age at s | `ps.age` | pre-season |
| n_hist — count of prior seasons with PA′ ≥ 1 | `ps` | ≤ s−1 |
| rp_share_lag1 = 1 − GS/G (P only) | `ps_P` | s−1 |

Cross-stage lag-1 deviations are information Tier 2 cannot use (stages fit independently);
they are inside the information set (same table, seasons ≤ T−1) and are the flexible
learner's legitimate edge, so they are in.

**Hyperparameters — fixed, pre-registered, never tuned on dev targets:**
primary A: `lr=.06, max_leaf_nodes=15, min_samples_leaf=40, l2_regularization=1.0,
max_iter=1000, early_stopping=True, validation_fraction=.15, n_iter_no_change=30,
random_state=1` (early-stopping split is a random subset of training rows, all ≤ T−1).
Sensitivity B (reported, never decides): `max_leaf_nodes=31, min_samples_leaf=20`.

## §3 Distributional scoring

Point RMSE is scored exactly as `weighted_metrics`. Marcel numbers come from canonical
`backtest.json` (repaired E5+E6 file); the pipeline is validated by reproducing Marcel's
RMSE from scratch before any GBM number is read.

Proper score: **CRPS**, Monte Carlo (500 draws, estimator mean|X−a| − ½mean|X−X′|),
PA′-weighted mean per (role, stat, target). Both models get the same aleatoric term so the
comparison isolates epistemic quality:

- **binomial/multinomial noise** s_binom(player, stat): sd of derived stats over
  `simulate_season` draws at the player's actual PA′ from the GBM stage probs — the same
  values added to both models' predictives (symmetric; cancels to first order).
- **Tier 2 epistemic:** split-normal reconstructed from the sidecar per-player
  (q10, q50, q90) — the M1 piecewise precedent. Sanity check: reconstructed cov80 must land
  within a few points of backtest.json's reported cov80, else the reconstruction is judged
  unusable and the distributional comparison is reported as pinball-on-sidecar-quantiles
  only, with that caveat.
- **GBM epistemic (the honest interval method for a point learner):** Normal(0, s_epi) per
  (role, stat, T), where s_epi² = max(0, weighted-var(stat residuals) − mean s_binom²) from
  an auxiliary fit trained on ≤ T−2 predicting season T−1 (out-of-sample within the
  training years; environment-forecast error is inside the residuals, so the env-shock role
  of E6 is covered empirically).

cov80 = share of actuals inside the empirical [q10, q90] of each model's predictive draws.
Secondary: pinball loss at .1/.9. Seeds fixed (numpy default_rng(7)).

## §4 Hybrid and accept/reject rules (pre-registered)

**Hybrid:** Tier 2 posterior mean + HGBR fitted to its residuals, stat level
(`actual − tier2_pred_mean`, weight PA′), features of §2 computed at the hybrid's target
plus `tier2_pred_mean`, `q90−q10` width, Marcel stat, `tier2 − marcel` gap. Training rows:
eval populations of dev targets T′ < T only (Tier 2 backfits before 2021 are impossible —
the 6-season window would need 2014 data). So the hybrid is scored on **2022–2024** with
expanding training (n ≈ 320/640/960 per role); Tier 2 and GBM comparators are re-averaged
on the same subset. Heavier regularisation, pre-registered: `max_leaf_nodes=7,
min_samples_leaf=30, lr=.05, max_iter=300, early_stopping=True, validation_fraction=.2,
random_state=1`. Hybrid predictive = Tier 2 predictive shifted by the correction.

**Rules (decided before any result; nothing ships unless its rule passes):**

- **A1, GBM point:** key-stat (wOBA/FIP) PA′-weighted RMSE beats Tier 2 in ≥ 3/4 dev
  targets AND the 4-target mean beats both Tier 2 and Marcel.
- **A2, GBM distributional:** key-stat mean CRPS beats Tier 2 in ≥ 3/4 targets AND mean
  cov80 ∈ [.75, .85].
- **A3, hybrid:** on 2022–2024, key-stat RMSE beats Tier 2 in ≥ 2/3 targets AND the mean
  beats both Tier 2 and GBM-alone AND mean CRPS ≤ Tier 2's AND cov80 ∈ [.75, .85].
- Components are diagnostic only (no multiplicity fishing); any component where a
  challenger is > 10% worse than Tier 2 is a named caveat on an otherwise-passing rule.
- Judged on primary config A only. 2025 is spent and is touched by nothing here.

**Pre-registered expectations (honest priors, on record):** GBM points land between Marcel
and Tier 2; babip is where Tier 2's pooling + park effects should win clearly; P FIP is the
GBM's best shot at beating Tier 2 (Marcel already does). A2 likely fails (a constant
per-cell epistemic sd against a calibrated per-player posterior). A3 marginal at n ≤ 960 —
expected fail, H the better shot. If all three fail, that is the deliverable: the
structured model survives a fair flexible challenger.

---

*Results appended below after the runs; nothing above this line changed after.*

## §5 Harness validation (before any GBM number was read)

- Marcel wOBA RMSE 2024 H reproduced from scratch to 6 decimals (.033716, n = 348) against
  canonical `backtest.json` — the actuals/scoring path is byte-compatible.
- Leakage: tripling season-T counts and poisoning season-≥T league logits in the raw bundle
  changes no GBM prediction (`train_slice` guards the whole feature path).
- Tier 2 split-normal reconstruction sanity (pre-registered): recon cov80 H wOBA .817 vs
  reported .820; P FIP .751 vs reported .761 — within a few points, usable.
- One deliberate asymmetry, in Tier 2's favour: the sidecar `pred_mean` (draw-mean) scores
  FIP .8131 vs canonical .8162 (derive-of-mean, Jensen gap). The GBM was compared against
  the *stronger* Tier 2 point, so every GBM win below is a fortiori.
- 2021 caveat: the GBM's epistemic sd for 2021 comes from an auxiliary fit scored on 2020
  (COVID, ~66k league PA), so s_epi(2021) is inflated (P FIP .74 runs-scale vs .55–.64 in
  other years); 2021 GBM intervals run wide (FIP cov80 .857).

## §6 Results (primary config A; PA′-weighted; dev targets 2021–2024)

Key stat, point RMSE per target (gbm | tier2 | marcel):

| role | 2021 | 2022 | 2023 | 2024 | mean |
|---|---|---|---|---|---|
| H wOBA | .0349 · .0340 · .0336 | .0340 · .0322 · .0358 | .0314 · .0324 · .0304 | .0330 · .0326 · .0337 | **.0333 · .0328 · .0334** |
| P FIP | .8236 · .7956 · .7831 | .8536 · .8841 · .8214 | .7831 · .8191 · .8389 | .7150 · .7538 · .7356 | **.7938 · .8131 · .7947** |

Component 4-target means (gbm / tier2 / marcel): H — k .0367/.0347/.0363,
bb .0205/.0199/.0199, hr .0127/.0125/.0124, babip .0327/.0317/.0332.
P — k .0396/.0388/.0400, bb .0210/.0216/.0206, hr .0107/.0107/.0109,
babip .0328/.0324/.0334. No component is > 10% worse than Tier 2 (worst: H k, +5.8%).

Distributional, key stat (CRPS per target, gbm | tier2-recon; cov80 means):

| role | 2021 | 2022 | 2023 | 2024 | CRPS mean | cov80 |
|---|---|---|---|---|---|---|
| H wOBA | .0196 · .0188 | .0193 · .0183 | .0175 · .0179 | .0184 · .0182 | .0187 · .0183 | gbm .793, t2 .817 |
| P FIP | .4675 · .4547 | .4759 · .5003 | .4353 · .4440 | .3914 · .4132 | .4425 · .4531 | gbm .827, t2 .751 |

Hybrid (scored 2022–2024 only; means on that subset):
H wOBA — hybrid .0324, tier2 .0324, gbm .0328, marcel .0333; CRPS hybrid .0183 vs tier2
.0181 (not better); cov80 .804. P FIP — hybrid **.7770**, tier2 .8190, gbm .7839, marcel
.7986; per target .7781/.8571/.6957 (the 2023 correction *hurt*: worst model that year);
CRPS .4253 vs tier2 .4525; cov80 .789.

**Verdicts against the pre-registered rules:**

- **A1 H — FAIL** (1/4 vs Tier 2; mean .0333 loses to Tier 2 .0328). **A2 H — FAIL**
  (CRPS 1/4). **A3 H — FAIL** (mean ties Tier 2, CRPS not better). The structured model
  survives the flexible challenger on hitters outright; the GBM is worst exactly on H k%,
  the highest-signal stage, where per-player partial pooling beats 3k rows of trees.
- **A1 P — PASS** (3/4 vs Tier 2, loses only 2021; mean .7938 < Tier 2 .8131 and < Marcel
  .7947 — the Marcel margin is .0009, fragile). **A2 P — PASS** (CRPS 3/4; cov80 .827 in
  band — the residual-based intervals are honestly calibrated, and on FIP better than the
  Tier 2 reconstruction's .751). **A3 P — PASS** (2/3 vs Tier 2, means beat both, CRPS
  better, cov80 in band) — with the named instability: one of three years (2023) the
  correction was the worst model on the board.

**Sensitivity B** (deeper trees, never decides): uniformly slightly worse — H wOBA mean
.0336, P FIP .8089. B still beats Tier 2 on FIP in 3/4, but loses to Marcel's mean: the
robust P finding is "GBM beats Tier 2 on FIP", while "GBM beats Marcel's mean" (margin
.0009 under A) is config-sensitive and should not be leaned on.

## §7 Verdict

**Hitters: the hierarchical model wins, and the result is clean.** The GBM — given
cross-stage features Tier 2 cannot see — loses on points (1/4), on CRPS (1/4), and the
hybrid adds nothing (ties Tier 2's subset mean, worse CRPS). It is worst exactly where
pooling is strongest (H k%: GBM .0367 vs Tier 2 .0347): ~600 players × 8 label seasons is
not enough data for trees to rediscover what a per-player hierarchical posterior encodes.
The M2c locked model survives a fair flexible challenger outright.

**Pitchers: a real, mechanism-consistent finding — but nothing ships.** The GBM beats
Tier 2's FIP points in 3/4 years and its CRPS in 3/4 with honestly calibrated intervals;
the hybrid is the best point model on every scoreable subset mean. The only information
the GBM holds that Tier 2 doesn't is *other stages' lag-1 deviations*, so this is direct
evidence for what M2c assessed and declined on cost: cross-stage structure matters for
pitchers (K/BB/HR mix is one arsenal, not three independent walks). Against the shipping
bar, though: the §6 gate as written is ≥ 3/4 **vs Marcel** + coverage, and the GBM is 2/4
vs Marcel (loses 2021, 2022) with a Marcel-mean margin (.0009) that flips sign under
sensitivity B. The hybrid cannot be scored on 2021 at all (no Tier 2 backfits exist before
2021 — the 6-season window would need 2014 data), passes a 3-target §6 analog (2/3, need
2, cov80 .789), but one of its three years was the worst model on the board and its
residual learner saw ≤ 960 rows. 2025 is a spent holdout and cannot arbitrate.
**Recommendation: production unchanged (Marcel points, Tier 2 bands). Do not ship either
challenger.** The P hybrid is the strongest post-project candidate; the right next test is
one new season (2026 targets) scored once, pre-registered, before any wiring.

**For the README (two or three sentences):** *We red-teamed the Bayesian model with a
gradient-boosted challenger on an identical information set, plus a Bayesian+GBM hybrid,
compared on point RMSE and CRPS under pre-registered accept rules. On hitters the
hierarchical model beat both challengers on every score — the structure earns its keep. On
pitchers the challengers beat the Bayesian FIP points (evidence that cross-stage
information, which per-stage independence discards, is real signal for pitchers), but
neither cleared the shipping gate against Marcel, so production is unchanged.*

## §8 Artifacts

- `backend/keystone/eval/ml_challenger.py` — challenger, hybrid, scoring (seeds fixed).
- `backend/keystone/eval/m4_verdict.py` — aggregates results into the §4 rules.
- `data/artifacts/m4/m4_results.json` — all 460 scored rows (A, B, hybrid, marcel,
  tier2-sidecar), plus run logs.
- Repro: `cd backend && PYTHONPATH=. ../.venv/bin/python -m keystone.eval.ml_challenger`
  (~7 min CPU), then `-m keystone.eval.m4_verdict ../data/artifacts/m4/m4_results.json`.
