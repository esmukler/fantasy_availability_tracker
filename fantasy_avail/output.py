from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from typing import Any, Callable, Dict, List, Optional, Tuple

from fantasy_avail.models import ProbableStart
from fantasy_avail.name_utils import normalize_name
from fantasy_avail.yahoo import (
    AVAIL_SOURCE_FREE_AGENT,
    AVAIL_SOURCE_NA_FREE_AGENT,
    AVAIL_SOURCE_WAIVERS,
    FANTASY_AVAIL_SOURCE_KEY,
)

_ANSI_RESET = "\033[0m"
_ANSI_RED = "\033[31m"

# Visiting @ Coors or Oakland Coliseum; home starts for those clubs' pitchers (abbr from StatsAPI / overrides).
_REDHIGH_MATCHUP_ABBR = frozenset({"COL", "ATH", "OAK"})


def _colorize_stat(value: Any, *, stat_name: str, use_ansi: bool) -> str:
    text = str(value)
    if not use_ansi:
        return text
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return text

    if stat_name == "era":
        if numeric < 3.0:
            return f"\033[32m{text}{_ANSI_RESET}"
        if numeric > 6.0:
            return f"\033[31m{text}{_ANSI_RESET}"
        if numeric > 5.0:
            return f"\033[33m{text}{_ANSI_RESET}"
        return text

    if stat_name == "whip":
        if numeric < 1.1:
            return f"\033[32m{text}{_ANSI_RESET}"
        if numeric > 1.5:
            return f"\033[31m{text}{_ANSI_RESET}"
        if numeric > 1.4:
            return f"\033[33m{text}{_ANSI_RESET}"
        return text

    return text


def _hits_include_waivers(hits: List[Dict[str, Any]]) -> bool:
    return any(h.get(FANTASY_AVAIL_SOURCE_KEY) == AVAIL_SOURCE_WAIVERS for h in hits)


def _hits_include_na(hits: List[Dict[str, Any]]) -> bool:
    return any(
        h.get(FANTASY_AVAIL_SOURCE_KEY) == AVAIL_SOURCE_NA_FREE_AGENT
        or (h.get("status") or "").strip().upper() == "NA"
        for h in hits
    )


def _yahoo_availability_from_hits(hits: List[Dict[str, Any]]) -> str:
    if _hits_include_waivers(hits):
        return AVAIL_SOURCE_WAIVERS
    if _hits_include_na(hits):
        return AVAIL_SOURCE_NA_FREE_AGENT
    return AVAIL_SOURCE_FREE_AGENT


def _availability_name_suffix(*, on_waivers: bool, on_na: bool) -> str:
    if on_waivers:
        return " (W)"
    if on_na:
        return " (NA)"
    return ""


