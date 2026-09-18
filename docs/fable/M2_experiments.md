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

## M2b decisions (2026-09-18, from `data/artifacts/m2/backtest_E2.json` + `backtest_E4.json`)

Headline (PA-weighted RMSE, mean 2021–2024): H wOBA marcel .0334 / base .0333 / E2 .0333 /
E4 .0333; P FIP marcel .7947 / base .8223 / E2 .8201 / E4 .8241. Gates FAIL for every variant
(H 2/4, P 1/4); production stays marcel.

- **E2 — REJECT** against its pre-registered rule. FIP RMSE improved in only **2/4** targets
  (2022 .8902→.8685, 2024 .7658→.7654; 2021 and 2023 worsened) vs the required ≥ 3/4. The
  cov80 half **passed exactly as registered**: mean .732 → .755, into [0.75, 0.85]
  (per-target .781/.714/.755/.771). H wOBA 2021 did not flip (.0341→.0340 vs marcel .0336).
  The H k_pct bias sub-check is unverifiable from disk — the E4 run overwrote the m2/ sidecars
  (single-slot sidecar naming; noted in HANDOFF). Mechanism read: the 2022 win is the
  registered bias story working (dead-ball trend, recency helps); the 2021 loss is the same
  weighting overcorrecting when the recent seasons mislead (2020 oddity + mid-2021 sticky-stuff
  break). The *shock* half of E2 did all the calibration work and none of the damage — the
  point-forecast half did the damage. Carried forward as E6.
- **E3 — NOT JUDGED.** `backtest_E3.json` is not on disk; the SP/RP full run apparently never
  completed. The change remains implemented and quick-validated; the full run goes back on
  Daniel's queue unchanged. No verdict, no goalpost move.
- **E4 — REJECT** against its pre-registered rule, with the most useful finding of the round.
  tau_mean fell for all four registered stages (H/k .1232→.0913, H/bb .1293→.0935,
  P/k .1457→.1070, P/bb .1204→.0873) ✓ — but the **chasing correlation did not move**
  (H/k .033→.034, H/bb .032→.033, P/k .107→.108, P/bb .051→.051) ✗, bb_pct improved in
  H 1/4, P 0/4 vs required ≥ 2/4 ✗, and P FIP slipped .8223→.8241 (H wOBA tied) — "improve or
  tie" ✗. **Why tau fell without anything changing:** StudentT(4) has variance 2·tau², and the
  fitted taus fell by almost exactly √2 (e.g. H/bb .0935·√2 = .132 ≈ .129). The innovation
  *variance* is data-identified and was conserved; t4 relabelled the scale. The year-to-year
  variance the model demands is real — the misspecification is that the random walk forces it
  to be **persistent**. That redirects to E5. Geometry: divergences 429 → 172 (H/hit_bip
  184→28, H/bb 94→29), most cluster r_hats down — far under the 2× reject threshold, a real
  gain. **Not shipped in M2b** (the pre-registered rule has no geometry-only accept, and
  swapping the innovation mid-M2b would change the baseline under E5/E6), but handed to M2c,
  which owns sampler geometry: evaluate `--innov t4` as the default in the lock-in bundle,
  where an accuracy-neutral change with cleaner geometry is worth adopting.
- **On E2's calibration counting for anything:** under the gates as written, no. The gate is
  accuracy AND coverage; P is 1/4 on accuracy, so cov80 .755 ships nothing by itself. But the
  P gate can never pass without the coverage fix even if accuracy is solved, so the shock is a
  necessary component of any path to a P gate PASS — which is exactly why it survives as E6
  while E2 as a bundle is rejected.

---

## E5 — Transient season-level noise (flag `--obs-noise`) — M2b, pre-registered before any run

- **Change.** `build_model(obs_noise=True)`: per observed player-season,
  `logit_p += sigma_obs · eps`, eps ~ N(0,1) non-centred, `sigma_obs ~ HalfNormal(0.2)`.
  `project` draws fresh transient noise per (player, horizon, draw) — added to the logit,
  never to the talent walk, so it does not accumulate.
