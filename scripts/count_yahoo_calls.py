#!/usr/bin/env python3
"""Compare Yahoo API HTTP call counts across availability strategies."""

from __future__ import annotations

import argparse
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, List

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from fantasy_avail.article_availability_summary import fetch_yahoo_available_players
from fantasy_avail.config import load_config
from fantasy_avail.yahoo import init_league, lookup_players_availability


DEFAULT_NAMES = [
    "Shohei Ohtani",
    "Aaron Judge",
    "Mookie Betts",
    "Ronald Acuña Jr.",
    "Fernando Tatis Jr.",
    "Vladimir Guerrero Jr.",
    "Juan Soto",
    "Freddie Freeman",
    "Jose Altuve",
    "Manny Machado",
]


@contextmanager
def count_yahoo_http_calls():
    from yahoo_fantasy_api import yhandler

    counter = {"n": 0}
    original_get = yhandler.YHandler.get

    def wrapped_get(self, uri, *args, **kwargs):
        counter["n"] += 1
        return original_get(self, uri, *args, **kwargs)

    yhandler.YHandler.get = wrapped_get
    try:
        yield counter
    finally:
        yhandler.YHandler.get = original_get


def _fresh_league(league_id: int, oauth_path: str, token_dir: str):
    league = init_league(league_id, oauth_path, token_dir)
    league.free_agent_cache = {}
    league.waivers_cache = None
    league.taken_players_cache = None
    league.player_details_cache = {}
    return league


def run_bulk(names: List[str], league_id: int, oauth_path: str, token_dir: str) -> int:
    with count_yahoo_http_calls() as counter:
        league = _fresh_league(league_id, oauth_path, token_dir)
        players = fetch_yahoo_available_players(league, include_waivers=True)
        idx = {str(p.get("name") or ""): p for p in players}
        for name in names:
            _ = idx.get(name)
    return counter["n"]


def run_targeted(names: List[str], league_id: int, oauth_path: str, token_dir: str) -> int:
    with count_yahoo_http_calls() as counter:
        league = _fresh_league(league_id, oauth_path, token_dir)
        lookup_players_availability(league, names, include_waivers=True)
    return counter["n"]


def run_taken_complement(names: List[str], league_id: int, oauth_path: str, token_dir: str) -> int:
    from fantasy_avail.yahoo import find_player_details_for_name

    with count_yahoo_http_calls() as counter:
        league = _fresh_league(league_id, oauth_path, token_dir)
        taken = league.taken_players() or []
        taken_ids = {int(p["player_id"]) for p in taken}
        for name in names:
            details = find_player_details_for_name(league, name)
            if details:
                _ = int(details["player_id"]) not in taken_ids
    return counter["n"]


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--names",
        nargs="+",
        default=DEFAULT_NAMES,
        help="Player display names to check (default: 10-name sample)",
    )
    parser.add_argument("--league-id", type=int, default=None)
    args = parser.parse_args(argv)

    cfg = load_config()
    league_id = args.league_id if args.league_id is not None else cfg.league_id
    names = args.names

    strategies: List[tuple[str, Callable[[], int]]] = [
        ("bulk FA+waiver fetch", lambda: run_bulk(names, league_id, cfg.oauth_path_str, cfg.token_dir_str)),
        ("targeted player_details+ownership", lambda: run_targeted(names, league_id, cfg.oauth_path_str, cfg.token_dir_str)),
        ("taken pool + player_details", lambda: run_taken_complement(names, league_id, cfg.oauth_path_str, cfg.token_dir_str)),
    ]

    print(f"League id: {league_id}")
    print(f"Names ({len(names)}): {', '.join(names)}")
    print()

    for label, fn in strategies:
        try:
            n = fn()
            print(f"{label}: {n} HTTP call(s)")
        except Exception as e:
            print(f"{label}: FAILED ({e})", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
