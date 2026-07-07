from __future__ import annotations

import datetime as dt
import sys
from typing import Any, Dict, List, Optional, Tuple

import requests

from fantasy_avail.config import AppConfig, load_config
from fantasy_avail.fantasypros import (
    fetch_probable_pitchers,
    load_fantasypros_cookie_file,
    log_fantasypros_cookie_status,
)
from fantasy_avail.mlb_api import (
    default_team_ops_csv_path,
    enrich_probables_with_schedule,
    fetch_mlb_pitching_season_stats,
    fetch_mlb_schedule,
    fetch_mlb_teams_context,
    finalize_probable_pitchers,
    format_game_time_pacific,
    maybe_refresh_team_ops_csv,
)
from fantasy_avail.models import ProbableStart
from fantasy_avail.name_utils import normalize_name
from fantasy_avail.output import (
    _hits_for_json,
    _yahoo_availability_from_hits,
    partition_probables_by_fa,
)
from fantasy_avail.overrides import (
    apply_abbr_overrides,
    load_player_name_overrides,
    load_team_abbr_overrides,
)
from fantasy_avail.availability_cache import get_availability_cache
from fantasy_avail.schemas import GetAvailableProbablePitchersResult, ProbablePitcherRow
from fantasy_avail.yahoo import (
    enrich_targeted_availability_lists_by_names,
    index_targeted_availability_by_names,
)


def _game_key(ps: ProbableStart) -> Tuple[dt.date, str, str]:
    return (ps.date, ps.away_abbr, ps.home_abbr)


def _index_probables_by_game(
    probables: List[ProbableStart],
) -> Dict[Tuple[dt.date, str, str], Dict[str, ProbableStart]]:
    by_game: Dict[Tuple[dt.date, str, str], Dict[str, ProbableStart]] = {}
    for ps in probables:
        by_game.setdefault(_game_key(ps), {})[ps.pitcher_side] = ps
    return by_game


def _opposing_pitcher_name(
    ps: ProbableStart,
    by_game: Dict[Tuple[dt.date, str, str], Dict[str, ProbableStart]],
) -> Optional[str]:
    sides = by_game.get(_game_key(ps))
    if not sides:
        return None
    other_side = "home" if ps.pitcher_side == "away" else "away"
    other = sides.get(other_side)
    return other.pitcher_name if other is not None else None


def _probable_row(
    ps: ProbableStart,
    hits: List[Dict[str, Any]],
    *,
    get_mlb_season_stats,
    include_stats: bool,
    opposing_pitcher_name: Optional[str] = None,
) -> ProbablePitcherRow:
    stats = None
    if include_stats and ps.pitcher_mlbam_id is not None:
        stats = get_mlb_season_stats(ps.pitcher_mlbam_id)
    availability = _yahoo_availability_from_hits(hits)
    return ProbablePitcherRow(
        date=ps.date.isoformat(),
        game_pk=ps.game_pk,
        fp_slug=ps.fp_slug,
        matchup={"away": ps.away_abbr, "home": ps.home_abbr},
        side=ps.pitcher_side,
        mlb_name=ps.pitcher_name,
        mlbam_id=ps.pitcher_mlbam_id,
        is_available=True,
        pitcher_team=ps.pitcher_team_abbr,
        opponent_team=ps.opponent_abbr,
        home_away=ps.pitcher_side,
        game_time_pt=format_game_time_pacific(ps.game_datetime),
        availability=availability,
        yahoo_availability=availability,
        yahoo_free_agents=_hits_for_json(hits),
        mlb_season_stats=stats,
        opposing_pitcher_name=opposing_pitcher_name,
    )


def _probable_sort_key(ps: ProbableStart) -> tuple:
    sentinel = dt.datetime.max.replace(tzinfo=dt.timezone.utc)
    game_dt = ps.game_datetime if ps.game_datetime is not None else sentinel
    return (ps.date, game_dt, ps.pitcher_name.lower())


