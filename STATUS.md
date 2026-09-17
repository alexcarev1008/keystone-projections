# KEYSTONE — STATUS

## Stage A — Opus builds (MANUAL.md §10)
- [ ] P0 Setup (Daniel): `make setup`, `make test` (7 pass), fg_guts.csv saved, git init
- [x] P1 Data layer
- [ ] P2 Backtest harness (Tier 1 + 2)
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
- `make data`   # fetch 2015–2026 + build all processed parquet (≈ 5–10 min, ~900 requests + a few hundred per-player splits per season)
- Paste the last ~20 lines of build output into "Results" below (per-season PA diff, modelled counts).
- Then Opus session for P2 (backtest harness).

## Results (paste summaries here, ≤ 30 lines each)

### P1 smoke test (fetch + build, 2024 only, agent-run)
- fetch: `2024: H=742 (traded 68) P=855 (traded 106) bios=1454`
- build sanity: player_PA=182,449 == team_totals_PA=182,449 (0.0000% diff)
- modelled H 2024: 649 (≥ 600 OK), modelled P 2024: 802 (≥ 600 OK)
- 10 processed parquet files written under `data/processed/`
- pytest: 7/7 pass

## Gates / production tier
- Hitters: TBD · Pitchers: TBD

## Decisions (one line each: date — decision — why)
- 2026-09-17 — Reference model verified on simulated data (0 divergences, 80% coverage 0.83) — MANUAL §5.3
- 2026-09-17 — Opus builds all phases; Fable is reserved for M1–M5 research missions — FABLE_MISSIONS.md §1
- 2026-09-17 — P1: season totals use bulk /stats (no teamId); per-team splits pulled from /people/{id}/stats only for numTeams>1 — the teamId-filtered /stats undercounts (Chisholm 2024: 191 PA only, missed 430 MIA); MANUAL §4.1 now updated to match.
- 2026-09-17 — `league_{H,P}.parquet` = stage_league_rates (modelled pop) joined with sf_rate (H) / kappa+lg_era+c_fip on all pitchers unfiltered (P). Guts stored raw as `guts.parquet`; the "latest available row" fallback for missing seasons happens at lookup time in downstream code.

## Blockers
- none
