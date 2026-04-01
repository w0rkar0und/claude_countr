import { useEffect } from 'react';
import { useStore } from './store';
import Header from './components/Header';
import Dashboard from './components/Dashboard';
import SettingsModal from './components/SettingsModal';

export default function App() {
  const darkMode = useStore((s) => s.darkMode);
  const fetchCurrentData = useStore((s) => s.fetchCurrentData);
  const fetchDateRange = useStore((s) => s.fetchDateRange);
  const fetchDailyData = useStore((s) => s.fetchDailyData);
  const fetchAlerts = useStore((s) => s.fetchAlerts);
  const initWebSocket = useStore((s) => s.initWebSocket);

  useEffect(() => {
    async function init() {
      await fetchDateRange();
      fetchCurrentData();
      fetchDailyData();
      fetchAlerts();
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
