# Token Usage Dashboard - Build Specification

**Project:** claude_countr — Unified real-time token usage monitoring across Claude Code sessions and Admin API usage  
**Owner:** Miten  
**Status:** Ready for Claude Code Build  
**Target Deployment:** Cloud-hosted (Vercel for frontend, Render/Railway for backend recommended)

---

## Project Overview

Build a cloud-hosted dashboard that aggregates token consumption from:
1. **Claude Code local sessions** (`~/.claude/projects/` JSONL files)
2. **Claude Admin API** (organizational usage via `/v1/organizations/usage_report/messages`)

Real-time display with 60-second auto-refresh + manual refresh button. Historical analytics by day/week/month with cost attribution by project/model.

---

## Architecture

### Data Flow
```
Claude Code JSONL Files ──────┐
                              ├──> Python Backend ──> SQLite DB ──> React Frontend
Claude Admin API ─────────────┘                          ↑
                                                        WebSocket
```

### Tech Stack
- **Backend:** Python 3.9+, FastAPI, APScheduler, file watchers
- **Frontend:** React 19 + TypeScript + Vite, Zustand, TailwindCSS
- **Database:** SQLite (file-based, no external dependency)
- **Real-time:** WebSocket for live updates
- **Hosting:** Frontend (Vercel), Backend (Render/Railway with persistent volume for SQLite)

---

## Backend Implementation

### Core Modules

#### 1. `api_client.py` — Admin API Interface
```python
# Responsibilities:
# - Query /v1/organizations/usage_report/messages endpoint
# - Parse responses and extract: timestamp, model, workspace_id, input_tokens, output_tokens, cache_creation_tokens, cache_read_tokens
# - Handle pagination
# - Require ADMIN_API_KEY from env
# - Return structured token counts for given date range

# Key function signatures:
def fetch_usage_report(starting_at: str, ending_at: str, bucket_width: str = "1m") -> dict
def fetch_cost_report(starting_at: str, ending_at: str, group_by: List[str] = ["workspace_id"]) -> dict
```

#### 2. `claude_code_parser.py` — Local JSONL File Parser
```python
# Responsibilities:
# - Watch ~/.claude/projects/ for changes (use watchdog library)
# - Parse JSONL files incrementally (only new entries since last read)
# - Extract: message content, token counts (if embedded), timestamp, session_id, file paths
# - Normalize Claude Code token data into schema matching API data
# - Handle multiple concurrent sessions
# - Track 5-hour session windows (session reset logic)

# Key function signatures:
def parse_claude_code_sessions() -> List[dict]  # Returns current active sessions with token counts
def watch_projects_directory(callback: Callable) -> None  # Start file watcher, call callback on change
def get_session_state(session_id: str) -> dict  # Returns time-to-reset, tokens used, burn rate
```

#### 3. `database.py` — SQLite Schema & Operations
```python
# SQLite schema:

# TABLE: api_usage
# Columns: id (int), timestamp (datetime), model (str), workspace_id (str), 
#          input_tokens (int), output_tokens (int), cache_creation (int), 
#          cache_read (int), cost (float), bucket_width (str)
# Indexes: timestamp, workspace_id, model

# TABLE: claude_code_sessions
# Columns: id (int), session_id (str), started_at (datetime), ended_at (datetime, nullable),
#          total_input_tokens (int), total_output_tokens (int), total_cache_creation (int),
#          total_cache_read (int), status (str: 'active'/'completed'), estimated_cost (float)
# Indexes: session_id, started_at

# TABLE: daily_summary
# Columns: id (int), date (date), workspace_id (str), model (str),
#          input_tokens (int), output_tokens (int), cache_tokens (int),
#          cost (float), source (str: 'api'/'claude_code'/'both')
# Indexes: date, workspace_id

# TABLE: cost_alerts
# Columns: id (int), created_at (datetime), session_id (str), alert_type (str),
#          message (str), threshold_percent (float)

# Key functions:
def init_db() -> None
def record_api_usage(data: dict) -> None
def record_claude_code_session(session: dict) -> None
def update_session_tokens(session_id: str, tokens: dict) -> None
def get_daily_summary(date: str) -> dict
def get_weekly_summary(start_date: str, end_date: str) -> dict
def get_monthly_summary(month: str) -> dict
def get_cost_by_model(start_date: str, end_date: str) -> dict
def get_cost_by_workspace(start_date: str, end_date: str) -> dict
def get_active_sessions() -> List[dict]
```

