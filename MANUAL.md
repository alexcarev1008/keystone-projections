# KEYSTONE — Build Manual

Bayesian MLB player projection system + scouting-report web app.
Author: Daniel Cho · Manual v1.1 · 2026-09-17 · Build phases: **Opus** · Research missions: **Fable** (`FABLE_MISSIONS.md`)

> **Who reads what.** This manual is for the **Opus build agent** (Stage A, §10). Fable does not build phases — Fable
> runs the research missions in `FABLE_MISSIONS.md` once Stage A is finished.
>
> **How to use this manual (build agent, read this first).**
> Each work session builds exactly one phase. Read §0–§3 (the contract) plus the one phase section you were
> assigned in §10, then only the spec sections that phase lists. Do not read other phases. Everything you need
> has already been decided; if something is truly ambiguous, choose the simplest option that satisfies the
> acceptance checks, write one line about it under "Decisions" in `STATUS.md`, and keep going.

---

## §0 Mission

Build a portfolio project for a Washington Nationals **player projections** analyst application. It has to show
two things: (1) statistical depth — Bayesian hierarchical modelling with honest uncertainty and honest validation;
(2) baseball understanding — component-based projections, regression to the mean that depends on how reliable
each stat is, aging, park effects, DIPS (pitchers control little of their BABIP), and playing-time information.

The Nationals' Player Projections postings (Sept 2026) call **Stan/PyMC** experience a major plus, and their R&D
engineering postings list FastAPI microservices. KEYSTONE is PyMC + FastAPI + React.

**Reviewer's 60-second experience:** open a player → see their history and a fan chart of projected seasons with
uncertainty bands → see a waterfall explaining *why* the projection is what it is → see a multi-year aging
outlook → open Methodology and see backtests against Marcel, with calibration.

## §1 What gets built

| Layer | What it is |
|---|---|
| Data | MLB Stats API (player-team-season counts, bios, venues) 2015–2026; optional Statcast barrel/hard-hit counts (Tier 3); a FanGraphs wOBA-weights CSV added by hand |
| Tier 1 | **Marcel** baseline (already written, tested) |
| Tier 2 | **Bayesian state-space model**, one per component stage (already written, tested on simulated data) |
| Tier 3 (optional) | Tier 2 + Statcast contact-quality indicators (already supported in the model code) |
| Evaluation | Rolling backtests on 2021–2024, a one-time holdout on 2025, gates that decide which tier ships |
| Artifacts | Parquet/JSON files the API serves; the API never fits models |
| API | FastAPI, read-only, loads artifacts at startup |
| Frontend | React + Vite + Recharts: Home/leaderboard, Player page, Methodology |

Scope: MLB hitters and pitchers only. No prospects, no defense, no baserunning, no wRC+/WAR.

## §2 Non-negotiables and token discipline

**Correctness rules**
1. **No leakage.** A projection for season T may only use data from seasons ≤ T−1. The backtest code must make this
   impossible by construction (filter before building anything) and a test must assert it.
2. **Never hard-code or hand-tune results.** Priors and constants are the ones in §5. Do not tune anything on 2025.
3. **Don't rewrite the verified reference modules** (§3). Import them. Small, additive changes only (new function or
   argument), and keep their tests passing.
4. Report results honestly, including tiers that fail their gates.

