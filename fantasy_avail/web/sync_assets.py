from __future__ import annotations

import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LOGO_NAME = "baseball-streamer-logo.png"
LOGO_SOURCE = REPO_ROOT / LOGO_NAME
LOGO_DESTINATIONS = (
    REPO_ROOT / "fantasy_avail" / "web" / "static" / LOGO_NAME,
    REPO_ROOT / "docs" / "static" / LOGO_NAME,
)


def sync_branding_assets() -> None:
    """Copy the repo-root logo into each web static folder."""
    if not LOGO_SOURCE.is_file():
        return
    for dest in LOGO_DESTINATIONS:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(LOGO_SOURCE, dest)


def main() -> int:
    if not LOGO_SOURCE.is_file():
        print(f"Logo not found: {LOGO_SOURCE}", file=sys.stderr)
        return 1
    sync_branding_assets()
    for dest in LOGO_DESTINATIONS:
        print(f"Synced {dest.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
