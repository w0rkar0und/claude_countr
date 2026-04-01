import { useEffect } from 'react';
import { useStore } from './store';
import Header from './components/Header';
import Dashboard from './components/Dashboard';
import SettingsModal from './components/SettingsModal';

export default function App() {
  const darkMode = useStore((s) => s.darkMode);
  const fetchCurrentData = useStore((s) => s.fetchCurrentData);
  const fetchDateRange = useStore((s) => s.fetchDateRange);
  const fetchAlerts = useStore((s) => s.fetchAlerts);
  const initWebSocket = useStore((s) => s.initWebSocket);
  const setView = useStore((s) => s.setView);

  useEffect(() => {
    async function init() {
      await fetchDateRange();
      await fetchCurrentData();
      fetchAlerts();
      // Default to "Today" view if no active sessions
      const state = useStore.getState();
      if (!state.currentData || state.currentData.sessions.length === 0) {
        setView('daily');
      }
    }
    init();
    const disconnect = initWebSocket();
    return disconnect;
  }, []);

  return (
    <div className={darkMode ? 'dark' : ''}>
      <div className="min-h-screen bg-slate-900 text-slate-200 flex flex-col">
        <Header />
        <Dashboard />
        <SettingsModal />
      </div>
    </div>
  );
}
