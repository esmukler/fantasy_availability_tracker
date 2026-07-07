# Fantasy availability tracker

Small script that scrapes Fantasy Pros’ default [MLB probable pitchers](https://www.fantasypros.com/mlb/probable-pitchers.php) page (the “next 7 days” grid), filters by `--start-date` and `--days`, and shows which of those starters are **free agents** in your Yahoo Fantasy Baseball league. Season pitching stats (W-L, ERA, WHIP, IP, K, QS) still come from the MLB Stats API using each player’s resolved MLBAM id.

## Run it

1. Create a virtualenv and install dependencies:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. Put your Yahoo OAuth app credentials in `oauth2.json` (see Yahoo Developer Network). The first run opens a browser to sign in and caches tokens under `.yahoo_tokens/`.

3. **Fantasy Pros (optional):** To get the full probable-pitchers table, copy [`fantasypros_cookie.example`](fantasypros_cookie.example) to `fantasypros_cookie.txt`, then paste your browser’s `cookie` request header (one line, no `Cookie:` prefix). That file is gitignored. Override path with `--fp-cookie-file` or disable with `--fp-cookie-file ''`.

4. Run the main script (replace `--league-id` with your Yahoo league id):

   ```bash
   python get_available_pitchers.py --league-id 43384 --show-unmatched
   ```

Use `python get_available_pitchers.py --help` for all options.

## Analyze article mentions (available players only)

You can also analyze a news/article URL and return a short summary for **only** the players currently available in your Yahoo league (free agents by default, plus waivers unless disabled).

```bash
python analyze_available_players.py \
  --url "https://example.com/mlb-notes" \
  --league-id 43384
```

Useful flags:

- `--json` for machine-readable output
- `--no-waivers` to only include free agents
- `--max-snippets 1` to keep output very brief
- `--debug-unmatched` to print detected names and which did not match available players

## Overrides

- **`team_abbr_overrides.json`** — optional; maps StatsAPI-style abbreviations for display (same as before).
- **`player_name_overrides.json`** — optional manual fixes when a pitcher’s name derived from the Fantasy Pros URL slug does not match Yahoo’s free-agent list:
  - `yahoo_name_by_slug`: keys are FP player slugs (e.g. `chris-sale`), values are the exact name Yahoo shows for that player.
  - `mlbam_by_slug`: optional numeric MLBAM ids if automatic lookup fails or picks the wrong player.

With `--show-unmatched`, the script prints each slug and a sample JSON line you can paste into `yahoo_name_by_slug`.

## MCP server (Cursor)

This repo includes a local MCP server so Cursor can answer league-availability questions via tools instead of shell scripts.

### Setup

1. Complete the Yahoo OAuth bootstrap above (run `get_available_pitchers.py` once so tokens exist).
2. Copy [`.cursor/mcp.json.example`](.cursor/mcp.json.example) to your Cursor MCP config (or merge into `.cursor/mcp.json`), replacing the absolute paths with your machine’s repo path.
3. Restart Cursor (or reload MCP servers).

Optional environment variables (also settable in `mcp.json` → `env`):

| Variable | Default | Purpose |
|----------|---------|---------|
| `FANTASY_LEAGUE_ID` | `43384` | Yahoo league id |
| `FANTASY_OAUTH_PATH` | `oauth2.json` | Yahoo OAuth credentials file |
| `FANTASY_TOKEN_DIR` | `.yahoo_tokens` | Cached Yahoo tokens |
| `FP_COOKIE_FILE` | `fantasypros_cookie.txt` | Fantasy Pros session cookie |
| `FANTASY_CACHE_TTL_SECONDS` | `600` | Yahoo full FA/waiver list cache TTL (`list_available_players` only) |

`oauth2.json` is gitignored; keep credentials local.

### Tools

Availability checks for **specific player names** use targeted Yahoo lookups (`player_details` + batched `ownership`) — not a full FA/waiver pool scan. That keeps API usage low when checking article subjects or small name lists.

| Tool | Use for |
|------|---------|
| `list_available_players_tool` | Full FA/waiver pool by position (slow; many API calls) |
| `check_player_availability_tool` | Is a player available? (batch names; preferred) |
| `get_available_probable_pitchers_tool` | Probable starters in date window who are FA/waivers |
| `analyze_article_availability_tool` | Article URL → main players → available subset + snippets |
| `refresh_team_ops_tool` | Refresh `team_ops_{season}.csv` |

Run manually for debugging:

```bash
python -m fantasy_avail.mcp_server
```

### Cursor skills (fallback)

If MCP is not enabled, the skills under [`.cursor/skills/`](.cursor/skills/) still work:

- `extract-article-main-players` — editorial player extraction only
- `article-main-players-yahoo-available` — extraction + Yahoo filter via CLI

With MCP enabled, prefer the MCP tools above; skills are optional fallback.

## Web UI (available pitchers)

A mobile-friendly one-page site shows **available probable starters** for the next 5 days (starting tomorrow), with matchup, Pacific game time, and season stats.

### Run the web server

1. Complete Yahoo OAuth bootstrap above (run `get_available_pitchers.py` once so tokens exist).
2. Install dependencies (includes Flask):

   ```bash
   pip install -r requirements.txt
   ```

3. Start the server:

   ```bash
   python -m fantasy_avail.web
   ```

4. Open [http://127.0.0.1:8080](http://127.0.0.1:8080). To view from a phone on the same Wi‑Fi:

   ```bash
   WEB_HOST=0.0.0.0 python -m fantasy_avail.web
   ```

Responses are cached on disk for up to 1 hour (`.cache/available_pitchers.json`). Use the **Refresh** button or `GET /api/pitchers?refresh=1` to bypass the cache.

Optional environment variables:

| Variable | Default | Purpose |
|----------|---------|---------|
| `WEB_CACHE_TTL_SECONDS` | `3600` | Disk cache TTL for `/api/pitchers` |
| `WEB_HOST` | `127.0.0.1` | Bind address |
| `WEB_PORT` | `8080` | Listen port |
| `WEB_CACHE_PATH` | `.cache/available_pitchers.json` | Cache file path |

A Fantasy Pros cookie (`fantasypros_cookie.txt`) is still recommended for a fuller probable-pitchers grid.
