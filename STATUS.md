# KEYSTONE — STATUS

## Stage A — Opus builds (MANUAL.md §10)
- [x] P0 Setup (Daniel): `make setup`, `make test` (7 pass), fg_guts.csv saved, git init
- [x] P1 Data layer
- [x] P2 Backtest harness (Tier 1 + 2)
- [ ] P3 Production artifacts
- [ ] P4 API
- [ ] P5 Frontend (+ screenshots in docs/screenshots/)
- [ ] P6 Statcast data + Tier 3 plumbing
- [ ] P6.5 Fable context pack (`make diagnostics`)

## Stage B — Fable missions (FABLE_MISSIONS.md)
- [ ] M1 Statistical red team ($15) → Opus wires handoff → Daniel re-runs → `make diagnostics`
- [ ] M2a Model research: diagnose + build ($22) → Daniel full backtests
- [ ] M2b Judge + iterate + holdout ($18) → Opus wires → `make project diagnostics`
- [ ] M3 Playing time + attrition ($15, first to cut) → Opus wires
- [ ] M4 Research memo ($20) → Opus: Methodology page + README (P7) → screenshots
- [ ] M5 Hiring-manager review + interview prep ($10) → Opus fixes

## Stage C — Opus final polish
- [ ] Handoff queue empty · `make test` + `npm run build` pass · re-run after the 2026 season ends

## Fable ledger (Daniel fills in after every Fable session)
| session | budget | actual | running total (cap $100, reserve $10) |
|---|---|---|---|

## Next command(s) for Daniel
- `make test`      # should now be 11 tests (7 existing + 4 new leakage tests, ~35 s)
- `make backtest`  # 4 targets x 2 roles x 12 stages = 48 fits. Estimated 60-110 min on the Air.
  Leave it running; it prints a progress line per fit. Watch for `<-- CHECK` (r_hat > 1.05).
- Paste the final summary table + the `gates` lines into "Results" below.
- Then: Opus session for P3 (production artifacts). Do NOT run `make holdout` yet — the pipeline
  refuses it until dev gates exist, and MANUAL §6 spends it only once.

## Results (paste summaries here, ≤ 30 lines each)

### P1 data layer — full `make data` (Daniel, 2026-09-17)
- fetch 2015–2026 OK. Per-season H/P/bios counts all present; traded-player splits pulled.
- PA sanity vs team totals: 0.0000% every season except 2026 (0.0006%, 1 PA, season in progress).
- Modelled population: H 573–685/season, P 709–850/season. All gates OK.
- Pre-2022 hitter row counts are ~1,250 vs ~770 after: that is the universal DH arriving in 2022
  (NL pitchers stop batting). Modelled counts are stable across the break, so the filter works.
- 10 processed parquet files written.

### P2 backtest harness — agent smoke tests (2026-09-17, cloud container, 2 cores)
`make backtest-quick` (2024, hitters, stages k+hr, 150 draws): **59 s**, 0 divergences,
`backtest_quick.json` valid. Full-path checks at the same reduced sampling, both roles:

    role stat           n  marcel   tier2    last  league  cov50  cov80
    H    woba         348 0.0337  0.0348  0.0478  0.0372   0.45   0.75
    H    babip        348 0.0338  0.0315  0.0547  0.0337   0.51   0.77
    H    k_pct        348 0.0349  0.0341  0.0400  0.0587   0.56   0.82
    H    hr_pct       348 0.0110  0.0131  0.0151  0.0142   0.48   0.76
    P    fip          332 0.7356  0.7619  1.0308  0.8008   0.43   0.74
    P    babip        332 0.0340  0.0331  0.0521  0.0338   0.46   0.77
    P    hr_pct       332 0.0098  0.0096  0.0147  0.0102   0.55   0.84

**These are not results** — 150 draws, one target, r_hat 1.05–1.67. They say the harness runs and
is calibrated (cov80 0.74–0.84 at nominal 0.80). `make backtest` produces the real numbers.

Correctness checks that do stand:
- The stage chain reproduces the FanGraphs wOBA formula and FIP to machine precision
  (max |diff| 1.7e-16 and 8.9e-16 over all 2024 players) — actual, projected and simulated
  stats all come from one function.
- PA-weighted wOBA over all 649 modelled 2024 hitters = **.3102** (MLB 2024 league wOBA .310).
  Judge .4758, Soto .4206, Alvarez .4016.
