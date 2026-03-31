import { useEffect } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from 'recharts';
import { useStore } from '../store';

const COLORS = ['#818cf8', '#34d399', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4'];

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

export default function DailyView() {
  const dailyData = useStore((s) => s.dailyData);
  const fetchDailyData = useStore((s) => s.fetchDailyData);

  useEffect(() => {
    if (!dailyData) fetchDailyData();
  }, []);

  if (!dailyData) {
    return <div className="px-6 py-8 text-center text-slate-500">Loading daily data...</div>;
  }

  const hourlyData = dailyData.hourly.map((h) => ({
    hour: `${String(h.hour).padStart(2, '0')}:00`,
    tokens: h.tokens,
    cost: h.cost,
  }));

  const modelData = Object.entries(dailyData.byModel).map(([model, data]) => ({
    name: model.replace('claude-', '').replace('-20251001', ''),
    cost: data.cost,
    tokens: data.inputTokens + data.outputTokens,
  }));

  return (
    <div className="px-6 py-4 space-y-6">
      <h2 className="text-lg font-semibold text-white">Today &mdash; {dailyData.date}</h2>

      {/* Summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <SummaryCard label="Total Tokens" value={formatTokens(dailyData.totalTokens)} />
        <SummaryCard label="Input" value={formatTokens(dailyData.totalInputTokens)} />
        <SummaryCard label="Output" value={formatTokens(dailyData.totalOutputTokens)} />
        <SummaryCard label="Cost" value={`$${dailyData.estimatedCost.toFixed(2)}`} accent />
      </div>

      {/* Hourly bar chart */}
      {hourlyData.length > 0 && (
        <div className="bg-slate-800 rounded-xl p-5 border border-slate-700">
          <h3 className="text-sm font-semibold text-slate-300 mb-3">Hourly Breakdown</h3>
          <div className="h-52">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={hourlyData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis dataKey="hour" stroke="#64748b" tick={{ fontSize: 10 }} />
                <YAxis stroke="#64748b" tick={{ fontSize: 10 }} tickFormatter={(v: number) => formatTokens(v)} />
                <Tooltip
                  contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8 }}
                  labelStyle={{ color: '#94a3b8' }}
                  formatter={(v) => [Number(v).toLocaleString(), 'Tokens']}
                />
                <Bar dataKey="tokens" fill="#818cf8" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Model cost pie chart */}
      {modelData.length > 0 && (
        <div className="bg-slate-800 rounded-xl p-5 border border-slate-700">
          <h3 className="text-sm font-semibold text-slate-300 mb-3">Cost by Model</h3>
          <div className="h-52 flex items-center justify-center">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={modelData}
                  dataKey="cost"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  outerRadius={80}
                  label={({ name, value }) => `${name}: $${Number(value).toFixed(2)}`}
                >
                  {modelData.map((_, i) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8 }}
                  formatter={(v) => [`$${Number(v).toFixed(4)}`, 'Cost']}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  );
}

function SummaryCard({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className="bg-slate-800 rounded-xl p-4 border border-slate-700">
      <div className="text-xs text-slate-500 mb-1">{label}</div>
      <div className={`text-xl font-bold ${accent ? 'text-indigo-400' : 'text-white'}`}>{value}</div>
    </div>
  );
}
