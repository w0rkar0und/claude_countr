# Token Usage Dashboard - Build Specification

**Project:** claude_countr — Unified real-time token usage monitoring across Claude Code sessions and Admin API usage
**Owner:** Miten
**Status:** Deployed to production. Phase 4 polish in progress.
**Target Deployment:** Frontend on Vercel (`claude.hydrae.mx`), Backend on Railway (`claudecountr-production.up.railway.app`)

---

## Project Overview

Build a cloud-hosted dashboard that aggregates token consumption from:
1. **Claude Code local sessions** (`~/.claude/projects/` JSONL files)
2. **Claude Admin API** (organizational usage via `/v1/organizations/usage_report/messages`)
3. **Claude Code Analytics API** (`/v1/organizations/usage_report/claude_code` — per-user, terminal type, LOC, commits, PRs)

Real-time display with 60-second auto-refresh + manual refresh button. Historical analytics by day/week/month with cost attribution by project/model.

---

## Architecture

### Data Flow
```
Claude Code JSONL Files ──────┐
                              ├──> Python Backend ──> SQLite DB ──> React Frontend
Claude Admin API ─────────────┤                          ↑
Claude Code Analytics API ────┘                        WebSocket
```

### Tech Stack
- **Backend:** Python 3.14, FastAPI 0.104, APScheduler, watchdog, httpx
- **Frontend:** React 19 + TypeScript + Vite 8, Zustand 5, TailwindCSS 4, Recharts
- **Database:** SQLite (WAL mode, file-based)
- **Real-time:** WebSocket for live updates
- **Hosting:** Frontend (Vercel), Backend (Railway)

---

## Deployment

### Live URLs
- **Frontend:** https://claude.hydrae.mx (also https://claude-countr.vercel.app)
- **Backend:** https://claudecountr-production.up.railway.app
- **DNS:** GoDaddy — CNAME `claude` → `cname.vercel-dns.com`

### Environment Variables (Railway)
| Variable | Value |
|----------|-------|
| `ADMIN_API_KEY` | Set in Railway dashboard (org: GLGI) |
| `FRONTEND_URL` | `https://claude.hydrae.mx` |
| `CLAUDE_CODE_HOME` | `~/.claude/projects` |
| `SQLITE_DB_PATH` | `./data/tokens.db` |

### Environment Variables (Vercel)
| Variable | Value |
|----------|-------|
| `VITE_API_URL` | `https://claudecountr-production.up.railway.app` |

### Railway Config
- **Root Directory:** `backend`
- **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`

### Vercel Config
- **Root Directory:** `frontend`
- **Build Command:** `npm run build`
- **Output Directory:** `dist`

---

## Current File Structure

```
claude_countr/
├── backend/
│   ├── main.py              # FastAPI server, 16+ routes, WebSocket /ws, lifespan, 30-day backfill on startup
│   ├── api_client.py         # Admin API + Claude Code Analytics polling
│   ├── claude_code_parser.py # JSONL parser with enriched fields
│   ├── database.py           # SQLite schema (5 tables) + CRUD + migrations
│   ├── scheduler.py          # APScheduler + WebSocket ConnectionManager
│   ├── config.py             # Env config + model pricing
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx           # Init: fetchDateRange → fetchCurrentData → auto-switch to daily if no sessions
│   │   ├── store.ts          # Zustand store — NO useShallow (React 19 compat)
│   │   ├── api/
│   │   │   └── client.ts     # REST + WebSocket client
│   │   └── components/
│   │       ├── Dashboard.tsx       # Tab navigation + view routing
│   │       ├── Header.tsx          # Logo, live indicator, refresh, settings
│   │       ├── CurrentSession.tsx  # Active session cards with progress bars
│   │       ├── CostByModelChart.tsx # Donut chart cost by model
│   │       ├── ToolUsageChart.tsx   # Horizontal bar chart of tool usage
│   │       ├── ProjectCards.tsx     # Project summary cards
│   │       ├── SessionGrid.tsx      # Session table with project/tool/branch info
│   │       ├── TokenBurnChart.tsx   # Hourly token burn line chart
│   │       ├── AlertBanner.tsx      # Threshold warning banners
│   │       ├── DailyView.tsx        # Today: summary cards + hourly bar + model pie
│   │       ├── WeeklyView.tsx       # This Week: daily bars + cost trend + model table
│   │       ├── MonthlyView.tsx      # This Month: weekly bars + model pie + workspace bars
│   │       └── SettingsModal.tsx    # Theme toggle + config display
│   ├── vite.config.ts        # Proxy /api and /ws to backend (dev only)
│   ├── package.json
│   └── tsconfig.json
├── CLAUDE.md
├── SETUP.md (gitignored — contains API keys)
└── .gitignore
```

---

## Backend API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/status` | Active sessions count, last update, WS clients, data sources |
| GET | `/api/current` | Active sessions with state, burn rate, warnings |
| GET | `/api/daily` | Daily token/cost summary with hourly + model breakdown |
| GET | `/api/weekly` | Weekly summary with daily breakdown + model table |
| GET | `/api/monthly` | Monthly summary with weekly breakdown + workspace |
| GET | `/api/sessions` | All sessions with project, tools, branch, subagent flag |
| GET | `/api/tools` | Aggregate tool usage across all sessions |
| GET | `/api/projects` | Project-level summaries with costs, tools, branches |
| GET | `/api/analytics` | Claude Code analytics (sessions, LOC, commits, PRs) |
| GET | `/api/alerts` | Recent cost/threshold alerts |
| GET | `/api/date-range` | Min/max dates with data in api_usage table |
| GET | `/api/debug/db` | Temporary: inspect stored API data (remove before prod) |
| POST | `/api/refresh` | Trigger immediate poll (last 24h) of all data sources |
| WS | `/ws` | Real-time updates with ping/pong keepalive |