- 4 leakage tests pass, including an end-to-end one: season-T counts rewritten (every player
  handed another player's line, league K collapsed to 2% of PA) changes no projection at all.

## Gates / production tier
- Hitters: TBD · Pitchers: TBD  (computed automatically into `backtest.json` by `make backtest`)

## Decisions (one line each: date — decision — why)
- 2026-09-17 — Reference model verified on simulated data (0 divergences, 80% coverage 0.83) — MANUAL §5.3
- 2026-09-17 — Opus builds all phases; Fable is reserved for M1–M5 research missions — FABLE_MISSIONS.md §1
- 2026-09-17 — P1: season totals use bulk /stats (no teamId); per-team splits pulled from /people/{id}/stats only for numTeams>1 — the teamId-filtered /stats undercounts (Chisholm 2024: 191 PA only, missed 430 MIA); MANUAL §4.1 now updated to match.
- 2026-09-17 — `league_{H,P}.parquet` = stage_league_rates (modelled pop) joined with sf_rate (H) / kappa+lg_era+c_fip on all pitchers unfiltered (P). Guts stored raw as `guts.parquet`; the "latest available row" fallback for missing seasons happens at lookup time in downstream code.
- 2026-09-17 — P2: eval population reads MANUAL §6's "PA'/BF' ≥ 1 in T−3…T−1" as **some** history in that window, not a PA in each of the three seasons — requiring all three would drop every young player and bias the sample to veterans.
- 2026-09-17 — P2: FIP (actual, projected and simulated alike) is computed from the rate components over each player's **actual IP**. MANUAL §6 requires it for the simulations; using it everywhere keeps RMSE comparing like with like instead of mixing in IP-conversion error. kappa is still used for the component rates and in Phase 3 artifacts.
- 2026-09-17 — P2: the Tier 2 gate's coverage test uses the **key stat's** mean cov80 (wOBA / FIP), the subject of the §6 sentence. The printed table also shows mean cov50/cov80 across all stats.
- 2026-09-17 — P2: `--quick` writes `backtest_quick.json`, not `backtest.json`, so a smoke test can never overwrite real backtest results. Same schema, same writer.
- 2026-09-17 — P2: when only some stages are fitted (`--quick`), the tier rows report **stage probabilities** (`stage_k`, `stage_hr`) instead of derived stats, since wOBA/FIP need every stage. Marcel and the baselines still report full derived stats in that mode.
- 2026-09-17 — P2: `pa_prime` moved into `components.py` (additive; `build.py` now delegates to it) so the backtest and the data layer share one definition of PA'.
- 2026-09-17 — P2: `make holdout` refuses to run unless `backtest.json` exists with gates recorded, and refuses a second run without `--force`. MANUAL §6 spends the holdout once.

## Questions for Fable M1 (statistical red team) — do not change these unilaterally
1. **Park-neutral projections scored against park-influenced actuals.** MANUAL §5.3 makes Tier 2
   projections park-neutral, but §6 scores them against what the player actually did in his real
   park. Marcel is park-blind too, but it inherits parks implicitly through the player's raw past
   rates, so it is not penalised the same way. In the smoke test Tier 2 loses to Marcel on exactly
   the two most park-sensitive stats (hr_pct .0131 vs .0110, wOBA .0348 vs .0337) while winning on
   the least park-sensitive (babip .0315 vs .0338, k_pct .0341 vs .0349). `state_space.project`
   already accepts `park_exposure`, so scoring the park-aware projection is a small change — but it
   is a modelling decision, so it waits for M1. Confirm or reject with the full backtest in hand.
2. **r_hat at production sampling.** At 150 draws the population parameters reach r_hat 1.05–1.67
   (worst: H `xbh` 1.41, P `hbp` 1.67 — both low-signal stages). The dev setting is 500/500, and
   the fit now prints `<-- CHECK` above 1.05. If the full run still shows r_hat > 1.05 on those
   stages, that is a reparameterisation question, not a tuning one.
3. **Marcel projects the 200-PA population ~.012 wOBA high** (mean projected .3231 vs actual
   .3109). Partly the missing rebaselining step (§5.2 documents it) against a 2021–23 environment
   that was hotter than 2024, partly selection: a player with a good 2021–23 who only reached
   200–400 PA in 2024 is usually one who declined. Worth a paragraph in the memo either way.

## Blockers
- none
