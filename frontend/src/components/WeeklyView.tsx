import { useEffect } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
} from 'recharts';
import { useStore } from '../store';

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

export default function WeeklyView() {
  const weeklyData = useStore((s) => s.weeklyData);
  const fetchWeeklyData = useStore((s) => s.fetchWeeklyData);

  useEffect(() => {
    if (!weeklyData) fetchWeeklyData();
  }, []);

  if (!weeklyData) {
    return <div className="px-6 py-8 text-center text-slate-500">Loading weekly data...</div>;
  }

  const daily = weeklyData.dailyBreakdown.map((d) => ({
    date: d.date.slice(5), // MM-DD
    tokens: d.tokens,
    cost: d.cost,
  }));

  const modelData = Object.entries(weeklyData.byModel).map(([model, data]) => ({
    name: model.replace('claude-', '').replace('-20251001', ''),
    ...data,
  }));

  return (
    <div className="px-6 py-4 space-y-6">
      <h2 className="text-lg font-semibold text-white">
        This Week &mdash; {weeklyData.startDate} to {weeklyData.endDate}
      </h2>

      {/* Summary cards */}
      <div className="grid grid-cols-3 gap-4">
        <SummaryCard label="Total Tokens" value={formatTokens(weeklyData.totalTokens)} />
        <SummaryCard label="Total Cost" value={`$${weeklyData.totalCost.toFixed(2)}`} accent />
        <SummaryCard label="Avg Daily Cost" value={`$${weeklyData.averageDailyCost.toFixed(2)}`} />
      </div>

      {/* Daily bar chart */}
      {daily.length > 0 && (
        <div className="bg-slate-800 rounded-xl p-5 border border-slate-700">
          <h3 className="text-sm font-semibold text-slate-300 mb-3">Daily Token Usage</h3>
          <div className="h-52">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={daily}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis dataKey="date" stroke="#64748b" tick={{ fontSize: 11 }} />
                <YAxis stroke="#64748b" tick={{ fontSize: 11 }} tickFormatter={(v: number) => formatTokens(v)} />
                <Tooltip
                  contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8 }}
                  formatter={(v) => [Number(v).toLocaleString(), 'Tokens']}
                />
                <Bar dataKey="tokens" fill="#818cf8" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Cost trend line */}
      {daily.length > 0 && (
        <div className="bg-slate-800 rounded-xl p-5 border border-slate-700">
          <h3 className="text-sm font-semibold text-slate-300 mb-3">Daily Cost Trend</h3>
          <div className="h-44">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={daily}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis dataKey="date" stroke="#64748b" tick={{ fontSize: 11 }} />
                <YAxis stroke="#64748b" tick={{ fontSize: 11 }} tickFormatter={(v: number) => `$${v.toFixed(0)}`} />
                <Tooltip
                  contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8 }}
                  formatter={(v) => [`$${Number(v).toFixed(4)}`, 'Cost']}
                />
                <Line type="monotone" dataKey="cost" stroke="#34d399" strokeWidth={2} dot={{ fill: '#34d399', r: 3 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Model table */}
      {modelData.length > 0 && (
        <div className="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden">
          <h3 className="text-sm font-semibold text-slate-300 px-5 pt-4 pb-2">By Model</h3>
          <table className="w-full text-sm">
            <thead className="text-xs text-slate-400 uppercase tracking-wide">
              <tr>
                <th className="px-5 py-2 text-left">Model</th>
                <th className="px-5 py-2 text-right">Tokens</th>
                <th className="px-5 py-2 text-right">Cost</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700">
              {modelData.map((m) => (
                <tr key={m.name} className="hover:bg-slate-700/50">
                  <td className="px-5 py-2.5 text-slate-300">{m.name}</td>
                  <td className="px-5 py-2.5 text-right text-slate-300">{formatTokens(m.tokens)}</td>
                  <td className="px-5 py-2.5 text-right text-slate-300">${m.cost.toFixed(4)}</td>
                </tr>
              ))}
            </tbody>
          </table>
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