#### 4. `scheduler.py` — Background Tasks
```python
# Responsibilities:
# - Schedule Admin API polling every 60 seconds (configurable)
# - Aggregate and normalize data into database
# - Calculate daily/weekly/monthly summaries
# - Detect session resets (5-hour windows) for Claude Code
# - Broadcast updates via WebSocket to connected clients
# - Alert logic (warn at 80%, 90%, 95% of session limits)

# Key functions:
def start_scheduler() -> None  # Initialize APScheduler
def poll_admin_api() -> None  # Fetch and store API usage
def process_claude_code_updates() -> None  # Parse local files, detect changes
def calculate_summaries() -> None  # Recompute day/week/month aggregates
def broadcast_update(data: dict) -> None  # Send to all WebSocket clients
```

#### 5. `main.py` — FastAPI Server
```python
# Endpoints:

# GET /api/status
# Returns: { active_sessions: int, last_update: datetime, data_sources: dict }

# GET /api/current
# Returns: { sessions: List[SessionData], burn_rate: float, time_to_reset: str, warnings: List[str] }

# GET /api/daily?date=YYYY-MM-DD
# Returns: { date, input_tokens, output_tokens, cache_tokens, cost, breakdown_by_model: dict }

# GET /api/weekly?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
# Returns: { start_date, end_date, total_tokens, daily_breakdown: List[dict], cost: float }

# GET /api/monthly?month=YYYY-MM
# Returns: { month, total_tokens, cost, workspace_breakdown: dict, model_breakdown: dict }

# GET /api/sessions
# Returns: List[{ session_id, status, started_at, tokens_used, estimated_cost, time_remaining }]

# POST /api/refresh
# Action: Trigger immediate poll of Admin API + Claude Code files
# Returns: { refreshed_at, data_freshness: str }

# WebSocket /ws
# Real-time updates: { event: 'update', data: CurrentStateData, timestamp: datetime }

# All endpoints should:
# - Include CORS headers for frontend on Vercel
# - Accept optional ?admin_api_key=... for local testing (store in env for prod)
# - Return structured JSON with clear error handling
```

### Configuration

Create `.env` file (not committed):
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

---

## Frontend Implementation

### Pages & Components

#### 1. Dashboard (Main Page)
**Components:**
- `<Header />` — Logo, time of last update, refresh button, settings icon
- `<CurrentSession />` — Active session info (time remaining, token burn rate, live meter)
- `<TokenBurnChart />` — Real-time line chart (last 2 hours, updated every 60s)
- `<SessionGrid />` — Grid of all active sessions with status badges
- `<AlertBanner />` — Display warnings when approaching session limits
- `<BreakdownTabs />` — Tab navigation: Today | This Week | This Month

#### 2. Today View
**Shows:**
- Total tokens consumed (input, output, cache)
- Cost breakdown by model
- Hourly burn rate trend
- Session list with individual costs
- Table: Time | Tokens (in/out) | Session | Model | Cost

#### 3. This Week View
**Shows:**
- Daily breakdown (bar chart: Mon–Sun)
- Total cost trend line
- Day-by-day table with summaries
- Workspace/project attribution (if available)

#### 4. This Month View
**Shows:**
- Weekly breakdown (line/bar combo)
- Cost by workspace (donut/pie chart)
- Cost by model (stacked bar)
- Top projects by token usage
- Month-to-date running total

#### 5. Settings Modal
**Options:**
- Admin API Key input (masked)
- Claude Code home directory path
- Polling interval (30–120 seconds)
- Cost alert thresholds (%)
- Theme toggle (light/dark)

### State Management (Zustand)
```typescript
interface DashboardState {
  currentData: CurrentStateData | null
  dailyData: DailySummaryData | null
  weeklyData: WeeklySummaryData | null
  monthlyData: MonthlySummaryData | null
  activeView: 'current' | 'daily' | 'weekly' | 'monthly'
  lastUpdate: Date | null
  isLoading: boolean
  error: string | null
  alerts: AlertData[]
  
  // Actions
  fetchCurrentData: () => Promise<void>
  fetchDailyData: (date: string) => Promise<void>
  fetchWeeklyData: (start: string, end: string) => Promise<void>
  fetchMonthlyData: (month: string) => Promise<void>
  refreshAll: () => Promise<void>
  subscribeToUpdates: (callback: Callable) => void
  setView: (view: string) => void
}
```

### Real-Time Updates
- WebSocket connection to `/ws` on page load
- Listeners for `update` events
- Zustand mutation on message arrival
- Auto-reconnect on disconnect (exponential backoff)
- Display "Live" indicator when connected, "Offline" with stale data indicator when not