def get_available_probable_pitchers(
    *,
    start_date: Optional[dt.date] = None,
    days: int = 5,
    league_id: Optional[int] = None,
    include_waivers: bool = True,
    include_stats: bool = True,
    all_probables: bool = False,
    season: Optional[int] = None,
    skip_team_ops_update: bool = False,
    oauth_path: Optional[str] = None,
    token_dir: Optional[str] = None,
    fp_cookie_file: Optional[str] = None,
    player_overrides: Optional[str] = None,
    team_abbr_overrides: Optional[str] = None,
    config: Optional[AppConfig] = None,
) -> GetAvailableProbablePitchersResult:
    cfg = config or load_config()
    lid = league_id if league_id is not None else cfg.league_id
    start = start_date or (dt.date.today() + dt.timedelta(days=1))
    season_year = season if season is not None else start.year
    warnings: List[str] = []

    fp_path = fp_cookie_file if fp_cookie_file is not None else str(cfg.fp_cookie_file)
    player_path = player_overrides or str(cfg.player_overrides)
    abbr_path = team_abbr_overrides or str(cfg.team_abbr_overrides)

    abbr_overrides = load_team_abbr_overrides(abbr_path)
    yahoo_by_slug, mlbam_by_slug = load_player_name_overrides(player_path)
    fp_cookie = load_fantasypros_cookie_file(fp_path) if fp_path.strip() else None
    log_fantasypros_cookie_status(fp_path or "", fp_cookie)

    mlb_session = requests.Session()
    mlb_stats_cache: Dict[int, Optional[Dict[str, Any]]] = {}
    mlbam_resolve_cache: Dict[str, Optional[int]] = {}

    if not skip_team_ops_update:
        try:
            maybe_refresh_team_ops_csv(mlb_session, season=season_year)
        except requests.RequestException as e:
            warnings.append(f"Team OPS CSV refresh skipped: {e}")

    def get_mlb_season_stats(mlbam_id: int) -> Optional[Dict[str, Any]]:
        if mlbam_id not in mlb_stats_cache:
            try:
                mlb_stats_cache[mlbam_id] = fetch_mlb_pitching_season_stats(
                    mlb_session, mlbam_id, season_year
                )
            except (requests.RequestException, ValueError, TypeError, KeyError):
                mlb_stats_cache[mlbam_id] = None
        return mlb_stats_cache[mlbam_id]

    try:
        raw = fetch_probable_pitchers(
            start_date=start,
            days=days,
            session=mlb_session,
            fp_cookie_header=fp_cookie,
        )
        probables = [
            apply_abbr_overrides(ps, abbr_overrides)
            for ps in finalize_probable_pitchers(
                mlb_session, raw, yahoo_by_slug, mlbam_by_slug, mlbam_resolve_cache
            )
        ]
        end_date = start + dt.timedelta(days=days - 1)
        try:
            schedule = fetch_mlb_schedule(mlb_session, start, end_date)
            probables = enrich_probables_with_schedule(probables, schedule)
        except requests.RequestException as e:
            warnings.append(f"MLB schedule enrichment skipped: {e}")
    except (RuntimeError, requests.HTTPError, requests.RequestException) as e:
        raise RuntimeError(f"Fantasy Pros fetch failed: {e}") from e

    if len(probables) < 20:
        if fp_path.strip():
            warnings.append(
                f"Only {len(probables)} probable starter(s) in window; "
                f"try updating cookie in {fp_path!r}."
            )
        else:
            warnings.append(
                f"Only {len(probables)} probable starter(s) in window; "
                "set FP_COOKIE_FILE for a fuller Fantasy Pros grid."
            )

    cache = get_availability_cache()
    try:
        league = cache.get_league(lid)
    except Exception as e:
        raise RuntimeError(
            f"Yahoo init failed: {e}. Re-run OAuth bootstrap (e.g. get_available_pitchers.py)."
        ) from e

    pitcher_names = list({ps.pitcher_name for ps in probables})
    try:
        available_by_name = index_targeted_availability_by_names(
            league,
            pitcher_names,
            include_waivers=include_waivers,
        )
    except Exception as e:
        raise RuntimeError(f"Yahoo availability lookup failed: {e}") from e
    matched, unmatched = partition_probables_by_fa(probables, available_by_name)
    if unmatched:
        enrich_targeted_availability_lists_by_names(
            league,
            [ps.pitcher_name for ps in unmatched],
            available_by_name,
            include_waivers=include_waivers,
        )
        matched, unmatched = partition_probables_by_fa(probables, available_by_name)

    by_game = _index_probables_by_game(probables)
    available_rows: List[ProbablePitcherRow] = []
    if all_probables:
        sorted_probables = sorted(probables, key=_probable_sort_key)
        for ps in sorted_probables:
            key = normalize_name(ps.pitcher_name)
            hits = available_by_name.get(key) or []
            if hits:
                available_rows.append(
                    _probable_row(
                        ps,
                        hits,
                        get_mlb_season_stats=get_mlb_season_stats,
                        include_stats=include_stats,
                        opposing_pitcher_name=_opposing_pitcher_name(ps, by_game),
                    )
                )
    else:
        sorted_matched = sorted(matched, key=lambda t: _probable_sort_key(t[0]))
        for ps, hits in sorted_matched:
            available_rows.append(
                _probable_row(
                    ps,
                    hits,
                    get_mlb_season_stats=get_mlb_season_stats,
                    include_stats=include_stats,
                    opposing_pitcher_name=_opposing_pitcher_name(ps, by_game),
                )
            )

    unmatched_payload = [
        {
            "date": ps.date.isoformat(),
            "fp_slug": ps.fp_slug,
            "mlb_name": ps.pitcher_name,
            "matchup": {"away": ps.away_abbr, "home": ps.home_abbr},
            "side": ps.pitcher_side,
        }
        for ps in unmatched
    ]

    return GetAvailableProbablePitchersResult(
        league_id=lid,
        start_date=start.isoformat(),
        days=days,
        available=available_rows,
        unmatched=unmatched_payload,
        warnings=warnings,
    )


