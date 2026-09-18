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
- [x] (M2c, UNBLOCKED — locked config is `--obs-noise --env-mode shock`, innov normal, no
  rp-effect; see M2_experiments.md §M2c) `backend/keystone/project.py` — thread the locked
  flags into the production pipeline, mirroring `eval/backtest.fit_stage_draws`:
  `obs_noise=True` → pass to `SS.build_model` (sigma_obs is picked up by `SS.project`
  automatically from the posterior); `env_mode="shock"` → mu_proj from `LG.projection_logit`,
  mu_sd from `LG.projection_logit_recency`'s sigma_env, pass `mu_sd` to `SS.project`. Do NOT
  wire rp_effect or innov t4 (both rejected). Add `project` CLI flags defaulting to the locked
  configuration with opt-outs — ✔ `make project --quick` completes, schema check passes,
  per-stage log shows the flags, waterfall still telescopes (< .001); `make test` green.
  _Opus 2026-09-18: `fit_and_project_stage`/`run` take `obs_noise=True, env_mode="shock"`;
  CLI `--obs-noise/--no-obs-noise`, `--env-mode {shock,mean3}` (recency not offered — rejected).
  Telescoping checked on a 7-stage hitter run (200 players, quick sampling): max |gap| 0._
- [x] (M2c, BEFORE Daniel's `make holdout`) `backend/keystone/pipeline.py` +
  `backend/keystone/eval/backtest.py` — make the locked config the default for `backtest` and
  `holdout`: `--obs-noise` default on (add `--no-obs-noise`), `--env-mode` default `shock`; the
  `holdout` subcommand currently passes no experiment flags to `bt.run`, so today it would score
  2025 with the OLD config — it must run the locked one — ✔ `backtest --quick` with no flags
  writes `experiment_flags: {env_mode: shock, obs_noise: true}` into the JSON; `make test` green.
  _Opus 2026-09-18: also flipped the `backtest.py` function defaults (fit_stage_draws →
  run). `holdout` passes the flags explicitly and refuses if they differ from
  `backtest.json.experiment_flags`, so it can't score a config the gates weren't decided on._
- [x] (M2c, BEFORE Daniel's `make holdout`) promote the locked dev run to canonical:
  copy `data/artifacts/m2/backtest_E5E6.json` → `data/artifacts/backtest.json` and
  `data/artifacts/m2/backtest_{predictions,posteriors}.parquet` (timestamps 14:05, they are the
  E5E6 run's) → `data/artifacts/` — this IS the full dev backtest under the locked config
  (seed 1), so no ~50-min re-run is needed; gates in the file: H FAIL 2/4 cov80 .820,
  P FAIL 1/4 cov80 .761, production_tier marcel/marcel — ✔ `make diagnostics` runs green off
  the promoted sidecars; `/api/meta` serves the new backtest block.
  _Opus 2026-09-18: copies are byte-identical to the m2 files. The superseded post-M1 baseline
  (incl. its pre-M2 tier3 rows) is archived as `m2/backtest_base{,_predictions,_posteriors}.*`._
- [x] (M2c) `frontend/src/pages/Methodology.tsx` + `backend/keystone/project.py` meta writer —
  document the locked model: (a) state-space section gains two sentences: a transient
  season-level noise term (sigma_obs, non-persistent, fitted per stage) separates single-season
  wiggle from talent drift, and projection intervals carry a common league-environment shock
  (sigma_env from year-over-year league-rate volatility); (b) meta.json records
  `model_config: {obs_noise: true, env_mode: "shock"}` and per-stage sigma_obs alongside tau;
  (c) Validation section: coverage now in band for both roles (H .82, P .76), gates still
  Marcel on points, and the M2 story in one paragraph — ✔ `npm run build` passes.
  _Opus 2026-09-18: `StageFit` carries `sigma_obs_mean` + `mu_sd`; meta stages gain
  `sigma_obs_mean` and `sigma_env`, meta gains `model_config` (also in the schema check). The
  Methodology page adds σ_obs/σ_env columns, the obs-noise term in the model equation, and the
  two sentences. Validation now scores dev targets only (the holdout is excluded from the
  averages) and adds the M2 paragraph plus a separate 2025 holdout table with one honest
  sentence: Tier 2 scored slightly below Marcel on both key stats, with cov80 in band. meta.json
  picks the new fields up on Daniel's next `make project`._
  _Opus 2026-09-18 (re-check): Daniel's `make project` finished at 16:19. It started about 15:44,
  before this item's 16:12 commit, so it wrote a pre-item meta.json with no `model_config` and no
  per-stage `sigma_obs_mean`/`sigma_env`. The fits themselves ran the locked config, which was wired
  at 14:54. `sigma_env` can be recomputed (H/hit_bip .0213, H/hr .1129, …), but `sigma_obs` only exists
  in the posterior, so meta can't be backfilled honestly. It needs one more `make project`. The page
  degrades cleanly without the fields: σ columns show "—" and the config line is hidden.
  Methodology's M2 paragraph and the holdout sentence are in place; `npm run build` passes._
- [x] (M2c, URGENT — BEFORE the holdout re-run) repair the canonical state after the
  misconfigured 2025 holdout (M2_experiments.md §"The 2025 holdout"): the 14:53 run raced the
  `handoff: M2c` commit and merged old-config (`mean3`/`obs_noise:false`) 2025 rows into the
  promoted `backtest.json`, stamped its `experiment_flags` over the file, set
  `holdout_target: 2025`, and appended 2025 rows to both sidecars. Repair: (a) move
  `data/artifacts/backtest.json` → `data/artifacts/m2/backtest_holdout_2025_misfire.json`
  (preserve — it is the permanent record of attempt 1); (b) re-copy
  `m2/backtest_E5E6.json` → `data/artifacts/backtest.json` and `m2/backtest_predictions.parquet`
  + `m2/backtest_posteriors.parquet` → `data/artifacts/` (the clean E5E6 copies, targets
  2021–2024 only) — ✔ canonical `backtest.json` has `holdout_target: null`,
  `experiment_flags: {env_mode: shock, obs_noise: true}`, no 2025 rows; sidecars have no 2025
  rows; `make diagnostics` green; `make holdout` then runs WITHOUT `--force` and its printed
  flags header shows the locked config.
  _Opus 2026-09-18: done; restored files are byte-identical to the m2 E5E6 copies. The misfire
  sidecars were archived too rather than overwritten:
  `m2/backtest_holdout_2025_misfire_{predictions,posteriors}.parquet`. Note: `handoff: M2c`
  (22bb1dc, 14:54) had committed the chimera `backtest.json`; this commit restores git as well.
  `make holdout` NOT run (Daniel's one-shot). Its preconditions were checked as plain logic on the
  restored file: gates present, `holdout_target` null, CLI and writer flag checks pass._
- [x] (M2c) guard hardening + regression test for the failure that let attempt 1 through —
  the CLI guard exists but lives only in `cmd_holdout`, so any path that reaches
  `bt.run(holdout=True)` directly (stale code, a script, a future refactor) can still score a
  mismatched config and overwrite the dev file's `experiment_flags`. (a) In
  `backend/keystone/eval/backtest.py` `run()`: when `holdout=True` and `out` exists, read the
  existing JSON's `experiment_flags`; if they differ from this run's
  `{env_mode, rp_effect, innov, obs_noise}`, raise `SystemExit` BEFORE fitting anything and
  before touching the file — the writer must never stamp new flags over a dev file it
  disagrees with. (b) `tests/`: regression test with a tmp-dir `backtest.json` fixture carrying
  `experiment_flags: {env_mode: mean3, ..., obs_noise: false}` + recorded gates: calling
  `run(targets=[2025], holdout=True, out=fixture)` with locked-config defaults raises
  SystemExit and leaves the fixture byte-unchanged; a second test with matching flags proceeds
  past the guard (monkeypatch the fitting to a stub). Also test `cmd_holdout` end-to-end via
  `pipeline.main(["holdout", ...])` on the mismatched fixture → SystemExit — ✔ `make test`
  green; the new tests fail if either guard is removed.
  _Opus 2026-09-18: `_refuse_holdout_flag_mismatch` runs in `run()` before `load_bundle()`, and
  again on the re-read just before `write_json`, because the file can change during a
  25-minute fit. Tests are in `test_m2c_locked_config.py`: the writer refuses on mean3 and
  missing-flag fixtures (file byte-unchanged, nothing loaded or fitted, no sidecars); it
  proceeds when flags match; it re-checks when the file changes mid-fit; and the CLI refuses
  end-to-end through the real `bt.run`. Mutation-checked: removing the writer guard or the CLI
  guard turns tests red. 49 pass._
- [ ] (artifact check B, Opus-filed 2026-09-18, no modelling change) null waterfall steps render as
  0, and dead NaN rows ship in projections — see STATUS Results "Artifact check B". (a)
  `frontend/src/components/Waterfall.tsx`: skip steps whose `value` is null. Don't draw a bar or a
  `.000` value for them, and compute each delta sentence against the last non-null step, so
  Aging → Neutral park reads as one delta instead of −.29/+.29 through a fake Statcast 0. If step 0 is
  null, start the chart at the first non-null step. (b) `backend/keystone/project.py`
  `waterfall_frame`: wrap the step-0 `to_stage_probs`/`derived_stats` call in
  `np.errstate(divide="ignore", invalid="ignore")` so the 0/0 `xbh / h_bip` stays an honest NaN
  without the warning spam. Don't touch the verified `marcel.py`. (c) `project.py` `projections_frame`:
  under marcel-anchor, drop ids whose Marcel stage rates are NaN (the 868 players with no 2024–26
  line, 27,256 all-NaN rows), and have the schema check fail on any non-finite q10..q90/mean — ✔
  `projections.parquet` has 0 non-finite quantile rows; a Judge (592450) page shows no .000 Statcast
  row and no ±.29 sentences; Tony Kemp (643393) renders without a .000 3-year line; `make test`
  green; `npm run build` passes. The `make project` re-run that acceptance needs can be the same
  one that fills meta.json's `model_config`/`sigma_obs_mean`.
- [ ] (M2b) `backend/keystone/eval/backtest.py` — sidecar filenames collide across experiment
  runs: `run()` writes `backtest_predictions{_quick}.parquet` / `backtest_posteriors{_quick}.parquet`
  into `out.parent`, so consecutive `--out ../data/artifacts/m2/backtest_E*.json` runs overwrite
  each other's sidecars (E2's were lost when E4 ran; it cost M2b one pre-registered sub-check).
  When `out` is not the default `backtest{_quick}.json`, derive the sidecar names from the out
  stem (e.g. `backtest_E5_predictions.parquet`) — ✔ two consecutive `--quick` runs with different
  `--out` names leave both sidecar pairs on disk; `make backtest-quick` still writes the
  default names so `make diagnostics` keeps working.

- [ ] (M3, Fable-filed 2026-09-18) Wire the playing-time hurdle into artifacts. `backend/keystone/project.py`:
  in `run()`, per role, build `PT.training_table(b.ps[role], role, projection_season)` and
  `PT.fit_pt` (module `keystone.models.playing_time`; seconds per fit, seed from the CLI seed),
  then `PT.build_pt_table(b.ps[role], role, projection_season)` on the projection population and
  `PT.simulate_horizons(fit, table, horizons=4)`. Join per (mlbam_id, horizon) onto
  `projections.parquet` as three new columns: `p_play`, `pt_expected`, `p_regular`
  (REGULAR_PT = 300 PA / 100 IP). Keep the existing `pt` column (Marcel, h=1) untouched for
  compatibility; leaderboard keeps using it. Players in projections but outside the PT population
  (no PT in the last two seasons) get NaN in the new columns — ✔ `make project` writes the columns;
  for a healthy regular (Judge 592450) h1 `p_play` > .95 and `pt_expected` within ±15% of Marcel `pt`;
  for an age-36 <150-PA player `pt_expected` < 100 at h1 and declines with h; `assert_schema` updated;
  `make test` green.
- [ ] (M3) Surface expected production in the API + UI. `api/main.py`: include the three columns in
  the player payload per horizon. Frontend `AgingOutlook` (or the multi-year section): show two
  lines per horizon — "if he plays" (existing conditional stats) and "expected" (counting stats
  scaled by `pt_expected`; rate stats unchanged, labelled with `p_play`), plus a
  "chance still an MLB regular" chip from `p_regular` at h=4. Copy for the Methodology page:
  (a) expected = p(plays) × conditional, independence assumption stated; (b) beyond year 1 the
  intervals are model-implied, not backtested; (c) PT hurdle beat Marcel PT on RMSE 8/8 dev
  targets (H −25%, P −11%, bias +126→+3 PA, +22→+1 IP), table in docs/fable/M3_playing_time.md —
  ✔ a fringe veteran's page shows expected ≪ conditional counting stats; `npm run build` passes.
- [ ] (M3) CLI + backtest hook (small): add `keystone.pipeline` subcommand `pt-backtest` running
  `PT.backtest_pt(b.ps, C.DEV_TARGETS)` and printing the table (no JSON artifact needed) — ✔ command
  runs end-to-end in ≲3 min and matches docs/fable/M3_playing_time.md §3 numbers at seed 1.
