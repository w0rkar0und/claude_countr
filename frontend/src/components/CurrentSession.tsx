import { useStore } from '../store';
import type { SessionState } from '../api/client';

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

function SessionCard({ session }: { session: SessionState }) {
  const pct = session.percent_to_limit ?? 0;
  const total =
    session.total_input_tokens +
    session.total_output_tokens +
    session.total_cache_creation +
    session.total_cache_read;

  const barColor =
    pct >= 95 ? 'bg-red-500' : pct >= 80 ? 'bg-amber-500' : 'bg-indigo-500';

  const topTools = Object.entries(session.tool_usage || {})
    .sort(([, a], [, b]) => b - a)
    .slice(0, 4);

  return (
    <div className="bg-slate-800 rounded-xl p-5 border border-slate-700">
      <div className="flex items-center justify-between mb-1">
        <span className="text-sm font-semibold text-white truncate max-w-[200px]">
          {session.project || session.session_id.split('/').pop()?.slice(0, 12)}
        </span>
        <span
          className={`text-xs font-medium px-2 py-0.5 rounded-full ${
            session.status === 'active'
              ? 'bg-emerald-500/15 text-emerald-400'
              : 'bg-slate-600/30 text-slate-400'
          }`}
        >
          {session.status}
        </span>
      </div>

      {/* Subagent + branch badges */}
      <div className="flex items-center gap-1.5 mb-3">
        <span className="text-[10px] text-slate-500 font-mono">
          {session.model.replace('claude-', '').replace('-20251001', '')}
        </span>
        {session.is_subagent && (
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-400">subagent</span>
        )}
        {session.git_branch && (
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-indigo-500/10 text-indigo-400">
            {session.git_branch}
          </span>
        )}
      </div>

      {/* Progress bar */}
      <div className="mb-4">
        <div className="flex justify-between text-xs text-slate-400 mb-1">
          <span>{session.time_remaining ?? 'N/A'} remaining</span>
          <span>{pct.toFixed(1)}%</span>
        </div>
        <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ${barColor}`}
            style={{ width: `${Math.min(pct, 100)}%` }}
          />
        </div>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-2 gap-3 mb-3">
        <div>
          <div className="text-xs text-slate-500 mb-0.5">Tokens</div>
          <div className="text-lg font-semibold text-white">{formatTokens(total)}</div>
        </div>
        <div>
          <div className="text-xs text-slate-500 mb-0.5">Cost</div>
          <div className="text-lg font-semibold text-indigo-400">${session.estimated_cost.toFixed(2)}</div>
        </div>
        <div>
          <div className="text-xs text-slate-500 mb-0.5">Burn Rate</div>
          <div className="text-sm text-slate-300">{formatTokens(session.burn_rate ?? 0)}/min</div>
        </div>
        <div>
          <div className="text-xs text-slate-500 mb-0.5">Messages</div>
          <div className="text-sm text-slate-300">{session.message_count ?? 0}</div>
        </div>
      </div>

      {/* Top tools */}
      {topTools.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {topTools.map(([name, count]) => (
            <span key={name} className="text-[10px] px-1.5 py-0.5 rounded bg-slate-700 text-slate-400">
              {name}: {count}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

export default function CurrentSession() {
  const currentData = useStore((s) => s.currentData);

  if (!currentData || currentData.sessions.length === 0) {
    return (
      <div className="px-6 py-8 text-center text-slate-500">
        No active sessions
      </div>
    );
  }

  return (
    <div className="px-6 py-4">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-white">
          Active Sessions
          <span className="ml-2 text-sm font-normal text-slate-400">
            ({currentData.totalActiveSessions})
          </span>
        </h2>
        <div className="text-sm text-slate-400">
          Aggregate burn: <span className="text-indigo-400 font-medium">{formatTokens(currentData.aggregateBurnRate)}/min</span>
        </div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {currentData.sessions.map((s) => (
          <SessionCard key={s.session_id} session={s} />
        ))}
      </div>
    </div>
  );
}
