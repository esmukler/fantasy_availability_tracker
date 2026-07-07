from __future__ import annotations

import csv
import datetime as dt
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

import requests

from fantasy_avail.models import ProbableStart

STATSAPI_TEAMS_URL = "https://statsapi.mlb.com/api/v1/teams"
STATSAPI_SCHEDULE_URL = "https://statsapi.mlb.com/api/v1/schedule"
STATSAPI_TEAMS_STATS_URL = "https://statsapi.mlb.com/api/v1/teams/stats"
STATSAPI_PEOPLE_SEARCH_URL = "https://statsapi.mlb.com/api/v1/people/search"
STATSAPI_PEOPLE_STATS_URL = "https://statsapi.mlb.com/api/v1/people/{player_id}/stats"

_REPO_ROOT = Path(__file__).resolve().parent.parent
_TEAM_OPS_STAMP_NAME = ".team_ops_last_run"


def fetch_mlb_teams_context(session: requests.Session) -> Tuple[Dict[str, str], Dict[str, str]]:
    """
    Returns (abbr_upper -> club name, fp_row_team_name_lower -> abbr_upper).
    Club name uses StatsAPI team 'name' (e.g. Arizona Diamondbacks).
    """
    resp = session.get(STATSAPI_TEAMS_URL, params={"sportId": 1}, timeout=30)
    resp.raise_for_status()
    teams = resp.json().get("teams") or []
    abbr_to_name: Dict[str, str] = {}
    row_name_to_abbr: Dict[str, str] = {}
    for t in teams:
        abbr = (t.get("abbreviation") or "").strip().upper()
        name = (t.get("name") or "").strip()
        if not abbr or not name:
            continue
        abbr_to_name[abbr] = name
        row_name_to_abbr[name.lower()] = abbr
        tn = (t.get("teamName") or "").strip()
        if tn:
            row_name_to_abbr[tn.lower()] = abbr
    return abbr_to_name, row_name_to_abbr


def resolve_mlbam_id(
    session: requests.Session,
    display_name: str,
    cache: Dict[str, Optional[int]],
) -> Optional[int]:
    if not display_name.strip():
        return None
    key = display_name.strip().lower()
    if key in cache:
        return cache[key]
    resp = session.get(
        STATSAPI_PEOPLE_SEARCH_URL,
        params={"names": display_name.strip()},
        timeout=30,
    )
    resp.raise_for_status()
    people = resp.json().get("people") or []
    pitchers: List[Dict[str, Any]] = []
    for p in people:
        pos = p.get("primaryPosition") or {}
        if pos.get("type") == "Pitcher" or pos.get("code") == "1":
            pitchers.append(p)
    candidates = pitchers if pitchers else people
    if not candidates:
        cache[key] = None
        return None
    target_lower = display_name.strip().lower()
    exact = [p for p in candidates if (p.get("fullName") or "").strip().lower() == target_lower]
    pool = exact if exact else candidates
    active = [p for p in pool if p.get("active") is True]
    pool2 = active if active else pool
    chosen = pool2[0]
    pid = chosen.get("id")
    if isinstance(pid, int):
        cache[key] = pid
        return pid
    cache[key] = None
    return None


def finalize_probable_pitchers(
    session: requests.Session,
    probables: List[ProbableStart],
    yahoo_name_by_slug: Dict[str, str],
    mlbam_by_slug: Dict[str, int],
    mlbam_cache: Dict[str, Optional[int]],
) -> List[ProbableStart]:
    """Apply manual Yahoo display names and resolve MLBAM ids (override or StatsAPI search)."""
    done: List[ProbableStart] = []
    for ps in probables:
        name = yahoo_name_by_slug.get(ps.fp_slug, ps.pitcher_name)
        if ps.fp_slug in mlbam_by_slug:
            mlbam = mlbam_by_slug[ps.fp_slug]
        else:
            mlbam = resolve_mlbam_id(session, name, mlbam_cache)
        done.append(
            ProbableStart(
                date=ps.date,
                game_pk=ps.game_pk,
                pitcher_name=name,
                pitcher_mlbam_id=mlbam,
                pitcher_side=ps.pitcher_side,
                away_team=ps.away_team,
                home_team=ps.home_team,
                away_abbr=ps.away_abbr,
                home_abbr=ps.home_abbr,
                fp_slug=ps.fp_slug,
                game_datetime=ps.game_datetime,
            )
        )
    return done


def _parse_game_datetime(raw: Any) -> Optional[dt.datetime]:
    if not raw or not isinstance(raw, str):
        return None
    text = raw.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = dt.datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=dt.timezone.utc)
    return parsed


