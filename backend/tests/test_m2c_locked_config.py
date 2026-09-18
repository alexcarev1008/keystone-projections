"""M2c locked config (docs/fable/M2_experiments.md): obs-noise + env shock are the CLI defaults
for backtest / holdout / project, and the holdout refuses to score a config the dev gates
were not decided on."""
import json

import pytest

from keystone import pipeline
from keystone import project as proj
from keystone.eval import backtest as bt

LOCKED = dict(env_mode="shock", rp_effect=False, innov="normal", obs_noise=True)


@pytest.fixture
def calls(monkeypatch):
    seen = []
    monkeypatch.setattr(bt, "run", lambda **kw: seen.append(("bt", kw)))
    monkeypatch.setattr(proj, "run", lambda **kw: seen.append(("proj", kw)))
    return seen


def test_backtest_defaults_to_locked_config(calls):
    pipeline.main(["backtest", "--quick"])
    kw = calls[-1][1]
    assert {k: kw[k] for k in LOCKED} == LOCKED


def test_backtest_opt_outs_and_legacy_flag(calls):
    pipeline.main(["backtest", "--quick", "--no-obs-noise", "--env-mode", "mean3"])
    assert (calls[-1][1]["obs_noise"], calls[-1][1]["env_mode"]) == (False, "mean3")
    pipeline.main(["backtest", "--quick", "--obs-noise", "--env-mode", "shock"])   # M2 commands
    assert (calls[-1][1]["obs_noise"], calls[-1][1]["env_mode"]) == (True, "shock")


def test_project_defaults_to_locked_config(calls):
    pipeline.main(["project", "--quick"])
    assert (calls[-1][1]["obs_noise"], calls[-1][1]["env_mode"]) == (True, "shock")
    pipeline.main(["project", "--quick", "--no-obs-noise", "--env-mode", "mean3"])
    assert (calls[-1][1]["obs_noise"], calls[-1][1]["env_mode"]) == (False, "mean3")


def _dev_backtest(tmp_path, flags):
    p = tmp_path / "backtest.json"
    p.write_text(json.dumps({"targets": [2024], "holdout_target": None,
                             "experiment_flags": flags, "rows": [],
                             "gates": {"H": {"tier2": {"pass": False}, "tier3": None}},
                             "production_tier": {"H": "marcel", "P": "marcel"}}))
    return p


def test_holdout_passes_locked_flags(calls, tmp_path):
    p = _dev_backtest(tmp_path, LOCKED)
    pipeline.main(["holdout", "--out", str(p)])
    who, kw = calls[-1]
    assert who == "bt" and kw["holdout"] is True and kw["targets"] == [2025]
    assert {k: kw[k] for k in LOCKED} == LOCKED


@pytest.mark.parametrize("dev_flags", [None, dict(LOCKED, env_mode="mean3", obs_noise=False)])
def test_holdout_refuses_config_mismatch(calls, tmp_path, dev_flags):
    p = _dev_backtest(tmp_path, dev_flags)
    with pytest.raises(SystemExit, match="does not match the dev backtest"):
        pipeline.main(["holdout", "--out", str(p)])
    assert calls == []
