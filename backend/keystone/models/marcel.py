"""Tier 1 baseline: Marcel (Tom Tango), applied to per-PA' events.

VERIFIED REFERENCE (tests: backend/tests/test_marcel.py). Extend, don't rewrite.

Hitters : weights 5/4/3 (T-1, T-2, T-3), regress with 1200 PA' of league average, PA = .5*PA1 + .1*PA2 + 200.
Pitchers: weights 3/2/1, regress with 1200 BF' of league average (Marcel-style choice; Tango's original
          pitcher regression is outs-based), IP = .5*IP1 + .1*IP2 + (60 if starter else 25).
League average for a player = his own mix of league seasons, weighted by w_j * PA_j.
Age (as of June 30 of target season): a = .006*(29-age) if age < 29 else -.003*(age-29).
  hitters : good events * (1+a), strikeouts / (1+a)
  pitchers: strikeouts * (1+a), other events / (1+a)
No rebaselining step. Output = stage probabilities, so keystone.components.derive_* work unchanged.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

H_EVENTS = ["k", "ubb", "hbp", "hr", "single", "double", "triple"]
P_EVENTS = ["k", "ubb", "hbp", "hr", "h_bip"]
CFG = {"H": dict(weights=(5, 4, 3), reg=1200.0, events=H_EVENTS),
       "P": dict(weights=(3, 2, 1), reg=1200.0, events=P_EVENTS)}


def events_table(df: pd.DataFrame, role: str) -> pd.DataFrame:
    """Per player-season event counts on the PA' / BF' basis (input: Stats API columns summed over teams)."""
    out = df[["mlbam_id", "season"]].copy()
    if role == "H":
        out["pa"] = df.plateAppearances - df.intentionalWalks - df.sacBunts - df.catchersInterference
        out["hbp"] = df.hitByPitch
        out["single"] = df.hits - df.doubles - df.triples - df.homeRuns
        out["double"], out["triple"] = df.doubles, df.triples
    else:
        out["pa"] = df.battersFaced - df.intentionalWalks - df.sacBunts - df.catchersInterference
        out["hbp"] = df.hitBatsmen
        out["h_bip"] = df.hits - df.homeRuns
    out["k"], out["ubb"], out["hr"] = df.strikeOuts, df.baseOnBalls - df.intentionalWalks, df.homeRuns
    return out


def to_stage_probs(r: dict) -> dict:
    """Per-PA' event rates -> conditional stage probabilities (inverse of components.per_pa_from_stage_rates)."""
    k, bb, hbp, hr = r["k"], r["ubb"], r["hbp"], r["hr"]
    contact = 1 - k - bb - hbp
    h_bip = r["h_bip"] if "h_bip" in r else r["single"] + r["double"] + r["triple"]
    p = dict(k=k, bb=bb / (1 - k), hbp=hbp / (1 - k - bb), hr=hr / contact, hit_bip=h_bip / (contact - hr))
    if "single" in r:
        xbh = r["double"] + r["triple"]
        p["xbh"] = xbh / h_bip
        p["triple"] = np.where(xbh > 0, r["triple"] / np.where(xbh > 0, xbh, 1), 0.0)
    return p


def marcel(ev: pd.DataFrame, role: str, target: int, ages: pd.Series) -> pd.DataFrame:
    """ev: events_table for all seasons (modelled population). ages: Series mlbam_id -> age in `target`.
    Returns one row per player with any PA' in target-3..target-1: mlbam_id, stage probs, pa_weighted."""
    cfg = CFG[role]
    E = cfg["events"]
    lg = ev.groupby("season")[E + ["pa"]].sum()
    lg_rate = lg[E].div(lg.pa, axis=0)
    rows = []
    for j, w in enumerate(cfg["weights"], start=1):
        s = target - j
        part = ev[ev.season == s].copy()
        part["w"] = w
        for e in E:
            part[f"lg_{e}"] = lg_rate.loc[s, e] if s in lg_rate.index else np.nan
        rows.append(part)
    hist = pd.concat(rows, ignore_index=True)
    hist = hist[hist.pa > 0]
    g = hist.assign(wpa=hist.w * hist.pa)
    agg = g.groupby("mlbam_id").apply(lambda d: pd.Series(
        {**{e: (d.w * d[e]).sum() for e in E},
         **{f"lg_{e}": (d.wpa * d[f"lg_{e}"]).sum() / d.wpa.sum() for e in E},
         "wpa": d.wpa.sum()}), include_groups=False)
    age = agg.index.map(ages).astype(float)
    a = np.where(age < 29, 0.006 * (29 - age), -0.003 * (age - 29))
    rates = {}
    for e in E:
        r = (agg[e] + cfg["reg"] * agg[f"lg_{e}"]) / (agg.wpa + cfg["reg"])
        good = (e != "k") if role == "H" else (e == "k")
        rates[e] = (r * (1 + a) if good else r / (1 + a)).to_numpy()
    p = to_stage_probs(rates)
    out = pd.DataFrame({"mlbam_id": agg.index, **p, "pa_weighted": agg.wpa.to_numpy()})
    return out


def marcel_playing_time(df: pd.DataFrame, role: str, target: int) -> pd.Series:
    """df: Stats API player-season totals. Hitters -> projected PA; pitchers -> projected IP."""
    y1, y2 = df[df.season == target - 1].set_index("mlbam_id"), df[df.season == target - 2].set_index("mlbam_id")
    ids = y1.index.union(y2.index)
    if role == "H":
        pa1, pa2 = y1.plateAppearances.reindex(ids).fillna(0), y2.plateAppearances.reindex(ids).fillna(0)
        return 0.5 * pa1 + 0.1 * pa2 + 200
    ip1 = (y1.outs / 3).reindex(ids).fillna(0)
    ip2 = (y2.outs / 3).reindex(ids).fillna(0)
    last = y1.reindex(ids)
    starter = (last.gamesStarted / last.gamesPitched.where(last.gamesPitched > 0)).fillna(0) >= 0.5
    return 0.5 * ip1 + 0.1 * ip2 + np.where(starter, 60, 25)
