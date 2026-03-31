import { useEffect, useState } from 'react';
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from 'recharts';
import { api, type SessionListItem } from '../api/client';

const COLORS = ['#818cf8', '#34d399', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4', '#ec4899'];

function formatModel(m: string): string {
  return m.replace('claude-', '').replace('-20251001', '').replace('<synthetic>', 'synthetic');
}

export default function CostByModelChart() {
  const [sessions, setSessions] = useState<SessionListItem[]>([]);

  useEffect(() => {
    api.getSessions().then(setSessions).catch(() => {});
  }, []);

  // Aggregate cost by model
  const byModel: Record<string, number> = {};
  for (const s of sessions) {
    const model = formatModel(s.model || 'unknown');
    byModel[model] = (byModel[model] || 0) + s.estimatedCost;
  }

  const data = Object.entries(byModel)
    .map(([name, cost]) => ({ name, cost: Math.round(cost * 100) / 100 }))
    .sort((a, b) => b.cost - a.cost);

  if (data.length === 0) return null;

  const totalCost = data.reduce((sum, d) => sum + d.cost, 0);

  return (
    <div className="bg-slate-800 rounded-xl p-5 border border-slate-700">
      <h3 className="text-sm font-semibold text-slate-300 mb-1">Cost by Model</h3>
      <div className="text-2xl font-bold text-indigo-400 mb-3">${totalCost.toFixed(2)}</div>
      <div className="flex items-center gap-6">
        <div className="w-40 h-40">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={data}
                dataKey="cost"
                nameKey="name"
                cx="50%"
                cy="50%"
                innerRadius={35}
                outerRadius={65}
                paddingAngle={2}
              >
                {data.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8 }}
                formatter={(v) => [`$${Number(v).toFixed(2)}`, 'Cost']}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>
        <div className="flex-1 space-y-2">
          {data.map((d, i) => (
            <div key={d.name} className="flex items-center gap-2">
              <span
                className="w-3 h-3 rounded-sm shrink-0"
                style={{ backgroundColor: COLORS[i % COLORS.length] }}
              />
              <span className="text-sm text-slate-300 flex-1 truncate">{d.name}</span>
              <span className="text-sm text-slate-400">${d.cost.toFixed(2)}</span>
              <span className="text-xs text-slate-500 w-10 text-right">
                {totalCost > 0 ? `${((d.cost / totalCost) * 100).toFixed(0)}%` : '0%'}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
