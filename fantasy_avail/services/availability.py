from __future__ import annotations

from typing import List, Optional

from fantasy_avail.availability_cache import AvailabilityCache, get_availability_cache
from fantasy_avail.config import AppConfig, load_config
from fantasy_avail.name_utils import normalize_name
from fantasy_avail.schemas import (
    AvailablePlayerRow,
    CheckPlayerAvailabilityResult,
    ListAvailablePlayersResult,
    PlayerAvailabilityCheck,
)
from fantasy_avail.yahoo import lookup_players_availability


def list_available_players(
    *,
    position_filter: Optional[str] = None,
    include_waivers: bool = True,
    league_id: Optional[int] = None,
    refresh: bool = False,
    cache: Optional[AvailabilityCache] = None,
    config: Optional[AppConfig] = None,
) -> ListAvailablePlayersResult:
    cfg = config or load_config()
    lid = league_id if league_id is not None else cfg.league_id
    c = cache or get_availability_cache()
    players, was_cached = c.get_available_players(
        league_id=lid,
        include_waivers=include_waivers,
        position_filter=position_filter,
        refresh=refresh,
    )
    rows: List[AvailablePlayerRow] = []
    for p in players:
        row = AvailablePlayerRow.from_yahoo(p)
        row.normalized_name = normalize_name(row.player_name)
        rows.append(row)
    rows.sort(key=lambda r: r.player_name.lower())
    return ListAvailablePlayersResult(
        players=rows,
        total=len(rows),
        position_filter=position_filter,
        include_waivers=include_waivers,
        league_id=lid,
        cached=was_cached,
    )


def check_player_availability(
    names: List[str],
    *,
    include_waivers: bool = True,
    league_id: Optional[int] = None,
    refresh: bool = False,
    cache: Optional[AvailabilityCache] = None,
    config: Optional[AppConfig] = None,
) -> CheckPlayerAvailabilityResult:
    cfg = config or load_config()
    lid = league_id if league_id is not None else cfg.league_id
    c = cache or get_availability_cache()
    league_reused = c.has_league(lid) and not refresh
    league = c.get_league(lid, refresh=refresh)
    lookups = lookup_players_availability(
        league, names, include_waivers=include_waivers
    )
    results: List[PlayerAvailabilityCheck] = []
    for hit in lookups:
        if hit.is_available and hit.yahoo_player:
            results.append(
                PlayerAvailabilityCheck(
                    query_name=hit.query_name,
                    normalized_name=hit.normalized_name,
                    is_available=True,
                    availability=hit.availability or "free_agent",
                    yahoo_player=hit.yahoo_player,
                )
            )
        else:
            results.append(
                PlayerAvailabilityCheck(
                    query_name=hit.query_name,
                    normalized_name=hit.normalized_name,
                    is_available=False,
                )
            )
    return CheckPlayerAvailabilityResult(
        league_id=lid,
        include_waivers=include_waivers,
        results=results,
        cached=league_reused,
    )