---

## Database Schema (5 tables)

1. **api_usage** — Admin API usage records with service_tier, context_window, inference_geo
2. **claude_code_sessions** — Enriched sessions with model, project, git_branch, version, is_subagent, tool_usage (JSON), message_count
3. **claude_code_analytics** — Per-user/day analytics from CC Analytics API (terminal_type, LOC, commits, PRs, tool actions)
4. **daily_summary** — Pre-aggregated daily data
5. **cost_alerts** — Alert history

---

## Workstreams

### Phase 1: Backend Foundation ✅ COMPLETE
- [x] FastAPI scaffold, env config, model pricing
- [x] `api_client.py` (Admin API polling)
- [x] `claude_code_parser.py` (JSONL parsing + file watching)
- [x] `database.py` (SQLite schema + CRUD)

### Phase 2: Backend Real-Time ✅ COMPLETE
- [x] `scheduler.py` (APScheduler background tasks, WebSocket ConnectionManager)
- [x] `main.py` (all endpoints + WebSocket /ws + scheduler/watcher lifespan)
- [x] Error handling, graceful shutdown

### Phase 3: Frontend UI ✅ COMPLETE
- [x] React 19 + Vite 8 + TypeScript + TailwindCSS 4 + Recharts + Zustand 5
- [x] Zustand store + API client (REST + WebSocket with auto-reconnect)
- [x] Dashboard (Header, CurrentSession, AlertBanner, tabs)
- [x] Today/Week/Month views with Recharts visualizations
- [x] Settings modal

### Phase 3.5: Data Enrichment ✅ COMPLETE
- [x] Fixed API client parsing bugs
- [x] Added Claude Code Analytics API endpoint
- [x] Enriched JSONL parser and DB schema
- [x] New endpoints: /api/tools, /api/projects, /api/analytics
- [x] New frontend components: CostByModelChart, ToolUsageChart, ProjectCards

### Phase 4: Bugs, Deployment & Polish ✅ PARTIALLY COMPLETE
- [x] **Fixed Zustand infinite loop** — Removed all `useShallow` usage; use individual scalar/ref selectors instead (React 19 `useSyncExternalStore` compat)
- [x] **Fixed Admin API errors** — Removed invalid `anthropic-beta` header, invalid `speed` group_by param, fixed CC Analytics date format (`YYYY-MM-DD`) and removed unsupported `ending_at` param
- [x] **Fixed empty dashboard on deploy** — Added 30-day backfill on startup, adaptive bucket_width (`1d`/`1h`/`1m`), date-range endpoint, auto-fallback to most recent data
- [x] **CORS** — Added `claude.hydrae.mx` and `claude-countr.vercel.app` to allowed origins
- [x] **Default view** — Auto-switches to Today tab when no active sessions
- [x] Deployed backend to Railway, frontend to Vercel
- [x] Custom domain `claude.hydrae.mx` configured via GoDaddy CNAME
- [ ] Remove `/api/debug/db` endpoint before final release
- [ ] WebSocket reconnection visual feedback
- [ ] Auto-refresh timer display in header
- [ ] Responsive design (mobile-friendly)
- [ ] Light mode styling (currently dark-only despite toggle)

### Phase 5: Future Enhancements
- [ ] Local backend option for live session monitoring (JSONL files only exist on user's machine, not Railway)
- [ ] Cloudflare Tunnel or ngrok for exposing local backend to Vercel frontend
- [ ] Date picker in frontend for navigating to specific dates
- [ ] More granular cost breakdown (cache creation vs cache read)

---

## Known Limitations

1. **No live session data on Railway** — The JSONL parser watches `~/.claude/projects/` which doesn't exist on the Railway server. Active session monitoring requires running the backend locally. The Admin API only provides aggregated historical usage, not live sessions.

2. **Limited org usage data** — The GLGI org currently has data from March 3-9, 2026 only. The dashboard auto-navigates to the most recent date with data.

3. **Admin API key** — Stored in Railway env vars. The key belongs to the GLGI organization.

---

## Key Technical Decisions

1. **No `useShallow` in Zustand** — React 19's `useSyncExternalStore` conflicts with Zustand's `useShallow` hook, causing infinite re-render loops. All store selectors use individual `useStore((s) => s.property)` calls instead. Derived values computed in component body, not selectors.

2. **Adaptive bucket_width** — Admin API polling uses `1d` for >24h ranges, `1h` for >1h, `1m` for short polls. Prevents timeout/empty responses on large time ranges.

3. **Date range fallback** — Frontend fetches `/api/date-range` on init. If today/this week/this month have no data, automatically falls back to the most recent date with data.

4. **CC Analytics API** — Only accepts `starting_at` (date format `YYYY-MM-DD`), no `ending_at` parameter.

---

## Configuration

`.env` file (not committed):
```
ADMIN_API_KEY=sk-ant-admin01-...
CLAUDE_CODE_HOME=~/.claude/projects
SQLITE_DB_PATH=./data/tokens.db
POLLING_INTERVAL=60
SESSION_RESET_HOURS=5
COST_ALERT_THRESHOLDS=0.8,0.9,0.95
BACKEND_PORT=8000
FRONTEND_URL=https://claude.hydrae.mx
```

## Running Locally

```bash
# Backend
cd backend
pip install -r requirements.txt
python -m uvicorn main:app --host 127.0.0.1 --port 8000

# Frontend
cd frontend
npm install
npx vite --port 5174 --strictPort
```

Dashboard at http://localhost:5174 (proxies API/WS to :8000).

---

**Last updated:** 2026-04-01, end of deployment session. Dashboard live at https://claude.hydrae.mx
