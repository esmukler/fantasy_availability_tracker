from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from fantasy_avail.article_utils import MentionSummary
from fantasy_avail.yahoo import FANTASY_AVAIL_SOURCE_KEY


def _strip_internal_keys(player: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in player.items() if k != FANTASY_AVAIL_SOURCE_KEY}


@dataclass
class AvailablePlayerRow:
    player_name: str
    normalized_name: str
    availability: str
    position_type: Optional[str] = None
    eligible_positions: Optional[List[str]] = None
    percent_owned: Optional[float] = None
    yahoo_player_id: Optional[str] = None

    @classmethod
    def from_yahoo(cls, player: Dict[str, Any]) -> AvailablePlayerRow:
        eligible = player.get("eligible_positions")
        if isinstance(eligible, str):
            eligible = [eligible]
        return cls(
            player_name=str(player.get("name") or ""),
            normalized_name="",
            availability=str(player.get(FANTASY_AVAIL_SOURCE_KEY) or "free_agent"),
            position_type=player.get("position_type"),
            eligible_positions=eligible if isinstance(eligible, list) else None,
            percent_owned=_coerce_float(player.get("percent_owned")),
            yahoo_player_id=str(player.get("player_id") or player.get("player_key") or "") or None,
        )


def _coerce_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@dataclass
class ListAvailablePlayersResult:
    players: List[AvailablePlayerRow]
    total: int
    position_filter: Optional[str]
    include_waivers: bool
    league_id: int
    cached: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "league_id": self.league_id,
            "position_filter": self.position_filter,
            "include_waivers": self.include_waivers,
            "total": self.total,
            "cached": self.cached,
            "players": [asdict(p) for p in self.players],
        }


@dataclass
class PlayerAvailabilityCheck:
    query_name: str
    normalized_name: str
    is_available: bool
    availability: Optional[str] = None
    yahoo_player: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        row: Dict[str, Any] = {
            "query_name": self.query_name,
            "normalized_name": self.normalized_name,
            "is_available": self.is_available,
            "availability": self.availability,
        }
        if self.yahoo_player is not None:
            row["yahoo_player"] = _strip_internal_keys(self.yahoo_player)
        return row


@dataclass
class CheckPlayerAvailabilityResult:
    league_id: int
    include_waivers: bool
    results: List[PlayerAvailabilityCheck]
    cached: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "league_id": self.league_id,
            "include_waivers": self.include_waivers,
            "cached": self.cached,
            "results": [r.to_dict() for r in self.results],
        }


@dataclass
class ArticleAvailablePlayer:
    player_name: str
    normalized_name: str
    availability: str
    snippets: List[str]
    yahoo_player: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "player_name": self.player_name,
            "normalized_name": self.normalized_name,
            "availability": self.availability,
            "snippets": self.snippets,
            "yahoo_player": _strip_internal_keys(self.yahoo_player),
        }

    @classmethod
    def from_mention(cls, mention: MentionSummary) -> ArticleAvailablePlayer:
        return cls(
            player_name=mention.player_name,
            normalized_name=mention.normalized_name,
            availability=mention.availability,
            snippets=list(mention.snippets),
            yahoo_player=mention.yahoo_player,
        )


@dataclass
class AnalyzeArticleAvailabilityResult:
    main_players: List[str]
    available: List[ArticleAvailablePlayer]
    not_in_pool: List[str]
    also_named: List[str] = field(default_factory=list)
    extraction_warnings: List[str] = field(default_factory=list)
    league_id: int = 0
    url: str = ""
    cached: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "league_id": self.league_id,
            "cached": self.cached,
            "main_players": self.main_players,
            "available": [a.to_dict() for a in self.available],
            "not_in_pool": self.not_in_pool,
            "also_named": self.also_named,
            "extraction_warnings": self.extraction_warnings,
        }


@dataclass
class ProbablePitcherRow:
    date: str
    game_pk: Optional[int]
    fp_slug: str
    matchup: Dict[str, str]
    side: str
    mlb_name: str
    mlbam_id: Optional[int]
    is_available: bool
    pitcher_team: str = ""
    opponent_team: str = ""
    home_away: str = ""
    game_time_pt: str = "TBD"
    availability: str = "free_agent"
    yahoo_availability: Optional[str] = None
    yahoo_free_agents: Optional[List[Dict[str, Any]]] = None
    mlb_season_stats: Optional[Dict[str, Any]] = None
    opposing_pitcher_name: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        row = asdict(self)
        if self.yahoo_free_agents is not None:
            row["yahoo_free_agents"] = [
                _strip_internal_keys(h) for h in self.yahoo_free_agents
            ]
        return row


@dataclass
class GetAvailableProbablePitchersResult:
    league_id: int
    start_date: str
    days: int
    available: List[ProbablePitcherRow]
    unmatched: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "league_id": self.league_id,
            "start_date": self.start_date,
            "days": self.days,
            "warnings": self.warnings,
            "available": [r.to_dict() for r in self.available],
            "unmatched": self.unmatched,
        }


@dataclass
class RefreshTeamOpsResult:
    season: int
    output_path: str
    refreshed: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