- **Hypothesis.** E4 proved the year-to-year logit variance (~.12–.13 for k/bb) is
  data-demanded but showed reshaping the walk can't help: the walk is the variance's only home,
  so it is forced to be persistent, and the filter chases T-1 (M1-F4, M2a-3). A transient term
  splits observed wiggle into drift (tau, persists) + season effects (sigma_obs, doesn't);
  posterior theta then leans toward the multi-year mean — which is what Marcel's regression
  gets right on BB%, the stablest skill in the sport and the only pitcher component tier2
  loses (.0220 vs .0206, carrying 3× weight in FIP).
- **Pre-registered expectation (full run).** tau falls materially (> 20%) for H/k, H/bb, P/k,
  P/bb with sigma_obs clearly nonzero there (this time NOT variance relabelling — the
  *effective* T-1 weight drops because eps absorbs the wiggle); chasing corr moves toward
  Marcel's; **bb_pct RMSE improves for both roles in ≥ 2/4 targets**; P FIP mean RMSE improves
  vs base .8223; H wOBA improves or ties; H wOBA cov80 stays in [.75, .85] (transient noise
  widens intervals — overshoot > .85 is a registered failure). **Reject if** divergences > 2×
  baseline (tau/sigma_obs/binomial variance partition may funnel) or if sigma_obs collapses
  to ~0 (then the term is unidentified and the experiment is null).
- **Decides.** §6 gate arithmetic on `backtest_E5.json`.
- **Quick validation (pre-registered).** `--quick` H 2024 k+hr, seed 1, vs M2a's recorded
  baseline quick (stage_k RMSE .0341, stage_hr .0172; tau H/k .1239, H/hr .1737): samples
  cleanly (divergences ≤ baseline + 10 at quick scale); sigma_obs posterior mean > .03 for k;
  tau H/k falls > 20%; stage_k RMSE ≤ .0345 (fits are re-sampled; small wiggle allowed).
- **Quick result.** All checks pass. 0 divergences both stages; sigma_obs k = .0800 (sd .0122,
  ~6.6 sd from 0), hr = .1335 (sd .0196); tau H/k .1239 → .0964 (−22%), H/hr .1737 → .1331
  (−23%); stage_k RMSE .0341 → **.0338** (Marcel .0349), stage_hr .0172 → **.0169** (= Marcel).
  Variance bookkeeping confirms the mechanism: .0964² + .0800² ≈ .1239² — the total year-to-year
  variance is conserved (as E4 showed it must be) but .0064 of it is now transient and no longer
  propagates into the projection. Goes to the full run.

## E6 — Environment shock without the recency point (flag `--env-mode shock`) — M2b

- **Change.** `fit_stage_draws`: mu_proj = baseline `projection_logit` (1/1/1 mean, untouched);
  mu_sd = `projection_logit_recency`'s sigma_env (E2's yoy-volatility term). Fit untouched;
  same seed ⇒ same fits as baseline. Pure scoring/interval delta.
- **Hypothesis.** E2 decomposes: the shock produced the cov80 gain (.732→.755, the registered
  target) and, being zero-mean, ~none of the RMSE movement; the recency point forecast produced
  the 2022 win AND the 2021/2023 losses. Keep the validated half, drop the coin-flip half.
- **Pre-registered expectation (full run, judged on `backtest_E5E6.json` vs `backtest_E5.json`).**
  Fits identical to the E5-alone run (same seed); all RMSE within noise of E5-alone; P FIP
  cov80 higher than E5-alone by roughly the E2 delta (~+.02), with the E5+E6 combination in
  [0.75, 0.85] for both roles — overshoot > .85 is a registered failure of the combination.
- **Decides.** Whether the shipping candidate is E5 or E5+E6.
- **Quick validation (pre-registered).** `--quick` H 2024 k+hr, seed 1: runs green; tau
  byte-equal to the plain baseline quick (pure scoring delta); stage RMSE within noise of .0341/.0172.
- **Quick result.** All checks pass. tau k .1239 / hr .1737 — identical to the recorded
  baseline quick (fits untouched); 0 divergences; stage_k .0338, stage_hr .0172 (within noise;
  the k tick is the zero-mean shock's Jensen wiggle on the draw mean). Goes to the full run.

## M2b full-run commands (Daniel; also in STATUS.md)

```
cd backend
PYTHONPATH=. ../.venv/bin/python -m keystone.pipeline backtest --rp-effect --roles P --out ../data/artifacts/m2/backtest_E3.json   # rerun — never completed
PYTHONPATH=. ../.venv/bin/python -m keystone.pipeline backtest --obs-noise --out ../data/artifacts/m2/backtest_E5.json
PYTHONPATH=. ../.venv/bin/python -m keystone.pipeline backtest --obs-noise --env-mode shock --out ../data/artifacts/m2/backtest_E5E6.json
```

E5 is judged vs base; E6's marginal effect is E5E6 vs E5. If E3 passes its (M2a) rule it is a
candidate for the M2c lock-in bundle alongside whatever survives here — combinations are
M2c's job, judged once, with the holdout still unspent.

---

## M2c decisions + lock-in (2026-09-18, from `backtest_E3.json` / `backtest_E5.json` / `backtest_E5E6.json`)

Headline (PA-weighted RMSE, mean 2021–2024): H wOBA marcel .0334 / base .0333 / E5 .0328 /
E5+E6 .0328; P FIP marcel .7947 / base .8223 / E3 .8204 / E5 .8162 / E5+E6 .8164.

- **E5 — ACCEPT.** Every pre-registered sub-check passed, none marginally:
  1. tau fell > 20% with sigma_obs clearly nonzero (mean over targets): H/k .1232→.0972 (−21%,
     sigma_obs .078), H/bb .1293→.0607 (−53%, .132), P/k .1457→.0994 (−32%, .113),
     P/bb .1204→.0897 (−26%, .098); every sigma_obs ≥ 7 sd from 0 — not relabelling this time:
  2. the chasing correlation moved to Marcel's side of zero on all four stages (computed
     identically on the base and E5E6 sidecars; E6 is fits-identical to E5): H/k +.042→−.038,
     H/bb +.048→−.070, P/k +.116→−.031, P/bb +.052→+.008.
  3. bb_pct RMSE improved in H 3/4 (2024 −.00002, the one miss) and P 4/4 — required ≥ 2/4 both.
  4. P FIP mean .8223→.8162 ✓; H wOBA .0333→.0328 ✓; H wOBA cov80 .806 in [.75,.85] ✓.
  5. No reject trigger: divergences 121 vs baseline 313 (H/hit_bip 181→25 — obs-noise
     largely dissolved the M1-F5 funnel as a side effect); sigma_obs nowhere near 0.