def format_game_time_pacific(game_datetime: Optional[dt.datetime]) -> str:
    """Format a game start time in US Pacific, or TBD when unknown."""
    if game_datetime is None:
        return "TBD"
    pt = game_datetime.astimezone(ZoneInfo("America/Los_Angeles"))
    time_part = pt.strftime("%I:%M %p").lstrip("0")
    return f"{pt:%a} {time_part} PT"


def fetch_mlb_schedule(
    session: requests.Session,
    start_date: date,
    end_date: date,
) -> Dict[Tuple[date, str, str], Tuple[int, dt.datetime]]:
    """
    Fetch MLB schedule for a date range.

    Returns a map of (game_date, away_abbr, home_abbr) -> (game_pk, game_datetime UTC).
    """
    resp = session.get(
        STATSAPI_SCHEDULE_URL,
        params={
            "sportId": 1,
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
            "hydrate": "team",
        },
        timeout=30,
    )
    resp.raise_for_status()
    out: Dict[Tuple[date, str, str], Tuple[int, dt.datetime]] = {}
    for day_block in resp.json().get("dates") or []:
        game_date_raw = day_block.get("date")
        if not game_date_raw:
            continue
        try:
            game_date = date.fromisoformat(str(game_date_raw))
        except ValueError:
            continue
        for game in day_block.get("games") or []:
            teams = game.get("teams") or {}
            away_abbr = (
                ((teams.get("away") or {}).get("team") or {}).get("abbreviation") or ""
            ).strip().upper()
            home_abbr = (
                ((teams.get("home") or {}).get("team") or {}).get("abbreviation") or ""
            ).strip().upper()
            if not away_abbr or not home_abbr:
                continue
            game_pk = game.get("gamePk")
            game_datetime = _parse_game_datetime(game.get("gameDate"))
            if not isinstance(game_pk, int) or game_datetime is None:
                continue
            key = (game_date, away_abbr, home_abbr)
            out[key] = (game_pk, game_datetime)
    return out


def enrich_probables_with_schedule(
    probables: List[ProbableStart],
    schedule: Dict[Tuple[date, str, str], Tuple[int, dt.datetime]],
) -> List[ProbableStart]:
    """Attach game_pk and game_datetime from MLB schedule when a matchup matches."""
    enriched: List[ProbableStart] = []
    for ps in probables:
        key = (ps.date, ps.away_abbr.strip().upper(), ps.home_abbr.strip().upper())
        match = schedule.get(key)
        if match is None:
            enriched.append(ps)
            continue
        game_pk, game_datetime = match
        enriched.append(
            ProbableStart(
                date=ps.date,
                game_pk=game_pk,
                pitcher_name=ps.pitcher_name,
                pitcher_mlbam_id=ps.pitcher_mlbam_id,
                pitcher_side=ps.pitcher_side,
                away_team=ps.away_team,
                home_team=ps.home_team,
                away_abbr=ps.away_abbr,
                home_abbr=ps.home_abbr,
                fp_slug=ps.fp_slug,
                game_datetime=game_datetime,
            )
        )
    return enriched


def _parse_pitching_stats_payload(payload: Dict[str, Any], season: int) -> Optional[Dict[str, Any]]:
    """Parse MLB StatsAPI /people/{id}/stats?stats=season,seasonAdvanced response."""
    season_st: Dict[str, Any] = {}
    advanced_st: Dict[str, Any] = {}
    for block in payload.get("stats") or []:
        t = (block.get("type") or {}).get("displayName", "")
        splits = block.get("splits") or []
        if not splits:
            continue
        st = splits[0].get("stat") or {}
        if t == "season":
            season_st = st
        elif t == "seasonAdvanced":
            advanced_st = st

    if not season_st:
        return None

    out: Dict[str, Any] = {
        "season": season,
        "wins": int(season_st.get("wins") or 0),
        "losses": int(season_st.get("losses") or 0),
        "games_started": int(season_st.get("gamesStarted") or 0),
        "games_pitched": int(season_st.get("gamesPlayed") or 0),
        "era": str(season_st.get("era") if season_st.get("era") is not None else "—"),
        "whip": str(season_st.get("whip") if season_st.get("whip") is not None else "—"),
        "innings_pitched": str(
            season_st.get("inningsPitched") if season_st.get("inningsPitched") is not None else "—"
        ),
        "strikeouts": int(season_st.get("strikeOuts") or 0),
    }
    if advanced_st is not None and "qualityStarts" in advanced_st:
        out["quality_starts"] = int(advanced_st.get("qualityStarts") or 0)
    return out


