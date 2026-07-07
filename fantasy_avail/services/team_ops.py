from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Optional

import requests

from fantasy_avail.mlb_api import (
    default_team_ops_csv_path,
    record_team_ops_csv_refreshed,
    write_team_ops_csv,
)
from fantasy_avail.schemas import RefreshTeamOpsResult


def refresh_team_ops(
    *,
    season: Optional[int] = None,
    output_path: Optional[Path] = None,
) -> RefreshTeamOpsResult:
    year = season if season is not None else dt.date.today().year
    out = output_path if output_path is not None else default_team_ops_csv_path(year)
    session = requests.Session()
    write_team_ops_csv(session, out, season=year)
    record_team_ops_csv_refreshed()
    return RefreshTeamOpsResult(
        season=year,
        output_path=str(out.resolve()),
        refreshed=True,
    )
