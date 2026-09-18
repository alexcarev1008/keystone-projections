# M2 — Model research experiments (Fable)

M2a written 2026-09-17, AFTER Daniel's post-M1 park-aware re-run, BEFORE any experiment run.
Gate (MANUAL §6): tier2 RMSE <= Marcel on the key stat in >= 3/4 dev targets AND key-stat mean
cov80 in [0.75, 0.85]. No 2025 involvement anywhere in M2a/M2b.

## M2a diagnosis (post-M1 state: park-aware scoring, dev targets 2021–2024)

State after M1: H wOBA essentially tied (.0333 vs Marcel .0334; wins 2022+2024, loses 2021 by
.0005 and 2023 by .0023; cov80 .783 ✓). P FIP still loses (.8223 vs .7947; wins 2023 only;
cov80 .732 ✗). Computed from the fresh sidecar + recomputed actuals (scratch, deleted):

1. **Environment lag (extends M1-F3).** PA-weighted FIP bias by target, marcel/tier2:
   2021 +.15/+.21 · 2022 +.28/+.39 · 2023 −.18/−.02 · 2024 +.09/+.14. The 2022 dead-ball year
   is the biggest single loss (tier2 .887 vs .821) and is mostly *bias*: debiasing 2022 alone
   would put tier2 at √(.887²−.394²) ≈ .794. Stage-level, tier2 over-projects H k_pct in all
   4 targets (+.0046..+.0084, Marcel +.0011..+.0047) and P bb_pct in all 4 — consistent with
   `projection_logit` = unweighted 3-season mean logit (2020 at full weight) lagging trending
   league rates. Tier 2's bias is *worse* than Marcel's on pitchers because Marcel's 5/4/3
   player-rate weighting is more recent than tier2's 1/1/1 environment mean.
   FIP cov80 .732 is the same disease: mu_proj is a point constant, so environment forecast
   error is missing entirely from the intervals; it is common across players, exactly the error
   RMSE-weighted coverage feels most.
2. **Relievers (new).** Splitting P FIP by T-season role (GS/G >= 0.5 = SP): tier2 loses RP in
   4/4 targets (RMSE .85/1.12/.91/.92 vs Marcel .81/1.01/.83/.84) while winning or tying SP in
   3/4 (2023 .770 vs .844, 2024 .657 vs .670). Both tiers project RP FIP high (bias +.15..+.69)
   but tier2 is worse: the hierarchy shrinks a reliever's theta toward a pooled mean whose K/BB/HR
   mix is starter-dominated (in BF terms), and lam·z(log BF) makes low-BF relievers the most
   shrunk. Pooling SP/RP into one population prior is a specification error Marcel doesn't share
   (Marcel regresses toward a rate mix that is at least the same for both, with fewer BF regressed).
3. **T-1 chasing (confirms M1-F4).** corr(T-1 deviation from own 3-yr mean, projection error),
   mean over targets — tier2/marcel: H k +.036/−.071 · H bb +.047/−.044 · P k +.103/−.072 ·
   P bb +.044/+.040. Tier2 over-weights T-1 exactly where skills are stablest; fitted tau
   (H/bb .129, H/k .123, P/k .146) implies implausible ~13%/yr relative talent swings — Gaussian
   innovations force one scale on a mixture of "most players barely move, a few jump".
4. Not pursued in M2a: fit-population reweighting (refuted, M1-F2); more Statcast indicators
   (tier3 lost on points, a weighting question deferred to M2b/c); H/hit_bip funnel (M2c);
   correlated stages (M2c).

Ranking by (expected gain × confidence) ÷ complexity: E2 > E3 > E4.

---

## E2 — League environment: recency-weighted point + environment uncertainty (flag `--env-mode recency`)

- **Change.** `league.projection_logit_recency`: mu_proj = weighted mean logit of the last 3
  seasons with weight ∝ recency (1/2/3) × season trial share (2020 self-downweights); plus
  sigma_env = sd of year-over-year league logit changes over the training window. `SS.project`
  adds one persistent sigma_env·z shock per posterior draw (common across horizons — environment
  error is shared, not per-player). Fit untouched; same seed ⇒ same fits as baseline.
- **Hypothesis.** The point fix removes the trend-lag half of the uniform bias (P bb, H k in all
  targets; FIP hardest via 13·HR); the shock supplies the missing common-error term in intervals.
- **Pre-registered expectation (full run).** P FIP RMSE improves in ≥ 3/4 targets vs the current
  tier2 run, FIP cov80 rises from .732 into [0.75, 0.85]; H k_pct bias shrinks toward 0 in all
  targets; H wOBA 2021 (gap .0005) plausibly flips. Risk registered: H babip 2023 may worsen
  slightly (shift-ban bump is unforecastable and 2022 gets more weight).