def run_probable_pitchers_cli(args) -> int:
    """CLI adapter: fetch data and emit via output.emit_results."""
    from fantasy_avail.mlb_api import fetch_mlb_teams_context
    from fantasy_avail.output import emit_results
    from fantasy_avail.overrides import load_opponent_colors_from_team_ops_csv

    cfg = load_config()
    season_year = args.season if args.season is not None else args.start_date.year
    mlb_session = requests.Session()
    mlb_stats_cache: Dict[int, Optional[Dict[str, Any]]] = {}
    mlbam_resolve_cache: Dict[str, Optional[int]] = {}

    abbr_overrides = load_team_abbr_overrides(args.abbr_overrides)
    yahoo_by_slug, mlbam_by_slug = load_player_name_overrides(args.player_overrides)
    fp_cookie = (
        load_fantasypros_cookie_file(args.fp_cookie_file)
        if (args.fp_cookie_file or "").strip()
        else None
    )
    log_fantasypros_cookie_status(args.fp_cookie_file or "", fp_cookie)

    if not args.skip_team_ops_update:
        try:
            maybe_refresh_team_ops_csv(mlb_session, season=season_year)
        except requests.RequestException as e:
            print(f"Team OPS CSV refresh skipped: {e}", file=sys.stderr)

    if args.no_opponent_colors:
        opponent_color_prefixes: Dict[str, str] = {}
    else:
        ops_csv = args.opponent_colors_csv or default_team_ops_csv_path(season_year)
        _, name_to_abbr = fetch_mlb_teams_context(mlb_session)
        opponent_color_prefixes = load_opponent_colors_from_team_ops_csv(
            ops_csv, name_to_abbr
        )

    def get_mlb_season_stats(mlbam_id: int) -> Optional[Dict[str, Any]]:
        if mlbam_id not in mlb_stats_cache:
            try:
                mlb_stats_cache[mlbam_id] = fetch_mlb_pitching_season_stats(
                    mlb_session, mlbam_id, season_year
                )
            except (requests.RequestException, ValueError, TypeError, KeyError):
                mlb_stats_cache[mlbam_id] = None
        return mlb_stats_cache[mlbam_id]

    try:
        raw = fetch_probable_pitchers(
            start_date=args.start_date,
            days=args.days,
            session=mlb_session,
            fp_cookie_header=fp_cookie,
        )
        probables = [
            apply_abbr_overrides(ps, abbr_overrides)
            for ps in finalize_probable_pitchers(
                mlb_session, raw, yahoo_by_slug, mlbam_by_slug, mlbam_resolve_cache
            )
        ]
    except RuntimeError as e:
        print(f"Fantasy Pros: {e}", file=sys.stderr)
        return 2
    except requests.HTTPError as e:
        print(f"HTTP error: {e}", file=sys.stderr)
        return 2
    except requests.RequestException as e:
        print(f"Request failed: {e}", file=sys.stderr)
        return 2

    if len(probables) < 20:
        if (args.fp_cookie_file or "").strip():
            cookie_hint = f"try updating the cookie in {args.fp_cookie_file!r}"
        else:
            cookie_hint = (
                "try --fp-cookie-file with a fresh Cookie header "
                "(see fantasypros_cookie.example)"
            )
        print(
            f"Fantasy Pros: only {len(probables)} probable starter(s) in the selected window; "
            f"if you expected a fuller grid, {cookie_hint}.",
            file=sys.stderr,
        )

    cache = get_availability_cache()
    try:
        league = cache.get_league(args.league_id)
    except Exception as e:
        print(f"Yahoo init failed: {e}", file=sys.stderr)
        return 3

    pitcher_names = list({ps.pitcher_name for ps in probables})
    try:
        available_by_name = index_targeted_availability_by_names(
            league,
            pitcher_names,
            include_waivers=True,
        )
    except Exception as e:
        print(f"Yahoo availability lookup failed: {e}", file=sys.stderr)
        return 3
    matched, unmatched = partition_probables_by_fa(probables, available_by_name)
    if unmatched:
        enrich_targeted_availability_lists_by_names(
            league,
            [ps.pitcher_name for ps in unmatched],
            available_by_name,
            include_waivers=True,
        )
        matched, unmatched = partition_probables_by_fa(probables, available_by_name)
    emit_results(
        args,
        probables,
        matched,
        unmatched,
        available_by_name,
        get_mlb_season_stats,
        opponent_color_prefixes,
    )
    return 0
