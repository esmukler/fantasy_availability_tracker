from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ProbableStart:
    date: dt.date
    game_pk: Optional[int]
    pitcher_name: str
    pitcher_mlbam_id: Optional[int]
    pitcher_side: str  # "away" | "home"
    away_team: str
    home_team: str
    away_abbr: str
    home_abbr: str
    fp_slug: str
    game_datetime: Optional[dt.datetime] = None

    @property
    def pitcher_team_abbr(self) -> str:
        return self.away_abbr if self.pitcher_side == "away" else self.home_abbr

    @property
    def opponent_abbr(self) -> str:
        return self.home_abbr if self.pitcher_side == "away" else self.away_abbr

    @property
    def venue_marker(self) -> str:
        return "@" if self.pitcher_side == "away" else "vs"
