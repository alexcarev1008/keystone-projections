"""Tier 3 plumbing (MANUAL.md §5.4).

Covers the three seams Phase 6 adds:
  1. `statcast.load_indicator` maps only the three stages in §5.4; other stages return None.
  2. `backtest.tier3_indicators` strips any indicator row at or after the target season, so the
     Statcast likelihood cannot leak information back through Tier 3.
  3. When an indicator is passed, `state_space.build_model` adds the `a_ind`/`b_ind` variables and
     the second `Binomial('ind', ...)` — i.e. the indicator likelihood is wired, not silently
     ignored. Fit behaviour (target_accept 0.95) is asserted at the caller.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from keystone.data import statcast as SC
from keystone.eval import backtest as BT
from keystone.models import state_space as SS


def _fake_statcast(path):
    """Write a minimal statcast_H.parquet with a row per (mlbam_id, season) for 2020..2024."""
    rows = []
    for s in range(2020, 2025):
        for pid in range(1000, 1005):
            rows.append({"mlbam_id": pid, "season": s, "attempts": 200,
                         "barrels": 20, "ev95plus": 60})
    pd.DataFrame(rows).to_parquet(path / "statcast_H.parquet", index=False)


def test_load_indicator_maps_the_three_tier3_stages(tmp_path):
    _fake_statcast(tmp_path)

    hr = SC.load_indicator("H", "hr", processed=tmp_path)
    assert set(hr.columns) == {"mlbam_id", "season", "ind_y", "ind_n"}
    assert (hr.ind_y == 20).all() and (hr.ind_n == 200).all()

    bip = SC.load_indicator("H", "hit_bip", processed=tmp_path)
    assert (bip.ind_y == 60).all() and (bip.ind_n == 200).all()

    for stage in ("k", "bb", "hbp", "xbh", "triple"):
        assert SC.load_indicator("H", stage, processed=tmp_path) is None

    assert SC.load_indicator("P", "hr", processed=tmp_path) is None   # file missing


def test_load_indicator_drops_rows_with_no_denominator(tmp_path):
    df = pd.DataFrame([{"mlbam_id": 1, "season": 2024, "attempts": 0, "barrels": 0, "ev95plus": 0},
                       {"mlbam_id": 2, "season": 2024, "attempts": 10, "barrels": 1, "ev95plus": 2}])
    df.to_parquet(tmp_path / "statcast_H.parquet", index=False)
    hr = SC.load_indicator("H", "hr", processed=tmp_path)
    assert list(hr.mlbam_id) == [2]


def test_tier3_indicators_strips_the_target_season(tmp_path, monkeypatch):
    _fake_statcast(tmp_path)
    monkeypatch.setattr(SC, "C", type("c", (), {"PROCESSED": tmp_path}))
    ind = BT.tier3_indicators("H", ["k", "hr", "hit_bip"], target=2024)
    assert set(ind.keys()) == {"hr", "hit_bip"}, "only §5.4 stages should have indicators"
    for stage, df in ind.items():
        assert df.season.max() < 2024, f"{stage} leaked season 2024 into the indicator"


def test_build_model_wires_indicator_when_asked():
    """The plumbing test: obs + ind columns → the pm.Model has an indicator likelihood."""
    rng = np.random.default_rng(0)
    obs = pd.DataFrame({
        "mlbam_id": np.repeat(np.arange(6), 3),
        "season": np.tile(np.arange(2021, 2024), 6),
        "age": np.tile([27, 28, 29], 6),
        "pa": np.full(18, 500),
        "y": rng.integers(80, 130, 18),
        "n": np.full(18, 500),
        "mu_league": np.full(18, -1.2),
        "ind_y": rng.integers(20, 50, 18),
        "ind_n": np.full(18, 200),
    })
    d = SS.build_stage_data(obs, window_end=2023, exposures=None)

    plain = SS.build_model(d, use_park=False, use_indicator=False)
    tier3 = SS.build_model(d, use_park=False, use_indicator=True)
    assert "a_ind" not in plain.named_vars and "b_ind" not in plain.named_vars
    for v in ("a_ind", "b_ind", "s_nu", "ind"):
        assert v in tier3.named_vars, f"indicator var {v!r} missing when use_indicator=True"
