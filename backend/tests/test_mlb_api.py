"""Offline parsing test: fake responses shaped exactly like the live Stats API (checked 2026-09-17)."""
import pandas as pd

from keystone.data import mlb_api


def fake_get(path, params, season=None):
    if path == "/teams":
        return {"teams": [{"id": 147, "abbreviation": "NYY", "venue": {"id": 3313, "name": "Yankee Stadium"}},
                          {"id": 146, "abbreviation": "MIA", "venue": {"id": 4169, "name": "loanDepot park"}}]}
    if path == "/stats":
        pa = {147: 191, 146: 430}[params["teamId"]]
        team_name = {147: "New York Yankees", 146: "Miami Marlins"}[params["teamId"]]
        return {"stats": [{"totalSplits": 1, "splits": [{
            "season": "2024", "numTeams": 2,
            "stat": {"plateAppearances": pa, "homeRuns": 11, "avg": ".256", "strikeOuts": 40},
            "team": {"id": params["teamId"], "name": team_name},
            "player": {"id": 665862, "fullName": "Jazz Chisholm Jr."}}]}]}
    if path == "/people":
        return {"people": [{"id": 665862, "fullName": "Jazz Chisholm Jr.", "birthDate": "1998-02-01",
                            "primaryPosition": {"abbreviation": "2B"}, "batSide": {"code": "L"},
                            "pitchHand": {"code": "R"}, "mlbDebutDate": "2020-09-01"}]}
    raise AssertionError(path)


def test_parsing(monkeypatch):
    monkeypatch.setattr(mlb_api, "_get", fake_get)
    t = mlb_api.teams(2024)
    assert set(t.venue_id) == {3313, 4169}
    s = mlb_api.player_team_stats(2024, "hitting")
    assert s.groupby("mlbam_id").plateAppearances.sum().loc[665862] == 621
    assert s.sacFlies.eq(0).all()                      # missing fields default to 0
    ppl = mlb_api.people([665862])
    assert ppl.primary_pos.iloc[0] == "2B"
    ages = mlb_api.season_age(pd.Series(["1998-02-01", "1994-07-05"]), pd.Series([2024, 2024]))
    assert list(ages) == [26, 29]                     # Ohtani born July 5 -> 29 on June 30, 2024
