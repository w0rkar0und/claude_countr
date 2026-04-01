import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { useStore } from '../store';

const EMPTY: never[] = [];

export default function TokenBurnChart() {
  const dailyData = useStore((s) => s.dailyData);
  const hourly = dailyData?.hourly ?? EMPTY;

  if (hourly.length === 0) {
    return (
      <div className="px-6 py-6 text-center text-slate-500 text-sm">
        No hourly data available for today
      </div>
    );
  }

  const data = hourly.map((h) => ({
    hour: `${String(h.hour).padStart(2, '0')}:00`,
    tokens: h.tokens,
    cost: h.cost,
  }));

  return (
    <div className="px-6 py-4">
      <h3 className="text-sm font-semibold text-slate-300 mb-3">Token Burn (Today, Hourly)</h3>
      <div className="h-56 bg-slate-800 rounded-xl p-4 border border-slate-700">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
            <XAxis dataKey="hour" stroke="#64748b" tick={{ fontSize: 11 }} />
            <YAxis
              stroke="#64748b"
              tick={{ fontSize: 11 }}
              tickFormatter={(v: number) =>
                v >= 1_000_000 ? `${(v / 1_000_000).toFixed(1)}M` : v >= 1_000 ? `${(v / 1_000).toFixed(0)}K` : String(v)
              }
            />
            <Tooltip
              contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8 }}
              labelStyle={{ color: '#94a3b8' }}
              itemStyle={{ color: '#a5b4fc' }}
              formatter={(v) => [Number(v).toLocaleString(), 'Tokens']}
            />
            <Line
              type="monotone"
              dataKey="tokens"
              stroke="#818cf8"
              strokeWidth={2}
              dot={{ fill: '#818cf8', r: 3 }}
              activeDot={{ r: 5 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
