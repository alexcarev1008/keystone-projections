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
