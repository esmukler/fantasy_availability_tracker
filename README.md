# Fantasy availability tracker

Yahoo Fantasy Baseball research tool with four feature domains:

1. **Yahoo availability** — check whether players are free agents, on waivers, or unrostered NA prospects
2. **Probable pitchers** — Fantasy Pros probable starters enriched with MLB stats, filtered to available arms
3. **Article analysis** — extract editorial main players from news URLs and return only those available in your league
4. **Team OPS** — cached team offensive stats for matchup context

**Human access:** web UI (`python -m fantasy_avail.web`). **Agent access:** MCP server for Cursor.

---

## Quick start

1. Create a virtualenv and install dependencies:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. Put your Yahoo OAuth app credentials in `oauth2.json` (see [Yahoo Developer Network](https://developer.yahoo.com/)). The first Yahoo API call opens a browser to sign in and caches tokens under `.yahoo_tokens/`.

3. **Fantasy Pros (optional):** Copy [`fantasypros_cookie.example`](fantasypros_cookie.example) to `fantasypros_cookie.txt`, then paste your browser's `cookie` request header (one line, no `Cookie:` prefix). That file is gitignored. Set `FP_COOKIE_FILE` to override the path.

4. Start the web server (this also completes OAuth bootstrap on first run):

   ```bash
   python -m fantasy_avail.web
   ```

5. Open [http://127.0.0.1:8080](http://127.0.0.1:8080).

---

## Web UI (primary)

A mobile-friendly site shows **available probable starters** for the next 5 days (starting tomorrow), with matchup, Pacific game time, opposing pitcher, and season stats.

### Run the server

```bash
python -m fantasy_avail.web
```

To view from a phone on the same Wi‑Fi:

```bash
WEB_HOST=0.0.0.0 python -m fantasy_avail.web
```

Responses are cached on disk for up to 1 hour (`.cache/available_pitchers.json`). Use the **Refresh** button or `GET /api/pitchers?refresh=1` to bypass the cache.

| Variable | Default | Purpose |
|----------|---------|---------|
| `WEB_CACHE_TTL_SECONDS` | `3600` | Disk cache TTL for `/api/pitchers` |
| `WEB_HOST` | `127.0.0.1` | Bind address |
| `WEB_PORT` | `8080` | Listen port |
| `WEB_CACHE_PATH` | `.cache/available_pitchers.json` | Cache file path |
| `FANTASY_LEAGUE_ID` | `43384` | Yahoo league id |
| `FANTASY_OAUTH_PATH` | `oauth2.json` | Yahoo OAuth credentials file |
| `FANTASY_TOKEN_DIR` | `.yahoo_tokens` | Cached Yahoo tokens |
| `FP_COOKIE_FILE` | `fantasypros_cookie.txt` | Fantasy Pros session cookie |

A Fantasy Pros cookie is recommended for a fuller probable-pitchers grid.

**Coming later:** article analysis, player lookup, and team-ops refresh in the web UI. Those features are available via MCP today.

---

## MCP server (Cursor agents)

A local MCP server lets Cursor answer league-availability questions via tools.

### Setup

1. Complete Yahoo OAuth bootstrap (start the web server or invoke any MCP tool once).
2. Configure [`.cursor/mcp.json`](.cursor/mcp.json) with your machine's repo path and venv python.
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

If MCP is not enabled, skills under [`.cursor/skills/`](.cursor/skills/) provide agent-driven fallbacks:

- `extract-article-main-players` — editorial player extraction only
- `article-main-players-yahoo-available` — extraction + Yahoo filter via MCP tools

With MCP enabled, prefer the MCP tools above.

---

## Overrides

- **`team_abbr_overrides.json`** — maps StatsAPI-style abbreviations for display.
- **`player_name_overrides.json`** — manual fixes when a pitcher's name from the Fantasy Pros URL slug does not match Yahoo:
  - `yahoo_name_by_slug`: keys are FP player slugs (e.g. `chris-sale`), values are the exact name Yahoo shows.
  - `mlbam_by_slug`: optional numeric MLBAM ids if automatic lookup fails.

Unmatched probable pitchers appear in the web API/MCP `unmatched` payload with their `fp_slug` for easy override entry.

---

## Project layout

```
fantasy_avail/
  yahoo.py              Yahoo OAuth, targeted + bulk availability
  fantasypros.py        Fantasy Pros probable-pitchers scrape
  mlb_api.py            MLB Stats API (schedule, stats, team OPS)
  article_utils.py      Article fetch and snippet extraction
  article_main_players.py  Editorial main-player extraction
  availability_cache.py Session league + bulk-list cache
  services/             Orchestration shared by web and MCP
    availability.py
    probable_pitchers.py
    article_analysis.py
    team_ops.py
  web/                  Flask UI
  mcp_server.py         FastMCP tools
  config.py             Env-based configuration
tests/
.cursor/                MCP config, agent skills, workspace rules
```

---

## Development

Run tests:

```bash
python tests/test_yahoo_ownership.py
python tests/test_probable_pitchers.py
python tests/test_mlb_schedule.py
python tests/test_web.py
```
