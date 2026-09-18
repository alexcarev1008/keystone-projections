# KEYSTONE — STATUS

## Stage A — Opus builds (MANUAL.md §10)
- [x] P0 Setup (Daniel): `make setup`, `make test` (7 pass), fg_guts.csv saved, git init
- [x] P1 Data layer
- [x] P2 Backtest harness (Tier 1 + 2)
- [x] P3 Production artifacts
- [x] P4 API
- [x] P5 Frontend (agent build; Daniel: `make api` + `make web` + save screenshots)
- [x] P6 Statcast data + Tier 3 plumbing
- [x] P6.5 Fable context pack (`make diagnostics`)

## Stage B — Fable missions (FABLE_MISSIONS.md) — $100 cap, revised 2026-09-17
- [x] M1 Statistical red team ($15) — done 2026-09-17, see `docs/fable/M1_audit.md` → Opus wires handoff → Daniel re-runs → `make diagnostics`
- [x] M2a Model research: diagnose + build ($20) — done 2026-09-17, see `docs/fable/M2_experiments.md` → Daniel full backtests (commands below)
- [x] M2b Judge + iterate ($20) — done 2026-09-18: E2/E4 rejected vs pre-registrations, E3 unjudged (run missing), E5/E6 built + quick-validated → Daniel full backtests (commands below)
- [x] M2c Judge + lock ($15) — done 2026-09-18: E5+E6 ACCEPTED (locked config `--obs-noise --env-mode shock`), E3 + t4 rejected, correlated stages declined with reasons → holdout attempt 1 misfired (ruled invalid) → Opus repaired state + writer guard → **holdout attempt 2 run + recorded, SPENT: tier2 beats Marcel on neither key stat (H wOBA .0309 vs .0305, P FIP .7399 vs .7317) but cov80 in band both (.83/.75) — M2 closed.** Remaining: `make project`, `make diagnostics` (HANDOFF item 4 done)
- [x] M3 follow-up ($8) — done 2026-09-18: talent covariate ACCEPTED 8/8 vs the shipped hurdle
  (M3_playing_time.md §7; Judge h1 258 → 545 expected PA); regulars-under-Marcel verdict in §8
  (real hurdle bias for H regulars, fixed by the same covariate; Marcel was wrong for P regulars)
  → 1 HANDOFF wiring item (talent=True + guts in project.py/pipeline.py + Methodology copy)
- [x] M3 Playing time + attrition hurdle model ($20) — done 2026-09-18, see `docs/fable/M3_playing_time.md`: Bayesian hurdle (P(plays) × E[PT|plays]) **beats Marcel PT 8/8 dev targets on the pre-registered RMSE gate** (H −25%, P −11%; bias +42..+127 PA → ±7, +6..+22 IP → ±1.1); multi-year outlook defined as expected production (p_play × conditional) with `p_play`/`pt_expected`/`p_regular` per horizon → 3 HANDOFF items for Opus (artifacts, API/UI, CLI) — wired 2026-09-18 (`handoff: M3`); lands on the next `make project`
- [x] M4 ML challenger + formal model comparison ($10) — done 2026-09-18, see `docs/fable/M4_ml_challenger.md`:
  HistGradientBoosting challenger + Bayesian+GBM hybrid, same information set, pre-registered rules.
  **Hitters: the hierarchical model wins outright** (GBM 1/4 on points, 1/4 on CRPS; hybrid adds nothing).
  **Pitchers: GBM beats tier2 FIP 3/4 on points AND CRPS (cov80 .83 in band); hybrid best of all on 2022–24
  (.7770 vs tier2 .8190, Marcel .7986)** — evidence cross-stage information matters for P — but the GBM is
  2/4 vs Marcel (§6 gate FAIL) and the hybrid is unstable (2023 worst on board, ≤960 training rows), so
  **nothing ships; production unchanged**. README language in §7. No new runs for Daniel.
- [x] Phase 7 memo + README — Opus, 2026-09-18: `docs/research_memo.md`, `README.md`; M4 leakage
  test wired (`tests/test_m4_leakage.py`, HANDOFF ticked). App + screenshot review: Daniel.
- [x] Outlook PT h1-only — Opus, 2026-09-18: AgingOutlook shows PA/IP + counting stats at h1 only;
  h2–h4 rows are rates only (unvalidated PT feedback at h2+). Methodology, memo §5, README updated.

## Stage C — Opus final polish
- [ ] Handoff queue empty · `make test` + `npm run build` pass · re-run after the 2026 season ends

## Fable ledger (Daniel fills in after every Fable session)
| session | budget | actual | running total (cap $100, reserve $10) |
|---|---|---|---|
| M1 | $15 | ~$5 (Fable self-estimate) | ~$5 |
| M2a | $20 | Daniel fills in (Fable self-estimate ~$8: input ~250k, output ~20k) | ~$13 |
| M2b | $20 | Daniel fills in (Fable self-estimate ~$7: input ~220k, output ~18k) | ~$20 |
| M2c | $15 | Daniel fills in (Fable self-estimate ~$6: input ~200k, output ~12k) | ~$26 |
| M3 | $20 | Daniel fills in (Fable self-estimate ~$4: input ~110k, output ~12k) | ~$30 |
| M3 follow-up | $8 | Daniel fills in (Fable self-estimate ~$2: input ~90k, output ~8k) | ~$32 |
| M4 | $10 | Daniel fills in (Fable self-estimate ~$3: input ~180k, output ~14k) | ~$35 |

