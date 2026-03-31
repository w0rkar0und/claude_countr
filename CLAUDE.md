# Token Usage Dashboard - Build Specification

**Project:** claude_countr — Unified real-time token usage monitoring across Claude Code sessions and Admin API usage
**Owner:** Miten
**Status:** Phases 1–3 complete + data enrichment. Frontend has Zustand infinite loop bug to fix. Ready for Phase 4 polish.
**Target Deployment:** Cloud-hosted (Vercel for frontend, Render/Railway for backend recommended)

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
- **Hosting:** Frontend (Vercel), Backend (Render/Railway with persistent volume for SQLite)

---

## Current File Structure

```
claude_countr/
├── backend/
│   ├── main.py              # FastAPI server, 16 routes, WebSocket /ws, lifespan
│   ├── api_client.py         # Admin API + Claude Code Analytics polling
│   ├── claude_code_parser.py # JSONL parser with enriched fields
│   ├── database.py           # SQLite schema (5 tables) + CRUD + migrations
│   ├── scheduler.py          # APScheduler + WebSocket ConnectionManager
│   ├── config.py             # Env config + model pricing
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── store.ts          # Zustand store (DashboardState)
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
│   ├── vite.config.ts        # Proxy /api and /ws to backend
│   ├── package.json
│   └── tsconfig.json
├── CLAUDE.md
├── SETUP.md
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
| POST | `/api/refresh` | Trigger immediate poll of all data sources |
| WS | `/ws` | Real-time updates with ping/pong keepalive |

---

## Database Schema (5 tables)

1. **api_usage** — Admin API usage records with service_tier, context_window, inference_geo, speed, web_search_requests
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
- [x] Local testing (32 sessions parsed)

### Phase 2: Backend Real-Time ✅ COMPLETE
- [x] `scheduler.py` (APScheduler background tasks, WebSocket ConnectionManager)
- [x] `main.py` (all endpoints + WebSocket /ws + scheduler/watcher lifespan)
- [x] Error handling (try/except → 500 JSON), graceful shutdown
- [x] Local testing: 13 routes, 86 sessions, scheduler lifecycle

### Phase 3: Frontend UI ✅ COMPLETE
- [x] React 19 + Vite 8 + TypeScript + TailwindCSS 4 + Recharts + Zustand 5
- [x] Zustand store + API client (REST + WebSocket with auto-reconnect)
- [x] Dashboard (Header, CurrentSession, AlertBanner, tabs)
- [x] Today/Week/Month views with Recharts visualizations
- [x] Settings modal
- [x] Production build passes (0 TS errors)

### Phase 3.5: Data Enrichment ✅ COMPLETE
- [x] Fixed API client parsing bugs (uncached_input_tokens, nested cache_creation, data[].results[] structure)
- [x] Added Claude Code Analytics API endpoint (/v1/organizations/usage_report/claude_code)
- [x] Enriched JSONL parser: tool_usage, project, git_branch, version, is_subagent, inference_geo, speed, message counts
- [x] Updated DB schema with migrations for new columns + claude_code_analytics table
- [x] New endpoints: /api/tools, /api/projects, /api/analytics
- [x] New frontend components: CostByModelChart (donut), ToolUsageChart (horizontal bars), ProjectCards (with tool mini-bars + branch/model badges)
- [x] Enriched SessionGrid (project grouping, tool tags, branch, subagent flag)
- [x] Enriched CurrentSession cards (project, branch, subagent, messages, tools)

### Phase 4: Real-Time & Polish (NEXT)
- [ ] **Fix Zustand infinite loop bug** — `useStore` selectors with `useShallow` were added but the "getSnapshot should be cached" error persists in React 19 StrictMode. Likely a remaining derived-value selector returning new refs. Debug with React DevTools.
- [ ] WebSocket reconnection visual feedback (connect/disconnect transitions)
- [ ] Auto-refresh timer display in header
- [ ] Responsive design (mobile-friendly)
- [ ] Light mode styling (currently dark-only despite toggle)

### Phase 5: Deployment
- [ ] Dockerize backend
- [ ] Deploy backend to Render/Railway
- [ ] Deploy frontend to Vercel
- [ ] Environment variable setup
- [ ] End-to-end testing on live URLs

---

## Known Issues

1. **Frontend infinite loop** — React 19 + Zustand 5 `useSyncExternalStore` conflict. The `useShallow` fix was applied to AlertBanner, TokenBurnChart, Header, App, and Settings but the error persists. Needs deeper investigation — may be a component somewhere still returning a new array/object ref from a selector. The `currentData?.warnings ?? []` pattern was the original culprit; similar patterns in other components should be audited.

2. **Admin API 401** — No `ADMIN_API_KEY` configured in `.env` yet. API data endpoints return empty results. Claude Code local JSONL parsing works fine without it.

3. **Port conflicts** — Dev machine has other Vite projects running. Frontend may need `--port 5174 --strictPort`. Backend on port 8000. CORS allows localhost:3000, :5173, :5174.

---

## Configuration

`.env` file (not committed):
```
ADMIN_API_KEY=sk-ant-admin-...
CLAUDE_CODE_HOME=~/.claude/projects
SQLITE_DB_PATH=./data/tokens.db
POLLING_INTERVAL=60
SESSION_RESET_HOURS=5
COST_ALERT_THRESHOLDS=0.8,0.9,0.95
BACKEND_PORT=8000
FRONTEND_URL=https://your-vercel-frontend.vercel.app
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

## Data Available (parsed from JSONL)

Each session now includes: project name, git branch, Claude Code version, subagent flag, tool usage counts (Read, Bash, Edit, Grep, Write, Glob, Agent, etc.), message counts (user/assistant), inference_geo, service_tier, speed.

88 sessions parsed across 19 projects. Top tools: Read (1,308), Bash (1,298), Edit (1,027), Grep (281), Write (214).

---

**Last updated:** 2026-03-31, end of Phase 3.5 session.