- **E6 — ACCEPT.** Judged as registered on E5E6 vs E5: fits byte-identical (tau equal to full
  precision across all 48 fits); all RMSE within noise (FIP .8162 vs .8164, wOBA .03276 vs
  .03278); P FIP cov80 .734→.761, +.027 ≈ the E2 delta, per-target .781/.702/.769/.792; both
  roles in band (H .820, P .761), no overshoot. **The shipping candidate is E5+E6.**
- **E3 — REJECT for the lock-in bundle.** Against its M2a rule: delta_role clearly nonzero with
  the registered signs in all 4 targets (k +.14..+.17, ~10 sd; hr −.09..−.14, ~5–7 sd) ✓;
  overall FIP improved 3/4 (2021/2023/2024; 2022 worsened .8902→.8941) ✓ vs required ≥ 2/4;
  but the **RP-subgroup ≥ 3/4 sub-check — the mechanism the experiment exists to test — is
  unverifiable**: the E5 run overwrote E3's predictions sidecar (same single-slot collision that
  cost E2 a sub-check; HANDOFF item still open). An unverifiable pass is not a pass. Weighing
  the rest: the marginal gain is small (.8223→.8204) and mostly subsumed by E5 (P k .0395 vs
  E5 .0388, P bb .0218 vs .0217); 2022 P/hr hit r_hat 1.363, the worst fit in the project, in
  exactly the year E3 got worse; and E3 was run against the old baseline, so bundling it would
  require one more ~50-min combined dev run to judge — for a variant carrying a convergence
  failure. Not worth the run. The idea stays plausible (the delta_role posteriors are real);
  re-testable post-M2 on top of the locked config if anyone wants it.
- **`--innov t4` for geometry — DECLINED**, per a quick check pre-registered before the run
  (`--quick --obs-noise --innov t4`, H 2024 k+hr, seed 1, vs E5-quick): divergences 0/1 ✓, but
  stage_k .0340 / stage_hr .0169 — identical to E5-quick, not strikingly better; tau H/k
  .0666 ≈ .0964/√2 — **the E4 relabelling reappears under obs-noise** (walk-share variance
  conserved, scale renamed); and max r_hat 1.371 on H/k at quick scale is a red flag, not the
  cleaner geometry that was t4's only remaining case. Its M2b geometry gain (313→172) was
  measured without obs-noise; E5 gets further (121) with the funnel fixed (H/hit_bip r_hat
  1.23→1.07). Adopting t4 would also make the locked config one no full dev run has validated.
- **Correlated stages — ASSESSED, NOT ATTEMPTED.** The observed cross-stage residual
  correlations (stage_correlations.csv, the honest data-only proxy) top out at P bb–k .32,
  H hr–xbh .31, H k–xbh .24, most pairs |r| < .15. A joint walk/shared factor pools information
  across stages — but the binding losses after E5 are regime/environment errors (P 2022
  .8905 vs marcel .8214 dead-ball; H 2023 .0322 vs .0304 shift ban), which cross-stage pooling
  does not touch, and the per-stage architecture would have to be rebuilt into one joint model
  (7 H + 5 P latent walks), resetting every validated result at ~10× sampling cost. Expected
  gain small, cost the largest in the project, holdout waiting. Declined with reasons, not
  deferred: post-holdout work if the project continues.

### The mean and the gate disagree on hitters — which measures projection skill?

