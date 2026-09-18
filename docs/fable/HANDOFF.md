# Fable → Opus handoff queue

Format: `- [ ] (M<n>) <file(s)> — <exact change> — ✔ <acceptance check>`
Opus: implement unchecked items in order, tick them, commit `handoff: M<n>`. Don't change modelling decisions.

- [x] (M1) `backend/keystone/eval/backtest.py` — persist a per-run sidecar next to backtest.json:
  `backtest_predictions.parquet` (target, role, tier, mlbam_id, stat, pred_mean, q10, q50, q90) and
  `backtest_posteriors.parquet` (target, role, tier, stage, tau_mean, tau_sd, sigma_pop_mean,
  sigma_pop_sd, lam_mean, lam_sd, sigma_age_mean, sigma_age_sd, park_sd_mean, park_sd_sd,
  ess_bulk_min, max_rhat, divergences). Write in `run_target`/`fit_stage_draws` where draws and
  idata already exist; `--quick` writes `*_quick` variants — ✔ after `make backtest`,
  `make diagnostics` fills the Tier 2/3 columns of residuals_by_bucket / pit_histograms /
  biggest_misses / posterior_summaries without schema changes.
- [x] (M1) `backend/keystone/diagnostics.py` — read the sidecar when present and emit Tier 2/3 rows
  in residuals_by_bucket.csv, pit_histograms.csv (real posterior-predictive PIT), biggest_misses.csv,
  posterior_summaries.csv — ✔ `make diagnostics` runs green with and without the sidecar on disk.
- [x] (M1, only if a tier2 gate flips to PASS after the re-run) `backend/keystone/project.py` —
  thread park exposure into the production projection the same way the backtest now scores it:
  build `park_exposure_map(exposures, window_end)` (import from eval.backtest or move to
  state_space) and pass it to `SS.project` for PARK_STAGES, so shipped points match the validated
  configuration — ✔ a Coors hitter's hr_pct q50 > his park-neutral value; waterfall still telescopes.
  _Opus 2026-09-17: wired ahead of the re-run at Daniel's direction (no-op under the current
  marcel-anchor). Coors-hitter acceptance is inherently gated on tier2 shipping mode and will
  fire the first time gates flip; the mechanic is observable in `project`'s per-stage log line._
- [x] (M1) `frontend/src/pages/Methodology.tsx` (Validation section) — one sentence: backtest
  scoring is park-aware as of M1 (Tier 2/3 projections evaluated in the player's last-season park,
  matching the park information Marcel carries implicitly); note `backtest.json.park_aware_scoring`
  — ✔ `npm run build` passes.
- [ ] (M2a, BLOCKED until M2c locks the config — M2b 2026-09-18 rejected E2 and E4 as bundles,
  E3 unjudged pending its rerun, E5/E6 pending full runs) `backend/keystone/project.py` —
  thread whichever flags survive into the production pipeline, mirroring
  `eval/backtest.fit_stage_draws`. Candidates now: `rp_effect` → merge `_rp_share` into the P obs
  frame (fillna + centring identical to backtest) and pass `role_x`/`use_role`;
  `obs_noise` (E5) → pass to `SS.build_model` (sigma_obs is picked up by `SS.project`
  automatically from the posterior); `env_mode="shock"` (E6) → mu_proj from
  `LG.projection_logit`, mu_sd from `LG.projection_logit_recency`'s sigma_env, pass `mu_sd` to
  `SS.project`; `innov="t4"` only if M2c adopts it for geometry. Add matching `project` CLI flags
  defaulting to the accepted configuration — ✔ `make project --quick` completes, schema check
  passes, and per-stage log shows the flags; `make test` green.
- [ ] (M2b) `backend/keystone/eval/backtest.py` — sidecar filenames collide across experiment
  runs: `run()` writes `backtest_predictions{_quick}.parquet` / `backtest_posteriors{_quick}.parquet`
  into `out.parent`, so consecutive `--out ../data/artifacts/m2/backtest_E*.json` runs overwrite
  each other's sidecars (E2's were lost when E4 ran; it cost M2b one pre-registered sub-check).
  When `out` is not the default `backtest{_quick}.json`, derive the sidecar names from the out
  stem (e.g. `backtest_E5_predictions.parquet`) — ✔ two consecutive `--quick` runs with different
  `--out` names leave both sidecar pairs on disk; `make backtest-quick` still writes the
  default names so `make diagnostics` keeps working.

