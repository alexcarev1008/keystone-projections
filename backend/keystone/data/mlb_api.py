"""MLB Stats API client with on-disk cache.

Endpoints + field names were checked against live responses on 2026-09-17 (see MANUAL.md §4), but this file
has NOT been executed against the network yet — Phase 1 runs it. If something breaks, fix the smallest thing.

Key facts verified:
  * /stats?stats=season&group={hitting|pitching}&season=Y&sportId=1&playerPool=ALL&limit=500&offset=N
    returns ONE split per player with SEASON TOTALS, plus numTeams and team = his last team
    (Justin Turner 2024: numTeams 2, 539 PA, team Seattle). 2024 hitting totalSplits = 742.
    The teamId= variant UNDERCOUNTS (one team: 27 splits / 5,164 PA vs a team total of 6,245) - do not use it.
  * /people/{id}/stats?stats=season&group=..&season=Y returns a totals split (no team key) plus one split
    per team - the only reliable source of per-team shares, needed only when numTeams > 1.
  * /teams?sportId=1&season=Y gives each team's home venue for that season (ATH 2025 = Sutter Health Park).
  * /people?personIds=a,b gives birthDate, primaryPosition.abbreviation ('P', 'TWP', '2B', ...), batSide, pitchHand.
  * /teams/stats?stats=season&group=hitting&season=Y&sportIds=1 gives team totals (2024 sum PA = 181,516).
  * Default game type is the regular season (Juan Soto 2024 = 713 PA).
"""
from __future__ import annotations

import hashlib
import json
import time
from datetime import date
from pathlib import Path

import pandas as pd
import requests

BASE = "https://statsapi.mlb.com/api/v1"
ROOT = Path(__file__).resolve().parents[3]          # repo root
CACHE = ROOT / "data" / "raw" / "statsapi"

HIT_COLS = ["plateAppearances", "atBats", "hits", "doubles", "triples", "homeRuns", "baseOnBalls",
            "intentionalWalks", "hitByPitch", "strikeOuts", "sacBunts", "sacFlies", "catchersInterference",
            "stolenBases", "caughtStealing", "gamesPlayed"]
PIT_COLS = ["battersFaced", "outs", "hits", "homeRuns", "baseOnBalls", "intentionalWalks", "hitBatsmen",
            "strikeOuts", "sacBunts", "sacFlies", "catchersInterference", "earnedRuns", "gamesPitched",
            "gamesStarted", "groundOuts", "airOuts"]


def _get(path: str, params: dict, season: int | None = None) -> dict:
    """GET with a file cache. Seasons still in progress (>= current year) expire after 12 hours."""
    CACHE.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha1((path + json.dumps(params, sort_keys=True)).encode()).hexdigest()
    f = CACHE / f"{key}.json"
    live = season is not None and season >= date.today().year
    if f.exists() and not (live and time.time() - f.stat().st_mtime > 12 * 3600):
        return json.loads(f.read_text())
    for attempt in range(4):
        try:
            r = requests.get(f"{BASE}{path}", params=params, timeout=30)
            r.raise_for_status()
            data = r.json()
            f.write_text(json.dumps(data))
            time.sleep(0.25)                      # be polite
            return data
        except requests.RequestException:
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError("unreachable")


def teams(season: int) -> pd.DataFrame:
    js = _get("/teams", {"sportId": 1, "season": season}, season)
    return pd.DataFrame([{"season": season, "team_id": t["id"], "team_abbr": t.get("abbreviation"),
                          "venue_id": t["venue"]["id"], "venue_name": t["venue"]["name"]} for t in js["teams"]])


def player_season_stats(season: int, group: str) -> pd.DataFrame:
    """One row per player for a season (SEASON TOTALS). group: 'hitting' | 'pitching'.

    Pages the unfiltered bulk endpoint. Never use teamId= for totals: it undercounts (MANUAL.md §4.1).
    Columns: season, mlbam_id, name, last_team_id, num_teams, + the count columns for that group.
    """
    cols = HIT_COLS if group == "hitting" else PIT_COLS
    out, offset = [], 0
    while True:
        params = {"stats": "season", "group": group, "season": season, "sportId": 1,
                  "playerPool": "ALL", "limit": 500, "offset": offset}
        block = _get("/stats", params, season)["stats"][0]
        splits = block.get("splits", [])
        for sp in splits:
            row = {"season": season, "mlbam_id": sp["player"]["id"], "name": sp["player"]["fullName"],
                   "last_team_id": (sp.get("team") or {}).get("id"), "num_teams": int(sp.get("numTeams", 1) or 1)}
            row.update({c: int(sp["stat"].get(c, 0) or 0) for c in cols})
            out.append(row)
        offset += len(splits)
        if not splits or offset >= block.get("totalSplits", 0):
            break
    df = pd.DataFrame(out)
    if df.mlbam_id.duplicated().any():          # the bulk endpoint must return each player once
        raise ValueError(f"duplicate players in bulk {group} {season}")
    return df


def player_team_splits(mlbam_id: int, season: int, group: str) -> pd.DataFrame:
    """Per-team splits for ONE player-season — call only when num_teams > 1 (about 100-150 players
    per season per group). Returns season, mlbam_id, team_id, pa (PA for hitting, BF for pitching).
    Splits without a team key are season totals and are dropped."""
    js = _get(f"/people/{int(mlbam_id)}/stats",
              {"stats": "season", "group": group, "season": season, "sportId": 1}, season)
    stats = js.get("stats") or []
    field = "plateAppearances" if group == "hitting" else "battersFaced"
    rows = []
    for sp in (stats[0].get("splits", []) if stats else []):
        team = sp.get("team")
        if team:
            rows.append({"season": season, "mlbam_id": int(mlbam_id), "team_id": team["id"],
                         "pa": int(sp["stat"].get(field, 0) or 0)})
    return pd.DataFrame(rows, columns=["season", "mlbam_id", "team_id", "pa"])


def team_totals(season: int, group: str) -> pd.DataFrame:
    js = _get("/teams/stats", {"stats": "season", "group": group, "season": season, "sportIds": 1}, season)
    cols = HIT_COLS if group == "hitting" else PIT_COLS
    return pd.DataFrame([{"season": season, "team_id": sp["team"]["id"],
                          **{c: int(sp["stat"].get(c, 0) or 0) for c in cols}} for sp in js["stats"][0]["splits"]])


def people(ids: list[int]) -> pd.DataFrame:
    rows = []
    ids = sorted(set(int(i) for i in ids))
    for i in range(0, len(ids), 150):
        chunk = ids[i:i + 150]
        js = _get("/people", {"personIds": ",".join(map(str, chunk))})
        for p in js.get("people", []):
            rows.append({"mlbam_id": p["id"], "name": p.get("fullName"), "birth_date": p.get("birthDate"),
                         "primary_pos": (p.get("primaryPosition") or {}).get("abbreviation"),
                         "bats": (p.get("batSide") or {}).get("code"), "throws": (p.get("pitchHand") or {}).get("code"),
                         "debut": p.get("mlbDebutDate")})
    return pd.DataFrame(rows)


def season_age(birth_date: pd.Series, season: pd.Series) -> pd.Series:
    """Baseball age: age on June 30 of the season (Baseball-Reference convention)."""
    b = pd.to_datetime(birth_date)
    after = (b.dt.month > 6) | ((b.dt.month == 6) & (b.dt.day > 30))
    return (season - b.dt.year - after.astype(int)).astype("Int64")
