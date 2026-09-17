PY ?= python3
VENV := .venv
RUN := cd backend && PYTHONPATH=. ../$(VENV)/bin/python
TIER ?= 2

.PHONY: setup test verify-sim data backtest-quick backtest holdout project statcast diagnostics api web

setup:            ## Phase 0 (Daniel)
	$(PY) -m venv $(VENV)
	$(VENV)/bin/python -m pip install --upgrade pip
	$(VENV)/bin/python -m pip install -r backend/requirements.txt

test:             ## all backend tests (~20 s)
	$(RUN) -m pytest

verify-sim:       ## full-scale simulation check of the model (~2 min)
	$(RUN) scripts/verify_state_space_sim.py

data:             ## Phase 1 (Daniel, ~5-10 min)
	$(RUN) -m keystone.pipeline fetch --start 2015 --end 2026
	$(RUN) -m keystone.pipeline build --end 2026

backtest-quick:   ## Phase 2 smoke test (Fable, < 5 min)
	$(RUN) -m keystone.pipeline backtest --quick

backtest:         ## Phase 2 full dev backtest (Daniel, long)
	$(RUN) -m keystone.pipeline backtest --targets 2021 2022 2023 2024 --tier $(TIER)

holdout:          ## run ONCE after gates are recorded (Daniel)
	$(RUN) -m keystone.pipeline holdout --target 2025 --tier $(TIER)

project:          ## Phase 3 production artifacts (Daniel, long)
	$(RUN) -m keystone.pipeline project --window-end 2026 --horizons 4

statcast:         ## Phase 6 optional (Daniel)
	$(RUN) -m keystone.pipeline statcast --start 2015 --end 2026

diagnostics:      ## Phase 6.5: Fable context pack (re-run after every handoff)
	$(RUN) -m keystone.pipeline diagnostics --out ../docs/fable_context

api:              ## Phase 4
	cd backend && ../$(VENV)/bin/python -m uvicorn keystone.api.main:app --reload --port 8000

web:              ## Phase 5
	cd frontend && npm install && npm run dev