**Token discipline (the user's Fable budget is limited — this matters)**
- Never print whole DataFrames, JSON responses, or files. Use `.shape`, `.head(3)`, `.columns`, or a 5-line summary.
- Never read `data/`, `.venv/`, `node_modules/`, or `*.parquet` with a file viewer.
- **Long jobs are run by Daniel, not you.** Anything expected to take longer than ~3 minutes (data download, full
  backtest, production fit) is written by you, smoke-tested with `--quick`, and then handed to Daniel as one
  `make` command in `STATUS.md`. Don't wait on it or poll it.
- Don't add dependencies beyond §3. No CSS frameworks, no state libraries, no chart libraries besides Recharts.
- No speculative refactors, no extra features, no alternative designs. Build the spec.
- If the same error happens twice, stop. Write the exact error and what you tried under "Blockers" in `STATUS.md`
  and end the session.
- End every session by updating `STATUS.md` (phase checkbox, commands for Daniel, decisions, blockers) and making a
  git commit: `phase N: <summary>`.

## §3 Repository layout (✅ = already exists and tested)

```
keystone-projections/
├── MANUAL.md                 ✅ this file
├── FABLE_MISSIONS.md         ✅ Fable's research missions (Stage B) — build agent: don't implement these
├── docs/                     fable_context/ (P6.5), fable/HANDOFF.md ✅, screenshots/ (P5)
├── CLAUDE.md / AGENTS.md     ✅ session bootstrap (points here)
├── STATUS.md                 ✅ progress log — update every session
├── Makefile                  ✅ command contract (targets call pipeline.py; implement those subcommands)
├── .gitignore                ✅
├── data/
│   ├── external/fg_guts.csv  ⬜ added by Daniel by hand (§4.4)
│   ├── raw/                  (API cache, gitignored)
│   ├── processed/            (tidy parquet, gitignored)
│   └── artifacts/            (served files: parquet/json, gitignored except meta.json + backtest.json)
├── backend/
│   ├── requirements.txt      ✅ pinned, verified resolvable
│   ├── pyproject.toml        ✅ pytest config (run pytest from backend/)
│   ├── keystone/
│   │   ├── components.py     ✅ stage definitions, derive_hitter/derive_pitcher, simulate_season
│   │   ├── league.py         ✅ league stage rates/logits, sf_rate, kappa, c_fip, projection_logit
│   │   ├── config.py         ⬜ Phase 1 — seasons, paths, constants from §5
│   │   ├── data/
│   │   │   ├── mlb_api.py    ✅ Stats API client + cache (parsing tested offline; network run in Phase 1)
│   │   │   ├── build.py      ⬜ Phase 1 — processed tables (§4.3)
│   │   │   └── statcast.py   ⬜ Phase 6 — Tier 3 indicators
│   │   ├── models/
│   │   │   ├── marcel.py     ✅ Tier 1
│   │   │   └── state_space.py✅ Tier 2/3 (fit + multi-year projection)
│   │   ├── eval/backtest.py  ⬜ Phase 2 (§6)
│   │   ├── project.py        ⬜ Phase 3 — production artifacts (§7)
│   │   ├── pipeline.py       ⬜ Phase 1–3 — CLI: fetch | build | backtest | holdout | project | statcast
│   │   └── api/main.py       ⬜ Phase 4 (§8)
│   ├── scripts/verify_state_space_sim.py ✅ full-scale simulation check
│   └── tests/                ✅ test_components, test_marcel_league, test_state_space, test_mlb_api
└── frontend/                 ⬜ Phase 5 (§9)
```

**Stack (pinned):** Python 3.11–3.14 (Daniel's Mac: 3.14.6; all pinned packages have 3.14 macOS arm64 wheels, checked 2026-09-17), pymc 5.28.5, nutpie 0.16.8, arviz <1, pandas 2.x (not 3),
pyarrow, requests, fastapi 0.141.1, uvicorn, pybaseball 2.2.7 (Tier 3 only), pytest.
Frontend: Node ≥ 20.19, Vite 8 (react-ts template), React 19, react-router-dom 7, recharts 3.

---

## §4 Data specification

### 4.1 Sources (checked live on 2026-09-17)
| Need | Endpoint | Notes |
|---|---|---|
| Teams + home venue per season | `/api/v1/teams?sportId=1&season=Y` | `teams[].venue.id`; handles the A's (Sutter Health Park 2025) and Rays (Steinbrenner Field 2025) moves |
| Player counts **per team** | `/api/v1/stats?stats=season&group={hitting,pitching}&season=Y&sportId=1&playerPool=ALL&teamId=T&limit=500` | A traded player appears under each team with that team's PA (Chisholm 2024: MIA 430 + NYY 191) |
| Team totals (sanity check) | `/api/v1/teams/stats?stats=season&group=hitting&season=Y&sportIds=1` | 2024 league PA = 181,516 |
| Bios | `/api/v1/people?personIds=a,b,…` | `birthDate`, `primaryPosition.abbreviation` (`P`, `TWP`, …), `batSide.code`, `pitchHand.code` |
| wOBA weights | FanGraphs Guts page, **saved by hand** | Automated access is blocked (403) — don't scrape |
| Tier 3 indicators | `pybaseball.statcast_batter_exitvelo_barrels(year, minBBE=1)` / `statcast_pitcher_exitvelo_barrels(year, minBBE=1)` | Savant leaderboard CSV; expected columns `player_id, attempts, barrels, ev95plus` — print `.columns` once and map if they differ |

`mlb_api.py` already implements these, with a cache (`data/raw/statsapi/`). Seasons ≥ the current year refresh after 12 h.

### 4.2 Seasons
Fetch 2015–2026. Model windows are **6 seasons** long: `window_end−5 … window_end`.
2026 is still in progress on 2026-09-17: record `data_through` (the fetch date) in `meta.json`, and re-run
`make data project` after the regular season ends.

### 4.3 Processed tables (`data/processed/*.parquet`, built by `build.py`)
1. `player_team_season_{H,P}`: raw rows from `player_team_stats` + `venue_id` (join on season/team).
2. `player_season_{H,P}`: sum over teams → one row per (mlbam_id, season). Add `team_abbr` (the team abbreviation, or
   `"2TM"`/`"3TM"`), `main_team_id` (the team with the most PA/BF), `age` (June 30 age via `mlb_api.season_age`).
3. `exposures_{H,P}`: mlbam_id, season, venue_id, `share` = that team's PA' (or BF') / the player's total.
4. `people`: from `mlb_api.people` for every id seen.
5. `league_{H,P}`: `league.stage_league_rates` on the **modelled population**, plus `league.hitter_constants` (H)
   and `league.pitcher_constants` on **all pitchers** (P).
6. `guts`: `data/external/fg_guts.csv` parsed (Season, wOBA, wBB, wHBP, w1B, w2B, w3B, wHR). Seasons without a row
   use the latest available row.

**Population filters (modelled population)**
- Hitters: `primary_pos != "P"` (keeps `TWP`, e.g. Ohtani), PA' ≥ 1.
- Pitchers: `primary_pos in {"P", "TWP"}`, BF' ≥ 1 (drops position players pitching blowouts).
- A two-way player gets separate H and P rows everywhere; every table is keyed by `(mlbam_id, role)`.

**Build sanity checks (build.py must assert; print one line each):**
- For each season, Σ player PA (all hitters, before filters) is within 1% of Σ team-totals PA.
- No negative stage counts (`components.stage_counts` already raises).
- At least 600 modelled hitters and 600 modelled pitchers per full season (2020: at least 400).

### 4.4 Manual step (Daniel)
Save FanGraphs Guts (fangraphs.com → Guts! → "wOBA and FIP constants") as `data/external/fg_guts.csv`, with the
header `Season,wOBA,wOBAScale,wBB,wHBP,w1B,w2B,w3B,wHR,runSB,runCS,R/PA,R/W,cFIP` and rows 2015–2026. If the file is
missing, `build.py` must stop with this instruction. Never invent weights.

---

## §5 Model specification

### 5.1 Component stages (implemented in `components.py`)
Each PA is a chain of conditional binomials on PA' = PA − IBB − SH − CI (pitchers: BF'):

| stage | successes / trials | park? | notes |
|---|---|---|---|
| `k` | K / PA' | no | reliable after very few PA → the model learns little shrinkage |
| `bb` | uBB / (PA'−K) | no | |
| `hbp` | HBP / (PA'−K−uBB) | no | |
| `hr` | HR / contact PA | yes | |
| `hit_bip` | (H−HR) / BIP | yes | exactly BABIP; for pitchers, expect small learned spread (DIPS) |
| `xbh` (H only) | (2B+3B) / (H−HR) | yes | |
| `triple` (H only) | 3B / (2B+3B) | yes | |

Derived stats (`derive_hitter`, `derive_pitcher`): K%, BB%, HR%, BABIP, AVG/OBP/SLG/ISO, **wOBA** (H); K%, BB%, K−BB%,
HR%, BABIP, **FIP** (P). FIP uses KEYSTONE's own uBB-based constant, so league FIP = league ERA (tested).
Stages are fit independently, and posterior draws are combined index-by-index (documented approximation: ignores
correlation between stages).

### 5.2 Tier 1 — Marcel (`models/marcel.py`)
Hitters: 5/4/3 weights, 1,200 PA' regression, PT = .5·PA₁ + .1·PA₂ + 200. Pitchers: 3/2/1, 1,200 BF', IP = .5·IP₁ +
.1·IP₂ + 60 (starter: GS/G ≥ .5 last season) or 25. Age factor a = .006·(29−age) below 29, −.003·(age−29) above.
**Marcel playing time is also the playing-time projection for every tier** (a documented limitation).

### 5.3 Tier 2 — Bayesian state-space model (`models/state_space.py`)
For each (role, stage), fit on the 6-season window:
```
theta[i, first] = lam·z(log PA'_first) + sigma_pop·e           # a player's first observed talent; more PA ⇒ teams trusted him
theta[i, t]     = theta[i, t−1] + g[age] + tau·e               # talent drifts (tau) and ages (g)
y[i, t] ~ Binomial(n[i, t], invlogit(mu_league[t] + theta[i, t] + X_park·phi))
```
- `mu_league[t]` = the fixed league logit from `league_{role}` (run environment: juiced ball, 2022 ball changes, rule changes).
- Priors: tau ~ HalfNormal(.3), sigma_pop ~ HalfNormal(1), lam ~ N(0,.5), g = smooth random walk over ages 20–40
  (g0 ~ N(0,.1), step sd ~ HalfNormal(.02)), phi = N(0,1)·park_sd, park_sd ~ HalfNormal(.1). Non-centred.
- Park effects only for park stages; `exposures` → `X_park = 0.5·share`.
- Sampler: nutpie, **backtests 2 chains × 500 draws (tune 500)**, **production 4 chains × 500 draws**, target_accept .9.
- Interpretation to surface in the UI/write-up: `tau` = how fast talent changes (acts as learned recency weights);
  `sigma_pop` = true-talent spread (compare `hit_bip` for pitchers vs hitters → DIPS); `g` = aging curve; `phi` = parks.

**Projection** (`state_space.project`): from each player's state at window_end, step forward h = 1…4 seasons, adding
`g[age]` and `tau·noise` → posterior talent draws for 4 seasons (uncertainty widens with h). League environment
`mu_proj = league.projection_logit(…, n_years=3)`. Projections are **park-neutral**, and conditional on the player
playing (no attrition model).

Simulated-data verification (`scripts/verify_state_space_sim.py`, ~1,800 players): 0 divergences, 80% interval
coverage 0.83, RMSE 0.0341 vs 0.0387 for a regressed 3-year average; ~45 s per fit on 2 cores.

### 5.4 Tier 3 — Statcast contact quality (optional Phase 6)
Add a binomial indicator that measures the same talent `theta` (already in `build_model(use_indicator=True)`):

| role | stage | ind_y / ind_n |
|---|---|---|
| H | `hr` | barrels / attempts (BBE) |
| H | `hit_bip` | ev95plus / attempts |
| P | `hr` | barrels allowed / attempts |

Use `target_accept=0.95` (0.9 caused divergences). Other stages stay Tier 2. On simulated data this cut RMSE
0.0341 → 0.0328 with coverage 0.82.

### 5.5 Waterfall ("Why this projection")
One per player: hitters' stat = wOBA, pitchers' = FIP, horizon 1. Each step is the derived stat averaged over draws,
computed from all stages. Bars = differences between consecutive steps (they telescope to the final value).

| step | label | stage probabilities used |
|---|---|---|
| 0 | "3-year line (5/4/3 weighted)" | raw weighted rates: Σw·events / Σw·PA' (no regression, no aging) |
| 1 | "Regression to the mean" | invlogit(mu_proj + theta[window_end]) (Tier 2, no aging) |
| 2 | "Aging (age N)" | step 1 + g[age_next] (no tau noise) |
| 3 | "Statcast contact quality" | only if Tier 3 ships: the Tier 3 version of step 2 |
| 4 | "Neutral-park projection" | = last of steps 2/3 (the total bar) |
| 5 | "At home park: VENUE" | step 4 + 0.5·phi[venue of main team in window_end] on park stages |

Use the target season's league constants (guts weights, sf_rate, kappa, c_fip; the latest available if the season
isn't in the table yet).

### 5.6 Aging curves
For each role and stage: G(age) = cumsum of posterior-mean g, from 20 to 40. Curve rate(age) =
invlogit(mu_proj + G(age) − G(27)). Also push all stage curves through `derive_*` → a typical wOBA/FIP curve by age.

---

## §6 Evaluation specification (`eval/backtest.py`)

- **Dev targets:** 2021, 2022, 2023, 2024 (window_end = T−1). **Holdout:** 2025, run once, after the gates are decided.
- **Leakage guard:** `backtest(target)` first does `data = data[data.season <= target-1]`. Actuals for T are loaded
  separately. `tests/test_backtest_leakage.py` asserts that perturbing season-T data doesn't change any projection.
- **Evaluation population:** players with PA' ≥ 200 (H) / BF' ≥ 200 (P) in T **and** PA'/BF' ≥ 1 in T−3…T−1.
- **Point projection:** Marcel's stage probabilities; Tier 2/3 = posterior mean of the talent probability, h = 1.
- **Metrics per (target, role, tier, stat):** n, PA-weighted RMSE, PA-weighted MAE. Stats: `k_pct, bb_pct, hr_pct,
  babip` and `woba` (H) / `fip` (P). Derived stats use the **target season's** league constants for every tier
  (these are environment constants, not player skill).
- **Calibration (Tier 2/3 only; Marcel has no intervals, which is a point to make in the write-up):**
  `simulate_season` with the player's **actual** PA' → 50% and 80% predictive-interval coverage for each stat.
  Pitchers' FIP in simulations uses actual IP.
- **Baselines also reported:** "last season's rate" and "league average".
- **Gates:** Tier 2 ships if its `woba` (H) and `fip` (P) RMSE ≤ Marcel's in ≥ 3 of 4 dev targets **and** mean 80%
  coverage is within [0.75, 0.85]. Tier 3 ships if it beats Tier 2 by the same rule. If Tier 2 fails, production
  uses Marcel points with Tier 2 bands, and the Methodology page says so plainly.
- **`--quick` mode** (for agents): target 2024 only, stages `k` and `hr`, 2 chains × 150 draws, hitters only. Must
  finish in under 5 minutes.
- Output: `data/artifacts/backtest.json` = `{generated_at, targets, holdout_target, rows:[{target, role, tier, stat,
  n, rmse, mae, cov50, cov80}], gates:{H:{tier2:bool, tier3:bool|null}, P:{…}}, production_tier:{H, P}}`.
  Print a compact summary table (≤ 30 lines).

## §7 Artifacts (`data/artifacts/`, written by `project.py`)

| file | columns |
|---|---|
| `players.parquet` | mlbam_id, name, roles ("H", "P", "HP"), primary_pos, bats, throws, birth_date, last_team_abbr, last_season |
| `history.parquet` | mlbam_id, role, season, team_abbr, age, pa (PA or BF), ip (P), stage counts, k_pct, bb_pct, hr_pct, babip; H: avg, obp, slg, iso, woba; P: k_minus_bb, fip, era |
| `projections.parquet` | mlbam_id, role, season, horizon (1–4), age, stat, mean, q10, q25, q50, q75, q90, tier, pt (h=1 only: PA or IP) |
| `waterfall.parquet` | mlbam_id, role, stat, step, label, value |
| `aging.parquet` | role, stat (stages + woba/fip), age, value |
| `league.parquet` | role, season, stat, value (league averages for reference lines, incl. the projection season) |
| `meta.json` | generated_at, data_through, window_end, projection_season, production_tier, model summaries (per stage: tau, sigma_pop, park_sd mean; top/bottom 3 venues by phi for `hr`), max r_hat, total divergences |
| `backtest.json` | §6 |

Projection population: every modelled player with PA'/BF' ≥ 1 in window_end, or in either of the two seasons before it.

## §8 API specification (`api/main.py`)

FastAPI loads all artifacts into memory at startup (pandas). CORS for `http://localhost:5173`. Read-only. No model
code imported. All rates are floats (0–1); formatting happens in the frontend.

| method + path | returns |
|---|---|
| `GET /api/health` | `{status:"ok"}` |
| `GET /api/meta` | meta.json + backtest.json |
| `GET /api/search?q=&limit=10` | `[{mlbam_id, name, roles, primary_pos, last_team_abbr}]` (case/accent-insensitive substring match) |
| `GET /api/leaderboard?role=H&sort=woba&min_pt=300&limit=100` | h=1 rows: mlbam_id, name, team, age, pt, and for each key stat {q10, q50, q90}. Defaults: H sort `woba` desc, min_pt 300 PA; P sort `fip` asc, min_pt 50 IP |
| `GET /api/players/{id}?role=H` | `{bio, role, history:[…], projections:{stat:[{season, horizon, age, q10, q25, q50, q75, q90}]}, pt, waterfall:[…], aging:{stat:[{age, value}]}, league:{stat:value}}`; 404 if not found; default role = the player's first role |

Test: `tests/test_api.py` using FastAPI TestClient on a tiny fixture artifact set (build the fixtures in the test).

## §9 Frontend specification (`frontend/`)

`npm create vite@latest frontend -- --template react-ts`, then add `react-router-dom recharts`. The Vite dev
server proxies `/api` → `http://127.0.0.1:8000`. Files:
```
src/main.tsx  App.tsx (router + top nav)  api.ts (typed fetchers)  format.ts  styles.css
src/pages/Home.tsx  Player.tsx  Methodology.tsx
src/components/Search.tsx  Leaderboard.tsx  FanChart.tsx  ComponentPanel.tsx  Waterfall.tsx  AgingOutlook.tsx  StatTable.tsx
```
**Design:** clean analyst tool, light theme, system-ui font, max width 1200px. Tokens in `styles.css`:
`--ink #14213d, --muted #5c677d, --bg #f7f8fa, --card #ffffff, --line #e3e6ec, --accent #1f3a93 (navy),
--accent-2 #b3261e (red, for "down" bars), --band80 rgba(31,58,147,.15), --band50 rgba(31,58,147,.30)`.
Cards with a 1px border, 8px radius, no shadows. No team logos or wordmarks.
**Formats (`format.ts`):** wOBA/AVG/OBP/SLG/ISO/BABIP → `.312` (3 decimals, no leading zero); K%/BB%/HR%/K−BB% → `24.1%`;
FIP/ERA → `3.47`; PA/IP integers; intervals shown as `.298–.341`.

**Home (`/`)**: title "KEYSTONE — Bayesian player projections", subtitle `Projections for {projection_season} · data
through {data_through}`. A search box (debounced 250 ms, dropdown of results → player page). Tabs Hitters | Pitchers →
sortable Leaderboard (click a column header), showing median with a small grey 80% range underneath.

**Player (`/player/:id?role=H`)**, top to bottom:
1. Header: name, age, team, position, B/T; role toggle if two-way.
2. Summary cards (h=1): wOBA or FIP (large), then K%, BB%, HR%, BABIP, projected PA/IP — each "median · 80% range".
3. **FanChart** (the key visual): x = season. History = dots (size ∝ PA) joined by a line for wOBA (H) or FIP (P);
   projection = 80% band + 50% band + median line for horizons 1–4; dashed league-average line; a vertical divider at
   window_end. Recharts `ComposedChart` with `Area dataKey={[low, high]}` range areas. Tooltip lists the values.
4. **ComponentPanel**: a 2×2 grid of small versions of the same chart for K%, BB%, HR%, BABIP.
5. **Waterfall** (horizontal bars): start bar, up/down bars (navy up, red down, from the hitter's perspective — for
   FIP, lower is good), end bar. Under it, one generated sentence per step, e.g. "Aging (age 33): −.006 wOBA".
6. **AgingOutlook**: a table of seasons h=1–4 (season, age, median, 80% range for wOBA/FIP, K%, BB%), plus a small
   line chart of the typical aging curve (from `aging`) with the player's ages marked.
7. **StatTable**: year-by-year history, projection rows in italics with a tinted background.

**Methodology (`/methodology`)**: written in JSX, no markdown library. Sections: Overview · Component stages · Marcel
· State-space model (with the equations as monospace text) · What the model learned (tau / sigma_pop / park table
from meta; the pitcher-vs-hitter BABIP spread as the DIPS finding) · Validation (backtest table from `/api/meta`:
rows = stat, columns = Marcel / Tier 2 / Tier 3 RMSE, and coverage; gate results; holdout) · Limitations (playing
time is Marcel; stages are independent; projections are park-neutral and conditional on playing; survivor bias;
2026 data through {data_through}) · Data sources.

No test runner for the frontend. Acceptance = `npm run build` passes with no TypeScript errors + the manual checks in Phase 5.

---

## §10 Phases

Legend: 🤖 Opus build agent does it · 👤 Daniel does it (usually a long-running command) · ✔ acceptance check

### Phase 0 — Setup 👤
1. `python3.12 --version` (install Python 3.12 from python.org if it's missing). `node --version` ≥ 20.19.
2. In the repo: `make setup` → creates `.venv`, installs requirements. Then `make test` → **7 tests pass** (~20 s).
3. Optional: `make verify-sim` (~2 min) → 0 divergences, coverage ≈ 0.8.
4. Save `data/external/fg_guts.csv` (§4.4). `git init && git add -A && git commit -m "phase 0: manual + verified reference"`.

### Phase 1 — Data layer 🤖 (read: §4, §5.1)
Build `config.py`, `data/build.py`, and `pipeline.py` subcommands `fetch` and `build` (the Makefile targets `data`).
Fetch loops seasons 2015–2026 over `mlb_api` (teams, player_team_stats for both groups, team_totals, people).
- 🤖 Smoke test: `.venv/bin/python -m keystone.pipeline fetch --start 2024 --end 2024` then `build --end 2024`
  (about 70 requests). ✔ The sanity checks in §4.3 print and pass.
- 👤 `make data` (full 2015–2026, ≈ 900 requests, roughly 5–10 min).
- ✔ `processed/` contains every table from §4.3; the check lines are pasted into STATUS.md by Daniel.

### Phase 2 — Backtest harness, Tier 1 + 2 🤖 (read: §5.2–5.3, §6)
Build `eval/backtest.py`, `pipeline.py backtest|holdout`, `tests/test_backtest_leakage.py` (use tiny synthetic data
and `--quick`-sized sampling).
- 🤖 `make backtest-quick` ✔ finishes in < 5 min; prints the table; `backtest.json` is valid.
- 👤 `make backtest` (4 targets × 12 stages; estimated 45–120 min on a MacBook Air). Paste the summary into STATUS.md.
- 🤖 (next session, only if needed) read the summary, apply the gates, record `production_tier`. No tuning.
- 👤 `make holdout` once, after the gates are recorded.

### Phase 3 — Production artifacts 🤖 (read: §5.3, §5.5, §5.6, §7)
Build `project.py` + `pipeline.py project` (window_end 2026 → projections for 2027–2030).
- 🤖 Add a `--quick` path (hitters, 200 players, 2 stages) that writes every artifact file with the correct schema.
  ✔ A schema check function asserts the columns in §7.
- 👤 `make project` (4 chains, all stages, both roles; estimated 20–40 min).
- ✔ Spot checks printed (≤ 15 lines): three well-known hitters' 2027 wOBA median + 80% range; waterfall sums to the
  final value within .001; bands widen from h=1 to h=4 for > 95% of players; max r_hat < 1.05.

### Phase 4 — API 🤖 (read: §7, §8)
✔ `make test` passes, including `test_api.py`. ✔ `make api` then `curl localhost:8000/api/players/<id>` returns the
full shape (check keys only; don't print the whole body).

### Phase 5 — Frontend 🤖 (read: §8, §9)
Build in this order, committing after each: api.ts/format.ts → Home + Search + Leaderboard → Player (FanChart
first, then the rest) → Methodology.
✔ `npm run build` has no errors. 👤 Daniel runs `make api` + `make web` and checks: search finds "Soto"; a player
page renders all 7 sections; a two-way toggle appears for Ohtani; Methodology shows the backtest table.
Agent: don't start a browser; Daniel reports visual bugs in STATUS.md and saves screenshots of Home, 3 player pages
(a hitter, a pitcher, Ohtani) and Methodology to `docs/screenshots/` (Fable Mission 5 reviews them).

### Phase 6 — Statcast data + Tier 3 plumbing 🤖 (read: §4.1 last row, §5.4, §6 gates)
**Not optional anymore — Fable's Mission 2 needs this data ready.** `data/statcast.py` + `pipeline.py statcast`;
join indicators onto the obs for the 3 stages in §5.4; add a `--tier 3` flag to backtest/project.
👤 `make statcast`, `make backtest TIER=3`. Record gates, but don't try to improve the model — that is Fable's job.

### Phase 6.5 — Fable context pack 🤖 (read: §6, §7, FABLE_MISSIONS.md §3)
Build `pipeline.py diagnostics` → writes `docs/fable_context/` exactly as specified in FABLE_MISSIONS.md §3.
✔ Every file listed there exists; `CONTEXT.md` ≤ 400 lines; each CSV ≤ 2,000 rows. 👤 `make diagnostics`.

### Phase 7 — Write-up and polish 🤖 (runs AFTER Fable Mission 4; read: STATUS.md, docs/research_memo.md)
`README.md` (≤ 150 lines): the pitch in 3 sentences, a screenshot placeholder, architecture diagram (ASCII), results
table from backtest.json, how to run, limitations, and "what I'd do next" (a playing-time model, correlated stages,
MiLB translations, pitch-level Stuff+ indicators). 👤 After the 2026 regular season ends: `make data project`, then commit.

## §11 Session kickoff prompts for the Opus build agent (one per session)

**Standard:**
> You are building KEYSTONE. Read `CLAUDE.md`, then `STATUS.md`, then MANUAL.md §0–§3 and **Phase N** in §10 plus
> only the spec sections that phase lists. Do Phase N only. Follow the §2 token rules exactly. When the acceptance
> checks pass (or you're blocked), update STATUS.md, commit, and stop.

**After a long 👤 job:**
> Daniel ran `<command>`. Output summary: `<paste ≤ 30 lines>`. Continue Phase N from STATUS.md.

**Wire a Fable handoff:**
> Read `docs/fable/HANDOFF.md`. Implement every unchecked item exactly as specified, run the listed checks, tick the
> items, update STATUS.md, commit `handoff: <mission>`. Don't change modelling decisions — ask in STATUS.md instead.

**Bug report:**
> Bug in Phase N: `<symptom, exact error, file:line if known>`. Fix only this. Don't refactor. Update STATUS.md and commit.

## §12 Known gotchas (already paid for — don't rediscover)
- PyMC `shape=` must be a Python `int`, not `numpy.int64` → wrap with `int()`.
- With the indicator likelihood, use target_accept 0.95; at 0.9 there were 28 divergences.
- pandas 3 breaks idioms and pymc/arviz assumptions → keep pandas < 3. `groupby.apply(..., include_groups=False)` needs pandas ≥ 2.2.
- arviz 1.0 is a breaking refactor → keep arviz < 1.
- FanGraphs and Savant block non-browser clients from some networks. FanGraphs data comes from the hand-saved CSV only;
  Savant goes through pybaseball (it has worked on Daniel's Mac before).
- The Stats API bulk `/stats` without `teamId` behaves differently for traded players — always query per team and sum.
- 2020 (60 games) stays in the data; small n is handled naturally by the binomial likelihood. Never drop it silently.
- Position players pitching and pitchers hitting are filtered by `primary_pos` (§4.3), not by stat thresholds.
- Age = age on June 30. Ohtani (born July 5, 1994) is 29 in 2024.
- Run pytest from `backend/` (pyproject sets `pythonpath`).
- A real-data fit stores `theta` and `e` for about 10k states × 2,000 draws (a few hundred MB). Fit stages one at a time,
  extract what you need (projection draws, g, phi, tau summaries), then `del idata` and call `gc.collect()`
  before the next stage.
- `state_space.project` returns every player with a state at window_end, including players last seen years ago.
  Filter to the projection population in §7.

## §13 For Daniel — talking points this build lets you make
- "I project components, not wOBA. Each stage is binomial, so K% shrinks less than BABIP automatically — the model
  learns each stat's reliability instead of me hard-coding stabilization points."
- "The state-space model learns recency weighting (tau) and the aging curve jointly from all seasons, which avoids
  the delta method's paired-season data loss."
- "It learned that pitchers' BABIP talent spread is a fraction of hitters' — DIPS falls out of the data."
- "Playing time is informative: the log-PA term in the talent prior shrinks part-timers toward a lower mean, not
  toward league average — similar to what OOPSY does by level."
- "I validated against Marcel with rolling-origin backtests, checked interval calibration, and held out 2025 until
  the end. Here's where it didn't beat Marcel, and why."