## Next command(s) for Daniel
- **HOLDOUT ATTEMPT 1 WAS MISCONFIGURED (2026-09-18 14:53) — ruled invalid, not spent.**
  Daniel's `make holdout` raced the `handoff: M2c` commit (14:54) by one minute and ran the
  pre-wiring code: no flags, no guard → it scored 2025 with the OLD config (`mean3`,
  `obs_noise: false`) and corrupted canonical `backtest.json` (old flags stamped over the
  promoted E5E6 file, `holdout_target: 2025` latched, old-config 2025 rows merged into file +
  sidecars). Full record + ruling + pre-commitments: `M2_experiments.md` §"The 2025 holdout".
  One re-run with the locked config is authorised (config was locked and committed before any
  2025 number existed; no modelling decision changes on the misfire numbers). In order:
  1. ~~**Opus:** the two new URGENT M2c HANDOFF items~~ DONE 2026-09-18 (`handoff: holdout
     repair`). Canonical `backtest.json` + both sidecars were restored byte-identical from the
     m2 E5E6 copies: `holdout_target: null`, flags `shock`/`obs_noise: true`, no 2025 rows
     anywhere. Attempt 1 is archived as `m2/backtest_holdout_2025_misfire.json` plus
     `m2/backtest_holdout_2025_misfire_{predictions,posteriors}.parquet`. `bt.run(holdout=True)`
     now refuses a flag mismatch before loading or fitting, and again before writing. The guard
     is covered by regression tests; `make test` passes (49). `make diagnostics` is green; the
     context pack is unchanged apart from its timestamp.
  2. ~~**Daniel:** `make holdout`~~ DONE 2026-09-18 — ran clean (flags header `shock`/
     `obs_noise: True`, guard passed, no `--force`). **The holdout is SPENT.**
  3. ~~Paste the printed 2025 table back~~ DONE — recorded in `M2_experiments.md`
     §"The 2025 holdout" and in Results below.
  4. ~~`make project` + `make diagnostics`~~ DONE 16:19. The run started before the HANDOFF item 4
     commit, though, so meta.json has no `model_config` / `sigma_obs_mean` / `sigma_env`. The
     projections are the locked config. Artifact checks A and B (Results) ran on these files.
  5. ~~the new "artifact check B" HANDOFF item~~ DONE 2026-09-18 (Fable, at Daniel's direction):
     Waterfall.tsx skips null steps and hides unshipped steps 3/4; project.py drops the 868
     all-NaN ids (verified orphans — absent from players.parquet, unreachable in the UI),
     silences the step-0 0/0, and the schema check now fails on non-finite quantiles.
     ~~M2b sidecar-filename collision~~ DONE 2026-09-18 (`sidecar_paths`, unit-tested).
     **← NEXT (Daniel):** `make project` (~35 min) + `make diagnostics` once. That single re-run
     fills meta.json (`model_config`/`sigma_obs_mean`/`sigma_env`), ships the M3 outlook columns,
     drops the orphan rows, and is the on-disk acceptance for artifact check B (c).
     ~~Then the three M3 HANDOFF items~~ DONE 2026-09-18 (`handoff: M3`). The same `make project`
     re-run writes `p_play`/`pt_expected`/`p_regular` into projections.parquet, and the player page's
     outlook picks them up. ~~Before shipping the outlook, read "Questions for Fable (M3 follow-up)"~~
     ANSWERED 2026-09-18: the talent covariate is accepted (M3_playing_time.md §7) and fixes the
     Judge case (.17 → .94 p_play at 2030). ~~Opus: wire the new "(M3 follow-up T1)" HANDOFF item~~
     DONE 2026-09-18 (`handoff: M3 follow-up talent covariate`). The `make project` re-run now ships
     the outlook with talent in the hurdle. After it runs, check Judge (592450): h1 p_play > .9 and
     pt_expected within ±35% of 545. ~~Then M4~~ — M4 DONE 2026-09-18, no Daniel runs needed
     (all M4 compute ran locally in-session; nothing ships).
- ~~After Fable M2b (2026-09-18): run the three M2b backtests~~ DONE 2026-09-18 (results below) (~50 + ~25 + ~50 min). E3's
  original run never completed (`backtest_E3.json` was not on disk), so it goes back on the
  queue unchanged. Note: consecutive runs overwrite each other's sidecar parquets in
  `data/artifacts/m2/` (HANDOFF item filed) — if Opus hasn't fixed that yet, either run them
  as-is (only the JSONs are strictly needed for M2c's judging) or copy the two
  `backtest_*.parquet` files aside between runs. From the repo root:
  - `cd backend && PYTHONPATH=. ../.venv/bin/python -m keystone.pipeline backtest --rp-effect --roles P --out ../data/artifacts/m2/backtest_E3.json`
  - `cd backend && PYTHONPATH=. ../.venv/bin/python -m keystone.pipeline backtest --obs-noise --out ../data/artifacts/m2/backtest_E5.json`
  - `cd backend && PYTHONPATH=. ../.venv/bin/python -m keystone.pipeline backtest --obs-noise --env-mode shock --out ../data/artifacts/m2/backtest_E5E6.json`
  - paste each printed RMSE table + gates into a fresh Fable session to start **M2c**
    ("Results of `<command>`: …"). Pre-registered accept/reject rules are in
    `docs/fable/M2_experiments.md` (E3 under its M2a entry, E5/E6 under M2b) — no goalpost
    moves. M2c judges these, attempts the correlated-stages/geometry upgrade (incl. deciding
    `--innov t4` for geometry — see the M2b decisions), locks the config, and only then
    `make holdout`. Still do NOT run `make holdout` before M2c says so.
- **After Fable M2a (2026-09-17): run the three experiment backtests.** DONE for E2/E4
  2026-09-18 (results below); E3 never completed — rerun folded into the M2b list above. Each writes its own JSON +
  sidecars under `data/artifacts/m2/` — `backtest.json`, the gates and the production tier are
  untouched until M2b accepts something. From the repo root (~50 + ~25 + ~60 min):
  - `cd backend && PYTHONPATH=. ../.venv/bin/python -m keystone.pipeline backtest --env-mode recency --out ../data/artifacts/m2/backtest_E2.json`
  - `cd backend && PYTHONPATH=. ../.venv/bin/python -m keystone.pipeline backtest --rp-effect --roles P --out ../data/artifacts/m2/backtest_E3.json`
  - `cd backend && PYTHONPATH=. ../.venv/bin/python -m keystone.pipeline backtest --innov t4 --out ../data/artifacts/m2/backtest_E4.json`
  - then `make diagnostics` (10 s — this also refreshes the context pack from the post-M1 sidecars;
    the current pack's Tier 2 CSV rows are stale because diagnostics ran before the M1 re-run).
  - paste each printed RMSE table + gates into a fresh Fable session ("Results of `<command>`: …")
    to start **M2b**. The pre-registered accept/reject rules are in `docs/fable/M2_experiments.md`
    — M2b judges against those, no goalpost moves. Still do NOT run `make holdout`.
- **After Fable M1 (2026-09-17):** ~~re-run the dev backtests~~ DONE 2026-09-17 (results below,
  M1's park-aware prediction confirmed: H/hr .0155 → .0128, H wOBA .0364 → .0333, gates still
  marcel for both roles but H is now 2/4 with cov80 .78 ✓). Original instructions kept for the record:
  (both runs, so tier2 and tier3 rows stay comparable — ~50 min each). Opus wired the M1
  sidecars 2026-09-17 (see Results below), so the re-run also writes
  `backtest_predictions.parquet` + `backtest_posteriors.parquet` next to `backtest.json`, which
  `make diagnostics` reads to fill the Tier 2/3 rows in the Fable context pack:
  - `make backtest`
  - `make backtest TIER=3`
  - `make diagnostics`
  - paste the printed RMSE table + gates back into a Fable session ("Results of `make backtest`: …").
    M1's pre-registered prediction (in M1_audit.md): H/hr RMSE → ~.0135, H/hr cov80 → ~.80,
    pitcher rows ~unchanged. Still do NOT run `make holdout`.
  - Item 3 of HANDOFF.md is already wired (park-aware `project.py` — no-op under marcel-anchor,
    kicks in the moment gates flip to tier2). No further action needed on that item.
- **Smoke-test P5** (one terminal per line, no long job):
  - `make api` — FastAPI on :8000 against `data/artifacts/`.
  - `make web` — Vite dev server on :5173 (first run does `npm install`).
  - Manual checks: search "Soto" finds him; a player page renders all 7 sections (header,
    summary cards, FanChart, ComponentPanel, Waterfall, AgingOutlook, StatTable); the H/P
    toggle appears for Ohtani (mlbam_id 660271); Methodology shows the backtest table
    (Marcel / Tier 2 / Tier 3 RMSE, cov80, gates).
  - Save four screenshots to `docs/screenshots/`: Home, one hitter (e.g. Judge 592450),
    one pitcher (e.g. Skubal 669373), Ohtani (660271), Methodology.
- P6.5 done (agent-only, no long compute); the context pack is at `docs/fable_context/`.
  Ready to launch **Fable M1** with the kickoff prompt in `FABLE_MISSIONS.md` §5.
- Backlog long jobs: none.
- **`make holdout` is now authorised — ONCE.** The three M2c HANDOFF items it waited on landed 2026-09-18 (see the ordered list at the top of this section).

## Results (paste summaries here, ≤ 30 lines each)

### Queue close-out — Fable (2026-09-18, at Daniel's direction)
- Outlook chip restores the threshold: "Chance still an MLB regular in 2027 (≥ 300 PA)" for H,
  "(≥ 100 IP)" for P — matches `REGULAR_PT` in playing_time.py.
- HANDOFF queue is now EMPTY. Closed: artifact check B parts (b)+(c) (errstate wrap; marcel-anchor
  NaN drop; schema check fails on non-finite quantiles — the 868 all-NaN ids verified as orphans
  absent from players.parquet, so parquet hygiene, not user-facing) and the M2b sidecar collision
  (`sidecar_paths`, unit-tested; the two-MCMC-run acceptance deliberately deferred to the next
  natural quick pair — naming logic is the whole fix). M4 leakage test was already ticked (Opus).
- `make test` 65 pass · `npm run build` passes. docs/screenshots/ holds five files but they are
  dated **2026-09-17, not today** — flagging, not fixing (screenshots are Daniel's). README.md
  links docs/research_memo.md (exists, 18 KB) and embeds all five screenshots.
- Remaining before Stage C closes: Daniel's one `make project` + `make diagnostics`.

### Outlook playing time h1-only — Opus (2026-09-18, frontend + docs, no compute)
- Decision: the hurdle PT model is backtested at h1 only (`make pt-backtest`); at h2+ it feeds its
  own simulated healthy seasons back in as the recent-PT feature, so injury-depressed stars' PT
  rises with age (Judge 545/579/620/646 PA at 35–38 while wOBA .419 → .369, checked against
  `projections.parquet`). We don't display numbers we haven't validated.
- `AgingOutlook.tsx`: h1 rows unchanged; h2–h4 rows keep the rate columns and replace the PT/count
  cells + "chance he plays" line with "rates only — playing time projected one year ahead". The
  "chance still an MLB regular" chip now uses h1 `p_regular` and the h1 season (was h4, the same
  unvalidated PT output). Footer notes PT is year-1 only.
- Methodology "Known artifact" paragraph → "Playing time is shown for year 1 only" + a Limitations
  bullet; memo §5 item 2 and README Limitations restated as a deliberate display decision.
- `npm run build` passes. Model/artifacts unchanged. To show h2+ PT again: backtest h2+ PT or fix the feedback.

### Phase 7 write-up — Opus (2026-09-18, docs + one test, no compute)
- `backend/tests/test_m4_leakage.py`: triples season-T counts + shifts season->=T league logits,
  asserts `fit_predict_stage` (k, hr) is `np.array_equal` to the clean run. Mutation check: the
  same perturbation without `train_slice` changes the predictions, so the test has teeth.
- `docs/research_memo.md`: leads with pre-registration + the negative results (dev gates 2/4, 1/4;
  2025 lost both key stats while winning 5/8 component rows → Marcel points + Tier 2 bands), then
  component-chain rationale, M1–M4 changes, open problems (unbacktested h2–h4 bands, old-star
  pt_expected rise, r_hat 1.16 / 89 div, correlated pitcher stages). Every number quoted from a
  committed file with its source cited; per-year dev table read from `backtest.json`.
- `README.md` (~95 lines): pitch, results table, stack + ASCII diagram, run commands, the 5
  screenshots (note: taken 2026-09-17, pre-M2/M3 — Daniel may want fresh ones after `make project`),
  limitations, next steps, link to memo. `make test` 63/63.

### M4 ML challenger — Fable (2026-09-18, all runs local ~15 min CPU, no Daniel compute)
- Design pre-registered and committed (2f1db13) before any result. Same information set as tier2
  (train_slice guard; leakage perturbation check passes), same scoring path (Marcel RMSE reproduced
  to 6 decimals), same eval population/weights. CRPS via MC draws; tier2 predictive reconstructed
  split-normal from the sidecar quantiles + shared binomial noise (recon cov80 within .01 of reported).
- Key stat, 4-target mean RMSE (gbm / tier2 / marcel): H wOBA .0333 / .0328 / .0334;
  P FIP .7938 / .8131 / .7947. CRPS mean: H .0187 / .0183; P .4425 / .4531.
- Verdicts vs pre-registered rules: H — A1/A2/A3 all FAIL (hierarchical model survives outright).
  P — A1/A2/A3 all PASS, but §6 ship gate (≥3/4 vs Marcel) FAILS (2/4; Marcel-mean margin .0009
  flips under the pre-registered sensitivity config). Hybrid P best on 2022–24 (.7770) yet worst
  model of 2023 — unstable at ≤960 training rows. Nothing ships; production unchanged.
- Finding worth keeping: the GBM's only informational edge is other stages' lag-1 deviations, and it
  wins exactly (and only) on pitcher FIP — direct evidence for M2c's declined correlated-stages
  hypothesis, now with numbers. Right next test: score GBM + hybrid once on 2026 targets, pre-registered.
- Artifacts: `data/artifacts/m4/m4_results.json` (460 rows) + logs; code `eval/ml_challenger.py`,
  `eval/m4_verdict.py`; full write-up `docs/fable/M4_ml_challenger.md`.

### M3 follow-up T1 wire-up — Opus (2026-09-18, code + copy, one 92 s backtest)
- `project.pt_outlook_frame`: `talent=True, guts=b.guts` on `PT.training_table` and `PT.build_pt_table`
  (`fit_pt` picks up the talent column itself; `simulate_horizons` holds it fixed). `pipeline.cmd_pt_backtest`:
  same kwargs on `PT.backtest_pt`, using the guts from the bundle it already loads. No model code touched.
- `make pt-backtest` (92 s, seed 1): hurdle RMSE is H 154.057/135.666/138.204/139.099 and
  P 34.856/34.849/33.574/36.642. That matches M3 §7's talent column on all 8 rows, and it beats Marcel 4/4 per role.
- Methodology: the features paragraph describes the talent term. There is a new "known artifact: optimism for old stars
  beyond year 1" paragraph (Judge h1 .96 / ~545, pt_expected can rise with horizon), and the "model-implied, not
  backtested" label is kept. The validation paragraph cites the §7 result.
- `make test` 62/62, `import keystone.project` OK, `npm run build` passes. Judge's acceptance check waits on `make project`.

### M3 PT hurdle backtest — Fable (2026-09-18, run locally, seed 1, dev targets only)
Pre-registered gate: hurdle expected-PT RMSE < Marcel PT RMSE in ≥3/4 dev targets per role.
Result: **8/8** (full table in `M3_playing_time.md` §3). RMSE (marcel → hurdle):
H 2021 190.5→156.8 · 2022 190.7→141.6 · 2023 205.0→144.0 · 2024 201.9→142.7
P 2021 37.2→35.2 · 2022 41.1→35.7 · 2023 42.1→34.7 · 2024 44.0→36.9
Bias: Marcel +42..+127 PA / +6..+22 IP; hurdle ±7 PA / ±1.1 IP. p_play Brier beats base
rate on all 8; decile calibration clean for P, H over-predicts play prob in the bottom two
deciles (conservative direction). Fits are seconds each (nutpie), run locally per §4 rule 4
— no Daniel compute needed. 2025 untouched. `make test` 55 pass. Multi-year outlook =
p_play × conditional production; per-horizon `p_play`/`pt_expected`/`p_regular` via
posterior simulation with feature roll-forward. Trustworthiness verdict (M3 doc §5):
conditional bands fine per artifact check A + holdout cov80; h2–h4 intervals are
model-implied, not backtested — label them so; the dominant multi-year error (conditional
numbers for 50–86%-attrition players) is what the hurdle fixes.

### Artifact check A — why H bands don't widen h1→h4 — Opus (2026-09-18, read-only, 16:19 `make project` artifacts)
**Not a bug.** The model does what it says; the MANUAL §10 ">95% widen" check measures the wrong space.
- **Denominator.** 12.5% H / 66.4% P count the 868 all-NaN players (check B) as "not widening". Among
  finite rows: H wOBA 157/892 = **17.6%**, P FIP 1113/1177 = **94.6%** (P3 pre-M2: 42.5% / 60.1%).
- **Drift does accumulate, in logit space.** Per-stat logit sd h1→h4 widens for 100% H k_pct, 98% H hr_pct,
  96% H babip, 100% P k_pct (medians: H k .195→.269, H hr .319→.347, H babip .087→.093).
- **Rate space is where it's lost.** Share of H players that widen h1→h4: k_pct 100%, babip 85%, bb 84%, but
  hr_pct 21%, iso 17%, slg 8.5%, wOBA 17.6%. wOBA by age: ≤25 52%, 26–28 18%, 29–31 2.5%, 32+ 11%, while
  the median q50 moves −.002 / −.013 / −.020 / −.032. hr_pct: ≤25 68% widen, 32+ 0.8% (width ×0.89).
  Mechanism: aging pulls HR/XBH rates down, and a low-p band's width scales with p·(1−p) × logit-sd,
  which is roughly proportional to p. A ~15% fall in HR rate cuts the band ~15% while the logit sd only
  grows ~9%. Pitchers show the mirror image: aging pushes the bad-event rates up (FIP q50 +.62 for 32+), so
  the bands grow with the level (32+: 99.8% widen).
- **Is h1 inflated by obs-noise / env shock? Mostly no.** H/hit_bip h1 logit variance ≈ .0076, of which
  τ² .0001 (1%), σ_env² .00045 (6%, σ_env .0213), σ_obs² ≈ .00085 (11%; .029 is the 2025-fit value because
  production σ_obs isn't in meta yet). The remaining ~81% is posterior talent uncertainty. h4 adds only
  3τ² = .0003 (+2% sd). Dropping σ_obs and σ_env entirely would move the h4/h1 sd ratio from 1.021 to
  1.026. For H/hr the constants are a larger share (τ² .009, σ_env² .013, σ_obs² ≈ .015 of ≈ .102):
  sd ratio 1.125 with them vs ≈ 1.17 without. So they dilute growth but don't drive the result.
- **Tiny taus: yes, and M2 shrank them.** Obs-noise absorbed part of what used to be drift (2024-target
  fits, pre-M2 → E5E6): H/hr .175→.136, H/k .124→.095, H/xbh .030→.021, H/hit_bip .013→.011. Together with
  the constant σ_obs/σ_env terms, that explains the fall from 42.5% to 17.6%.
- **Reading.** Growth is small because hit_bip/xbh τ is tiny and h1 is dominated by talent uncertainty.
  Where rate-space bands shrink, the cause is hitter aging dragging HR/XBH levels down. A logit
  random walk with a declining level doesn't imply wider rate-space bands. Suggest re-stating the
  acceptance check as "per-stage logit sd widens for >95%" (passes at 96–100%). This is a doc
  change, not a modelling one; no HANDOFF item.

### Artifact check B — NaN/inf in projections/history — Opus (2026-09-18, read-only)
- **history.parquet: clean.** 0 inf. NaNs are structural only: pitcher columns on H rows (4,446) and
  hitter columns on P rows (5,454).
- **projections.parquet: 27,256 / 92,324 rows NaN (29.5%), 0 inf.** They belong to 868 players
  (369 H, 499 P), and each of them is NaN in every row, stat and horizon. All have `pt` NaN, none is in
  `players.parquet` or `history.parquet` (both only carry players active 2024+), and their h1 ages run
  26–47 (median 34). So these are state-space fit-window players with no 2024–26 Marcel line: the
  Marcel anchor is NaN, so every anchored draw is NaN. They come from missing data, not from the
  divide-by-zero. **API/UI: not shown.** `/api/players/{id}` 404s (not in players), and the leaderboard
  drops them (`pt >= min_pt` is False for NaN). They do distort artifact-level checks (see A).
- **The divide-by-zero warnings come from `waterfall.parquet`, not projections.** `marcel.to_stage_probs`
  computes `xbh / h_bip`, which is 0/0 when a player had no hits on balls in play in 2024–26
  (`triple` is guarded, `xbh` isn't). The result is a NaN step 0 (3-year line) for 391 H + 1 P players.
  **23 of them are visible** (in players.parquet, e.g. Tony Kemp 643393, Greg Allen 656185, Grae
  Kessinger 666197, Kyler Fedko 693459, Evan Justice 687145 (P); all have 1–25 PA / 0.1 IP since 2024).
- **UI bug (genuine, every player page).** `Waterfall.tsx` renders `value ?? 0`. Step 3 (Statcast) is
  NaN→null for all 2,937 waterfalls by design (Tier 3 isn't shipped), so, from reading the code, every
  player page shows a "Statcast contact quality .000" row and delta sentences of about −.29 and then
  +.29 wOBA. It also stretches the bar axis down to 0. The 23 players above also get a .000 3-year line.
  Filed as a HANDOFF item.
- Side note: 261 finite-projection players (every one whose last season is 2024) have `pt` NaN at
  h1. They are left off the leaderboard by design and show `pt` null on their pages. Not a bug.

### 2025 holdout attempt 2 — SPENT (Daniel, 2026-09-18, locked config, guard passed, no --force)
Full record + reading: `M2_experiments.md` §"The 2025 holdout". Key rows (marcel | tier2):
H wOBA .0305 | .0309 (cov80 .83) · P FIP .7317 | .7399 (cov80 .75). Against the pre-registered
expectation: H "close to or better" — close (−.0004), not better; P worse — yes; cov80 in band
both — yes (9/10 stat rows in [.75,.85], H k .76 at the floor). Marcel had its best year of the
five scored; the dev-mean H advantage didn't carry (n=1 — decides nothing about the mean-vs-gate
argument, which stands as an argument). Component pattern replicated out-of-sample: tier2 wins
BABIP both roles (H .0302 vs .0327, P .0319 vs .0336), P hr, P k, H bb; loses H k, P bb.
Calibration — the E6 claim — validated on 2025. Gates unchanged by design: production ships
Marcel points + Tier 2 bands, and the holdout says the bands are honest. The old-config misfire
scored ~identically on 2025 key stats (H .0309 / P .7402) — recorded, acted on by no one, per
the pre-commitments. 2025-fit health: worst r_hat 1.27 (P/hr), 1.23 (H/xbh), 63 divergences —
the known geometry blemishes. **M2 closed.**

### 2025 holdout attempt 1 — MISFIRE (Daniel, 2026-09-18 14:53, ruled invalid by Fable M2c)
Ran the pre-handoff code (raced the wiring commit by 1 min): old config `mean3`/no obs-noise,
NOT the locked E5+E6. Recorded permanently, decides nothing (old config, n=319 H / 325 P):
H wOBA marcel .0305 / tier2 .0309 (cov80 .81) · P FIP marcel .7317 / tier2 .7402 (cov80 .75).
Ruling: holdout NOT spent — the locked config was committed before any 2025 number existed and
the re-run obligation follows from the misconfiguration, not the numbers. Pre-commitments in
M2_experiments.md §"The 2025 holdout": locked config ships regardless of the old-vs-new 2025
comparison; one re-run only; spent after it whatever it says. State repair + writer-level
guard + regression test filed as URGENT HANDOFF items (canonical backtest.json is currently a
chimera — E5E6 dev rows, old-config 2025 rows, old flags, latched holdout_target — and must be
restored from the m2/ E5E6 copies before the re-run).

### M2c handoff wire-up — Opus (2026-09-18, code + file copy, no long compute)
Ticked the first three M2c items in `docs/fable/HANDOFF.md`. Item 4 (Methodology + meta.json
docs) is still open and doesn't block the holdout.
- **project.py.** `fit_and_project_stage`/`run` default to the locked config, mirroring
  `backtest.fit_stage_draws`: `obs_noise=True` → `SS.build_model` (SS.project picks sigma_obs up
  from the posterior); `env_mode="shock"` keeps the mean3 `mu_proj` and passes recency's
  sigma_env as `mu_sd` to both the neutral and the park-aware projection. No rp_effect, no t4.
  r_hat now covers sigma_obs. Per-stage log: `config: obs_noise on (sigma_obs …), env_mode shock
  (mu_sd …), tau …`. `project --no-obs-noise --env-mode mean3` restores the pre-M2 model.
- **Defaults.** `backtest.py` (fit_stage_draws → run) and the `backtest` CLI default to
  `--obs-noise --env-mode shock`, opt-outs `--no-obs-noise` / `--env-mode mean3` (the old
  `--obs-noise` spelling still parses). `holdout` passes the locked flags explicitly and
  **refuses** if they differ from `backtest.json.experiment_flags`.
- **Promotion.** `m2/backtest_E5E6.json` → `backtest.json`, `m2/backtest_{predictions,posteriors}.parquet`
  → `data/artifacts/` (byte-identical, all 14:05:35). The post-M1 baseline is archived as
  `m2/backtest_base.json` + `m2/backtest_base_{predictions,posteriors}.parquet` (sidecars aren't
  in git). `backtest.json` no longer carries the pre-M2 tier3 rows; its tier3 gate is "not evaluated".
- **Acceptance.** `make test` 44/44 (6 new in `tests/test_m2c_locked_config.py`). `backtest
  --quick`, no flags → `experiment_flags {env_mode: shock, rp_effect: false, innov: normal,
  obs_noise: true}`, stage_k .0335 / stage_hr .0169 (Marcel .0349 / .0169). `project --quick`
  completes, schema check OK, flags in the log. `--quick` emits no waterfall, so a scratch
  7-stage hitter run (200 players, quick sampling, locked config): telescoping max |gap| 0 over
  200 hitters. `make diagnostics` green off the promoted sidecars (context pack refreshed).
  `/api/meta` → 200 with the new block (H 2/4 cov80 .819, P 1/4 .761, marcel/marcel). A dry
  `holdout` against the real `backtest.json` (bt.run stubbed) passes the guard with the locked flags.
- **Watch in `make project`:** quick-scale r_hat is higher with obs-noise: H/k 1.15 (pre-M2 quick
  1.14), H/hr 1.27 (1.17), H/bb 1.30 in the 7-stage scratch run. Quick sampling is not a
  convergence test (the E5E6 dev fits cut divergences 313 → 121), but read the full run's max r_hat.
- **For Fable (observation, no change made):** each stage reseeds `default_rng(seed)` and draws the
  env shock first, so every stage gets the same z per draw. That's true in the backtest too, so it
  is what was validated. Env shocks are perfectly correlated across stages within a draw, and the
  wOBA/FIP band widths inherit that assumption.

### M2c judge + lock — Fable (2026-09-18)
Full verdicts: `docs/fable/M2_experiments.md` §"M2c decisions". Judged the three full runs:
- **E5 ACCEPT** — every pre-registered sub-check passed: tau −21..−53% with sigma_obs ≥ 7 sd
  from 0 (not relabelling); chasing corr crossed to Marcel's side on all 4 stages (P/k
  +.116→−.031); bb_pct H 3/4, P 4/4; FIP mean .8223→.8162; wOBA .0333→.0328; divergences
  313→121 with the M1-F5 H/hit_bip funnel largely dissolved (181→25, r_hat 1.23→1.07).
- **E6 ACCEPT** — fits byte-identical to E5, RMSE within noise, P FIP cov80 .734→.761 (≈ the
  E2 delta, as registered), both roles in band. Shipping candidate = **E5+E6**.
- **E3 REJECT** for the bundle — delta_role real (~10 sd, right signs) and overall FIP 3/4 ✓,
  but the RP-subgroup sub-check (the mechanism test) is unverifiable (sidecar overwritten,
  same collision that cost E2), r_hat 1.363 on 2022 P/hr is the worst fit in the project, and
  the gain (.8204) is mostly subsumed by E5 (.8162). Bundling would cost another full run.
- **t4 DECLINED** on a pre-registered quick: under obs-noise the E4 relabelling reappears
  (tau .0964→.0666 ≈ /√2), RMSE identical, r_hat 1.371 red flag. Correlated stages assessed
  and declined: observed cross-stage corr ≤ .32, binding losses are environment-regime errors
  pooling can't touch, cost = full joint-model rebuild.
- **Locked config: tier2 `--obs-noise --env-mode shock`** = `backtest_E5E6.json` exactly.
  Gates: H FAIL 2/4 (cov80 .820 ✓), P FAIL 1/4 (.761 ✓) → production stays Marcel points +
  Tier 2 bands; coverage in band for both roles for the first time. On the H mean-vs-gate
  split (.0328 beats .0334 but 2/4 years): the mean is the better skill measure (n=4 sign test
  discards magnitude; E5 improved all 4 years vs base) — argued in the doc, gate left as
  written, no goalpost move. 4 HANDOFF items for Opus; holdout order + command above.
  Fable self-estimate ~$6.

### M2b judge + iterate — Fable (2026-09-18)
Full verdicts + new pre-registrations: `docs/fable/M2_experiments.md` §"M2b decisions".
Judged E2/E4 full runs (E3's run never completed — rerun queued, no verdict). Gates still FAIL
everywhere (H 2/4, P 1/4); production stays marcel.
- **E2 REJECT** (rule: FIP better in ≥3/4 — got 2/4: 2022 .890→.869 big, 2024 tiny; 2021/2023
  worse). Its cov80 half passed exactly as registered (.732→.755, into band). Decomposition:
  the env *shock* did all the calibration work, the recency *point* forecast did all the damage
  → shock carried forward alone as **E6 `--env-mode shock`** (fits untouched, interval-only).
- **E4 REJECT** (tau fell ✓ but chasing corr unchanged, bb_pct H 1/4 / P 0/4 vs ≥2/4, FIP
  .8223→.8241). Key finding: t(4) has variance 2τ², and fitted τ fell by almost exactly √2 —
  the year-to-year variance is data-demanded and was *conserved*, just relabelled. The walk is
  that variance's only home, so it's forced to be persistent → T-1 chasing (M1-F4). Geometry
  gain is real (divergences 429→172, H/hit_bip 184→28): handed to M2c (owns geometry), not
  shipped for accuracy.
- **E5 `--obs-noise` (new)**: transient season-level logit noise sigma_obs·eps per player-season,
  non-persistent (never enters the walk; projection draws it fresh per horizon). The direct fix
  E4's finding points at: give the variance a non-persistent home so theta stops tracking
  walk-rate noise Marcel regresses away. Targets BB% (only losing P component, 3× FIP weight).
  Quick: 0 divergences, sigma_obs k=.080 (6.6 sd from 0), tau k −22% with total variance
  conserved (.0964²+.080²≈.1239²), stage_k .0341→.0338, stage_hr .0172→.0169 (=Marcel) ✓.
- **E6 quick**: fits byte-equal to baseline (tau .1239/.1737 identical), RMSE within noise ✓.
- Tests 38/38 (3 new in `tests/test_m2b_experiments.py`). Also fixed: sigma_obs missing from
  the posteriors sidecar row writer; filed HANDOFF item for sidecar filename collisions across
  `--out` runs (cost E2 one sub-check). Fable self-estimate ~$7.

### M2a diagnose + build — Fable (2026-09-17)
Full diagnosis + pre-registrations: `docs/fable/M2_experiments.md`. Post-M1 state: H wOBA tied
(.0333 vs .0334, 2/4 wins, cov80 .78 ✓ — needs one flip of 2021 gap .0005 / 2023 gap .0023);
P FIP loses (.8223 vs .7947, 1/4, cov80 .73 ✗). Three causes found, three upgrades shipped
behind default-off backtest flags, each quick-validated against its pre-registration:
- **Environment lag.** FIP bias marcel/tier2: 2021 +.15/+.21, 2022 +.28/+.39, 2023 −.18/−.02,
  2024 +.09/+.14 — 2022 (dead ball) is mostly bias; tier2's 1/1/1 3-yr mean mu_proj lags trends
  worse than Marcel's 5/4/3 rates (tier2 over-projects H k_pct and P bb_pct in all 4 targets).
  FIP cov80 .73 = zero environment uncertainty in the draws (a common error RMSE-weighting feels).
  → **E2 `--env-mode recency`**: recency×size-weighted league forecast + common env shock per
  draw. Quick: fits identical, stage_k .0341→.0339, hr unchanged ✓.
- **RP pooling.** P FIP by T-role: tier2 loses relievers in 4/4 targets (RMSE .85/1.12/.91/.92
  vs Marcel .81/1.01/.83/.84) while winning/tying SP 3/4 — shrinkage drags RPs toward an
  SP-dominated mix. → **E3 `--rp-effect`**: centred rp_share covariate (1−GS/G), T-1 role
  projected forward. Quick: delta_role k +.141 (sd .015), hr −.137 (sd .021), RMSE ok ✓.
- **T-1 chasing (M1-F4 confirmed).** corr(T-1 dev, error) tier2 +.04..+.10 vs Marcel −.05 on
  k/bb; Gaussian innovations force one scale, inflating tau on the stablest skills.
  → **E4 `--innov t4`**: Student-t(4) transitions (first-season Normal, latent dim unchanged,
  projection noise matched). Quick: tau H/k .124→.092, RMSE within noise, geometry fine ✓.
Tests 35/35 pass (4 new in `tests/test_m2a_experiments.py`). Full-run commands above; M2b
judges each against `M2_experiments.md` — the pre-registered expectations are written down,
no goalpost moves. Fable self-estimate: ~$8 (input ~250k, output ~20k).

### M1 handoff wire-up — Opus (2026-09-17, code only, no long compute)
Ticked items 1, 2, 4 in `docs/fable/HANDOFF.md`; item 3 deferred (see below).
- **backtest.py sidecar.** `_diagnostics` now returns mean+sd for every scalar pop param
  (tau, sigma_pop, lam, sigma_age, park_sd) plus ess_bulk_min alongside max_rhat/divergences.
  `run_target` returns `(score_rows, pred_rows, post_rows)`; `run()` merges per-target
  block-by-block into `backtest_predictions{,_quick}.parquet` and
  `backtest_posteriors{,_quick}.parquet` next to `backtest{,_quick}.json`. Predictions cover the
  eval intersection (players with actuals). FIP pred draws use per-player actual PA/IP; hitter
  derived stats broadcast cleanly.
- **diagnostics.py consumes it.** `residuals_by_bucket` / `pit_histograms` / `biggest_misses` /
  `posterior_summaries` gain Tier 2/3 rows when the sidecar is on disk (falls back to Marcel-only
  when missing, so `make diagnostics` runs green either way). Sidecar-fed PIT is piecewise-linear
  from q10/q50/q90 (not truly posterior-predictive, called out in the `note` column); tier2 cov80
  in residuals_by_bucket is computed from sidecar q10/q90 against the actual.
- **Methodology.tsx** gains one Validation-section sentence: "As of M1, backtest scoring is
  park-aware… see `backtest.json.park_aware_scoring`." `npm run build` passes (609 modules,
  672 kB bundle unchanged).
- **Item 3 deferred** — the "thread park exposure into `project.py`" edit is gated on a tier2
  gate flip to PASS after Daniel's re-run. Current gates on disk still say Marcel for both roles.
- **Acceptance:** `make test` 31/31 pass; `make backtest-quick` writes both sidecar files (696
  pred rows, 2 post rows) alongside `backtest_quick.json`; `make diagnostics` runs green with and
  without the sidecar on disk. Quick sidecar carries only H `stage_k`/`stage_hr` rows, so
  residuals_by_bucket etc. show non-Marcel rows only after Daniel's full re-run populates
  derived-stat predictions.

### M1 item 3 — Opus (2026-09-17, code only, no long compute)
Ticked at Daniel's direction ahead of the re-run: shipped in place so the moment a tier2 gate
flips to PASS, `make project` picks up park-aware points automatically. No-op meanwhile.
- **project.py.** `_home_park_exposure` (top-venue, share = 1) removed and replaced with
  `park_exposure_map(b.exp[role], window_end)` — identical construction to `backtest.park_exposure_map`,
  so shipped park exposure and validated park exposure are the same object. `StageFit` gains an
  optional `P_park_aware` array (h=1..H) for `PARK_STAGES` only; non-park stages leave it None.
- **What ships when.** `projections_frame` uses `P_park_aware` for park stages when it exists,
  else `P_neutral`. Under `production_tier=marcel`, `_anchor_to_marcel` shifts all h=1 medians to
  Marcel — since park exposure only adds a per-player logit constant and aging drift is
  park-independent, park-aware and park-neutral produce identical shipped stats under the anchor.
  When (if) tier2 gate PASSes, the anchor is bypassed and Coors hitters' hr_pct q50 rises.
- **Waterfall.** Step 4 ("Neutral-park projection") still uses `P_neutral[:, 0, :]`; step 5
  ("At home park") now uses `P_park_aware[:, 0, :]` (actual T-1 shares, so traded players get a
  mixture) instead of the old top-venue-only h=1. Telescoping identity (step5 − step0 = Σ deltas)
  is preserved by construction of the loop.
- **Acceptance.** `make test` 31/31 pass; `make project --quick` completes, schema check passes,
  and the new per-stage log confirms park-aware draws differ from neutral (H/hr h=1: mean Δ
  -0.0001, max |Δ| 0.0022 at quick sampling — tiny because 200-player cap × 150 draws barely
  learns the park effect; a full run will show the expected larger deltas). Coors-hitter q50
  acceptance is inherently gated on tier2 shipping mode.

### M1 statistical red team — Fable (2026-09-17)
Full findings: `docs/fable/M1_audit.md`. One root cause fixed, four findings for M2, rest clean.
- **F1 (fixed): backtest scored Tier 2 park-neutral against in-park actuals — a handicap Marcel
  doesn't carry.** Explains H/hr being the worst stat AND the H-vs-P asymmetry (park_sd .35 vs .12).
  Fix: park-aware scoring via T-1 venue shares (leakage-safe), default on, `--park-neutral` opt-out,
  recorded in backtest.json. Pre-registered quick validation (identical fits, 2024 H): tier2
  stage_hr RMSE .0202 → .0172 (Marcel .0169); stage_k unchanged. Tests +2 (31 pass).
- **F2: Q1(b) refuted.** Observed H/hr talent sd among regulars .541 ≈ model √(sigma_pop²+park²)
  .509 — no over-shrinkage from the part-timer-heavy fit population. M2a shouldn't spend a change there.
- **F3: Marcel wOBA bias +.0085 is uniform across ages** → stale environment + selection, shared by
  tier2's 3-yr mean mu_proj (2020 equal-weighted). M2a menu: league environment projection.
- **F4: BB% loss cause hypothesis** — tau .135/.123 for bb/k (stablest skills) looks inflated,
  making tier2 over-weight T-1; candidate M2a change: age/PA-dependent or heavy-tailed innovations.
- **F5: H/hit_bip funnel cause** — tau .017 ⇒ per-player states collapse; per-element non-centring
  can't absorb the cumulative-sum degeneracy. M2c reparameterisation target.
- Clean: leakage (incl. new exposure path), stage math, ages, traded/two-way, 2020, Marcel fidelity.
- Fable self-estimate: ~$5 (input ~150k, output ~15k).

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

### P5 Frontend — agent (2026-09-17, code only, `npm run build` passes)
Vite 8 + React 19 + react-router-dom 7 + recharts 3, TypeScript strict. Structure per §9:
- `main.tsx` (BrowserRouter root), `App.tsx` (nav + `/`, `/player/:id`, `/methodology` routes).
- `api.ts`: typed fetchers for `/api/search|leaderboard|meta|players/:id`; every field the API
  actually emits is typed. `format.ts`: rate3 (`.312`), pct (`24.1%`), ratio2 (`3.47`), int0;
  per-stat `fmtStat/fmtRange/statLabel` using the sets in §9. `styles.css`: the design tokens
  from §9, one file, no CSS framework.
- `pages/Home.tsx`: title + subtitle (`Projections for {projection_season} · data through
  {data_through}` from `/api/meta`), Search, Hitters/Pitchers tabs → Leaderboard.
- `components/Search.tsx`: debounced 250 ms, dropdown of hits, Enter opens the first one,
  clicking outside closes.
- `components/Leaderboard.tsx`: sortable header (defaults H sort=woba desc / P sort=fip asc,
  min_pt 300 PA / 50 IP per §8); each cell shows median with the 80% range beneath in muted.
- `pages/Player.tsx`: header, summary cards (key stat highlighted in navy), FanChart, then
  ComponentPanel, Waterfall, AgingOutlook, StatTable. Two-way toggle only when `bio.roles` has
  both H and P. `role=` in the URL is the source of truth (via `useSearchParams`).
- `components/FanChart.tsx`: Recharts `ComposedChart`; history dots sized by PA/IP + line;
  projection band80 + band50 areas + median line; dashed league line via `ReferenceLine`;
  vertical divider at `window_end + 0.5`. Tooltip lists actual, projected, and both bands.
- `components/ComponentPanel.tsx`: 2×2 grid of small FanCharts for K%, BB%, HR%, BABIP.
- `components/Waterfall.tsx`: horizontal bars per step (start/end = accent, deltas colored
  navy=good / red=bad from the hitter's perspective, inverted for FIP); one sentence per step.
- `components/AgingOutlook.tsx`: h=1…4 table + typical aging curve with `ReferenceDot`s at
  the player's ages.
- `components/StatTable.tsx`: year-by-year history + projection rows italicized on tinted bg.
- `pages/Methodology.tsx`: Overview, stages, Marcel, state-space (equations as `<pre>`),
  What learned (per-stage tau/sigma_pop/park_sd from meta + DIPS callout comparing
  H vs P `hit_bip` sigma_pop + HR park top/bottom), Validation (RMSE + cov80 tables per role,
  gate results, holdout), Limitations, Data sources.
- Vite proxies `/api` → `http://127.0.0.1:8000` (§9 requirement). Removed the default
  `App.css / index.css / assets/`.
- `npm run build` → 0 TS errors, 609 modules, 671 kB bundle (recharts dominates; single-page
  app so code-splitting is not worth the complexity here).

### P6.5 Fable context pack — agent (2026-09-17, `make diagnostics`, ~10 s)
`backend/keystone/diagnostics.py` + `pipeline.py diagnostics` write `docs/fable_context/`.
Consumes only what is on disk (backtest.json, meta.json, aging.parquet, processed/*); no model
fits, so it is safe to re-run any time. Files written (row counts in parentheses):
- `CONTEXT.md` (143 lines, cap 400): one-page project brief with the three open findings from
  Phase 2 + the M1 questions leading, model equations from §5, data coverage per season, gate
  results, per-stage population parameters from meta.json, and a "gaps" section spelling out the
  sidecar (`backtest_predictions.parquet`, `backtest_posteriors.parquet`) Fable can request via
  HANDOFF to unlock per-player Tier 2/3 rows.
- `code_map.md`: one line per backend file (purpose + public names).
- `backtest_summary.csv` (200): backtest.json rows without the diagnostics sentinels.
- `posterior_summaries.csv` (108): meta.json stages (target=window_end) + backtest per-target
  diagnostics rows (max_rhat/divergences). tau/sigma_pop/lam/sigma_age null per target — that
  needs the posteriors sidecar.
- `aging_curves.csv` (462): mean G(age) per role×stage from aging.parquet; q10/q90 null.
- `park_effects.csv` (16): top/bottom 3 hr parks per role from meta.json; other park stages get a
  summary row (phi_mean null).
- `residuals_by_bucket.csv` (1,375): PA-weighted n/mean_error/RMSE per Marcel row bucketed by age
  (<=24 / 25-27 / 28-30 / 31-33 / >=34), prior PA (<150 / 150-400 / >400), and history length
  (1 / 2 / 3+). Tier 2/3 rows absent (need per-player sidecar).
- `pit_histograms.csv` (100): pooled Marcel residual PIT via a normal approx (scale = per-role
  PA-weighted RMSE across dev targets). Real PP-PIT for Tier 2/3 needs the sidecar.
- `biggest_misses.csv` (320): 40 largest |wOBA/FIP error| per (role, dev target) for Marcel with
  name/age/prior_pa/pred/actual.
- `stage_correlations.csv` (74): observed residual (rate − season league rate) across the last
  window per player, PA-weighted, correlated between stages within role — a proxy for talent
  correlation that Fable M2c can compare with an eventual posterior version.
- `pt_summary.csv` (26): Marcel PT vs actual PA/IP by age×prior-PT bucket for target=2025 (the
  last complete season); includes share_zero_actual per bucket.
Acceptance: every file exists ✓, CONTEXT.md 143/400 lines ✓, every CSV under the 2,000-row cap ✓,
`make test` 29/29 ✓.

### P6 Tier 3 backtest — `make backtest TIER=3` (Daniel, 2026-09-17)
- Runs 3 mapped stages (H/hr, H/hit_bip, P/hr) with the Statcast indicator likelihood at
  target_accept 0.95; other stages stay Tier 2 within the same run. Rows merged into
  `backtest.json` alongside the Tier 2 rows.
- PA-weighted RMSE, averaged over 2021–2024:

      HITTERS   marcel   tier2    tier3    last  league
      k_pct     0.0363   0.0350   0.0350  0.0468 0.0593
      bb_pct    0.0199   0.0204   0.0204  0.0284 0.0282
      hr_pct    0.0124   0.0155   0.0171  0.0169 0.0157
      babip     0.0332   0.0318   0.0327  0.0605 0.0353
      woba      0.0334   0.0364   0.0400  0.0520 0.0371

      PITCHERS  marcel   tier2    tier3    last  league
      k_pct     0.0400   0.0397   0.0397  0.0518 0.0526
      bb_pct    0.0206   0.0220   0.0220  0.0344 0.0247
      hr_pct    0.0109   0.0107   0.0118  0.0191 0.0113
      babip     0.0334   0.0326   0.0326  0.0613 0.0329
      fip       0.7947   0.8196   0.8672  1.3123 0.8732

- Gates (rerun with the merged table): **H tier3 FAIL** (0/4 vs tier2, cov80 .77);
  **P tier3 FAIL** (0/4 vs tier2, cov80 .72). Sampler health improved a lot —
  H/hit_bip max r_hat 1.04 (was 1.23), total divergences 96 across 48 fits (was 313) —
  target_accept .95 works, but the point projection on the three mapped stages is worse,
  not better, on the dev targets. Tier 3 does not ship. `production_tier` stays
  **H = marcel**, **P = marcel** — the §6 Marcel-points-with-Tier-2-bands fallback still holds.
  Real finding for Fable M2: Statcast helped calibration and geometry, but Barrel/Attempts
  as a linear indicator on the same theta apparently drags HR% projections toward the
  Statcast rate faster than Marcel's raw-count regression does, and hitters' Barrel% is
  itself noisy over 4 seasons. Something to iterate on, not a tuning failure.

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

## Gates / production tier (from `data/artifacts/backtest.json` = promoted E5E6 run, 2026-09-18)
- **Hitters: Marcel** — Tier 2 (locked config) fails on accuracy only: 2/4 targets beat Marcel
  on wOBA RMSE (need 3), though the 4-year mean is better (.0328 vs .0334). cov80 .819 ✓.
- **Pitchers: Marcel** — Tier 2 fails: 1/4 targets beat Marcel on FIP RMSE (mean .8164 vs
  .7947). cov80 .761 ✓ — both roles in band for the first time.
- Per MANUAL §6, production ships **Marcel points with Tier 2 bands**, and the Methodology page
  must say so plainly. Bands, aging drift and waterfall come from the locked config after the
  next `make project`.
- Tier 3: not in the promoted file. It was last evaluated pre-M2 on the old config (FAIL for both
  roles), and those rows are archived in `data/artifacts/m2/backtest_base.json`.
- Holdout 2025: **unspent**, authorised once now (see Next commands).

## Decisions (one line each: date — decision — why)
- 2026-09-18 — M3 wiring (Opus): the outlook's "if he plays" PT is pt_expected / p_play from the same simulation, so the expected line = p_play × conditional exactly. Counts = posterior-mean rate × PT. Pitchers show IP only, because K counts would need a per-player BF/IP conversion the artifacts don't carry. `pt-backtest` refuses targets ≥ 2025.
- 2026-09-17 — Fable budget re-split: cut the research-memo and hiring-manager-review missions (writing and judgement Daniel/Opus can do), moved the $30 into model research (M2 now 3 sessions, $55), playing time ($20) and a new ML-challenger mission ($10) — Fable is reserved for modelling and statistics only.
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
- 2026-09-17 — P5: no state library, no CSS framework, no chart library besides recharts (§2). All state in local `useState`; router state via `useSearchParams` for the H/P role toggle so a two-way player's URL is shareable.
- 2026-09-17 — P5: FanChart draws range areas via Recharts `Area dataKey="band80"` with `[q10, q90]` tuples (Recharts renders two-element arrays as ranges). History dots sized by PA (2.5–6 px radius). Vertical divider at `window_end + 0.5` so it sits between window_end and h=1.
- 2026-09-17 — P5: Vite proxy `/api → http://127.0.0.1:8000` (§9); CORS on the API is already set to `http://localhost:5173`. No `.env` file — the proxy target is hard-coded because the API always runs on that port locally per the Makefile.
- 2026-09-17 — P6 Tier 3 gate: FAILS for both roles (0/4 wins vs Tier 2 on the key stat). `production_tier` stays `marcel` for H and P — same Marcel-points-with-Tier-2-bands shipping mode as after Phase 2. Recorded as measured, no tuning; the delta is a Fable M2 research finding, not a bug.
- 2026-09-17 — P6.5: diagnostics is artifact-consuming only (no model fits) so it stays cheap and re-runnable after every Fable handoff. Every file listed in FABLE_MISSIONS.md §3 is emitted; columns that need per-player Tier 2/3 posteriors are left null and the CONTEXT.md "gaps" section names the one HANDOFF item (`backtest_predictions.parquet` + `backtest_posteriors.parquet` from backtest.py) that unlocks them. Chosen over re-fitting because a full backtest is a Daniel job.
- 2026-09-17 — P6.5: pit_histograms.csv uses a normal-approx PIT (Φ((actual − pred) / RMSE_scale)) pooled across dev targets for Marcel. Called out in the CSV's `note` column and in CONTEXT.md; real posterior-predictive PIT for Tier 2/3 lands after the sidecar exists.
- 2026-09-17 — P6.5: stage_correlations.csv uses observed residual (rate − season league rate) as the talent proxy; the "correlated stages" question is really about the model posterior, which needs the sidecar. This proxy is the honest read from data alone.

- 2026-09-17 — M1: backtest scores Tier 2/3 park stages in the player's T-1 park (park-aware) by default — park-neutral scoring handicapped only Tier 2 vs a park-inheriting Marcel; `--park-neutral` preserves the old behaviour; gates re-decided by Daniel's re-run, not edited by hand.
- 2026-09-18 — M2c wiring: the locked config (obs-noise + env shock) is the default everywhere (`backtest.py` functions, the `backtest`/`holdout`/`project` CLIs, `project.py`) with opt-outs back to the pre-M2 model; `project` offers only shock/mean3 because recency was rejected.
- 2026-09-18 — M2c wiring: `holdout` refuses to run unless its flags match `backtest.json.experiment_flags`. The holdout is one-shot, and a mismatch means scoring a model the gates weren't decided on (which the unwired holdout would have done).
- 2026-09-18 — M2c promotion: the superseded post-M1 baseline backtest (JSON + untracked sidecars, incl. the pre-M2 tier3 rows) is archived under `data/artifacts/m2/backtest_base*` rather than discarded, because the M2 verdicts cite its numbers.
- 2026-09-18 — M2c holdout spent: attempt 2 ran the locked config clean (guard passed). Recorded as measured: tier2 beats Marcel on neither 2025 key stat (H −.0004, P −.0082) but cov80 is in band on both (.83/.75) — shipping mode (Marcel points + Tier 2 bands) unchanged and now holdout-validated on its calibration claim. No tuning, no re-run, M2 closed.
- 2026-09-18 — M3: PT hurdle ships (pre-registered RMSE gate, 8/8 dev targets vs Marcel PT; 2025 untouched). Multi-year outlook = expected production (p_play × conditional) alongside conditional lines; h2–h4 intervals labelled model-implied per artifact check A + M3 doc §5. Missed-time proxy kept but near-zero coefficient once s1/s2 in the model — recorded, not re-tuned.
- 2026-09-18 — M2c holdout ruling: attempt 1 (14:53) scored the superseded config because the run raced the wiring commit — ruled invalid, holdout NOT spent; one locked-config re-run authorised with pre-commitments recorded (config ships regardless of the now-leaked old-vs-new 2025 comparison; no modelling decision changes on the misfire numbers; spent after the re-run whatever it says).
- 2026-09-18 — M2c: production configuration locked = tier2 `--obs-noise --env-mode shock` (the `backtest_E5E6.json` run, seed 1) — E5 and E6 passed every pre-registered sub-check; E3 rejected (core sub-check unverifiable + r_hat 1.363 + gain subsumed by E5); `--innov t4` declined (relabelling reappears under obs-noise, no geometry win); correlated stages declined with reasons (weak observed corr, binding losses are regime errors, rebuild cost). Gates still FAIL → Marcel points + Tier 2 bands; holdout runs the locked config after Opus wires the flags.
- 2026-09-18 — M2c: on hitters the 4-year mean RMSE (.0328 vs Marcel .0334, better in all 4 years vs base) and the per-year gate (2/4) disagree; recorded the argument that the mean measures skill better, but left the pre-registered gate unmoved for this decision.
- 2026-09-18 — M2b: E2 and E4 rejected against their pre-registered rules (no goalpost moves); E4's variance-conservation finding redirects M1-F4 to a transient obs-noise term (E5) and E2's validated shock half survives as E6; E4's geometry gain deferred to M2c rather than shipped mid-stream, so E5/E6 are judged against a stable baseline.
- 2026-09-17 — M2a: three upgrades behind backtest flags, all default-off, pre-registered in `docs/fable/M2_experiments.md` before any run — E2 `--env-mode recency` (recency+size-weighted league forecast + common env shock in projection draws), E3 `--rp-effect` (SP/RP covariate on P stages, T-1 role projected forward), E4 `--innov t4` (Student-t(4) talent innovations, nu fixed, projection noise matched). Full runs write to `data/artifacts/m2/` so `backtest.json` and the gates stay untouched until M2b accepts; production `project.py` wiring is a HANDOFF item gated on M2b.

## Questions for Fable (M3 follow-up) — Opus 2026-09-18, found while wiring; ANSWERED by Fable 2026-09-18

Both answered in `docs/fable/M3_playing_time.md` §7–§8 (pre-registered, dev targets only, 2025
untouched). (1) A talent covariate (guts-based wOBA / FIP-core deviation from seasons ≤ T−1,
ballast 600 PA / 180 IP) was **ACCEPTED 8/8** vs the shipped hurdle (H RMSE 156.8/141.5/144.0/142.7
→ 154.1/135.7/138.2/139.1; P 35.1/35.7/34.7/36.9 → 34.9/34.9/33.6/36.6); Judge h1 p_play .78 → .96,
pt_expected 258 → 545. New caveat, recorded not patched: old stars' pt_expected can *rise* with
horizon (simulated healthy seasons replace the depressed observed PT). Wiring = one open HANDOFF
item (two one-line call changes + Methodology copy). (2) Verdict: the lower number was **not**
correct for hitter regulars — Marcel's +126 PA bias lives in fringe/old players; in the regulars
bucket Marcel is nearly unbiased (+4 PA) and the base hurdle was −65 PA (talent omission, same
root cause as (1)); talent cuts it to −18. For pitcher regulars the hurdle was right and Marcel
over-projects (+27 IP). Per-bucket table is in §8. Original questions kept below for the record.
Measured on real data with the wired `pt_outlook_frame` (projection season 2027, seed 1):
1. **Stars in their mid-30s after a short season.** Judge (285 PA in 2026 after 679, age 35 in 2027):
   h1 p_play .78, pt_expected 258 (Marcel 410), p_play .52/.28/.17 at h2–h4. The hurdle has no
   talent covariate, only PT history and a quadratic in age. Should a good hitter's rate (e.g.
   Marcel wOBA) enter X? That is a new pre-registration, not a tweak.
2. **Regulars sit ~11% under Marcel.** Across 44 hitters with ≥600 PA in 2025 and ≥550 in 2026,
   median pt_expected is 0.89× Marcel and 61% land within ±15%. The HANDOFF acceptance asked for
   ±15%. Dropping the partial-2026 outcome from training barely moves it (0.894). The partial 2026
   *features* (season ~95% complete) remain a candidate cause; re-check after the season ends.
   Marcel's own overall bias is +126 PA, so under Marcel for regulars may simply be right. Is
   there a per-bucket (regulars) bias table from the dev backtest?

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
