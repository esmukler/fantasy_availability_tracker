from __future__ import annotations

import datetime as dt
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

import requests

from fantasy_avail.config import AppConfig, load_config
from fantasy_avail.fantasypros import (
    fetch_probable_pitchers,
    load_fantasypros_cookie_file,
    log_fantasypros_cookie_status,
)
from fantasy_avail.mlb_api import (
    enrich_probables_with_schedule,
    fetch_mlb_pitching_season_stats,
    fetch_mlb_schedule,
    finalize_probable_pitchers,
    format_game_time_pacific,
    maybe_refresh_team_ops_csv,
)
from fantasy_avail.models import ProbableStart
from fantasy_avail.name_utils import normalize_name
from fantasy_avail.overrides import (
    apply_abbr_overrides,
    load_player_name_overrides,
    load_team_abbr_overrides,
)
from fantasy_avail.availability_cache import get_availability_cache
from fantasy_avail.schemas import GetAvailableProbablePitchersResult, ProbablePitcherRow
from fantasy_avail.yahoo import (
    enrich_targeted_availability_lists_by_names,
    hits_for_json,
    index_targeted_availability_by_names,
    yahoo_availability_from_hits,
)

PACIFIC_TZ = ZoneInfo("America/Los_Angeles")


def default_start_date() -> dt.date:
    """Return the default schedule start: tomorrow in US Pacific time.

    "Tomorrow" is defined relative to the current calendar day in
    ``America/Los_Angeles`` so the first day shown stays e.g. Wednesday until
    11:59 PM Tuesday Pacific, regardless of the host machine's timezone.
    """
    pacific_today = dt.datetime.now(PACIFIC_TZ).date()
    return pacific_today + dt.timedelta(days=1)


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
    availability = yahoo_availability_from_hits(hits)
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
        yahoo_free_agents=hits_for_json(hits),
        mlb_season_stats=stats,
        opposing_pitcher_name=opposing_pitcher_name,
    )


def _era_sort_value(stats: Optional[Dict[str, Any]]) -> float:
    if not stats:
        return float("inf")
    era = stats.get("era")
    if era is None or era == "—":
        return float("inf")
    try:
        return float(era)
    except (TypeError, ValueError):
        return float("inf")


def _probable_row_sort_key(row: ProbablePitcherRow) -> tuple:
    return (row.date, _era_sort_value(row.mlb_season_stats), row.mlb_name.lower())


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
    start = start_date or default_start_date()
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
            f"Yahoo init failed: {e}. Start the web server or an MCP tool to complete OAuth bootstrap."
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
        for ps in probables:
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
        for ps, hits in matched:
            available_rows.append(
                _probable_row(
                    ps,
                    hits,
                    get_mlb_season_stats=get_mlb_season_stats,
                    include_stats=include_stats,
                    opposing_pitcher_name=_opposing_pitcher_name(ps, by_game),
                )
            )

    available_rows.sort(key=_probable_row_sort_key)

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
