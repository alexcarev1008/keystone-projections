"""FastAPI TestClient checks against a hand-built fixture artifact set (MANUAL.md §8).

The fixtures cover the smallest interesting cases: a hitter, a pitcher, a two-way player, and
one player who exists in `players.parquet` but has no projection rows (should still resolve).
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from keystone.api.main import create_app


HORIZONS = [1, 2, 3, 4]
H_STATS = ["woba", "k_pct", "bb_pct", "hr_pct", "babip"]
P_STATS = ["fip", "k_pct", "bb_pct", "hr_pct", "babip"]
BIO_COLS = ["mlbam_id", "name", "roles", "primary_pos", "bats", "throws",
            "birth_date", "last_team_abbr", "last_season"]


def _projection_rows(pid: int, role: str, base: dict[str, float]) -> list[dict]:
    """Emit one row per (horizon, stat) with q10..q90 spread around a per-stat mean."""
    rows = []
    for h in HORIZONS:
        for stat, mu in base.items():
            drift = 0.0 if stat == "woba" or stat == "fip" else 0.0
            m = mu + 0.001 * (h - 1)
            spread = 0.05 * m if role == "H" else 0.03 * m
            q10, q25, q50, q75, q90 = m - spread, m - spread / 2, m, m + spread / 2, m + spread
            rows.append({"mlbam_id": pid, "role": role, "season": 2026 + h,
                         "horizon": h, "age": 28 + h, "stat": stat,
                         "mean": m, "q10": q10, "q25": q25, "q50": q50, "q75": q75, "q90": q90,
                         "tier": "tier2",
                         "pt": (500.0 if role == "H" else 150.0) if h == 1 else None,
                         # M3 PT outlook; player 3 is outside the PT population (NaN)
                         "p_play": None if pid == 3 else 0.9 - 0.1 * h,
                         "pt_expected": None if pid == 3 else 450.0 - 50.0 * h,
                         "p_regular": None if pid == 3 else 0.8 - 0.1 * h})
    return rows


@pytest.fixture(scope="module")
def artifacts(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("artifacts")

    players = pd.DataFrame([
        {"mlbam_id": 1, "name": "Andrés Jiménez", "roles": "H", "primary_pos": "OF",
         "bats": "L", "throws": "R", "birth_date": "1996-04-01",
         "last_team_abbr": "WSH", "last_season": 2026},
        {"mlbam_id": 2, "name": "Bobby Pitcher", "roles": "P", "primary_pos": "P",
         "bats": "R", "throws": "R", "birth_date": "1993-08-15",
         "last_team_abbr": "LAD", "last_season": 2026},
        {"mlbam_id": 3, "name": "Two Way", "roles": "HP", "primary_pos": "TWP",
         "bats": "L", "throws": "R", "birth_date": "1994-07-05",
         "last_team_abbr": "LAA", "last_season": 2026},
        {"mlbam_id": 4, "name": "Ghost Player", "roles": "H", "primary_pos": "IF",
         "bats": "R", "throws": "R", "birth_date": "1999-01-01",
         "last_team_abbr": None, "last_season": None},
    ])
    players.to_parquet(out / "players.parquet", index=False)

    history_rows = []
    for pid, role in [(1, "H"), (3, "H"), (3, "P"), (2, "P")]:
        for season in (2024, 2025, 2026):
            row = {"mlbam_id": pid, "role": role, "season": season,
                   "team_abbr": "WSH", "age": 27 + (season - 2024),
                   "pa": 500 if role == "H" else 700,
                   "ip": None if role == "H" else 160.0,
                   "k_pct": 0.22, "bb_pct": 0.08, "hr_pct": 0.035, "babip": 0.300}
            if role == "H":
                row.update({"woba": 0.340})
            else:
                row.update({"fip": 3.80})
            history_rows.append(row)
    pd.DataFrame(history_rows).to_parquet(out / "history.parquet", index=False)

    proj_rows = []
    proj_rows += _projection_rows(1, "H", {"woba": 0.360, "k_pct": 0.22, "bb_pct": 0.09,
                                            "hr_pct": 0.040, "babip": 0.310})
    proj_rows += _projection_rows(3, "H", {"woba": 0.380, "k_pct": 0.24, "bb_pct": 0.10,
                                            "hr_pct": 0.050, "babip": 0.320})
    proj_rows += _projection_rows(2, "P", {"fip": 3.20, "k_pct": 0.28, "bb_pct": 0.07,
                                            "hr_pct": 0.028, "babip": 0.290})
    proj_rows += _projection_rows(3, "P", {"fip": 3.70, "k_pct": 0.25, "bb_pct": 0.08,
                                            "hr_pct": 0.035, "babip": 0.300})
    pd.DataFrame(proj_rows).to_parquet(out / "projections.parquet", index=False)

    wf_rows = []
    for pid, role, stat in [(1, "H", "woba"), (3, "H", "woba"),
                             (2, "P", "fip"), (3, "P", "fip")]:
        for step, label, val in [(0, "3-year line", 0.350),
                                  (1, "Regression", 0.360),
                                  (2, "Aging (age 29)", 0.358),
                                  (3, "Statcast", 0.358),
                                  (4, "Neutral-park", 0.358),
                                  (5, "At home park", 0.362)]:
            wf_rows.append({"mlbam_id": pid, "role": role, "stat": stat,
                            "step": step, "label": label, "value": val})
    pd.DataFrame(wf_rows).to_parquet(out / "waterfall.parquet", index=False)

    aging_rows = []
    for role, stats in (("H", H_STATS), ("P", P_STATS)):
        for stat in stats:
            for age in range(20, 41):
                aging_rows.append({"role": role, "stat": stat, "age": age,
                                   "value": 0.010 * (age - 27) + 0.3})
    pd.DataFrame(aging_rows).to_parquet(out / "aging.parquet", index=False)

    league_rows = []
    for role, stats in (("H", H_STATS), ("P", P_STATS)):
        for season in (2025, 2026, 2027):
            for stat in stats:
                league_rows.append({"role": role, "season": season, "stat": stat,
                                     "value": 0.310 if stat == "woba" else
                                              3.90 if stat == "fip" else 0.22})
    pd.DataFrame(league_rows).to_parquet(out / "league.parquet", index=False)

    meta = {"generated_at": "2026-09-17T00:00:00+00:00", "data_through": "2026-09-17",
            "window_end": 2026, "projection_season": 2027, "horizons": 4,
            "production_tier": {"H": "tier2", "P": "tier2"},
            "stages": {"H/k": {"tau_mean": 0.1, "sigma_pop_mean": 0.3,
                                "park_sd_mean": None, "max_rhat": 1.01, "divergences": 0}},
            "max_rhat": 1.01, "total_divergences": 0}
    (out / "meta.json").write_text(json.dumps(meta))

    backtest = {"generated_at": "2026-09-17", "targets": [2024], "holdout_target": 2025,
                "rows": [], "gates": {"H": {"tier2": {"pass": False}, "tier3": None},
                                       "P": {"tier2": {"pass": False}, "tier3": None}},
                "production_tier": {"H": "tier2", "P": "tier2"}}
    (out / "backtest.json").write_text(json.dumps(backtest))
    return out


@pytest.fixture(scope="module")
def client(artifacts) -> TestClient:
    return TestClient(create_app(artifacts))


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_meta_bundles_backtest(client):
    r = client.get("/api/meta")
    assert r.status_code == 200
    body = r.json()
    assert "meta" in body and "backtest" in body
    assert body["meta"]["projection_season"] == 2027
    assert body["backtest"]["production_tier"] == {"H": "tier2", "P": "tier2"}


def test_search_case_and_accent_insensitive(client):
    r = client.get("/api/search", params={"q": "andres", "limit": 5}).json()
    assert any(row["mlbam_id"] == 1 for row in r)
    r = client.get("/api/search", params={"q": "ANDRES"}).json()
    assert any(row["mlbam_id"] == 1 for row in r)
    r = client.get("/api/search", params={"q": "jimen"}).json()
    assert any(row["mlbam_id"] == 1 for row in r)


def test_search_empty_query_returns_empty(client):
    assert client.get("/api/search", params={"q": ""}).json() == []


def test_search_limit_applied(client):
    r = client.get("/api/search", params={"q": "a", "limit": 2}).json()
    assert len(r) <= 2


def test_leaderboard_hitter_defaults(client):
    r = client.get("/api/leaderboard", params={"role": "H"}).json()
    assert len(r) >= 1
    top = r[0]
    for k in ("mlbam_id", "name", "team", "age", "pt"):
        assert k in top
    for stat in H_STATS:
        assert stat in top
        assert {"q10", "q50", "q90"} <= set(top[stat].keys())
    q50s = [row["woba"]["q50"] for row in r]
    assert q50s == sorted(q50s, reverse=True)


def test_leaderboard_pitcher_defaults(client):
    r = client.get("/api/leaderboard", params={"role": "P"}).json()
    assert len(r) >= 1
    q50s = [row["fip"]["q50"] for row in r]
    assert q50s == sorted(q50s)  # asc default


def test_leaderboard_min_pt_filter(client):
    r = client.get("/api/leaderboard", params={"role": "H", "min_pt": 10000}).json()
    assert r == []


def test_leaderboard_bad_role(client):
    r = client.get("/api/leaderboard", params={"role": "X"})
    assert r.status_code == 400


def test_player_full_shape_hitter(client):
    r = client.get("/api/players/1")
    assert r.status_code == 200
    body = r.json()
    assert set(body.keys()) == {"bio", "role", "history", "projections",
                                 "pt", "playing_time", "waterfall", "aging", "league"}
    assert body["role"] == "H"
    for col in BIO_COLS:
        assert col in body["bio"]
    assert body["pt"] == 500.0
    assert len(body["history"]) == 3
    assert set(body["projections"].keys()) >= set(H_STATS)
    for row in body["projections"]["woba"]:
        assert {"season", "horizon", "age", "q10", "q25", "q50", "q75", "q90"} <= row.keys()
    assert len(body["waterfall"]) == 6
    assert set(body["aging"].keys()) == set(H_STATS)
    assert set(body["league"].keys()) >= set(H_STATS)


def test_player_default_role_two_way(client):
    r = client.get("/api/players/3").json()
    assert r["role"] == "H"
    r_p = client.get("/api/players/3", params={"role": "P"}).json()
    assert r_p["role"] == "P"
    assert "fip" in r_p["projections"]


def test_player_role_not_available(client):
    r = client.get("/api/players/1", params={"role": "P"})
    assert r.status_code == 404


def test_player_missing_returns_404(client):
    assert client.get("/api/players/999999").status_code == 404


def test_player_with_no_projections_still_resolves(client):
    r = client.get("/api/players/4")
    assert r.status_code == 200
    body = r.json()
    assert body["projections"] == {}
    assert body["pt"] is None
    assert body["playing_time"] == []
    assert body["history"] == []


def test_player_playing_time_per_horizon(client):
    pt = client.get("/api/players/1").json()["playing_time"]
    assert [r["horizon"] for r in pt] == HORIZONS
    assert pt[0]["season"] == 2027 and pt[0]["age"] == 29
    assert pt[0]["p_play"] == pytest.approx(0.8)
    assert pt[3]["pt_expected"] == pytest.approx(250.0)
    assert pt[3]["p_regular"] == pytest.approx(0.4)


def test_player_playing_time_outside_population_is_null(client):
    pt = client.get("/api/players/3").json()["playing_time"]
    assert len(pt) == 4
    assert all(r["p_play"] is None and r["pt_expected"] is None and r["p_regular"] is None for r in pt)
