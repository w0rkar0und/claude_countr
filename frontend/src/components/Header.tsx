import { useStore } from '../store';

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const secs = Math.floor(diff / 1000);
  if (secs < 60) return `${secs}s ago`;
  const mins = Math.floor(secs / 60);
  if (mins < 60) return `${mins}m ago`;
  return `${Math.floor(mins / 60)}h ${mins % 60}m ago`;
}

export default function Header() {
  const lastUpdate = useStore((s) => s.lastUpdate);
  const wsConnected = useStore((s) => s.wsConnected);
  const isLoading = useStore((s) => s.isLoading);
  const darkMode = useStore((s) => s.darkMode);
  const refreshAll = useStore((s) => s.refreshAll);
  const setSettingsOpen = useStore((s) => s.setSettingsOpen);
  const toggleDarkMode = useStore((s) => s.toggleDarkMode);

  return (
    <header className="flex items-center justify-between px-6 py-4 border-b border-slate-700 bg-slate-900">
      <div className="flex items-center gap-3">
        <h1 className="text-xl font-semibold text-white tracking-tight">claude_countr</h1>
        <span
          className={`inline-flex items-center gap-1.5 text-xs font-medium px-2 py-0.5 rounded-full ${
            wsConnected
              ? 'bg-emerald-500/15 text-emerald-400'
              : 'bg-red-500/15 text-red-400'
          }`}
        >
          <span className={`w-1.5 h-1.5 rounded-full ${wsConnected ? 'bg-emerald-400 animate-pulse' : 'bg-red-400'}`} />
          {wsConnected ? 'Live' : 'Offline'}
        </span>
      </div>

      <div className="flex items-center gap-4">
        {lastUpdate && (
          <span className="text-xs text-slate-400">
            Updated {timeAgo(lastUpdate)}
          </span>
        )}

        <button
          onClick={refreshAll}
          disabled={isLoading}
          className="px-3 py-1.5 text-sm font-medium rounded-md bg-indigo-600 text-white hover:bg-indigo-500 disabled:opacity-50 transition-colors"
        >
          {isLoading ? 'Refreshing...' : 'Refresh'}
        </button>

        <button
          onClick={toggleDarkMode}
          className="p-1.5 rounded-md text-slate-400 hover:text-white hover:bg-slate-700 transition-colors"
          title={darkMode ? 'Light mode' : 'Dark mode'}
        >
          {darkMode ? (
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" /></svg>
          ) : (
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" /></svg>
          )}
        </button>

        <button
          onClick={() => setSettingsOpen(true)}
          className="p-1.5 rounded-md text-slate-400 hover:text-white hover:bg-slate-700 transition-colors"
          title="Settings"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /></svg>
        </button>
      </div>
    </header>
  );
}