def fetch_mlb_pitching_season_stats(
    session: requests.Session,
    mlbam_id: int,
    season: int,
) -> Optional[Dict[str, Any]]:
    url = STATSAPI_PEOPLE_STATS_URL.format(player_id=mlbam_id)
    params = {"stats": "season,seasonAdvanced", "group": "pitching", "season": str(season)}
    resp = session.get(url, params=params, timeout=30)
    resp.raise_for_status()
    return _parse_pitching_stats_payload(resp.json(), season)


def fetch_team_season_ops(
    session: requests.Session,
    season: int,
) -> List[Tuple[str, str, float]]:
    """Season hitting OPS per team from Stats API (30 rows)."""
    resp = session.get(
        STATSAPI_TEAMS_STATS_URL,
        params={
            "stats": "season",
            "group": "hitting",
            "sportId": 1,
            "season": str(season),
        },
        timeout=30,
    )
    resp.raise_for_status()
    stats = resp.json().get("stats") or []
    if not stats:
        return []
    splits = stats[0].get("splits") or []
    rows: List[Tuple[str, str, float]] = []
    for sp in splits:
        team = (sp.get("team") or {}).get("name") or ""
        raw_ops = (sp.get("stat") or {}).get("ops")
        ops_s = "" if raw_ops is None else str(raw_ops).strip()
        try:
            val = float(ops_s) if ops_s else 0.0
        except ValueError:
            val = 0.0
        rows.append((team, ops_s, val))
    return rows


def _competition_ranks_by_ops(
    sorted_rows: List[Tuple[str, str, float]],
) -> List[Tuple[int, str, str]]:
    """Competition ranking: tied OPS share rank; next rank skips."""
    out: List[Tuple[int, str, str]] = []
    rank = 1
    for i, (team, ops_s, val) in enumerate(sorted_rows):
        if i > 0 and val < sorted_rows[i - 1][2]:
            rank = i + 1
        out.append((rank, team, ops_s))
    return out


def write_team_ops_csv(
    session: requests.Session,
    output_path: Path | str,
    *,
    season: Optional[int] = None,
) -> Path:
    """
    Fetch team hitting OPS for ``season`` (default: calendar year), sort by OPS
    descending, write CSV with columns rank,team,ops. Overwrites ``output_path``.
    """
    if season is None:
        season = date.today().year
    path = Path(output_path)
    rows = fetch_team_season_ops(session, season)
    rows.sort(key=lambda x: (-x[2], x[0]))
    ranked = _competition_ranks_by_ops(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["rank", "team", "ops"])
        w.writerows(ranked)
    return path


def default_team_ops_csv_path(season: Optional[int] = None) -> Path:
    if season is None:
        season = date.today().year
    return _REPO_ROOT / f"team_ops_{season}.csv"


def _team_ops_stamp_path(repo_root: Path) -> Path:
    return repo_root / _TEAM_OPS_STAMP_NAME


def team_ops_csv_stale(repo_root: Path, today: Optional[date] = None) -> bool:
    """True if we have not successfully refreshed team OPS CSV today (local date)."""
    today = today or date.today()
    stamp = _team_ops_stamp_path(repo_root)
    if not stamp.exists():
        return True
    try:
        last = date.fromisoformat(stamp.read_text(encoding="utf-8").strip())
    except (ValueError, OSError):
        return True
    return last < today


def _mark_team_ops_csv_refreshed(repo_root: Path, today: Optional[date] = None) -> None:
    today = today or date.today()
    _team_ops_stamp_path(repo_root).write_text(today.isoformat() + "\n", encoding="utf-8")


def record_team_ops_csv_refreshed(
    repo_root: Optional[Path] = None,
    today: Optional[date] = None,
) -> None:
    """Mark team OPS as refreshed for today (used after a manual ``update_team_ops`` run)."""
    _mark_team_ops_csv_refreshed(repo_root if repo_root is not None else _REPO_ROOT, today)


def maybe_refresh_team_ops_csv(
    session: requests.Session,
    *,
    season: int,
    repo_root: Optional[Path] = None,
) -> bool:
    """
    If team OPS was not refreshed yet today, fetch from Stats API and overwrite
    ``team_ops_{season}.csv``. Returns True when a refresh ran.
    """
    root = repo_root if repo_root is not None else _REPO_ROOT
    if not team_ops_csv_stale(root):
        return False
    write_team_ops_csv(session, default_team_ops_csv_path(season), season=season)
    _mark_team_ops_csv_refreshed(root)
    return True
