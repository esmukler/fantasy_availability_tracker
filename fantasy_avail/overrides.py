from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from typing import Dict, Tuple

from fantasy_avail.models import ProbableStart

# ANSI SGR foreground; used by load_opponent_abbr_colors (keys = JSON color names, lowercase).
_OPPONENT_COLOR_PREFIX: Dict[str, str] = {
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "blue": "\033[34m",
    "magenta": "\033[35m",
    "cyan": "\033[36m",
}


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


def load_opponent_abbr_colors(path: str) -> Dict[str, str]:
    """Map opponent abbreviation (uppercase) to ANSI color open sequence.

    JSON shape: {\"by_color\": {\"red\": [\"LAD\", ...], \"green\": [...], ...}}.
    Later color keys in by_color overwrite earlier ones for the same abbreviation.
    Unknown color names are skipped.
    """
    if not path or not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        return {}
    by_color = data.get("by_color")
    if not isinstance(by_color, dict):
        return {}
    out: Dict[str, str] = {}
    for color_name, abbrs in by_color.items():
        if not isinstance(color_name, str):
            continue
        prefix = _OPPONENT_COLOR_PREFIX.get(color_name.strip().lower())
        if not prefix:
            continue
        if not isinstance(abbrs, list):
            continue
        for a in abbrs:
            if not isinstance(a, str):
                continue
            aa = a.strip().upper()
            if aa:
                out[aa] = prefix
    return out


def load_opponent_colors_from_team_ops_csv(
    path: str | Path,
    team_name_to_abbr: Dict[str, str],
) -> Dict[str, str]:
    """Map opponent abbreviation (uppercase) to ANSI color from ``team_ops_*.csv`` rows.

    Rows must be ordered best OPS first. The first five teams are red, the next five
    yellow, and the last seven green (``if``/``elif`` so tiers do not double-count).

    ``team_name_to_abbr`` maps lowercase StatsAPI club ``name`` (e.g. ``dodgers`` via
    full name key) to abbreviation — use ``fetch_mlb_teams_context``'s second dict.
    """
    p = Path(path)
    if not team_name_to_abbr or not p.is_file():
        return {}
    teams: list[str] = []
    with p.open(newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        cols = {x.strip() for x in (r.fieldnames or [])}
        if "team" not in cols:
            return {}
        for row in r:
            name = (row.get("team") or "").strip()
            if name:
                teams.append(name)
    if not teams:
        return {}
    n = len(teams)
    out: Dict[str, str] = {}
    for i, team in enumerate(teams):
        abbr = team_name_to_abbr.get(team.lower())
        if not abbr:
            continue
        aa = abbr.strip().upper()
        if not aa:
            continue
        if i < 5:
            prefix = _OPPONENT_COLOR_PREFIX["red"]
        elif i < 10:
            prefix = _OPPONENT_COLOR_PREFIX["yellow"]
        elif i >= n - 7:
            prefix = _OPPONENT_COLOR_PREFIX["green"]
        else:
            continue
        out[aa] = prefix
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
