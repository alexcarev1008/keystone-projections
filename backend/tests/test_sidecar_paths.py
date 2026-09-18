"""M2b HANDOFF item: experiment runs must not overwrite each other's sidecars."""
from pathlib import Path

from keystone.eval.backtest import sidecar_paths


def test_default_names_unchanged():
    pred, post = sidecar_paths(Path("data/artifacts/backtest.json"), quick=False)
    assert pred.name == "backtest_predictions.parquet"
    assert post.name == "backtest_posteriors.parquet"
    pred, post = sidecar_paths(Path("data/artifacts/backtest_quick.json"), quick=True)
    assert pred.name == "backtest_predictions_quick.parquet"
    assert post.name == "backtest_posteriors_quick.parquet"


def test_custom_out_gets_own_sidecars():
    e5, _ = sidecar_paths(Path("data/artifacts/m2/backtest_E5.json"), quick=False)
    e6, _ = sidecar_paths(Path("data/artifacts/m2/backtest_E5E6.json"), quick=False)
    assert e5.name == "backtest_E5_predictions.parquet"
    assert e6.name == "backtest_E5E6_predictions.parquet"
    assert e5 != e6
    q, _ = sidecar_paths(Path("x/custom.json"), quick=True)
    assert q.name == "custom_predictions.parquet"
