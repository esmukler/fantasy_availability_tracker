from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence

from fantasy_avail.name_utils import normalize_name

# Internal marker on Yahoo player dicts for output (stripped from JSON).
FANTASY_AVAIL_SOURCE_KEY = "_fantasy_avail_source"
AVAIL_SOURCE_FREE_AGENT = "free_agent"
AVAIL_SOURCE_WAIVERS = "waivers"
AVAIL_SOURCE_NA_FREE_AGENT = "na_free_agent"

# Yahoo's ownership endpoint returns at most ~25 players per request.
_OWNERSHIP_BATCH_SIZE = 25

_FALLBACK_POSITIONS = ("C", "1B", "2B", "3B", "SS", "OF", "Util", "SP", "RP")


def init_league(league_id: int, oauth_path: str, token_dir: str):
    try:
        from yahoo_oauth import OAuth2
        from yahoo_fantasy_api import Game
        from yahoo_fantasy_api.league import League
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            "Missing dependencies. Install requirements first:\n"
            "  pip install -r requirements.txt\n"
        ) from e

    sc = OAuth2(None, None, from_file=oauth_path, store_path=token_dir)
    gm = Game(sc, "mlb")
    game_id = gm.game_id()
    league_key = f"{game_id}.l.{league_id}"
    return League(sc, league_key)


