import { useStore } from '../store';

export default function SettingsModal() {
  const settingsOpen = useStore((s) => s.settingsOpen);
  const setSettingsOpen = useStore((s) => s.setSettingsOpen);
  const darkMode = useStore((s) => s.darkMode);
  const toggleDarkMode = useStore((s) => s.toggleDarkMode);

  if (!settingsOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={() => setSettingsOpen(false)}
      />

      {/* Modal */}
      <div className="relative bg-slate-800 rounded-2xl border border-slate-700 w-full max-w-md p-6 shadow-2xl">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-semibold text-white">Settings</h2>
          <button
            onClick={() => setSettingsOpen(false)}
            className="p-1 rounded-md text-slate-400 hover:text-white hover:bg-slate-700 transition-colors"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="space-y-5">
          {/* API URL */}
          <SettingField
            label="Backend API URL"
            description="Set via VITE_API_URL environment variable"
            value={import.meta.env.VITE_API_URL || 'http://localhost:8000 (proxy)'}
            disabled
          />

          {/* Polling interval */}
          <SettingField
            label="Polling Interval"
            description="Configured on the backend (POLLING_INTERVAL env var)"
            value="60 seconds (default)"
            disabled
          />

          {/* Theme toggle */}
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm font-medium text-slate-200">Dark Mode</div>
              <div className="text-xs text-slate-500">Toggle light/dark theme</div>
            </div>
            <button
              onClick={toggleDarkMode}
              className={`relative w-11 h-6 rounded-full transition-colors ${
                darkMode ? 'bg-indigo-600' : 'bg-slate-600'
              }`}
            >
              <span
                className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white transition-transform ${
                  darkMode ? 'translate-x-5' : ''
                }`}
              />
            </button>
          </div>

          {/* Alert thresholds */}
          <SettingField
            label="Alert Thresholds"
            description="Configured on the backend (COST_ALERT_THRESHOLDS env var)"
            value="80%, 90%, 95%"
            disabled
          />
        </div>

        <div className="mt-6 pt-4 border-t border-slate-700">
          <p className="text-xs text-slate-500">
            Most settings are configured via environment variables on the backend.
            See the project CLAUDE.md for configuration details.
          </p>
        </div>
      </div>
    </div>
  );
}

function SettingField({
  label,
  description,
  value,
  disabled,
}: {
  label: string;
  description: string;
  value: string;
  disabled?: boolean;
}) {
  return (
    <div>
      <label className="text-sm font-medium text-slate-200">{label}</label>
      <p className="text-xs text-slate-500 mb-1.5">{description}</p>
      <input
        type="text"
        value={value}
        disabled={disabled}
        readOnly
        className="w-full px-3 py-2 text-sm bg-slate-900 border border-slate-700 rounded-lg text-slate-400 disabled:opacity-60"
      />
    </div>
  );
}
