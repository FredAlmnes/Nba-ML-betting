# External Integrations

**Analysis Date:** 2026-08-19

## APIs & External Services

**Sports Data:**
- **NBA Stats API (via `nba_api` package)** - unofficial wrapper around `stats.nba.com` endpoints. Free, no API key required.
  - `leaguegamefinder.LeagueGameFinder` - historical game results, used in `01_hent_data.py:36-40` (bulk season pull) and `06_bot.py:110-115` (result verification for settled bets).
  - `teamgamelogs.TeamGameLogs` - recent per-team game logs for live feature generation, `04_value_detector.py:93-97`.
  - `leaguedashplayerstats.LeagueDashPlayerStats` - league-wide player stats (season averages + last-N-games) used for the injury/availability filter, `05_skadefilter.py:44-48`.
  - `teams.get_teams()` - static team metadata (id/name/abbreviation lookup table), used in `01_hent_data.py:20`, `04_value_detector.py:117`, `05_skadefilter.py:168`, `06_bot.py:76`.
  - Rate limiting: no formal throttling library; each call site adds a manual `time.sleep()` (0.5–1.0s) between requests to avoid hitting NBA's informal rate limits.

**Odds Data:**
- **The Odds API** (`https://the-odds-api.com`) - third-party bookmaker odds aggregator.
  - Endpoint used: `GET https://api.the-odds-api.com/v4/sports/basketball_nba/odds/` (`04_value_detector.py:52`).
  - Params: `apiKey`, `regions=eu`, `markets=h2h` (moneyline), `oddsFormat=decimal`, `dateFormat=iso` (`04_value_detector.py:53-59`).
  - Free tier: 500 calls/month (per code comment, `04_value_detector.py:12`).
  - Client: raw `requests.get()` call, no SDK.
  - Response headers are inspected for quota tracking: `respons.headers.get('x-requests-remaining', ...)` (`04_value_detector.py:73`).
  - **Auth:** API key passed as a query parameter (`apiKey`). **The key is hardcoded as a plaintext Python literal directly in source** (`04_value_detector.py:30`, variable `API_NØKKEL`) rather than sourced from an environment variable, `.env` file, or secrets manager. This file is tracked in git (not in `.gitignore`), so the key is committed to version control history. Treat this as a live secret requiring rotation/redaction, not something to reference by value.
  - Failure handling: non-200 responses call `sys.exit(1)` (`04_value_detector.py:63-67`), explicitly chosen over `exit()` so that the parent process (`06_bot.py`, via `subprocess.run`) can detect the failure via return code.

## Data Storage

**Databases:**
- None. No SQL/NoSQL database, no ORM, no connection strings anywhere in the codebase.

**File Storage:**
- Local filesystem only. All persistent state is flat files in the repo root:
  - `nba_kamper_raw.csv` - raw historical game data (output of `01_hent_data.py`)
  - `nba_features.csv` - engineered features (output of `02_feature_engineering.py`)
  - `nba_modell.pkl` - pickled trained model + calibrator + feature column list (output of `03_tren_modell.py`, loaded by `04_value_detector.py`)
  - `value_bets_idag.csv` - today's flagged value bets (output of `04_value_detector.py`)
  - `value_bets_med_skadefilter.csv` - value bets after injury filtering (output of `05_skadefilter.py`)
  - `bankroll.json` - current balance + historical balance timeline (`06_bot.py:37`)
  - `bets.json` - full bet ledger with status/outcome (`06_bot.py:38`)
  - `dashboard.html` - generated static report/visualization (`06_bot.py:39`)

**Caching:**
- None (no Redis/memcached). `05_skadefilter.py:174` uses a simple in-process Python `dict` (`cache = {}`) to avoid re-fetching player-health status for the same team twice within a single run — not persisted between runs.

## Authentication & Identity

**Auth Provider:**
- None. This is a single-user, locally-run script suite with no login, session, or user-identity system of any kind.

## Monitoring & Observability

**Error Tracking:**
- None. No Sentry/Bugsnag/etc. Errors surface via `print()` statements and process exit codes only (e.g., `04_value_detector.py:63-67`, `06_bot.py:237-238,244-245`).

**Logs:**
- Console output only (`print()` throughout every script, heavily annotated with emoji status markers). No structured logging, no log files, no log aggregation.

## CI/CD & Deployment

**Hosting:**
- None. No hosting/deployment target — everything runs on the local developer machine.

**CI Pipeline:**
- None. No `.github/workflows/`, no other CI config detected.

## Environment Configuration

**Required env vars:**
- None are actually read from the environment. The Odds API key is a hardcoded literal in `04_value_detector.py` (see above) rather than an env var, despite `.gitignore` reserving `.env` for this purpose.

**Secrets location:**
- Hardcoded in source: `API_NØKKEL` in `04_value_detector.py:30` (The Odds API key). No `.env` file exists in the repo despite being gitignored.
- `.gitignore` also excludes generated data/model files (`nba_kamper_raw.csv`, `nba_features.csv`, `nba_modell.pkl`, `value_bets_idag.csv`, `value_bets_med_skadefilter.csv`) and personal bankroll data (`bankroll.json`, `bets.json`) — these are treated as local/private artifacts, not secrets per se, but are excluded from version control.

## Webhooks & Callbacks

**Incoming:**
- None. No server, no listening ports, no webhook receivers anywhere in the codebase.

**Outgoing:**
- None beyond the two outbound API integrations above (NBA Stats API, The Odds API). No notifications (no Slack/Telegram/email/SMS integration) despite `06_bot.py` being intended for unattended daily runs.

---

*Integration audit: 2026-08-19*