### Charts & Visualizations
- **Real-time burn rate:** Recharts `LineChart` (last 120 minutes, updates every 60s)
- **Daily breakdown:** Recharts `BarChart` (7 days)
- **Cost by model:** Recharts `PieChart` or `RadarChart`
- **Cost by workspace:** Recharts `BarChart` (grouped/stacked)
- **Session meter:** Custom SVG circular progress (% of 5-hour limit)

### Styling
- TailwindCSS for all components
- Dark mode as default (user prefers working in dark envs), light mode toggle
- Color scheme:
  - Primary: Indigo-600
  - Success: Emerald-500
  - Warning: Amber-500
  - Danger: Red-600
  - Neutral: Slate-700/800

---

## Data Structures

### CurrentStateData
```typescript
{
  sessions: [
    {
      sessionId: string
      source: 'claude_code' | 'api'
      startedAt: ISO8601
      status: 'active' | 'idle' | 'completed'
      inputTokens: number
      outputTokens: number
      cacheCreationTokens: number
      cacheReadTokens: number
      totalTokens: number
      estimatedCost: number
      model: string
      workspace?: string
      timeRemaining?: string  // "4h 32m" for Claude Code
      burnRate: number  // tokens/min
      percentToLimit: number  // 0-100 for Claude Code 5hr window
    }
  ]
  totalActiveSessions: number
  aggregateBurnRate: number
  lastUpdate: ISO8601
  warnings: {
    sessionId: string
    type: 'approaching_limit' | 'high_burn_rate'
    message: string
    severity: 'info' | 'warning' | 'critical'
  }[]
}
```

### DailySummaryData
```typescript
{
  date: string  // YYYY-MM-DD
  totalInputTokens: number
  totalOutputTokens: number
  totalCacheTokens: number
  totalTokens: number
  estimatedCost: number
  byModel: {
    [model: string]: {
      inputTokens: number
      outputTokens: number
      cost: number
    }
  }
  hourly: [
    { hour: number, tokens: number, cost: number }
  ]
  sessions: [
    {
      sessionId: string
      tokens: number
      cost: number
      startedAt: ISO8601
      endedAt: ISO8601
    }
  ]
}
```

### WeeklySummaryData
```typescript
{
  startDate: string  // YYYY-MM-DD
  endDate: string    // YYYY-MM-DD
  dailyBreakdown: [
    { date: string, tokens: number, cost: number }
  ]
  totalTokens: number
  totalCost: number
  averageDailyCost: number
  byModel: { [model: string]: { tokens: number, cost: number } }
  byWorkspace?: { [workspace: string]: { tokens: number, cost: number } }
}
```

### MonthlySummaryData
```typescript
{
  month: string  // YYYY-MM
  weeklyBreakdown: [
    { week: number, tokens: number, cost: number }
  ]
  totalTokens: number
  totalCost: number
  averageDailyCost: number
  byModel: { [model: string]: { tokens: number, cost: number } }
  byWorkspace?: { [workspace: string]: { tokens: number, cost: number } }
  topProjects?: [
    { projectId: string, tokens: number, cost: number }
  ]
}
```

---

## Deployment

### Backend (Python)

**Option 1: Render**
1. Push repo to GitHub
2. Create Render Web Service from GitHub
3. Set environment variables in Render dashboard
4. Add persistent disk at `/data` for SQLite
5. Deploy (builds automatically on push)

**Option 2: Railway**
1. Connect GitHub repo
2. Railway auto-detects Python + builds
3. Set env vars in Railway dashboard
4. Deploy

**Dockerfile** (if needed):
```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**requirements.txt**:
```
fastapi==0.104.1
uvicorn==0.24.0
python-dotenv==1.0.0
apscheduler==3.10.0
watchdog==3.0.0
aiofiles==23.2.0
httpx==0.25.0
sqlite3  # stdlib
```

### Frontend (React + Vite)

**Build & Deploy to Vercel:**
1. Create `vercel.json` at root:
```json
{
  "buildCommand": "vite build",
  "outputDirectory": "dist",
  "env": {
    "VITE_API_URL": "@vite_api_url"
  }
}
```

2. In Vercel dashboard:
   - Link GitHub repo
   - Set `VITE_API_URL=https://your-backend.onrender.com` (or Railway equivalent)
   - Deploy

3. Create `vite.config.ts`:
```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': process.env.VITE_API_URL || 'http://localhost:8000'
    }
  }
})
```

---

## Workstreams for Claude Code

### Phase 1: Backend Foundation ✅ COMPLETE
- [x] Set up FastAPI scaffold, env config
- [x] Implement `api_client.py` (Admin API polling)
- [x] Implement `claude_code_parser.py` (JSONL parsing + file watching)
- [x] Implement `database.py` (SQLite schema + CRUD)
- [x] Test Admin API + local file integration locally (32 sessions parsed successfully)

