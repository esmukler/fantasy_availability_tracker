from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, Optional

from fantasy_avail.mlb_api import default_team_ops_csv_path

OpponentHighlight = Optional[str]  # None, "bad", "warn", "good"


def opponent_highlight_tiers_from_csv(csv_path: Path) -> Dict[str, str]:
    """Map team abbreviation (uppercase) to highlight tier from ``team_ops_*.csv``.

    Rows must be ordered best OPS first. Ranks 1–5 are bad (red), 6–10 warn (yellow),
    and the bottom seven teams are good (green). Middle ranks are not highlighted.
    """
    if not csv_path.is_file():
        return {}
    teams: list[tuple[str, Optional[str]]] = []
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = {x.strip() for x in (reader.fieldnames or [])}
        if "team" not in fieldnames:
            return {}
        has_abbr = "abbr" in fieldnames
        for row in reader:
            name = (row.get("team") or "").strip()
            if not name:
                continue
            abbr = (row.get("abbr") or "").strip().upper() if has_abbr else ""
            teams.append((name, abbr or None))
    if not teams:
        return {}
    n = len(teams)
    out: Dict[str, str] = {}
    for i, (team, abbr) in enumerate(teams):
        aa = abbr
        if not aa:
            continue
        if i < 5:
            tier = "bad"
        elif i < 10:
            tier = "warn"
        elif i >= n - 7:
            tier = "good"
        else:
            continue
        out[aa] = tier
    return out


def opponent_highlight_for_abbr(abbr: str, tiers: Dict[str, str]) -> OpponentHighlight:
    if not abbr:
        return None
    return tiers.get(abbr.strip().upper())


def ensure_opponent_highlights(
    payload: Dict[str, Any],
    *,
    season: Optional[int] = None,
) -> None:
    """Attach opponent_highlight to each pitcher from the on-disk team OPS CSV."""
    if season is None:
        start_date = payload.get("start_date")
        if isinstance(start_date, str) and len(start_date) >= 4:
            try:
                season = int(start_date[:4])
            except ValueError:
                season = None
    tiers = opponent_highlight_tiers_from_csv(default_team_ops_csv_path(season))
    for pitcher in payload.get("pitchers") or []:
        abbr = pitcher.get("opponent_team") or ""
        pitcher["opponent_highlight"] = opponent_highlight_for_abbr(abbr, tiers)
