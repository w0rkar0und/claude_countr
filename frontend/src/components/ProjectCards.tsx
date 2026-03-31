import { useEffect, useState } from 'react';
import { api, type ProjectSummary } from '../api/client';

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

function ProjectCard({ project }: { project: ProjectSummary }) {
  const topTools = Object.entries(project.tools_used)
    .sort(([, a], [, b]) => b - a)
    .slice(0, 5);

  const totalToolUses = Object.values(project.tools_used).reduce((a, b) => a + b, 0);

  return (
    <div className="bg-slate-800 rounded-xl p-5 border border-slate-700">
      <div className="flex items-center justify-between mb-3">
        <h4 className="text-base font-semibold text-white truncate">{project.project}</h4>
        <div className="flex items-center gap-2">
          {project.active_sessions > 0 && (
            <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400">
              {project.active_sessions} active
            </span>
          )}
          <span className="text-xs text-slate-500">{project.session_count} sessions</span>
        </div>
      </div>

      {/* Cost and tokens */}
      <div className="grid grid-cols-2 gap-3 mb-4">
        <div>
          <div className="text-xs text-slate-500">Cost</div>
          <div className="text-lg font-bold text-indigo-400">${project.total_cost.toFixed(2)}</div>
        </div>
        <div>
          <div className="text-xs text-slate-500">Tokens</div>
          <div className="text-lg font-bold text-white">{formatTokens(project.total_tokens)}</div>
        </div>
      </div>

      {/* Tool usage mini-bars */}
      {topTools.length > 0 && (
        <div className="space-y-1.5 mb-3">
          <div className="text-xs text-slate-500">Top Tools</div>
          {topTools.map(([name, count]) => (
            <div key={name} className="flex items-center gap-2">
              <span className="text-xs text-slate-400 w-16 truncate">{name}</span>
              <div className="flex-1 h-1.5 bg-slate-700 rounded-full overflow-hidden">
                <div
                  className="h-full bg-indigo-500/70 rounded-full"
                  style={{ width: `${Math.min((count / totalToolUses) * 100 * 3, 100)}%` }}
                />
              </div>
              <span className="text-xs text-slate-500 w-10 text-right">{count}</span>
            </div>
          ))}
        </div>
      )}

      {/* Models and branches */}
      <div className="flex flex-wrap gap-1.5">
        {project.models_used.map((m) => (
          <span key={m} className="text-[10px] px-1.5 py-0.5 rounded bg-slate-700 text-slate-400">
            {m.replace('claude-', '').replace('-20251001', '')}
          </span>
        ))}
        {project.git_branches.slice(0, 2).map((b) => (
          <span key={b} className="text-[10px] px-1.5 py-0.5 rounded bg-indigo-500/10 text-indigo-400">
            {b}
          </span>
        ))}
      </div>
    </div>
  );
}

export default function ProjectCards() {
  const [projects, setProjects] = useState<ProjectSummary[]>([]);

  useEffect(() => {
    api.getProjects().then(setProjects).catch(() => {});
  }, []);

  if (projects.length === 0) return null;

  return (
    <div className="px-6 py-4">
      <h3 className="text-sm font-semibold text-slate-300 mb-3">
        Projects
        <span className="ml-2 text-xs font-normal text-slate-500">({projects.length})</span>
      </h3>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {projects.map((p) => (
          <ProjectCard key={p.project} project={p} />
        ))}
      </div>
    </div>
  );
}
