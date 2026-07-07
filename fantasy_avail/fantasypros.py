from __future__ import annotations

import datetime as dt
import os
import re
import sys
from typing import Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup

from fantasy_avail.mlb_api import fetch_mlb_teams_context
from fantasy_avail.models import ProbableStart
from fantasy_avail.name_utils import slug_to_display_name

FANTASYPROS_PROBABLE_PITCHERS_URL = "https://www.fantasypros.com/mlb/probable-pitchers.php"

_FP_DEFAULT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
_PLAYER_LINK_RE = re.compile(r"/mlb/players/([a-z0-9-]+)\.php", re.I)


def _parse_table_header_date(header: str, ref_year: int) -> Optional[dt.date]:
    """
    Parse FP column headers like 'Tue Mar 31' or 'Wed Apr 1' using ref_year,
    adjusting year if the date would be far from a typical MLB calendar spring.
    """
    h = header.strip()
    parts = h.split()
    if len(parts) < 3:
        return None
    mon_s, day_s = parts[-2], parts[-1]
    try:
        month = dt.datetime.strptime(mon_s, "%b").month
        day = int(day_s)
    except ValueError:
        return None
    try:
        d = dt.date(ref_year, month, day)
    except ValueError:
        return None
    ref = dt.date(ref_year, 3, 15)
    if d < ref - dt.timedelta(days=60):
        d = dt.date(ref_year + 1, month, day)
    elif d > ref + dt.timedelta(days=270):
        d = dt.date(ref_year - 1, month, day)
    return d


def _cell_opponent_token(cell_text: str) -> Optional[str]:
    t = cell_text.strip()
    if not t:
        return None
    first = t.split()[0]
    if first.startswith("@"):
        return first[1:].strip().upper() or None
    return first.strip().upper() or None


def load_fantasypros_cookie_file(path: str) -> Optional[str]:
    """
    Read a Cookie header value from a local file.
    Ignores blank lines and lines starting with #. Multiple non-comment lines are joined with '; '.
    """
    if not path or not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        chunks: List[str] = []
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            chunks.append(line.rstrip(";").strip())
    if not chunks:
        return None
    return "; ".join(chunks)


def log_fantasypros_cookie_status(path: str, cookie: Optional[str]) -> None:
    """One-line stderr hint so a wrong/missing cookie file is obvious."""
    p = path.strip()
    if not p:
        return
    if not os.path.isfile(p):
        print(
            f"Fantasy Pros: cookie file not found ({p!r}) — using logged-out grid. "
            f"Expected default filename is fantasypros_cookie.txt (pros, not props).",
            file=sys.stderr,
        )
        return
    if not cookie:
        print(
            f"Fantasy Pros: cookie file {p!r} is empty or only comments — using logged-out grid.",
            file=sys.stderr,
        )
        return
    print(
        f"Fantasy Pros: sending Cookie header from {p!r} ({len(cookie)} chars).",
        file=sys.stderr,
    )


def fetch_probable_pitchers(
    start_date: dt.date,
    days: int,
    session: Optional[requests.Session] = None,
    fp_cookie_header: Optional[str] = None,
) -> List[ProbableStart]:
    if days <= 0:
        return []

    end_date = start_date + dt.timedelta(days=days - 1)
    s = session or requests.Session()
    headers: Dict[str, str] = {"User-Agent": _FP_DEFAULT_UA}
    if fp_cookie_header:
        headers["Cookie"] = fp_cookie_header
    resp = s.get(FANTASYPROS_PROBABLE_PITCHERS_URL, headers=headers, timeout=45)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table", class_=lambda c: c and "table-condensed" in c.split())
    if table is None:
        raise RuntimeError("Fantasy Pros: could not find probable pitchers table (markup changed?)")

    abbr_to_name, row_name_to_abbr = fetch_mlb_teams_context(s)

    header_row = table.find("tr")
    if header_row is None:
        return []
    ths = header_row.find_all("th")
    if len(ths) < 2:
        return []

    date_cols: List[Tuple[int, dt.date]] = []
    ref_year = start_date.year
    for idx, th in enumerate(ths[1:], start=1):
        label = th.get_text(strip=True)
        gd = _parse_table_header_date(label, ref_year)
        if gd is None:
            continue
        if gd < start_date or gd > end_date:
            continue
        date_cols.append((idx, gd))

    out: List[ProbableStart] = []
    for tr in table.find_all("tr")[1:]:
        cells = tr.find_all("td")
        if len(cells) < 2:
            continue
        team_cell = cells[0]
        pitcher_team_label = team_cell.get_text(separator=" ", strip=True)
        slug_key = pitcher_team_label.lower()
        pitcher_abbr = row_name_to_abbr.get(slug_key)
        if not pitcher_abbr:
            continue

        for col_idx, game_date in date_cols:
            if col_idx >= len(cells):
                continue
            td = cells[col_idx]
            link = td.find("a", href=_PLAYER_LINK_RE)
            if link is None:
                continue
            m = _PLAYER_LINK_RE.search(link.get("href", ""))
            if not m:
                continue
            fp_slug = m.group(1).lower()
            opp_tok = _cell_opponent_token(td.get_text(separator=" ", strip=True))
            if not opp_tok:
                continue
            opp_name = abbr_to_name.get(opp_tok, opp_tok)
            cell_raw = td.get_text(separator=" ", strip=True)
            is_away = cell_raw.lstrip().startswith("@")

            if is_away:
                away_abbr, home_abbr = pitcher_abbr, opp_tok
                away_team, home_team = pitcher_team_label, opp_name
                side = "away"
            else:
                away_abbr, home_abbr = opp_tok, pitcher_abbr
                away_team, home_team = opp_name, pitcher_team_label
                side = "home"

            out.append(
                ProbableStart(
                    date=game_date,
                    game_pk=None,
                    pitcher_name=slug_to_display_name(fp_slug),
                    pitcher_mlbam_id=None,
                    pitcher_side=side,
                    away_team=away_team,
                    home_team=home_team,
                    away_abbr=away_abbr,
                    home_abbr=home_abbr,
                    fp_slug=fp_slug,
                )
            )

    return out
