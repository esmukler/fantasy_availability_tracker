from __future__ import annotations

import datetime as dt
import json
import logging
import sys
from typing import List, Optional

from mcp.server.fastmcp import FastMCP

from fantasy_avail.config import load_config
from fantasy_avail.services.article_analysis import analyze_article_availability
from fantasy_avail.services.availability import check_player_availability, list_available_players
from fantasy_avail.services.probable_pitchers import get_available_probable_pitchers
from fantasy_avail.services.team_ops import refresh_team_ops

logging.basicConfig(stream=sys.stderr, level=logging.INFO)
logger = logging.getLogger(__name__)

mcp = FastMCP(
    "fantasy-availability",
    instructions=(
        "Tools for checking Yahoo Fantasy Baseball league player availability, "
        "probable starting pitchers, and article-based waiver/FA analysis."
    ),
)


def _json_response(payload) -> str:
    return json.dumps(payload, indent=2, default=str)


@mcp.tool()
def list_available_players_tool(
    position_filter: Optional[str] = None,
    include_waivers: bool = True,
    league_id: Optional[int] = None,
    refresh: bool = False,
) -> str:
    """List free agents and waiver players in the configured Yahoo league.

    Note: This scans the full FA/waiver pool (many Yahoo API calls). Prefer
    check_player_availability_tool for checking specific player names.

    Args:
        position_filter: Optional position filter (e.g. P, C, 1B, OF, SP, RP).
        include_waivers: Include waiver players (default true).
        league_id: Yahoo league id (default from FANTASY_LEAGUE_ID or 43384).
        refresh: Bypass session cache and refetch from Yahoo.
    """
    result = list_available_players(
        position_filter=position_filter,
        include_waivers=include_waivers,
        league_id=league_id,
        refresh=refresh,
    )
    return _json_response(result.to_dict())


@mcp.tool()
def check_player_availability_tool(
    names: List[str],
    include_waivers: bool = True,
    league_id: Optional[int] = None,
    refresh: bool = False,
) -> str:
    """Check whether one or more players are free agents or on waivers.

    Args:
        names: Player display names to check (batch supported).
        include_waivers: Include waiver players (default true).
        league_id: Yahoo league id (default from config).
        refresh: Re-initialize Yahoo league session (clears library player cache).
    """
    if not names:
        return _json_response({"error": "names must be a non-empty list"})
    result = check_player_availability(
        names,
        include_waivers=include_waivers,
        league_id=league_id,
        refresh=refresh,
    )
    return _json_response(result.to_dict())


@mcp.tool()
def get_available_probable_pitchers_tool(
    start_date: Optional[str] = None,
    days: int = 5,
    include_waivers: bool = True,
    include_stats: bool = True,
    all_probables: bool = False,
    league_id: Optional[int] = None,
    season: Optional[int] = None,
    skip_team_ops_update: bool = False,
) -> str:
    """Find probable MLB starting pitchers who are FA, on waivers, or NA free agents.

    Args:
        start_date: First day of schedule window YYYY-MM-DD (default tomorrow in US Pacific time).
        days: Number of days in window (default 5).
        include_waivers: Include waiver pitchers (default true).
        include_stats: Attach MLB season pitching stats (default true).
        all_probables: Return all probables that are available (not just matched subset).
        league_id: Yahoo league id (default from config).
        season: MLB stats season year (default year of start_date).
        skip_team_ops_update: Skip daily team OPS CSV refresh.
    """
    parsed_start: Optional[dt.date] = None
    if start_date:
        parsed_start = dt.date.fromisoformat(start_date)
    result = get_available_probable_pitchers(
        start_date=parsed_start,
        days=days,
        league_id=league_id,
        include_waivers=include_waivers,
        include_stats=include_stats,
        all_probables=all_probables,
        season=season,
        skip_team_ops_update=skip_team_ops_update,
    )
    return _json_response(result.to_dict())


@mcp.tool()
def analyze_article_availability_tool(
    url: str,
    include_waivers: bool = True,
    max_snippets: int = 2,
    league_id: Optional[int] = None,
    refresh: bool = False,
) -> str:
    """Fetch an article, extract main players, and return those available in the league.

    Returns main_players, available (with article snippets), not_in_pool, and warnings.

    Args:
        url: Article URL to analyze.
        include_waivers: Include waiver players (default true).
        max_snippets: Max article snippets per available player (default 2).
        league_id: Yahoo league id (default from config).
        refresh: Bypass session cache and refetch from Yahoo.
    """
    result = analyze_article_availability(
        url,
        include_waivers=include_waivers,
        max_snippets=max_snippets,
        league_id=league_id,
        refresh=refresh,
    )
    return _json_response(result.to_dict())


@mcp.tool()
def refresh_team_ops_tool(season: Optional[int] = None) -> str:
    """Refresh team_ops_{season}.csv from the MLB Stats API.

    Args:
        season: MLB season year (default current calendar year).
    """
    result = refresh_team_ops(season=season)
    return _json_response(result.to_dict())


def main() -> None:
    cfg = load_config()
    logger.info(
        "Starting fantasy-availability MCP server (league_id=%s, cache_ttl=%ss)",
        cfg.league_id,
        cfg.cache_ttl_seconds,
    )
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
