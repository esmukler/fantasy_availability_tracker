from __future__ import annotations

import threading
import time
from typing import Any, Dict, Optional

from flask import Flask, jsonify, render_template, request

from fantasy_avail.config import load_config
from fantasy_avail.services.probable_pitchers import get_available_probable_pitchers
from fantasy_avail.web.cache import DiskCache
from fantasy_avail.web.serialize import _format_cached_at, ensure_stats_highlights, result_to_web_payload

DAYS = 5
_fetch_lock = threading.Lock()
_fetch_condition = threading.Condition(_fetch_lock)
_fetch_in_progress = False


def _fetch_fresh_payload(cache: DiskCache) -> Dict[str, Any]:
    result = get_available_probable_pitchers(
        days=DAYS,
        include_waivers=True,
        skip_team_ops_update=True,
    )
    fetched_at = cache.write(result_to_web_payload(result, cached=False))
    return result_to_web_payload(result, cached=False, cached_at=fetched_at)


def _payload_from_disk(cache: DiskCache) -> Optional[Dict[str, Any]]:
    cached = cache.read()
    if cached is None:
        return None
    payload = dict(cached.data)
    payload["cached"] = True
    if "cached_at" not in payload:
        payload["cached_at"] = _format_cached_at(cached.fetched_at)
    ensure_stats_highlights(payload)
    return payload


def _get_payload(cache: DiskCache, *, refresh: bool = False) -> Dict[str, Any]:
    """Return cached data or run a single shared fresh fetch."""
    global _fetch_in_progress

    if not refresh:
        payload = _payload_from_disk(cache)
        if payload is not None:
            return payload

    with _fetch_condition:
        if not refresh:
            payload = _payload_from_disk(cache)
            if payload is not None:
                return payload

        deadline = time.time() + 180
        while _fetch_in_progress:
            remaining = deadline - time.time()
            if remaining <= 0:
                raise RuntimeError("Timed out waiting for pitcher data. Try Refresh.")
            _fetch_condition.wait(timeout=min(1.0, remaining))
            if not refresh:
                payload = _payload_from_disk(cache)
                if payload is not None:
                    return payload

        _fetch_in_progress = True

    try:
        return _fetch_fresh_payload(cache)
    finally:
        with _fetch_condition:
            _fetch_in_progress = False
            _fetch_condition.notify_all()


def _warm_cache_async(cache: DiskCache) -> None:
    if cache.read() is not None:
        return

    def _run() -> None:
        try:
            _get_payload(cache, refresh=False)
        except Exception:
            pass

    threading.Thread(target=_run, name="pitchers-warm", daemon=True).start()


def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    cache = DiskCache()

    @app.get("/")
    def index():
        _warm_cache_async(cache)
        return render_template("index.html")

    @app.get("/api/pitchers")
    def api_pitchers():
        refresh = request.args.get("refresh", "").lower() in {"1", "true", "yes"}
        try:
            payload = _get_payload(cache, refresh=refresh)
        except Exception as e:
            return jsonify({"error": str(e)}), 500
        if refresh:
            payload["cached"] = False
        return jsonify(payload)

    return app


def run_server(*, host: Optional[str] = None, port: Optional[int] = None) -> None:
    cfg = load_config()
    app = create_app()
    _warm_cache_async(DiskCache())
    app.run(
        host=host if host is not None else cfg.web_host,
        port=port if port is not None else cfg.web_port,
        debug=False,
        threaded=True,
    )