E5 hitters beat Marcel on the 4-year PA-weighted mean (.0328 vs .0334) but win only 2/4 years,
losing 2021 by .0002 and 2023 by .0018, so the gate (≥ 3/4) fails. **The mean is the better
measure of skill.** Per-year win counting is a sign test with n = 4: it throws away magnitude
(a .0002 loss counts the same as a .0023 loss), and its sampling noise at n = 4 exceeds that of
the mean it is guarding. The count's one virtue — robustness to a single lucky year — matters,
but E5's mean win is not one lucky year: it improves the mean in 4/4 years for H wOBA
(.0341→.0338, .0338→.0326, .0327→.0322, .0329→.0326 vs base). Judged by expected loss, the
locked hitter model is now better than Marcel. **The gate stays as written for this decision**
(it was pre-registered; moving it after seeing the numbers is exactly what pre-registration
exists to prevent): production points remain Marcel for both roles. Recommendation for the
README/memo, not for this decision: a future gate should test the mean RMSE difference with a
paired-by-player block bootstrap rather than count years.

### Locked production configuration

**Tier 2 with `--obs-noise --env-mode shock` (E5+E6), innov normal, no rp-effect, park-aware
scoring — exactly the configuration of the full dev run in `backtest_E5E6.json`, seed 1.**
Gates on that run: H FAIL 2/4 (cov80 .820 ✓), P FAIL 1/4 (cov80 .761 ✓) → per MANUAL §6,
production ships **Marcel points with Tier 2 bands**, where the bands, aging drift and
waterfall now come from the locked config. Coverage is in band for both roles for the first
time in the project.

Holdout (Daniel, ONCE, after Opus wires the HANDOFF items so the holdout subcommand carries
the locked flags and `backtest.json` is the promoted E5E6 run):

```
make holdout
```

Record the 2025 result in this file and STATUS.md exactly as printed, good or bad.

---

## The 2025 holdout (M2c)

### Attempt 1, 2026-09-18 — MISCONFIGURED, ruled invalid

`make holdout` ran at 14:53 local with the pre-handoff pipeline — Daniel's run raced Opus's
wiring commit (`handoff: M2c`, 14:54) by one minute. The code that executed had no model-config
flags on the holdout subcommand and no flag-match guard (both were added in the commit that
landed sixty seconds later), so it scored 2025 with the OLD defaults
`{env_mode: mean3, obs_noise: false}` — the superseded pre-M2 model, not the locked E5+E6 —
and then stamped those flags over the promoted `backtest.json` and set `holdout_target: 2025`.
The canonical file is now a chimera (locked-config dev rows, old-config 2025 rows, flags that
claim the whole file is old-config); repair is a HANDOFF item.

Result as printed, recorded permanently (old config, 2025, n = 319 H / 325 P):

    H  woba  marcel .0305 | tier2 .0309 (cov80 .81)     P  fip   marcel .7317 | tier2 .7402 (cov80 .75)
    H  bb    .0197 | .0196    H  hr  .0117 | .0118      P  bb    .0172 | .0185    P  k   .0380 | .0377
    H  k     .0364 | .0378    H  babip .0327 | .0303    P  hr    .0100 | .0098    P  babip .0336 | .0319

### Ruling: the holdout is NOT spent; one re-run with the locked config is authorised

Reasoning, written before the re-run:
- The one-shot rule exists to prevent adaptive selection on 2025 — trying configurations and
  keeping the one that looks best. That opportunity does not arise here: the locked
  configuration was decided on dev evidence alone and committed (`8ced169`) before any 2025
  number existed, and the need to re-run follows from the misconfiguration itself, not from
  the numbers the misfire printed. The run was invalid by construction whatever it said.
- Declaring the holdout spent would leave the production model permanently unscored on 2025,
  defeating the holdout's purpose, as a penalty for a one-minute race between two agents.
- **The leak, stated honestly:** we now know the 2025 Marcel baselines (H .0305, P .7317) and
  that the *old* tier2 config scored H .0309 / P .7402 with cov80 .81/.75 on 2025. Once the
  locked config is scored, both configs' 2025 results will be known, which is exactly the
  comparison the one-shot rule forbids acting on. **Pre-commitments, therefore:** (1) the
  locked configuration ships regardless of which config looks better on 2025 — the lock was
  made on dev evidence and is not revisited; (2) no modelling decision of any kind changes on
  the misfire numbers; (3) the re-run happens once, and the holdout is spent after it,
  whatever it prints. The dev-side expectation for the legitimate run was already on record in
  STATUS.md before any 2025 number: H wOBA close to or better than Marcel, P FIP worse than
  Marcel, cov80 in [.75, .85] for both.

### Attempt 2 (locked config `--obs-noise --env-mode shock`) — pending

Runs after the state repair (HANDOFF): restore canonical `backtest.json` + sidecars from the
clean E5E6 copies in `m2/`, archive the misfire file. Then `make holdout`, once. Result to be
recorded here exactly as printed.
