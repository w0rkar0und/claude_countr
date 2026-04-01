const BASE = import.meta.env.VITE_API_URL ?? '';

async function fetchJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

async function postJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { method: 'POST' });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

// --- Types ---

export interface SessionState {
  session_id: string;
  started_at: string;
  ended_at: string | null;
  total_input_tokens: number;
  total_output_tokens: number;
  total_cache_creation: number;
  total_cache_read: number;
  status: 'active' | 'completed';
  estimated_cost: number;
  model: string;
  time_remaining?: string;
  percent_to_limit?: number;
  burn_rate?: number;
  project?: string;
  git_branch?: string;
  is_subagent?: boolean;
  tool_usage?: Record<string, number>;
  message_count?: number;
}

export interface Warning {
  sessionId: string;
  type: string;
  message: string;
  severity: 'info' | 'warning' | 'critical';
}

export interface CurrentData {
  sessions: SessionState[];
  totalActiveSessions: number;
  aggregateBurnRate: number;
  lastUpdate: string;
  warnings: Warning[];
}

export interface StatusData {
  active_sessions: number;
  last_update: string | null;
  websocket_clients: number;
  data_sources: { admin_api: boolean; claude_code: boolean };
}

export interface DailyData {
  date: string;
  totalInputTokens: number;
  totalOutputTokens: number;
  totalCacheTokens: number;
  totalTokens: number;
  estimatedCost: number;
  byModel: Record<string, { inputTokens: number; outputTokens: number; cost: number }>;
  hourly: { hour: number; tokens: number; cost: number }[];
}

export interface WeeklyData {
  startDate: string;
  endDate: string;
  dailyBreakdown: { date: string; tokens: number; cost: number }[];
  totalTokens: number;
  totalCost: number;
  averageDailyCost: number;
  byModel: Record<string, { tokens: number; cost: number }>;
}

export interface MonthlyData {
  month: string;
  weeklyBreakdown: { week: number; tokens: number; cost: number }[];
  totalTokens: number;
  totalCost: number;
  averageDailyCost: number;
  byModel: Record<string, { tokens: number; cost: number }>;
  byWorkspace: Record<string, { tokens: number; cost: number }>;
}

export interface SessionListItem {
  sessionId: string;
  status: string;
  startedAt: string;
  tokensUsed: number;
  estimatedCost: number;
  timeRemaining: string;
  model: string;
  project: string;
  gitBranch: string;
  isSubagent: boolean;
  toolUsage: Record<string, number>;
  messageCount: number;
}

export type ToolUsageMap = Record<string, number>;

export interface ProjectSummary {
  project: string;
  session_count: number;
  active_sessions: number;
  total_tokens: number;
  total_cost: number;
  models_used: string[];
  tools_used: Record<string, number>;
  git_branches: string[];
}

export interface RefreshResult {
  refreshed_at: string;
  api_records_fetched: number;
  sessions_parsed: number;
  data_freshness: string;
}

export interface Alert {
  id: number;
  created_at: string;
  session_id: string;
  alert_type: string;
  message: string;
  threshold_percent: number;
}

// --- API Functions ---

export interface DateRange {
  minDate: string | null;
  maxDate: string | null;
}

export const api = {
  getStatus: () => fetchJSON<StatusData>('/api/status'),
  getCurrent: () => fetchJSON<CurrentData>('/api/current'),
  getDateRange: () => fetchJSON<DateRange>('/api/date-range'),
  getDaily: (date?: string) =>
    fetchJSON<DailyData>(`/api/daily${date ? `?date_str=${date}` : ''}`),
  getWeekly: (start?: string, end?: string) => {
    const params = new URLSearchParams();
    if (start) params.set('start_date', start);
    if (end) params.set('end_date', end);
    const qs = params.toString();
    return fetchJSON<WeeklyData>(`/api/weekly${qs ? `?${qs}` : ''}`);
  },
  getMonthly: (month?: string) =>
    fetchJSON<MonthlyData>(`/api/monthly${month ? `?month=${month}` : ''}`),
  getSessions: () => fetchJSON<SessionListItem[]>('/api/sessions'),
  getTools: () => fetchJSON<ToolUsageMap>('/api/tools'),
  getProjects: () => fetchJSON<ProjectSummary[]>('/api/projects'),
  refresh: () => postJSON<RefreshResult>('/api/refresh'),
  getAlerts: () => fetchJSON<Alert[]>('/api/alerts'),
};

// --- WebSocket ---

export type WSCallback = (data: { event: string; data: CurrentData; timestamp: string }) => void;
export type WSStatusCallback = (connected: boolean) => void;

export function connectWebSocket(onMessage: WSCallback, onStatus?: WSStatusCallback): () => void {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsBase = import.meta.env.VITE_API_URL
    ? import.meta.env.VITE_API_URL.replace(/^http/, 'ws')
    : `${protocol}//${window.location.host}`;
  const url = `${wsBase}/ws`;

  let ws: WebSocket | null = null;
  let retries = 0;
  let closed = false;
  let pingInterval: ReturnType<typeof setInterval>;

  function connect() {
    if (closed) return;
    ws = new WebSocket(url);

    ws.onopen = () => {
      retries = 0;
      onStatus?.(true);
      pingInterval = setInterval(() => {
        if (ws?.readyState === WebSocket.OPEN) ws.send('ping');
      }, 30000);
    };

    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data);
        if (msg.event === 'pong') return;
        onMessage(msg);
      } catch { /* ignore bad JSON */ }
    };

    ws.onclose = () => {
      clearInterval(pingInterval);
      onStatus?.(false);
      if (!closed) {
        const delay = Math.min(1000 * 2 ** retries, 30000);
        retries++;
        setTimeout(connect, delay);
      }
    };

    ws.onerror = () => ws?.close();
  }

  connect();

  return () => {
    closed = true;
    clearInterval(pingInterval);
    ws?.close();
  };
}
