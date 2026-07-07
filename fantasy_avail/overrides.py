from __future__ import annotations

import json
import os
from typing import Dict, Tuple

from fantasy_avail.models import ProbableStart


def load_team_abbr_overrides(path: str) -> Dict[str, str]:
    if not path:
        return {}
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and isinstance(data.get("overrides"), dict):
        overrides = data["overrides"]
    elif isinstance(data, dict):
        overrides = data
    else:
        overrides = {}
    out: Dict[str, str] = {}
    for k, v in overrides.items():
        if not isinstance(k, str) or not isinstance(v, str):
            continue
        kk = k.strip()
        vv = v.strip()
        if kk and vv:
            out[kk] = vv
    return out


def load_player_name_overrides(path: str) -> Tuple[Dict[str, str], Dict[str, int]]:
    yahoo: Dict[str, str] = {}
    mlbam: Dict[str, int] = {}
    if not path or not os.path.exists(path):
        return yahoo, mlbam
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        return yahoo, mlbam
    raw_y = data.get("yahoo_name_by_slug") or {}
    if isinstance(raw_y, dict):
        for k, v in raw_y.items():
            if isinstance(k, str) and isinstance(v, str) and k.strip() and v.strip():
                yahoo[k.strip().lower()] = v.strip()
    raw_m = data.get("mlbam_by_slug") or {}
    if isinstance(raw_m, dict):
        for k, v in raw_m.items():
            if not isinstance(k, str) or not k.strip():
                continue
            try:
                mlbam[k.strip().lower()] = int(v)
            except (TypeError, ValueError):
                continue
    return yahoo, mlbam


def apply_abbr_overrides(ps: ProbableStart, overrides: Dict[str, str]) -> ProbableStart:
    if not overrides:
        return ps
    away_abbr = overrides.get(ps.away_abbr, ps.away_abbr)
    home_abbr = overrides.get(ps.home_abbr, ps.home_abbr)
    if away_abbr == ps.away_abbr and home_abbr == ps.home_abbr:
        return ps
    return ProbableStart(
        date=ps.date,
        game_pk=ps.game_pk,
        pitcher_name=ps.pitcher_name,
        pitcher_mlbam_id=ps.pitcher_mlbam_id,
        pitcher_side=ps.pitcher_side,
        away_team=ps.away_team,
        home_team=ps.home_team,
        away_abbr=away_abbr,
        home_abbr=home_abbr,
        fp_slug=ps.fp_slug,
        game_datetime=ps.game_datetime,
    )
