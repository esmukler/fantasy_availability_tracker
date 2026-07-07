from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_LEAGUE_ID = 43384
DEFAULT_OAUTH_PATH = REPO_ROOT / "oauth2.json"
DEFAULT_TOKEN_DIR = REPO_ROOT / ".yahoo_tokens"
DEFAULT_FP_COOKIE_FILE = REPO_ROOT / "fantasypros_cookie.txt"
DEFAULT_PLAYER_OVERRIDES = REPO_ROOT / "player_name_overrides.json"
DEFAULT_TEAM_ABBR_OVERRIDES = REPO_ROOT / "team_abbr_overrides.json"
DEFAULT_CACHE_TTL_SECONDS = 600
DEFAULT_WEB_CACHE_TTL_SECONDS = 3600
DEFAULT_WEB_HOST = "127.0.0.1"
DEFAULT_WEB_PORT = 8080
DEFAULT_WEB_CACHE_PATH = REPO_ROOT / ".cache" / "available_pitchers.json"


@dataclass(frozen=True)
class AppConfig:
    league_id: int
    oauth_path: Path
    token_dir: Path
    fp_cookie_file: Path
    player_overrides: Path
    team_abbr_overrides: Path
    cache_ttl_seconds: int
    web_cache_ttl_seconds: int
    web_host: str
    web_port: int
    web_cache_path: Path

    @property
    def oauth_path_str(self) -> str:
        return str(self.oauth_path)

    @property
    def token_dir_str(self) -> str:
        return str(self.token_dir)


def load_config() -> AppConfig:
    league_raw = os.environ.get("FANTASY_LEAGUE_ID", str(DEFAULT_LEAGUE_ID))
    oauth_raw = os.environ.get("FANTASY_OAUTH_PATH", str(DEFAULT_OAUTH_PATH))
    token_raw = os.environ.get("FANTASY_TOKEN_DIR", str(DEFAULT_TOKEN_DIR))
    fp_raw = os.environ.get("FP_COOKIE_FILE", str(DEFAULT_FP_COOKIE_FILE))
    player_raw = os.environ.get("FANTASY_PLAYER_OVERRIDES", str(DEFAULT_PLAYER_OVERRIDES))
    team_raw = os.environ.get("FANTASY_TEAM_ABBR_OVERRIDES", str(DEFAULT_TEAM_ABBR_OVERRIDES))
    ttl_raw = os.environ.get("FANTASY_CACHE_TTL_SECONDS", str(DEFAULT_CACHE_TTL_SECONDS))
    web_ttl_raw = os.environ.get("WEB_CACHE_TTL_SECONDS", str(DEFAULT_WEB_CACHE_TTL_SECONDS))
    web_host = os.environ.get("WEB_HOST", DEFAULT_WEB_HOST)
    web_port_raw = os.environ.get("WEB_PORT", str(DEFAULT_WEB_PORT))
    web_cache_raw = os.environ.get("WEB_CACHE_PATH", str(DEFAULT_WEB_CACHE_PATH))

    return AppConfig(
        league_id=int(league_raw),
        oauth_path=Path(oauth_raw),
        token_dir=Path(token_raw),
        fp_cookie_file=Path(fp_raw),
        player_overrides=Path(player_raw),
        team_abbr_overrides=Path(team_raw),
        cache_ttl_seconds=int(ttl_raw),
        web_cache_ttl_seconds=int(web_ttl_raw),
        web_host=web_host,
        web_port=int(web_port_raw),
        web_cache_path=Path(web_cache_raw),
    )
