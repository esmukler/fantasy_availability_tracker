from __future__ import annotations

import shutil
import sys
from pathlib import Path

from flask import render_template

from fantasy_avail.web.app import create_app

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_STATIC_DIR = Path(__file__).resolve().parent / "static"
DOCS_DIR = REPO_ROOT / "docs"
DOCS_STATIC_DIR = DOCS_DIR / "static"


def sync_static_assets() -> None:
    """Copy web static assets into docs/static for GitHub Pages."""
    DOCS_STATIC_DIR.mkdir(parents=True, exist_ok=True)
    for item in WEB_STATIC_DIR.iterdir():
        if item.is_file():
            shutil.copy2(item, DOCS_STATIC_DIR / item.name)


def render_pages_index_html() -> str:
    """Render the shared template for GitHub Pages."""
    app = create_app()
    with app.app_context():
        return render_template("index.html", deploy_mode="pages")


def sync_docs_site() -> None:
    """Regenerate docs/index.html and docs/static from the Flask web sources."""
    sync_static_assets()
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    (DOCS_DIR / "index.html").write_text(render_pages_index_html(), encoding="utf-8")


def main() -> int:
    try:
        sync_docs_site()
    except Exception as exc:
        print(f"Static site sync failed: {exc}", file=sys.stderr)
        return 1
    print(f"Synced {DOCS_DIR.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
