"""M3 wiring: PT outlook join onto projections, and the pt-backtest CLI's holdout refusal."""
import numpy as np
import pandas as pd
import pytest

from keystone import pipeline
from keystone import project as P


def _proj():
    return pd.DataFrame([{"mlbam_id": pid, "role": role, "horizon": h, "stat": s,
                          "pt": 500.0 if h == 1 else np.nan}
                         for pid, role in [(1, "H"), (2, "H"), (1, "P")]
                         for h in (1, 2) for s in ("k_pct", "woba")])


def test_join_pt_outlook_left_join_nan_outside_population():
    pt = pd.DataFrame([{"mlbam_id": 1, "role": "H", "horizon": h, "p_play": .9 / h,
                        "pt_expected": 500.0 / h, "p_regular": .8 / h} for h in (1, 2)])
    out = P.join_pt_outlook(_proj(), pt)
    assert len(out) == 12
    h1 = out[(out.mlbam_id == 1) & (out.role == "H") & (out.horizon == 2)]
    assert (h1.pt_expected == 250.0).all() and (h1.p_play == .45).all()
    # player 2 and player 1's P role are outside the PT population -> NaN in all three columns
    rest = out[~((out.mlbam_id == 1) & (out.role == "H"))]
    assert rest[P.PT_COLS].isna().all().all()
    # Marcel pt column untouched
    pd.testing.assert_series_equal(out.pt, _proj().pt, check_names=False)


def test_join_pt_outlook_empty_projections_has_columns():
    out = P.join_pt_outlook(pd.DataFrame(), pd.DataFrame(columns=["mlbam_id", "role", "horizon"] + P.PT_COLS))
    assert set(P.PT_COLS) <= set(out.columns)


def test_pt_backtest_refuses_holdout_target(monkeypatch):
    import keystone.eval.backtest as bt
    monkeypatch.setattr(bt, "load_bundle", lambda: pytest.fail("must refuse before loading data"))
    with pytest.raises(SystemExit):
        pipeline.main(["pt-backtest", "--targets", "2024", "2025"])
