import { useEffect, useState } from 'react';
import { api, type SessionListItem } from '../api/client';

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

function formatModel(m: string): string {
  return m.replace('claude-', '').replace('-20251001', '');
}

function SessionRow({ s }: { s: SessionListItem }) {
  const topTools = Object.entries(s.toolUsage || {})
    .sort(([, a], [, b]) => b - a)
    .slice(0, 4);

  return (
    <tr className="bg-slate-800/50 hover:bg-slate-800 transition-colors">
      <td className="px-4 py-2.5">
        <div className="flex items-center gap-2">
          <span
            className={`w-2 h-2 rounded-full shrink-0 ${
              s.status === 'active' ? 'bg-emerald-400 animate-pulse' : 'bg-slate-600'
            }`}
          />
          <div>
            <div className="text-sm text-slate-200 font-medium">{s.project || 'unknown'}</div>
            <div className="text-[10px] text-slate-500 font-mono">
              {s.sessionId.split('/').pop()?.slice(0, 12)}
              {s.isSubagent && (
                <span className="ml-1 text-amber-500/70">subagent</span>
              )}
            </div>
          </div>
        </div>
      </td>
      <td className="px-4 py-2.5 text-xs text-slate-400">
        {formatModel(s.model)}
      </td>
      <td className="px-4 py-2.5 text-right">
        <div className="text-sm text-slate-300">{formatTokens(s.tokensUsed)}</div>
        <div className="text-[10px] text-slate-500">{s.messageCount} msgs</div>
      </td>
      <td className="px-4 py-2.5 text-right text-sm text-slate-300">
        ${s.estimatedCost.toFixed(2)}
      </td>
      <td className="px-4 py-2.5">
        <div className="flex flex-wrap gap-1">
          {topTools.map(([name, count]) => (
            <span key={name} className="text-[10px] px-1.5 py-0.5 rounded bg-slate-700 text-slate-400">
              {name}:{count}
            </span>
          ))}
        </div>
      </td>
      <td className="px-4 py-2.5 text-right text-xs text-slate-500">
        {s.status === 'active' ? (
          <span className="text-emerald-400">{s.timeRemaining}</span>
        ) : (
          s.gitBranch || '-'
        )}
      </td>
    </tr>
  );
}

export default function SessionGrid() {
  const [sessions, setSessions] = useState<SessionListItem[]>([]);

  useEffect(() => {
    api.getSessions().then(setSessions).catch(() => {});
  }, []);

  if (sessions.length === 0) return null;

  const active = sessions.filter((s) => s.status === 'active');
  const completed = sessions.filter((s) => s.status !== 'active');

  return (
    <div className="px-6 py-4">
      <h3 className="text-sm font-semibold text-slate-300 mb-3">
        Sessions
        <span className="ml-2 text-xs font-normal text-slate-500">
          ({active.length} active, {completed.length} completed)
        </span>
      </h3>
      <div className="overflow-x-auto rounded-xl border border-slate-700">
        <table className="w-full text-sm text-left">
          <thead className="bg-slate-800 text-slate-400 text-xs uppercase tracking-wide">
            <tr>
              <th className="px-4 py-3">Project / Session</th>
              <th className="px-4 py-3">Model</th>
              <th className="px-4 py-3 text-right">Tokens</th>
              <th className="px-4 py-3 text-right">Cost</th>
              <th className="px-4 py-3">Tools</th>
              <th className="px-4 py-3 text-right">Time / Branch</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-700/50">
            {active.map((s) => (
              <SessionRow key={s.sessionId} s={s} />
            ))}
            {completed.slice(0, 20).map((s) => (
              <SessionRow key={s.sessionId} s={s} />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
