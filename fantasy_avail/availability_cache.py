from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from fantasy_avail.config import AppConfig, load_config
from fantasy_avail.yahoo import init_league

CacheKey = Tuple[int, bool, str]


@dataclass
class _CacheEntry:
    players: List[Dict[str, Any]]
    fetched_at: float


class AvailabilityCache:
    """Session-scoped cache for Yahoo FA/waiver player lists."""

    def __init__(self, *, ttl_seconds: Optional[int] = None, config: Optional[AppConfig] = None):
        self._config = config or load_config()
        self._ttl = ttl_seconds if ttl_seconds is not None else self._config.cache_ttl_seconds
        self._entries: Dict[CacheKey, _CacheEntry] = {}
        self._league_cache: Dict[int, Any] = {}

    def _make_key(
        self,
        *,
        league_id: int,
        include_waivers: bool,
        position_filter: Optional[str],
    ) -> CacheKey:
        pos = (position_filter or "ALL").strip().upper()
        return (league_id, include_waivers, pos)

    def _is_fresh(self, entry: _CacheEntry) -> bool:
        return (time.monotonic() - entry.fetched_at) < self._ttl

    def has_league(self, league_id: Optional[int] = None) -> bool:
        lid = league_id if league_id is not None else self._config.league_id
        return lid in self._league_cache

    def get_league(self, league_id: Optional[int] = None, *, refresh: bool = False):
        lid = league_id if league_id is not None else self._config.league_id
        if refresh and lid in self._league_cache:
            del self._league_cache[lid]
        if lid not in self._league_cache:
            self._league_cache[lid] = init_league(
                lid,
                self._config.oauth_path_str,
                self._config.token_dir_str,
            )
        return self._league_cache[lid]

    def get_available_players(
        self,
        *,
        league_id: Optional[int] = None,
        include_waivers: bool = True,
        position_filter: Optional[str] = None,
        refresh: bool = False,
    ) -> Tuple[List[Dict[str, Any]], bool]:
        """Full FA/waiver pool scan — only for list_available_players."""
        from fantasy_avail.yahoo import fetch_yahoo_available_players

        lid = league_id if league_id is not None else self._config.league_id
        key = self._make_key(
            league_id=lid,
            include_waivers=include_waivers,
            position_filter=position_filter,
        )
        entry = self._entries.get(key)
        if not refresh and entry is not None and self._is_fresh(entry):
            players = self._filter_by_position(entry.players, position_filter)
            return players, True

        league = self.get_league(lid)
        players = fetch_yahoo_available_players(league, include_waivers=include_waivers)
        self._entries[key] = _CacheEntry(players=list(players), fetched_at=time.monotonic())
        return self._filter_by_position(players, position_filter), False

    @staticmethod
    def _filter_by_position(
        players: List[Dict[str, Any]],
        position_filter: Optional[str],
    ) -> List[Dict[str, Any]]:
        if not position_filter:
            return list(players)
        want = position_filter.strip().upper()
        out: List[Dict[str, Any]] = []
        for p in players:
            pos = str(p.get("position_type") or "").strip().upper()
            eligible = p.get("eligible_positions") or []
            if isinstance(eligible, str):
                eligible = [eligible]
            eligible_upper = {str(x).strip().upper() for x in eligible}
            if pos == want or want in eligible_upper:
                out.append(p)
        return out

    def invalidate(self) -> None:
        self._entries.clear()


# Module-level singleton for the MCP server process lifetime.
_global_cache: Optional[AvailabilityCache] = None


def get_availability_cache() -> AvailabilityCache:
    global _global_cache
    if _global_cache is None:
        _global_cache = AvailabilityCache()
    return _global_cache
