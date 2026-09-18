"""M4 challenger leakage guard (docs/fable/M4_ml_challenger.md §5, made permanent).

Mirror of test_backtest_leakage.py for `ml_challenger.fit_predict_stage`: tripling every
season-T count and shifting every season->=T league logit in the raw bundle must not change a
single GBM prediction, because `train_slice` guards the whole feature path.
"""
from __future__ import annotations

import numpy as np

from keystone.eval import backtest as BT
from keystone.eval import ml_challenger as ML
from tests.test_backtest_leakage import TARGET, _bundle, _player_seasons

COUNTS = ["plateAppearances", "strikeOuts", "baseOnBalls", "hitByPitch", "homeRuns", "hits",
          "doubles", "triples", "sacFlies"]


def _perturb(b: BT.Bundle) -> BT.Bundle:
    ps = b.ps["H"].copy()
    m = ps.season == TARGET
    ps.loc[m, COUNTS] = ps.loc[m, COUNTS] * 3
    lg = b.lg["H"].copy()
    lg.loc[lg.season >= TARGET, "logit"] += 1.0
    return BT.Bundle(ps={**b.ps, "H": ps}, exp=b.exp, lg={**b.lg, "H": lg}, guts=b.guts,
                     people=b.people)


def test_gbm_predictions_ignore_season_target_and_later():
    clean = _bundle(_player_seasons())
    poisoned = _perturb(clean)
    assert not poisoned.ps["H"].equals(clean.ps["H"]), "perturbation must change the bundle"
    ids = BT.eval_population(clean, "H", TARGET)
    assert len(ids) > 0
    hp = {**ML.HP_A, "max_iter": 50}
    for stage in ("k", "hr"):
        a = ML.fit_predict_stage(BT.train_slice(clean, TARGET), "H", stage, TARGET, ids, hp)
        c = ML.fit_predict_stage(BT.train_slice(poisoned, TARGET), "H", stage, TARGET, ids, hp)
        assert np.all(np.isfinite(a))
        assert np.array_equal(a, c), f"season-T data changed the GBM {stage} projection"
