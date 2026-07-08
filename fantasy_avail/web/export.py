from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from fantasy_avail.services.probable_pitchers import get_available_probable_pitchers
from fantasy_avail.web.serialize import result_to_web_payload

DAYS = 5


def export_pitchers(*, output: Path) -> None:
    result = get_available_probable_pitchers(
        days=DAYS,
        include_waivers=True,
    )
    payload = result_to_web_payload(result, cached=False, cached_at=time.time())
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export available probable pitchers JSON for GitHub Pages.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/data/pitchers.json"),
        help="Output JSON path (default: docs/data/pitchers.json)",
    )
    args = parser.parse_args(argv)

    try:
        export_pitchers(output=args.output)
    except Exception as exc:
        print(f"Export failed: {exc}", file=sys.stderr)
        return 1
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
