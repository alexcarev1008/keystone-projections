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
- [ ] (M1, only if a tier2 gate flips to PASS after the re-run) `backend/keystone/project.py` —
  thread park exposure into the production projection the same way the backtest now scores it:
  build `park_exposure_map(exposures, window_end)` (import from eval.backtest or move to
  state_space) and pass it to `SS.project` for PARK_STAGES, so shipped points match the validated
  configuration — ✔ a Coors hitter's hr_pct q50 > his park-neutral value; waterfall still telescopes.
  _Deferred by Opus 2026-09-17: trigger condition (tier2 gate PASS) requires Daniel's re-run of
  `make backtest` + `make backtest TIER=3` first. Asked in STATUS.md._
- [x] (M1) `frontend/src/pages/Methodology.tsx` (Validation section) — one sentence: backtest
  scoring is park-aware as of M1 (Tier 2/3 projections evaluated in the player's last-season park,
  matching the park information Marcel carries implicitly); note `backtest.json.park_aware_scoring`
  — ✔ `npm run build` passes.

