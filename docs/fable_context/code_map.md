# code_map — one line per backend file

generated: 2026-09-18T20:19:56+00:00

- `keystone/__init__.py` — (no docstring)
- `keystone/api/__init__.py` — (no docstring)
- `keystone/api/main.py` — FastAPI read-only server for KEYSTONE artifacts (MANUAL.md §8).  (key: State, create_app(), health(), meta(), search(), leaderboard())
- `keystone/components.py` — Component ("stage") definitions and deterministic derivations.  (key: pa_prime(), stage_counts(), per_pa_from_stage_rates(), derive_hitter(), derive_pitcher(), simulate_season())
- `keystone/config.py` — Seasons, paths, and constants that everything else imports (MANUAL.md §4, §5).  (key: ensure_dirs())
- `keystone/data/__init__.py` — (no docstring)
- `keystone/data/build.py` — Processed tables (MANUAL.md §4.3): parquet outputs under data/processed/.  (key: build_all())
- `keystone/data/mlb_api.py` — MLB Stats API client with on-disk cache.  (key: teams(), player_season_stats(), player_team_splits(), team_totals(), people(), season_age())
- `keystone/data/statcast.py` — Statcast contact-quality indicators (MANUAL.md §4.1 last row, §5.4).  (key: fetch_seasons(), build_processed(), load_indicator())
- `keystone/diagnostics.py` — Phase 6.5 — Fable context pack (FABLE_MISSIONS.md §3).  (key: build_backtest_summary(), build_posterior_summaries(), build_aging_curves(), build_park_effects(), MarcelRun, build_residuals_by_bucket())
- `keystone/eval/__init__.py` — (no docstring)
- `keystone/eval/backtest.py` — Rolling-origin backtest: Tier 1 (Marcel) vs Tier 2/3 (state-space). MANUAL.md §6.  (key: Bundle, load_bundle(), rd(), train_slice(), cut(), scoring_env())
- `keystone/league.py` — League-season constants. VERIFIED REFERENCE (tests: backend/tests/test_league.py).  (key: stage_league_rates(), hitter_constants(), pitcher_constants(), projection_logit(), projection_logit_recency())
- `keystone/models/__init__.py` — (no docstring)
- `keystone/models/marcel.py` — Tier 1 baseline: Marcel (Tom Tango), applied to per-PA' events.  (key: events_table(), to_stage_probs(), marcel(), marcel_playing_time())
- `keystone/models/state_space.py` — Tier 2/3 model: Bayesian state-space ("random-walk talent") model for ONE binomial stage.  (key: StageData, build_stage_data(), build_model(), fit(), project())
- `keystone/pipeline.py` — KEYSTONE CLI. Subcommands: fetch, build (P1) · backtest, holdout (P2) · project (P3) · statcast (P6).  (key: cmd_fetch(), cmd_build(), cmd_backtest(), cmd_project(), cmd_statcast(), cmd_diagnostics())
- `keystone/project.py` — Production artifacts (MANUAL.md §7): writes the parquet + meta.json set the API serves.  (key: latest_env(), row(), derived_stats(), StageFit, fit_and_project_stage(), projections_frame())
