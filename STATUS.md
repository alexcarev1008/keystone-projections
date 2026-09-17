# KEYSTONE — STATUS

## Stage A — Opus builds (MANUAL.md §10)
- [ ] P0 Setup (Daniel): `make setup`, `make test` (7 pass), fg_guts.csv saved, git init
- [ ] P1 Data layer
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
- `make setup && make test`

## Results (paste summaries here, ≤ 30 lines each)

## Gates / production tier
- Hitters: TBD · Pitchers: TBD

## Decisions (one line each: date — decision — why)
- 2026-09-17 — Reference model verified on simulated data (0 divergences, 80% coverage 0.83) — MANUAL §5.3
- 2026-09-17 — Opus builds all phases; Fable is reserved for M1–M5 research missions — FABLE_MISSIONS.md §1

## Blockers
- none
