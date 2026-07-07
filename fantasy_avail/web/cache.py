from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from fantasy_avail.config import AppConfig, load_config


@dataclass
class CachedPayload:
    data: Dict[str, Any]
    fetched_at: float


class DiskCache:
    """File-backed cache for assembled web API responses."""

    def __init__(self, *, cache_path: Optional[Path] = None, ttl_seconds: Optional[int] = None):
        cfg = load_config()
        self._path = cache_path if cache_path is not None else cfg.web_cache_path
        self._ttl = ttl_seconds if ttl_seconds is not None else cfg.web_cache_ttl_seconds

    @property
    def path(self) -> Path:
        return self._path

    def _is_fresh(self, fetched_at: float) -> bool:
        return (time.time() - fetched_at) < self._ttl

    def read(self) -> Optional[CachedPayload]:
        if not self._path.exists():
            return None
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        fetched_at = raw.get("fetched_at")
        data = raw.get("data")
        if not isinstance(fetched_at, (int, float)) or not isinstance(data, dict):
            return None
        if not self._is_fresh(float(fetched_at)):
            return None
        return CachedPayload(data=data, fetched_at=float(fetched_at))

    def write(self, data: Dict[str, Any]) -> float:
        fetched_at = time.time()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"fetched_at": fetched_at, "data": data}
        self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return fetched_at
