from __future__ import annotations

import datetime as dt
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from fantasy_avail.opponent_ops_highlights import ensure_opponent_highlights
from fantasy_avail.schemas import GetAvailableProbablePitchersResult, ProbablePitcherRow
from fantasy_avail.stat_highlights import stat_highlights_for
from fantasy_avail.yahoo import yahoo_gamelog_url


def _format_cached_at(ts: float) -> str:
    pacific = dt.datetime.fromtimestamp(ts, tz=ZoneInfo("America/Los_Angeles"))
    return pacific.isoformat(timespec="seconds")


def _format_date_range(start_date: str, days: int) -> str:
    start = dt.date.fromisoformat(start_date)
    end = start + dt.timedelta(days=days - 1)
    if start.month == end.month:
        return f"{start:%b} {start.day}–{end.day}"
    return f"{start:%b} {start.day}–{end:%b} {end.day}"


def _stats_payload(stats: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not stats:
        return None
    payload = {
        "wins": stats.get("wins"),
        "losses": stats.get("losses"),
        "era": stats.get("era"),
        "whip": stats.get("whip"),
        "innings_pitched": stats.get("innings_pitched"),
        "strikeouts": stats.get("strikeouts"),
    }
    payload["highlights"] = stat_highlights_for(payload)
    return payload


def ensure_stats_highlights(payload: Dict[str, Any]) -> None:
    for pitcher in payload.get("pitchers") or []:
        stats = pitcher.get("stats")
        if stats:
            stats["highlights"] = stat_highlights_for(stats)


def ensure_web_payload_enrichments(payload: Dict[str, Any]) -> None:
    """Backfill derived fields for disk-cached payloads written before enrichment."""
    ensure_stats_highlights(payload)
    ensure_opponent_highlights(payload)


def _game_time_for_tile(game_time_pt: str) -> str:
    """Drop weekday prefix; day is shown in the section header."""
    if game_time_pt == "TBD":
        return game_time_pt
    parts = game_time_pt.split(" ", 1)
    if len(parts) == 2:
        return parts[1]
    return game_time_pt


def _yahoo_gamelog_url_from_row(row: ProbablePitcherRow) -> Optional[str]:
    agents = row.yahoo_free_agents
    if not agents:
        return None
    player_id = agents[0].get("player_id")
    if player_id is None:
        return None
    return yahoo_gamelog_url(player_id)


def pitcher_row_to_web(row: ProbablePitcherRow) -> Dict[str, Any]:
    return {
        "name": row.mlb_name,
        "date": row.date,
        "pitcher_team": row.pitcher_team,
        "opponent_team": row.opponent_team,
        "home_away": row.home_away,
        "game_time_pt": _game_time_for_tile(row.game_time_pt),
        "availability": row.availability,
        "stats": _stats_payload(row.mlb_season_stats),
        "opposing_pitcher_name": row.opposing_pitcher_name,
        "yahoo_gamelog_url": _yahoo_gamelog_url_from_row(row),
    }


def result_to_web_payload(
    result: GetAvailableProbablePitchersResult,
    *,
    cached: bool,
    cached_at: Optional[float] = None,
) -> Dict[str, Any]:
    pitchers: List[Dict[str, Any]] = [pitcher_row_to_web(row) for row in result.available]
    payload: Dict[str, Any] = {
        "league_id": result.league_id,
        "start_date": result.start_date,
        "days": result.days,
        "date_range": _format_date_range(result.start_date, result.days),
        "cached": cached,
        "pitchers": pitchers,
        "warnings": list(result.warnings),
    }
    if cached_at is not None:
        payload["cached_at"] = _format_cached_at(cached_at)
    ensure_web_payload_enrichments(payload)
    return payload
