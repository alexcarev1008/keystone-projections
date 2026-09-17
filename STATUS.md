# KEYSTONE — STATUS

## Stage A — Opus builds (MANUAL.md §10)
- [x] P0 Setup (Daniel): `make setup`, `make test` (7 pass), fg_guts.csv saved, git init
- [x] P1 Data layer
- [x] P2 Backtest harness (Tier 1 + 2)
- [x] P3 Production artifacts
- [x] P4 API
- [ ] P5 Frontend (+ screenshots in docs/screenshots/)
- [x] P6 Statcast data + Tier 3 plumbing
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
- Next Opus session: **P5 (Frontend)** — Vite + React + Recharts against the live API. Also
  outstanding: P6.5 (Fable context pack). No long jobs to run before either.
- Backlog long jobs (any order, when convenient):
  - `make statcast` (long, first fetch of the Savant leaderboards 2015–2026;
    pybaseball hits savant, agent doesn't). Writes `data/raw/statcast/{H,P}_{year}.parquet`
    + `data/processed/statcast_{H,P}.parquet` (mlbam_id, season, attempts, barrels, ev95plus).
  - `make backtest TIER=3`. Fits the 3 §5.4 stages (H/hr, H/hit_bip, P/hr)
    with the Statcast indicator likelihood at target_accept 0.95; all other stages stay Tier 2.
    Merges new rows into `data/artifacts/backtest.json` without erasing the Tier 2 rows;
    `production_tier` recomputes for both roles from the combined table.
- P6.5 kickoff prompt must remind the agent that CONTEXT.md leads with the three open
  findings from Phase 2 + the M1 note:
  (1) hitter HR% (Tier 2 .0155 vs Marcel .0124, cov80 .71),
  (2) H/hit_bip divergence concentration (181 of 313),
  (3) park-neutral scoring question in the M1 notes below.
- **Still do NOT run `make holdout`.** Stage B M2b spends it after Fable iterates the model.

## Results (paste summaries here, ≤ 30 lines each)

### P1 data layer — full `make data` (Daniel, 2026-09-17)
- fetch 2015–2026 OK. Per-season H/P/bios counts all present; traded-player splits pulled.
- PA sanity vs team totals: 0.0000% every season except 2026 (0.0006%, 1 PA, season in progress).
- Modelled population: H 573–685/season, P 709–850/season. All gates OK.
- Pre-2022 hitter row counts are ~1,250 vs ~770 after: that is the universal DH arriving in 2022
  (NL pitchers stop batting). Modelled counts are stable across the break, so the filter works.
- 10 processed parquet files written.

### P2 harness correctness (agent, 2026-09-17, cloud container)
`make backtest-quick` equivalent: **59 s**, 0 divergences, valid JSON. Checks that stand
independently of any model result:
- The stage chain reproduces the FanGraphs wOBA formula and FIP to machine precision
  (max |diff| 1.7e-16 and 8.9e-16 over all 2024 players). Actual, projected and simulated stats
  all come from one function, so no tier is scored on a different formula than another.
- PA-weighted wOBA over all 649 modelled 2024 hitters = **.3102** (MLB 2024 league wOBA .310).
  Judge .4758, Soto .4206, Alvarez .4016.
- 11 tests pass (7 existing + 4 leakage), including an end-to-end one: season-T counts rewritten
  (every player handed another player's line, league K collapsed to 2% of PA) changes no
  projection at all.

### P2 full dev backtest — `make backtest` (Daniel, 2026-09-17, ~50 min, 500 draws × 2 chains)
PA-weighted RMSE, mean over targets 2021–2024. n = 322–348 hitters / 325–334 pitchers per target.
cov50/cov80 are Tier 2's interval coverage (nominal .50 / .80).

    HITTERS   marcel   tier2    last  league   cov50 cov80
    k_pct     0.0363  0.0350  0.0468  0.0593    0.52  0.83
    bb_pct    0.0199  0.0204  0.0284  0.0282    0.52  0.79
    hr_pct    0.0124  0.0155  0.0169  0.0157    0.42  0.71
    babip     0.0332  0.0318  0.0605  0.0353    0.51  0.80
    woba      0.0334  0.0364  0.0520  0.0371    0.46  0.76

    PITCHERS  marcel   tier2    last  league   cov50 cov80
    k_pct     0.0400  0.0397  0.0518  0.0526    0.57  0.82
    bb_pct    0.0206  0.0220  0.0344  0.0247    0.49  0.78
    hr_pct    0.0109  0.0107  0.0191  0.0113    0.49  0.77
    babip     0.0334  0.0326  0.0613  0.0329    0.47  0.77
    fip       0.7947  0.8196  1.3123  0.8732    0.44  0.73

Per-target key stat (marcel / tier2):
    wOBA  2021 .0336/.0358   2022 .0358/.0415   2023 .0304/.0333   2024 .0337/.0350   (Marcel 4/4)
    FIP   2021 .783/.808     2022 .821/.885     2023 .839/.823*    2024 .736/.763     (Marcel 3/4)
    (* the only Tier 2 win on either key stat)

What the components say, which the headline hides:
- Tier 2 **wins where shrinkage is the whole job**: K% both roles, BABIP both roles, pitcher HR%.
  It loses on BB% (both) and, badly, on **hitter HR%: .0155 vs .0124, 25% worse**.
- wHR is 2.05, the largest wOBA weight, so the hitter HR stage alone plausibly accounts for the
  wOBA gap. Hitter HR% also has the **worst calibration of any stat (cov80 .71)** — intervals too
  narrow *and* the point off, which reads as mis-specification rather than mere over-shrinkage.
- **DIPS falls out of the validation, not just the model.** Pitcher BABIP: league average .0329
  BEATS Marcel .0334; "last season" is catastrophic at .0613; Tier 2 is best at .0326. Hitter
  BABIP: league .0353 vs last-season .0605. Pitchers barely own their BABIP; hitters partly do.
- **Interval calibration is Tier 2's real win**: cov80 .71–.83 against a nominal .80 across ten
  role/stat combinations, cov50 .42–.57 against .50. Marcel produces no intervals at all.

Sampler health, and it is not clean: **313 divergences over 48 fits**, **19 of 48 fits above
r_hat 1.05**. Concentrated, not diffuse:

    role/stage    divergences (4 fits)   max r_hat
    H/hit_bip                    181         1.231
    H/bb                          47         1.061
    P/hit_bip                     29         1.133
    H/hr                          20         1.058
    P/bb                          20         1.045
    all others                    ≤3          ≤1.202  (H/triple 1.231 with 0 divergences)

H/hit_bip alone is 58% of all divergences. The verified simulation had 0 at this scale, so this is
real-data structure the parameterisation does not absorb.

### P3 production pipeline — agent smoke test (2026-09-17, `project --quick`)
`--quick` fits hitters, 200 players, stages k+hr, 150 draws × 2 chains — writes every artifact
into `data/artifacts/_quick/` so a real `make project` is never overwritten.
- Runtime: ~40 s per stage, ~1.5 min total (well under the 5-min agent budget).
- Schema check passes for all 6 parquet files + meta.json (columns per §7).
- Fit r_hat 1.14 / 1.17 at quick sampling — expected; production uses 500 draws × 4 chains.
- `projections.parquet` emits `stage_k` and `stage_hr` rows in partial mode (like backtest quick);
  the full run emits derived stats (k_pct, bb_pct, hr_pct, babip, avg, obp, slg, iso, woba for H;
  k_pct, bb_pct, hr_pct, babip, k_minus_bb, fip, era for P).
- 11 tests still pass.

### P6 Statcast + Tier 3 plumbing — agent (2026-09-17, code only)
- `data/statcast.py`: `fetch_seasons` (pybaseball `statcast_{batter,pitcher}_exitvelo_barrels`,
  `minBBE=1`), caches to `data/raw/statcast/{role}_{year}.parquet`; `build_processed` writes
  `statcast_{H,P}.parquet` with columns (mlbam_id, season, attempts, barrels, ev95plus).
  `load_indicator(role, stage)` maps the three §5.4 stages via `INDICATOR_MAP` and returns
  (mlbam_id, season, ind_y, ind_n) with `ind_n > 0`; other stages return `None`, so the fitter
  falls back to Tier 2 for them automatically.
- `pipeline.py statcast --start --end` wired; Makefile target `make statcast` already existed.
- `backtest.tier3_indicators(role, stages, target)` strips seasons ≥ target from every indicator
  (no leakage into the Statcast likelihood) and hands them to `tier_draws`.
- `project.py`: `fit_and_project_stage` now accepts an indicator; `--tier 3` overrides
  `production_tier` to tier3 for all roles and feeds indicators to the three mapped stages.
- Model plumbing already in place (verified reference): `state_space.build_model(...,
  use_indicator=True)` adds a_ind/b_ind/nu + a second Binomial, fit at target_accept 0.95.
- Tests: 4 new in `test_statcast_tier3.py` (indicator column map, drop rows with zero denom,
  target-season strip, model wires `a_ind`/`b_ind`/`ind` when use_indicator=True).
  Full suite: **15 passed** in ~14 s.
- No Statcast download run; no Tier 3 backtest run. Both are Daniel jobs listed above.

### P4 API — agent (2026-09-17, code only)
FastAPI in `backend/keystone/api/main.py` loads all 6 parquet files + meta.json + backtest.json
at startup into an in-memory `State`; no model code imported. `create_app(artifacts_dir)` is a
factory so tests point at fixture dirs. CORS allows `http://localhost:5173` only.

- `/api/health` → `{"status":"ok"}`.
- `/api/meta` → `{"meta": <meta.json>, "backtest": <backtest.json>}`.
- `/api/search?q=&limit=` → case- and accent-insensitive substring match (`unicodedata.NFKD`
  with combining marks stripped); empty q returns `[]`.
- `/api/leaderboard?role={H,P}&sort=&order=&min_pt=&limit=`. Defaults per §8: H sort=woba desc
  min_pt=300; P sort=fip asc min_pt=50. Key stats are `[woba, k_pct, bb_pct, hr_pct, babip]`
  for H / `[fip, k_pct, bb_pct, hr_pct, babip]` for P — each returns `{q10, q50, q90}` at h=1.
- `/api/players/{id}?role=` → `{bio, role, history, projections:{stat:[…]}, pt, waterfall,
  aging:{stat:[…]}, league:{stat:value}}`. Default role = "H" if the player has one, else "P".
  404 when the id is unknown OR when the requested role doesn't apply to that player.

Tests: `tests/test_api.py` (14 tests) builds a small fixture set (a hitter, a pitcher, a
two-way, and a projection-less player). It covers every endpoint, both leaderboard sort
directions, min_pt filter, empty-query search, accent folding, two-way role toggle, and 404
paths. Full suite: **29 passed** in ~17 s. Live smoke against `data/artifacts/`: `curl
/api/players/665742?role=H` returns the full shape; `/api/leaderboard?role=P` returns
`[Mason Miller, Cade Smith, Skubal]` (fip q50 2.59/2.82/2.86). Uvicorn came up on the first
try, no import warnings.

`httpx2>=2.13` added to `requirements.txt` — Starlette's TestClient needs it on Python 3.14.

### P3 full `make project` (Daniel, 2026-09-17, ~35 min, 4 chains × 500 draws over 12 fits)
- 2,936 players projected × 4 horizons × 9 stats (H) / 7 stats (P) = 92,324 rows.
- Schema check passes for all 6 parquet files + meta.json.
- Spot-check winners: three well-known hitters' 2027 wOBA looks like their skill:
  Judge 0.417 [.389, .449], Soto 0.390 [.362, .420], Alvarez 0.388 [.365, .416].
- Waterfall telescoping max |gap| = 0.0000 (target < .001) ✓.

**Two spot checks miss their spec targets, and both are real model findings, not code bugs:**
1. **Bands widen h1→h4 in 42.5% of H (wOBA) / 60.1% of P (FIP) — target > 95%.** Cause: several
   stages fit tau ≈ 0.02: `hit_bip` H .017 / P .026, `xbh` .022, `hr` P .055. `var(theta_h) =
   var(theta_we) + h·tau²`, so tiny tau ⇒ h=4 spread ≈ h=1 spread for the stages BABIP + XBH drive.
   FIP widens more than wOBA because its variance is dominated by the high-tau HR stage.
2. **max r_hat 1.11 (target < 1.05); 97 divergences.** Worst r_hat: P/k 1.111, P/hr 1.104,
   H/hbp 1.070. This is milder than the P2 backtest fits (up to 1.23) — 4 chains × 500 draws
   is enough for the population parameters to converge on all but two stages.

Real modeling findings this run surfaces (write in the Methodology page):
- **DIPS falls out of the fit.** P/hit_bip sigma_pop = 0.048 vs H/hit_bip 0.092 — pitcher BABIP
  talent spread is about half of hitters'. Combined with tiny P/hit_bip tau, pitcher BABIP is a
  near-constant per player.
- **Aging is largest on power (H/hr sigma_age contribution) and smallest on BABIP** — matches
  the received wisdom.
- **Park effects, park_sd (posterior mean):** H/hr 0.351 (largest, ~35% logit swing between
  extremes), H/xbh 0.092, H/hit_bip 0.058, H/triple 0.257. Pitcher park effects are smaller
  because a pitcher's home games are half the total. Top/bottom 3 HR parks are in `meta.json`.

## Gates / production tier (from `data/artifacts/backtest.json`, 2026-09-17)
- **Hitters: Marcel** — Tier 2 fails: 0/4 targets beat Marcel on wOBA RMSE (need 3).
  cov80 mean .759 ✓ in [0.75, 0.85], so hitters fail on accuracy only, not calibration.
- **Pitchers: Marcel** — Tier 2 fails: 1/4 targets (2023 only) beat Marcel on FIP RMSE.
  cov80 mean .726 ✗ below .75, so pitchers fail on both criteria; FIP intervals are a shade narrow.
- Per MANUAL §6, production ships **Marcel points with Tier 2 bands**, and the Methodology page
  must say so plainly.
- Tier 3 not evaluated yet (Phase 6 regenerates gates with `--tier 3`).
- Holdout 2025: **unspent**, deliberately (see Decisions).

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
- 2026-09-17 — P2 result: Tier 2 fails both gates on the dev targets, so production is Marcel points + Tier 2 bands per §6. Recorded as measured — no tuning, no re-running with different settings.
- 2026-09-17 — The 2025 holdout stays **unspent** until after Fable M2b. §10 P2 permits it now, but M2a/M2b will change the model, and a one-shot holdout scored against a superseded model is wasted.
- 2026-09-17 — P3: production_tier=marcel triggers the §6 fallback. Implementation shifts each Tier 2 stage draw in **logit space** by `logit(Marcel_h1) − logit(median(Tier2_h1))` per (player, stage), leaving Tier 2's aging trajectory and posterior spread intact. Result: q50 at h=1 = Marcel_h1 (up to round-off); bands at h=1 = Tier 2's spread anchored at Marcel; h=2..4 propagate Tier 2's aging drift from the Marcel anchor. If tier2 ever passes, the shift is bypassed and Tier 2 is used directly.
- 2026-09-17 — P3: `project --quick` writes to `data/artifacts/_quick/` (never `data/artifacts/`) so a smoke test cannot overwrite a real production run. Same schema, same writer.
- 2026-09-17 — P3: waterfall (§5.5) and derived aging curves (§5.6) emit rows only when every stage is fit (production run). `--quick` writes empty parquet files with the correct column schema so the check passes.
- 2026-09-17 — P3: `history.parquet` includes raw stage counts (`k_y`, `k_n`, ...) alongside derived rates. Small extra bytes; makes the API and Methodology tables reconstruct-from-source without re-reading `player_season_{H,P}`.
- 2026-09-17 — P3: FIP in projections and history is rebased on each player's Marcel PT (h=1) or actual IP (history) to match the P2 convention (§6 requires it for simulations).
- 2026-09-17 — P3 result: the ">95% of players see wider h=4 bands than h=1" spot check hits 42.5% (H wOBA) / 60.1% (P FIP). This is what the fitted model actually says — several stages have tau ≈ 0.02, so `h·tau²` growth is dwarfed by initial state variance for young/lightly-observed players. Recorded honestly; the Methodology page should show band widths per stage rather than claim uniform widening.
- 2026-09-17 — P6: Tier 3 obs frame is Tier 2's obs left-joined to `data/processed/statcast_{role}.parquet` mapped via `INDICATOR_MAP` (H/hr: barrels/attempts; H/hit_bip: ev95plus/attempts; P/hr: barrels/attempts). Stages not in the map fit as Tier 2 within the same tier=3 run — the manual only names those three, and `state_space.build_model` already uses the indicator only when told to.
- 2026-09-17 — P6: leakage guard for Tier 3 is `backtest.tier3_indicators(...).season < target`. Same construction as Tier 2's `train_slice`: filter before building anything the model can see.
- 2026-09-17 — P6: `project --tier 3` sets `production_tier` to tier3 for every role and rewrites `data/artifacts/` accordingly. When the flag is absent, `project.py` still follows `backtest.json.production_tier`, so a run after Fable's Tier 3 backtest picks up the new gate automatically.
- 2026-09-17 — P4: `create_app(artifacts_dir)` factory + module-level `app = create_app()` so both `uvicorn keystone.api.main:app` (real artifacts) and the test suite (fixture dirs) work without env vars or globals.
- 2026-09-17 — P4: `/api/leaderboard` key stats are `[woba, k_pct, bb_pct, hr_pct, babip]` (H) / `[fip, k_pct, bb_pct, hr_pct, babip]` (P) — the §9 Player-page summary cards. §8 says "each key stat"; making them the same set the summary cards use keeps Home consistent with the Player page.
- 2026-09-17 — P4: `httpx2>=2.13` added to requirements. Starlette 0.51's TestClient requires it on Python 3.14 (imports fail without). Not a runtime dep of the API itself; only needed to run `tests/test_api.py`.

## Questions for Fable M1 (statistical red team) — do not change these unilaterally
1. **Hitter HR% is where Tier 2 loses, and there are two candidate causes.** It is Tier 2's worst
   stat (.0155 vs Marcel's .0124) with the worst calibration (cov80 .71), and wHR = 2.05 makes it
   the biggest single lever on wOBA.
   (a) *Park-neutrality.* §5.3 makes Tier 2 projections park-neutral, but §6 scores them against
   what the player did in his real park. Marcel is park-blind too, yet it inherits parks
   implicitly through the player's raw past rates, so it is not penalised the same way.
   `state_space.project` already accepts `park_exposure`, so scoring a park-aware projection is a
   small change — but it is a modelling decision, so it waits for M1.
   (b) *Over-shrinkage.* Against (a): **pitcher** HR% is a Tier 2 *win* (.0107 vs .0109) even
   though pitchers work in the same parks. The model is fit on all ~1,205 hitters with PA' ≥ 1 in
   the window, a population dominated by part-timers, which could depress sigma_pop and over-shrink
   high-HR regulars.
   M1 should separate the two: score the park-aware projection, and independently compare the
   fitted sigma_pop for H/hr against the observed talent spread among 600-PA hitters.
2. **Sampler geometry, measured at production sampling.** 313 divergences over 48 fits at 500/500,
   181 of them in H/hit_bip, plus 19 of 48 fits above r_hat 1.05 (worst H/hit_bip and H/triple,
   both 1.231). The verified simulation had 0 divergences at this scale, so this is real-data
   structure the non-centred parameterisation does not absorb — most likely a funnel where
   sigma_pop is small next to binomial noise. This is a reparameterisation question, not a tuning
   one, and it comes first: no one should judge a model fix while a third of the fits are this
   unhealthy.
3. **Marcel projects the 200-PA population ~.012 wOBA high** (mean projected .3231 vs actual
   .3109 in 2024). Partly the missing rebaselining step (§5.2 documents it) against a 2021–23
   environment hotter than 2024; partly selection — a player with a good 2021–23 who only reached
   200–400 PA in 2024 is usually one who declined. Worth a paragraph in the memo either way.
4. **BB% loses for both roles** (.0204 vs .0199 H, .0220 vs .0206 P) despite walks being one of
   the most stable skills, where a hierarchical model should be at its strongest. Lower priority
   than 1 and 2, but it does not fit the "shrinkage helps unstable stats" story and may share a
   cause with 2 (H/bb is the second-largest divergence cluster, 47).

## Blockers
- none