### Phase 2: Backend Real-Time (3–4 hours)
- [ ] Implement `scheduler.py` (background tasks, WebSocket broadcasting)
- [ ] Complete `main.py` (all endpoints + WebSocket server)
- [ ] Error handling, retry logic, graceful degradation
- [ ] Local testing with mock data

### Phase 3: Frontend UI (4–5 hours)
- [ ] Set up React + Vite scaffold
- [ ] Implement Zustand store + API client
- [ ] Build Dashboard page + components (Header, SessionGrid, Charts)
- [ ] Build Today/Week/Month views
- [ ] Implement Settings modal

### Phase 4: Real-Time & Polish (3–4 hours)
- [ ] WebSocket integration + reconnection logic
- [ ] Live charts (Recharts integration)
- [ ] Alert system + notifications
- [ ] Dark mode toggle + styling refinement
- [ ] Responsive design (mobile-friendly)

### Phase 5: Deployment (2–3 hours)
- [ ] Dockerize backend (if needed)
- [ ] Deploy backend to Render/Railway
- [ ] Deploy frontend to Vercel
- [ ] Environment variable setup
- [ ] Test end-to-end on live URLs

---

## Notes & Constraints

1. **Admin API Key Security:** Store ONLY in backend env, never expose to frontend. Frontend calls `/api/*` endpoints only.

2. **Claude Code Session Windows:** Each session lasts 5 hours from first message. Calculate `time_remaining` as `(started_at + 5h) - now()`. Alert at 80%, 90%, 95% of window consumed.

3. **Cost Calculation:** 
   - Use model-specific rates from Anthropic pricing (embed in backend)
   - Cache creation tokens cost more than cache read tokens
   - Include in all summaries

4. **Data Freshness:** 
   - Admin API lags by ~5 minutes (documented by Anthropic)
   - Claude Code local files are immediate
   - Always display "Last updated: 2 min ago" on dashboard

5. **Multi-Tenancy (Future):** 
   - If multiple admin API keys, store separately in DB
   - Add workspace filter in frontend
   - Track by workspace_id in all summaries

6. **Offline Resilience:** 
   - WebSocket disconnect → show stale data with "Offline" indicator
   - Manual refresh button always available
   - Auto-retry WebSocket (exponential backoff, max 5 retries)

---

## Success Criteria

- ✅ Dashboard loads in <3s on initial page load
- ✅ Real-time updates appear within 5 seconds of event (via WebSocket)
- ✅ 60-second poll cycle from Admin API → visible on dashboard
- ✅ Current, Daily, Weekly, Monthly views fully functional
- ✅ Session time-to-reset countdown accurate to ±5 seconds
- ✅ Alerts trigger at specified thresholds
- ✅ Manual refresh button works instantly
- ✅ Deploy to cloud URLs without errors
- ✅ Dark mode default, light mode toggle works
- ✅ No console errors in browser DevTools

---

## Questions for Implementation

1. What is your Admin API Key? (Or should I use env placeholder for now?)
2. What is your Render/Railway deploy target? (Or preference between the two?)
3. Should alerts trigger browser notifications, or just dashboard banner?
4. Do you have specific workspaces in your Admin API setup that matter for breakdown?
5. Preference: SQLite file in repo (gitignored) or persistent volume on hosting?

---

## File Structure (Completed)

```
token-dashboard/
├── backend/
│   ├── main.py
│   ├── api_client.py
│   ├── claude_code_parser.py
│   ├── database.py
│   ├── scheduler.py
│   ├── config.py
│   ├── requirements.txt
│   ├── .env (gitignored)
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── store.ts (Zustand)
│   │   ├── api/
│   │   │   └── client.ts
│   │   ├── components/
│   │   │   ├── Dashboard.tsx
│   │   │   ├── Header.tsx
│   │   │   ├── CurrentSession.tsx
│   │   │   ├── TokenBurnChart.tsx
│   │   │   ├── SessionGrid.tsx
│   │   │   ├── AlertBanner.tsx
│   │   │   ├── DailyView.tsx
│   │   │   ├── WeeklyView.tsx
│   │   │   ├── MonthlyView.tsx
│   │   │   └── SettingsModal.tsx
│   │   └── styles/
│   │       └── globals.css (Tailwind)
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── package.json
│   └── vercel.json
├── docker-compose.yml (local dev)
├── README.md
└── .gitignore
```

---

**Status:** Phase 1 complete. Phase 0 (setup) and Phase 1 (backend foundation) pushed to GitHub. Ready for Phase 2.
