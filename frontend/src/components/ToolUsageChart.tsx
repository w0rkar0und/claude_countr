import { useEffect, useState } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { api, type ToolUsageMap } from '../api/client';

const TOOL_COLORS: Record<string, string> = {
  Read: '#818cf8',
  Bash: '#f59e0b',
  Edit: '#34d399',
  Write: '#8b5cf6',
  Grep: '#06b6d4',
  Glob: '#ec4899',
  Agent: '#ef4444',
  TaskCreate: '#64748b',
  TaskUpdate: '#64748b',
  ToolSearch: '#64748b',
  WebFetch: '#f97316',
  WebSearch: '#f97316',
};

export default function ToolUsageChart() {
  const [tools, setTools] = useState<ToolUsageMap>({});

  useEffect(() => {
    api.getTools().then(setTools).catch(() => {});
  }, []);

  const data = Object.entries(tools)
    .map(([name, count]) => ({ name, count, fill: TOOL_COLORS[name] || '#64748b' }))
    .slice(0, 12);

  if (data.length === 0) return null;

  return (
    <div className="bg-slate-800 rounded-xl p-5 border border-slate-700">
      <h3 className="text-sm font-semibold text-slate-300 mb-3">Tool Usage (All Sessions)</h3>
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical" margin={{ left: 10 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#334155" horizontal={false} />
            <XAxis type="number" stroke="#64748b" tick={{ fontSize: 11 }} />
            <YAxis
              type="category"
              dataKey="name"
              stroke="#64748b"
              tick={{ fontSize: 12, fill: '#94a3b8' }}
              width={90}
            />
            <Tooltip
              contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8 }}
              labelStyle={{ color: '#e2e8f0', fontWeight: 600 }}
              formatter={(v) => [Number(v).toLocaleString(), 'Uses']}
            />
            <Bar dataKey="count" radius={[0, 6, 6, 0]} barSize={20}>
              {data.map((entry, i) => (
                <rect key={i} fill={entry.fill} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
