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


# Holdout attempt 1 regression (M2_experiments.md §"The 2025 holdout"): the old-config run reached
# bt.run(holdout=True) directly and stamped its flags over the promoted dev file. The writer
# itself must refuse, before loading, fitting or writing anything.

OLD = dict(LOCKED, env_mode="mean3", obs_noise=False)


@pytest.fixture
def fits(monkeypatch):
    """Real bt.run, stubbed data load + per-target fit; records how far a run got."""
    seen = []
    monkeypatch.setattr(bt, "load_bundle", lambda: seen.append("load"))

    def run_target(b, role, target, *a, **kw):
        seen.append((target, role))
        return [], [], []
    monkeypatch.setattr(bt, "run_target", run_target)
    return seen


@pytest.mark.parametrize("dev_flags", [OLD, None])
def test_writer_refuses_holdout_on_mismatched_dev_file(fits, tmp_path, dev_flags):
    p = _dev_backtest(tmp_path, dev_flags)
    before = p.read_bytes()
    with pytest.raises(SystemExit, match="holdout refused"):
        bt.run(targets=[2025], holdout=True, out=p)                  # locked-config defaults
    assert fits == []
    assert p.read_bytes() == before
    assert [f.name for f in tmp_path.iterdir()] == ["backtest.json"]  # no sidecars written


def test_writer_holdout_proceeds_when_flags_match(fits, tmp_path):
    p = _dev_backtest(tmp_path, LOCKED)
    payload = bt.run(targets=[2025], holdout=True, out=p)
    assert fits == ["load", (2025, "H"), (2025, "P")]
    assert payload["holdout_target"] == 2025 and payload["experiment_flags"] == LOCKED


def test_writer_rechecks_flags_before_writing(fits, tmp_path, monkeypatch):
    p = _dev_backtest(tmp_path, LOCKED)
    (tmp_path / "swap").mkdir()
    swapped = _dev_backtest(tmp_path / "swap", OLD).read_bytes()

    def run_target(*a, **kw):                     # the dev file is replaced during the fit
        p.write_bytes(swapped)
        return [], [], []
    monkeypatch.setattr(bt, "run_target", run_target)
    with pytest.raises(SystemExit, match="holdout refused"):
        bt.run(targets=[2025], holdout=True, out=p)
    assert p.read_bytes() == swapped


def test_cli_holdout_refuses_mismatch_end_to_end(fits, tmp_path):
    """Through pipeline.main with the real bt.run: the CLI guard (not the writer's) fires first."""
    p = _dev_backtest(tmp_path, OLD)
    before = p.read_bytes()
    with pytest.raises(SystemExit, match=r"\[holdout\] model config .* does not match"):
        pipeline.main(["holdout", "--out", str(p)])
    assert fits == []
    assert p.read_bytes() == before
