# Fantasy availability tracker

Yahoo Fantasy Baseball research tool with four feature domains:

1. **Yahoo availability** — check whether players are free agents, on waivers, or unrostered NA prospects
2. **Probable pitchers** — Fantasy Pros probable starters enriched with MLB stats, filtered to available arms
3. **Article analysis** — extract editorial main players from news URLs and return only those available in your league
4. **Team OPS** — cached team offensive stats for matchup context

**Human access:** web UI locally (`python -m fantasy_avail.web`) or on [GitHub Pages](https://esmukler.github.io/fantasy_availability_tracker/). **Agent access:** MCP server for Cursor.

---

## Quick start

1. Create a virtualenv and install dependencies:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. Copy [`oauth2.json.example`](oauth2.json.example) to `oauth2.json` and add your Yahoo app credentials (see [Yahoo Developer Network](https://developer.yahoo.com/)). The first Yahoo API call opens a browser to sign in and caches tokens under `.yahoo_tokens/`.

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

## Deployment (GitHub Pages)

The public site is a static frontend in [`docs/`](docs/) backed by [`docs/data/pitchers.json`](docs/data/pitchers.json). A GitHub Actions workflow refreshes that JSON every 6 hours and on demand.

### Enable Pages

1. Repo **Settings → Pages**
2. Source: deploy from branch **`main`**, folder **`/docs`**
3. Site URL: `https://esmukler.github.io/fantasy_availability_tracker/`

### GitHub Secrets

| Secret | Required | Purpose |
|--------|----------|---------|
| `YAHOO_OAUTH_JSON` | Yes | Full contents of your local `oauth2.json` after OAuth bootstrap (must include `refresh_token`) |
| `FP_COOKIE` | Recommended | Fantasy Pros session cookie (one line, same as `fantasypros_cookie.txt`) |
| `PAGES_REFRESH_TOKEN` | Recommended | Fine-grained PAT with `actions:write` on this repo so the **Refresh** button can trigger a workflow run. This token is written into the public `docs/js/config.js` by CI — use a repo-scoped token you are comfortable exposing; the only risk is someone spamming workflow runs.

**One-time OAuth bootstrap for CI:**

1. Run `python -m fantasy_avail.web` locally and complete Yahoo sign-in.
2. Confirm `oauth2.json` contains `refresh_token`.
3. Copy the entire file into the `YAHOO_OAUTH_JSON` secret.

**Refresh button:** dispatches the [Refresh pitcher data](.github/workflows/refresh-data.yml) workflow, then polls until `pitchers.json` updates (up to ~3 minutes). Without `PAGES_REFRESH_TOKEN`, Refresh only reloads the last committed JSON.

**Fantasy Pros cookie:** expires periodically. Update the `FP_COOKIE` secret when the probable-pitchers grid shrinks.

### Manual workflow run

Actions → **Refresh pitcher data** → **Run workflow**.

### Local static preview

```bash
python -m fantasy_avail.web.export --output docs/data/pitchers.json
python -m http.server --directory docs 8888
```

Open [http://127.0.0.1:8888](http://127.0.0.1:8888).

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
  web/                  Flask UI + static export for GitHub Pages
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