- **Decides.** §6 gate arithmetic on `backtest_E2.json` (tier2 vs marcel rows in that file).
- **Quick validation (pre-registered).** `--quick` H 2024 k+hr, seed 1, vs baseline quick:
  identical fits; stage_k RMSE falls (2024 H k bias was +.0046); stage_hr ~unchanged
  (H hr bias 2024 +.0006, nothing to remove).
- **Quick result.** Fits identical to baseline (tau/r_hat byte-equal — pure scoring delta).
  stage_k RMSE .0341 → .0339 (Marcel .0349); stage_hr .0172 → .0172. Matches the
  pre-registered expectation; goes to the full run.

## E3 — SP/RP covariate on pitcher stages (flag `--rp-effect`)

- **Change.** Per pitcher-season covariate rp_share = 1 − GS/G (from player_season_P), centred
  over the fit rows; `build_model` adds delta_role ~ Normal(0, 0.5) with logit_p += delta_role ·
  x. Projection uses the player's last observed rp_share (T-1 role predicts T role), same
  centring. H role ignores the flag.
- **Hypothesis.** With the role offset carried by delta_role, theta shrinkage no longer drags
  relievers toward the starter-dominated mix; the RP block (loses 4/4) improves without hurting
  SP (the covariate is ~0-cost for pure starters after centring).
- **Pre-registered expectation (full run).** delta_role posterior clearly nonzero for P k (RP
  K% higher) and P hr (RP HR% lower); P FIP RMSE improves vs the current tier2 run in the RP
  subgroup in ≥ 3/4 targets and overall FIP RMSE improves in ≥ 2/4; cov80 direction unconstrained.
- **Decides.** §6 gate arithmetic on `backtest_E3.json` (P only).
- **Quick validation (pre-registered).** `--quick --roles P --stages k hr` 2024: samples cleanly
  (divergences ≤ baseline + 10, r_hat < 1.1); |delta_role| posterior mean > its sd for k;
  stage_k RMSE not worse than the P-quick baseline by more than noise (fits are re-sampled, so
  small wiggle allowed).
- **Quick result.** delta_role k = +0.141 (sd .015), hr = −0.137 (sd .021) — right signs (RP
  K% up, RP HR% down), both ~7–10 sd from 0. stage_k RMSE .0371 → .0369, stage_hr .0141 → .0142
  (P-quick baseline: k .0371, hr .0141). Divergences 2/0 (baseline 0/1); r_hat ~1.12 at quick
  sampling. All pre-registered checks pass; goes to the full run.

## E4 — Student-t(4) talent innovations (flag `--innov t4`)

- **Change.** Transition noise tau·e with e ~ StudentT(4) instead of Normal (first-season
  population draw stays Normal; disjoint index sets keep the latent dimension unchanged).
  nu = 4 fixed, pre-registered — not tuned.
- **Hypothesis.** Talent changes are a mixture (mostly tiny, occasionally large: injury, swing
  or pitch-mix change). A Gaussian forces one scale, inflating tau and over-weighting T-1 on
  stable skills; t(4) lets the scale fall for the mass while keeping big moves reachable.
- **Pre-registered expectation (full run).** tau_mean falls for H/k, H/bb, P/k, P/bb; the
  chasing correlation moves toward 0; bb_pct RMSE improves for both roles in ≥ 2/4 targets; key
  stats improve or tie (this is a variance fix, smaller than E2/E3 — H wOBA 2021's .0005 gap is
  the realistic flip). Registered risk: heavier tails may worsen sampler geometry; reject if
  divergences blow up (> 2× baseline) even if RMSE ties.
- **Decides.** §6 gate arithmetic on `backtest_E4.json`.
- **Quick validation (pre-registered).** `--quick` H 2024 k+hr: samples cleanly; tau posterior
  mean for k falls vs baseline quick; stage_k RMSE within noise of baseline or better.
- **Quick result.** tau H/k .1239 → .0916, H/hr .1737 → .1284 (both fell, as hypothesised —
  the scale drops when the tails carry the jumps). stage_k RMSE .0341 → .0341, stage_hr
  .0172 → .0172. Divergences 0/1 (baseline 0/0); max r_hat 1.19 on k at 150-draw quick
  sampling (baseline itself shows 1.11 on hr at this scale — geometry judged at the full run's
  500/500). Goes to the full run.

---

## Full-run commands (Daniel; see STATUS.md)

Each writes its own JSON + sidecars under `data/artifacts/m2/` — `backtest.json` and the
production gates are untouched until M2b accepts something.

```
cd backend
PYTHONPATH=. ../.venv/bin/python -m keystone.pipeline backtest --env-mode recency --out ../data/artifacts/m2/backtest_E2.json
PYTHONPATH=. ../.venv/bin/python -m keystone.pipeline backtest --rp-effect --roles P --out ../data/artifacts/m2/backtest_E3.json
PYTHONPATH=. ../.venv/bin/python -m keystone.pipeline backtest --innov t4 --out ../data/artifacts/m2/backtest_E4.json
```

## M2b decisions

(to be filled by M2b against the pre-registered expectations above — no goalpost moves)