def _dedupe_players(players: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for p in players:
        key = str(
            p.get("player_id")
            or p.get("player_key")
            or p.get("name")
            or json.dumps(p, sort_keys=True, default=str)
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


def _tag_players(players: Iterable[Dict[str, Any]], source: str) -> List[Dict[str, Any]]:
    tagged: List[Dict[str, Any]] = []
    for p in players:
        row = dict(p)
        row[FANTASY_AVAIL_SOURCE_KEY] = source
        tagged.append(row)
    return tagged


def _fetch_free_agents_all_positions(league) -> List[Dict[str, Any]]:
    all_free_agents: List[Dict[str, Any]] = []
    try:
        all_free_agents = league.free_agents() or []
    except TypeError:
        for pos in _FALLBACK_POSITIONS:
            all_free_agents.extend(league.free_agents(pos) or [])
    except Exception:
        for pos in _FALLBACK_POSITIONS:
            try:
                all_free_agents.extend(league.free_agents(pos) or [])
            except Exception:
                continue
    return _dedupe_players(all_free_agents)


def _fetch_waivers(league) -> List[Dict[str, Any]]:
    try:
        waiver_players = league.waivers() or []
    except Exception:
        waiver_players = []
    return _dedupe_players(waiver_players)


def fetch_yahoo_available_players(league, include_waivers: bool = True) -> List[Dict[str, Any]]:
    """Full FA/waiver pool scan — expensive; prefer targeted lookups when possible."""
    all_free_agents = _fetch_free_agents_all_positions(league)
    tagged = _tag_players(all_free_agents, AVAIL_SOURCE_FREE_AGENT)
    if not include_waivers:
        return tagged

    waiver_players = _fetch_waivers(league)
    fa_names = {normalize_name(str(p.get("name") or "")) for p in tagged}
    for p in waiver_players:
        nm = normalize_name(str(p.get("name") or ""))
        if not nm or nm in fa_names:
            continue
        row = dict(p)
        row[FANTASY_AVAIL_SOURCE_KEY] = AVAIL_SOURCE_WAIVERS
        tagged.append(row)

    return tagged


def _hits_include_waivers(hits: List[Dict[str, Any]]) -> bool:
    return any(h.get(FANTASY_AVAIL_SOURCE_KEY) == AVAIL_SOURCE_WAIVERS for h in hits)


def _hits_include_na(hits: List[Dict[str, Any]]) -> bool:
    return any(
        h.get(FANTASY_AVAIL_SOURCE_KEY) == AVAIL_SOURCE_NA_FREE_AGENT
        or (h.get("status") or "").strip().upper() == "NA"
        for h in hits
    )


def yahoo_availability_from_hits(hits: List[Dict[str, Any]]) -> str:
    if _hits_include_waivers(hits):
        return AVAIL_SOURCE_WAIVERS
    if _hits_include_na(hits):
        return AVAIL_SOURCE_NA_FREE_AGENT
    return AVAIL_SOURCE_FREE_AGENT


def hits_for_json(hits: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [{k: v for k, v in h.items() if k != FANTASY_AVAIL_SOURCE_KEY} for h in hits]


def yahoo_gamelog_url(player_id: int | str) -> str:
    return f"https://sports.yahoo.com/mlb/players/{int(player_id)}/gamelog/"


def yahoo_display_name(details: Dict[str, Any]) -> str:
    name = details.get("name")
    if isinstance(name, dict):
        return str(name.get("full") or "").strip()
    return str(name or "").strip()


def _eligible_positions_from_details(details: Dict[str, Any]) -> List[str]:
    eligible = details.get("eligible_positions") or []
    if not eligible:
        return []
    if isinstance(eligible[0], dict):
        return [str(e.get("position") or "") for e in eligible if e.get("position")]
    return [str(e) for e in eligible]


def player_details_to_availability_row(
    details: Dict[str, Any],
    *,
    source: str,
) -> Dict[str, Any]:
    return {
        "player_id": int(details["player_id"]),
        "name": yahoo_display_name(details),
        "position_type": str(details.get("position_type") or ""),
        "eligible_positions": _eligible_positions_from_details(details),
        "status": str(details.get("status") or ""),
        FANTASY_AVAIL_SOURCE_KEY: source,
    }


def fetch_player_ownership_batched(
    league,
    player_ids: Sequence[int],
    *,
    batch_size: int = _OWNERSHIP_BATCH_SIZE,
) -> Dict[str, Dict[str, Any]]:
    """Fetch Yahoo ownership for many player ids, chunking to API limits."""
    ownership: Dict[str, Dict[str, Any]] = {}
    if not player_ids:
        return ownership

    unique_ids = list(dict.fromkeys(int(pid) for pid in player_ids))
    for i in range(0, len(unique_ids), batch_size):
        chunk = unique_ids[i : i + batch_size]
        try:
            ownership.update(league.ownership(chunk) or {})
        except Exception:
            continue
    return ownership


def ownership_indicates_available(
    ownership_info: Dict[str, Any],
    *,
    include_waivers: bool = True,
) -> bool:
    own_type = (ownership_info.get("ownership_type") or "").strip().lower()
    if own_type == "freeagents":
        return True
    return include_waivers and own_type == "waivers"


def _availability_source_for_ownership(
    ownership_info: Dict[str, Any],
    *,
    player_status: str,
) -> str:
    own_type = (ownership_info.get("ownership_type") or "").strip().lower()
    if own_type == "waivers":
        return AVAIL_SOURCE_WAIVERS
    if (player_status or "").strip().upper() == "NA":
        return AVAIL_SOURCE_NA_FREE_AGENT
    return AVAIL_SOURCE_FREE_AGENT


@dataclass(frozen=True)
class PlayerAvailabilityLookup:
    query_name: str
    normalized_name: str
    is_available: bool
    availability: Optional[str] = None
    yahoo_player: Optional[Dict[str, Any]] = None


def lookup_players_availability(
    league,
    names: Sequence[str],
    *,
    include_waivers: bool = True,
) -> List[PlayerAvailabilityLookup]:
    """
    Resolve display names to availability via player_details + batched ownership.

    Makes one ownership call for all resolved player IDs (no bulk FA/waiver fetch).
    """
    resolved: List[tuple[str, str, Dict[str, Any]]] = []
    results: List[PlayerAvailabilityLookup] = []

    for raw_name in names:
        key = normalize_name(raw_name)
        if not key:
            results.append(
                PlayerAvailabilityLookup(
                    query_name=raw_name,
                    normalized_name=key,
                    is_available=False,
                )
            )
            continue

        details = find_player_details_for_name(league, raw_name)
        if not details:
            results.append(
                PlayerAvailabilityLookup(
                    query_name=raw_name,
                    normalized_name=key,
                    is_available=False,
                )
            )
            continue

        resolved.append((raw_name, key, details))

    if not resolved:
        return results

    pids = [int(d["player_id"]) for _, _, d in resolved]
    ownership = fetch_player_ownership_batched(league, pids)

    for raw_name, key, details in resolved:
        pid = int(details["player_id"])
        own_info = ownership.get(str(pid), {})
        if not ownership_indicates_available(own_info, include_waivers=include_waivers):
            results.append(
                PlayerAvailabilityLookup(
                    query_name=raw_name,
                    normalized_name=key,
                    is_available=False,
                )
            )
            continue

        source = _availability_source_for_ownership(
            own_info,
            player_status=str(details.get("status") or ""),
        )
        row = player_details_to_availability_row(details, source=source)
        results.append(
            PlayerAvailabilityLookup(
                query_name=raw_name,
                normalized_name=key,
                is_available=True,
                availability=source,
                yahoo_player=row,
            )
        )

    return results


def index_targeted_availability_by_names(
    league,
    names: Iterable[str],
    *,
    include_waivers: bool = True,
) -> Dict[str, List[Dict[str, Any]]]:
    """Index available players by normalized name (values are single-element lists)."""
    idx: Dict[str, List[Dict[str, Any]]] = {}
    for hit in lookup_players_availability(league, list(names), include_waivers=include_waivers):
        if not hit.is_available or not hit.yahoo_player:
            continue
        idx[hit.normalized_name] = [hit.yahoo_player]
        yahoo_key = normalize_name(str(hit.yahoo_player.get("name") or ""))
        if yahoo_key and yahoo_key not in idx:
            idx[yahoo_key] = [hit.yahoo_player]
    return idx


def availability_index_from_lookups(
    lookups: Sequence[PlayerAvailabilityLookup],
) -> Dict[str, Dict[str, Any]]:
    """Build a normalized-name -> player dict from lookup results."""
    idx: Dict[str, Dict[str, Any]] = {}
    for hit in lookups:
        if not hit.is_available or not hit.yahoo_player:
            continue
        idx[hit.normalized_name] = hit.yahoo_player
        yahoo_key = normalize_name(str(hit.yahoo_player.get("name") or ""))
        if yahoo_key and yahoo_key not in idx:
            idx[yahoo_key] = hit.yahoo_player
    return idx


def find_player_details_for_name(league, query_name: str) -> Optional[Dict[str, Any]]:
    key = normalize_name(query_name)
    if not key:
        return None
    try:
        matches = league.player_details(query_name) or []
    except Exception:
        return None
    if not matches:
        return None

    exact = [m for m in matches if normalize_name(yahoo_display_name(m)) == key]
    if len(exact) == 1:
        return exact[0]

    prefix = [
        m
        for m in matches
        if normalize_name(yahoo_display_name(m)).startswith(f"{key} ")
    ]
    if len(prefix) == 1:
        return prefix[0]

    if len(matches) == 1:
        return matches[0]
    return None


def lookup_league_available_player(
    league,
    query_name: str,
    *,
    fa_waiver_idx: Optional[Dict[str, Dict[str, Any]]] = None,
    include_waivers: bool = True,
) -> Optional[Dict[str, Any]]:
    """
    Resolve a display name to an unrostered league player.

    Optional fa_waiver_idx is a legacy shortcut when a bulk index is already loaded.
    """
    key = normalize_name(query_name)
    if not key:
        return None
    if fa_waiver_idx is not None:
        hit = fa_waiver_idx.get(key)
        if hit:
            return hit

    hits = lookup_players_availability(
        league, [query_name], include_waivers=include_waivers
    )
    if not hits or not hits[0].is_available:
        return None
    return hits[0].yahoo_player


def enrich_targeted_availability_lists_by_names(
    league,
    names: Iterable[str],
    available_by_name: Dict[str, List[Dict[str, Any]]],
    *,
    include_waivers: bool = True,
) -> None:
    """Add targeted availability hits to a list-valued index (probable pitchers)."""
    pending = [
        name
        for name in names
        if normalize_name(name) and normalize_name(name) not in available_by_name
    ]
    if not pending:
        return
    available_by_name.update(
        index_targeted_availability_by_names(
            league, pending, include_waivers=include_waivers
        )
    )