def _hits_for_json(hits: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [{k: v for k, v in h.items() if k != FANTASY_AVAIL_SOURCE_KEY} for h in hits]


def format_game_date_for_display(d: dt.date) -> str:
    """Human-readable date for terminal output, e.g. Wed Apr 1."""
    return f"{d:%a %b} {d.day}"


def _format_pitcher_line(
    ps: ProbableStart,
    status: str,
    opponent_color_prefixes: Optional[Dict[str, str]] = None,
    name_suffix: str = "",
    *,
    use_ansi: bool = False,
) -> str:
    p_abbr = ps.pitcher_team_abbr.strip()
    o_abbr = ps.opponent_abbr.strip()
    pitcher_team = p_abbr or (ps.away_team if ps.pitcher_side == "away" else ps.home_team)
    opponent_team = o_abbr or (ps.home_team if ps.pitcher_side == "away" else ps.away_team)
    prefixes = opponent_color_prefixes or {}

    if use_ansi and ps.pitcher_side == "home" and p_abbr and p_abbr.upper() in _REDHIGH_MATCHUP_ABBR:
        team_parens = f"{_ANSI_RED}({pitcher_team}){_ANSI_RESET}"
    else:
        team_parens = f"({pitcher_team})"

    if use_ansi and ps.pitcher_side == "away" and o_abbr and o_abbr.upper() in _REDHIGH_MATCHUP_ABBR:
        opponent_display = f"{_ANSI_RED}{ps.venue_marker}{opponent_team}{_ANSI_RESET}"
    elif o_abbr and prefixes:
        open_seq = prefixes.get(o_abbr.upper())
        opponent_display = (
            f"{open_seq}{opponent_team}{_ANSI_RESET}" if open_seq else opponent_team
        )
        opponent_display = f"{ps.venue_marker}{opponent_display}"
    else:
        opponent_display = f"{ps.venue_marker}{opponent_team}"

    return (
        f"{format_game_date_for_display(ps.date)}  [{status}] {ps.pitcher_name}{name_suffix} {team_parens} "
        f"- {opponent_display}"
    )


def format_available_line(
    ps: ProbableStart,
    opponent_color_prefixes: Optional[Dict[str, str]] = None,
    *,
    on_waivers: bool = False,
    on_na: bool = False,
    use_ansi: bool = False,
) -> str:
    suffix = _availability_name_suffix(on_waivers=on_waivers, on_na=on_na)
    return _format_pitcher_line(
        ps,
        status="AVAIL",
        opponent_color_prefixes=opponent_color_prefixes,
        name_suffix=suffix,
        use_ansi=use_ansi,
    )


def format_all_line(
    ps: ProbableStart,
    is_available: bool,
    opponent_color_prefixes: Optional[Dict[str, str]] = None,
    *,
    on_waivers: bool = False,
    on_na: bool = False,
    use_ansi: bool = False,
) -> str:
    suffix = (
        _availability_name_suffix(on_waivers=on_waivers, on_na=on_na)
        if is_available
        else ""
    )
    return _format_pitcher_line(
        ps,
        status=("AVAIL" if is_available else "TAKEN"),
        opponent_color_prefixes=opponent_color_prefixes,
        name_suffix=suffix,
        use_ansi=use_ansi,
    )


def format_mlb_season_stats_line(stats: Dict[str, Any], *, use_ansi: bool = False) -> str:
    era_display = _colorize_stat(stats["era"], stat_name="era", use_ansi=use_ansi)
    whip_display = _colorize_stat(stats["whip"], stat_name="whip", use_ansi=use_ansi)
    parts = [
        f"W-L: {stats['wins']}-{stats['losses']}",
        f"GS/GP: {stats['games_started']}/{stats['games_pitched']}",
        f"ERA: {era_display}",
        f"WHIP: {whip_display}",
        f"IP: {stats['innings_pitched']}",
        f"K: {stats['strikeouts']}",
    ]
    if "quality_starts" in stats:
        parts.append(f"QS: {stats['quality_starts']}")
    return "    " + " | ".join(parts)


def emit_results(
    args: argparse.Namespace,
    probables: List[ProbableStart],
    matched: List[Tuple[ProbableStart, List[Dict[str, Any]]]],
    unmatched: List[ProbableStart],
    available_by_name: Dict[str, List[Dict[str, Any]]],
    get_mlb_season_stats: Callable[[int], Optional[Dict[str, Any]]],
    opponent_color_prefixes: Dict[str, str],
) -> None:
    if args.json:
        if args.all_probables:
            payload = []
            for ps in sorted(
                probables, key=lambda x: (x.date, x.away_abbr, x.home_abbr, x.pitcher_side)
            ):
                key = normalize_name(ps.pitcher_name)
                hits = available_by_name.get(key) or []
                is_av = bool(hits)
                row: Dict[str, Any] = {
                    "date": ps.date.isoformat(),
                    "game_pk": ps.game_pk,
                    "fp_slug": ps.fp_slug,
                    "matchup": {"away": ps.away_abbr, "home": ps.home_abbr},
                    "side": ps.pitcher_side,
                    "mlb_name": ps.pitcher_name,
                    "mlbam_id": ps.pitcher_mlbam_id,
                    "is_available": is_av,
                }
                if is_av:
                    row["yahoo_availability"] = _yahoo_availability_from_hits(hits)
                payload.append(row)
        else:
            payload = []
            for ps, hits in matched:
                row: Dict[str, Any] = {
                    "date": ps.date.isoformat(),
                    "game_pk": ps.game_pk,
                    "fp_slug": ps.fp_slug,
                    "matchup": {"away": ps.away_abbr, "home": ps.home_abbr},
                    "side": ps.pitcher_side,
                    "mlb_name": ps.pitcher_name,
                    "mlbam_id": ps.pitcher_mlbam_id,
                    "is_available": True,
                    "yahoo_availability": _yahoo_availability_from_hits(hits),
                    "yahoo_free_agents": _hits_for_json(hits),
                }
                if ps.pitcher_mlbam_id is not None:
                    row["mlb_season_stats"] = get_mlb_season_stats(ps.pitcher_mlbam_id)
                else:
                    row["mlb_season_stats"] = None
                payload.append(row)
        print(json.dumps(payload, indent=2, sort_keys=False))
        return

    use_ansi = sys.stdout.isatty() and not (os.environ.get("NO_COLOR") or "").strip()
    opp_colors = opponent_color_prefixes if use_ansi else {}

    if args.all_probables:
        print(f"All probable pitchers with Yahoo availability (league_id={args.league_id})")
        print("-" * 72)
        if not probables:
            print("(none)")
        for i, ps in enumerate(
            sorted(
                probables, key=lambda x: (x.date, x.away_abbr, x.home_abbr, x.pitcher_side)
            )
        ):
            if i > 0:
                print()
            key = normalize_name(ps.pitcher_name)
            hits = available_by_name.get(key) or []
            is_available = bool(hits)
            on_waivers = _hits_include_waivers(hits) if hits else False
            on_na = _hits_include_na(hits) if hits else False
            print(
                format_all_line(
                    ps,
                    is_available=is_available,
                    opponent_color_prefixes=opp_colors,
                    on_waivers=on_waivers,
                    on_na=on_na,
                    use_ansi=use_ansi,
                )
            )
        return

    print(
        f"Matched probable pitchers available as FA, waivers, or NA "
        f"(league_id={args.league_id})"
    )
    print("-" * 72)
    if not matched:
        print("(none)")
    for i, (ps, hits) in enumerate(matched):
        if i > 0:
            print()
        print(
            format_available_line(
                ps,
                opponent_color_prefixes=opp_colors,
                on_waivers=_hits_include_waivers(hits),
                on_na=_hits_include_na(hits),
                use_ansi=use_ansi,
            )
        )
        if ps.pitcher_mlbam_id is not None:
            st = get_mlb_season_stats(ps.pitcher_mlbam_id)
            if st:
                print(format_mlb_season_stats_line(st, use_ansi=use_ansi))
            else:
                print("    (MLB season stats unavailable)")

        else:
            print("    (no MLB player id for stats)")

    if args.show_unmatched:
        print(
            "\nUnmatched probable pitchers "
            "(name didn’t match a Yahoo FA, waiver, or NA free agent)"
        )
        print(
            "Add fixes under yahoo_name_by_slug in "
            f"{args.player_overrides!r} (key = fp_slug).",
            file=sys.stderr,
        )
        print("-" * 72)
        if not unmatched:
            print("(none)")
        for i, ps in enumerate(unmatched):
            if i > 0:
                print()
            print(
                format_all_line(
                    ps,
                    is_available=False,
                    opponent_color_prefixes=opp_colors,
                    use_ansi=use_ansi,
                )
            )
            print(
                f"    fp_slug={ps.fp_slug!r}  "
                f"(yahoo_name_by_slug: {ps.fp_slug!r}: \"<name as Yahoo lists it>\")"
            )


def partition_probables_by_fa(
    probables: List[ProbableStart],
    available_by_name: Dict[str, List[Dict[str, Any]]],
) -> Tuple[List[Tuple[ProbableStart, List[Dict[str, Any]]]], List[ProbableStart]]:
    matched: List[Tuple[ProbableStart, List[Dict[str, Any]]]] = []
    unmatched: List[ProbableStart] = []
    for ps in probables:
        key = normalize_name(ps.pitcher_name)
        hits = available_by_name.get(key)
        if hits:
            matched.append((ps, hits))
        else:
            unmatched.append(ps)
    matched.sort(key=lambda t: (t[0].date, t[0].away_abbr, t[0].home_abbr, t[0].pitcher_side))
    unmatched.sort(key=lambda ps: (ps.date, ps.away_abbr, ps.home_abbr, ps.pitcher_side))
    return matched, unmatched
