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
- [ ] (M2c, UNBLOCKED — locked config is `--obs-noise --env-mode shock`, innov normal, no
  rp-effect; see M2_experiments.md §M2c) `backend/keystone/project.py` — thread the locked
  flags into the production pipeline, mirroring `eval/backtest.fit_stage_draws`:
  `obs_noise=True` → pass to `SS.build_model` (sigma_obs is picked up by `SS.project`
  automatically from the posterior); `env_mode="shock"` → mu_proj from `LG.projection_logit`,
  mu_sd from `LG.projection_logit_recency`'s sigma_env, pass `mu_sd` to `SS.project`. Do NOT
  wire rp_effect or innov t4 (both rejected). Add `project` CLI flags defaulting to the locked
  configuration with opt-outs — ✔ `make project --quick` completes, schema check passes,
  per-stage log shows the flags, waterfall still telescopes (< .001); `make test` green.
- [ ] (M2c, BEFORE Daniel's `make holdout`) `backend/keystone/pipeline.py` +
  `backend/keystone/eval/backtest.py` — make the locked config the default for `backtest` and
  `holdout`: `--obs-noise` default on (add `--no-obs-noise`), `--env-mode` default `shock`; the
  `holdout` subcommand currently passes no experiment flags to `bt.run`, so today it would score
  2025 with the OLD config — it must run the locked one — ✔ `backtest --quick` with no flags
  writes `experiment_flags: {env_mode: shock, obs_noise: true}` into the JSON; `make test` green.
- [ ] (M2c, BEFORE Daniel's `make holdout`) promote the locked dev run to canonical:
  copy `data/artifacts/m2/backtest_E5E6.json` → `data/artifacts/backtest.json` and
  `data/artifacts/m2/backtest_{predictions,posteriors}.parquet` (timestamps 14:05, they are the
  E5E6 run's) → `data/artifacts/` — this IS the full dev backtest under the locked config
  (seed 1), so no ~50-min re-run is needed; gates in the file: H FAIL 2/4 cov80 .820,
  P FAIL 1/4 cov80 .761, production_tier marcel/marcel — ✔ `make diagnostics` runs green off
  the promoted sidecars; `/api/meta` serves the new backtest block.
- [ ] (M2c) `frontend/src/pages/Methodology.tsx` + `backend/keystone/project.py` meta writer —
  document the locked model: (a) state-space section gains two sentences: a transient
  season-level noise term (sigma_obs, non-persistent, fitted per stage) separates single-season
  wiggle from talent drift, and projection intervals carry a common league-environment shock
  (sigma_env from year-over-year league-rate volatility); (b) meta.json records
  `model_config: {obs_noise: true, env_mode: "shock"}` and per-stage sigma_obs alongside tau;
  (c) Validation section: coverage now in band for both roles (H .82, P .76), gates still
  Marcel on points, and the M2 story in one paragraph — ✔ `npm run build` passes.
- [ ] (M2b) `backend/keystone/eval/backtest.py` — sidecar filenames collide across experiment
  runs: `run()` writes `backtest_predictions{_quick}.parquet` / `backtest_posteriors{_quick}.parquet`
  into `out.parent`, so consecutive `--out ../data/artifacts/m2/backtest_E*.json` runs overwrite
  each other's sidecars (E2's were lost when E4 ran; it cost M2b one pre-registered sub-check).
  When `out` is not the default `backtest{_quick}.json`, derive the sidecar names from the out
  stem (e.g. `backtest_E5_predictions.parquet`) — ✔ two consecutive `--quick` runs with different
  `--out` names leave both sidecar pairs on disk; `make backtest-quick` still writes the
  default names so `make diagnostics` keeps working.

