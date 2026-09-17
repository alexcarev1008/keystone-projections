"""Offline parsing test: fake responses shaped exactly like the live Stats API (checked 2026-09-17)."""
import pandas as pd

from keystone.data import mlb_api


def fake_get(path, params, season=None):
    if path == "/teams":
        return {"teams": [{"id": 147, "abbreviation": "NYY", "venue": {"id": 3313, "name": "Yankee Stadium"}},
                          {"id": 146, "abbreviation": "MIA", "venue": {"id": 4169, "name": "loanDepot park"}}]}
    if path == "/stats":                      # bulk: one row per player, season totals, team = last team
        assert "teamId" not in params, "teamId-filtered stats undercount - see MANUAL.md 4.1"
        if params["offset"] >= 2:
            return {"stats": [{"totalSplits": 2, "splits": []}]}
        return {"stats": [{"totalSplits": 2, "splits": [
            {"season": "2024", "numTeams": 2,
             "stat": {"plateAppearances": 621, "homeRuns": 24, "strikeOuts": 145},
             "team": {"id": 147, "name": "New York Yankees"},
             "player": {"id": 665862, "fullName": "Jazz Chisholm Jr."}},
            {"season": "2024", "numTeams": 1,
             "stat": {"plateAppearances": 713, "homeRuns": 41, "strikeOuts": 119},
             "team": {"id": 147, "name": "New York Yankees"},
             "player": {"id": 665742, "fullName": "Juan Soto"}}]}]}
    if path == "/people/665862/stats":        # per-team splits: totals split has no team key
        return {"stats": [{"splits": [
            {"stat": {"plateAppearances": 621}, "numTeams": 2},
            {"stat": {"plateAppearances": 430}, "team": {"id": 146, "name": "Miami Marlins"}},
            {"stat": {"plateAppearances": 191}, "team": {"id": 147, "name": "New York Yankees"}}]}]}
    if path == "/people":
        return {"people": [{"id": 665862, "fullName": "Jazz Chisholm Jr.", "birthDate": "1998-02-01",
                            "primaryPosition": {"abbreviation": "2B"}, "batSide": {"code": "L"},
                            "pitchHand": {"code": "R"}, "mlbDebutDate": "2020-09-01"}]}
    raise AssertionError(path)


def test_parsing(monkeypatch):
    monkeypatch.setattr(mlb_api, "_get", fake_get)
    t = mlb_api.teams(2024)
    assert set(t.venue_id) == {3313, 4169}

    s = mlb_api.player_season_stats(2024, "hitting")
    assert len(s) == 2 and not s.mlbam_id.duplicated().any()
    row = s.set_index("mlbam_id").loc[665862]
    assert row.plateAppearances == 621 and row.num_teams == 2 and row.last_team_id == 147
    assert s.sacFlies.eq(0).all()                       # missing fields default to 0

    sp = mlb_api.player_team_splits(665862, 2024, "hitting")
    assert len(sp) == 2 and sp.pa.sum() == 621          # totals split dropped, per-team splits kept
    assert set(sp.team_id) == {146, 147}

    ppl = mlb_api.people([665862])
    assert ppl.primary_pos.iloc[0] == "2B"
    ages = mlb_api.season_age(pd.Series(["1998-02-01", "1994-07-05"]), pd.Series([2024, 2024]))
    assert list(ages) == [26, 29]                       # Ohtani born July 5 -> 29 on June 30, 2024
