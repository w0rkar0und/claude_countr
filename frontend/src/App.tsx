import { useEffect } from 'react';
import { useShallow } from 'zustand/react/shallow';
import { useStore } from './store';
import Header from './components/Header';
import Dashboard from './components/Dashboard';
import SettingsModal from './components/SettingsModal';

export default function App() {
  const darkMode = useStore((s) => s.darkMode);
  const { fetchCurrentData, fetchDailyData, fetchAlerts, initWebSocket } = useStore(
    useShallow((s) => ({
      fetchCurrentData: s.fetchCurrentData,
      fetchDailyData: s.fetchDailyData,
      fetchAlerts: s.fetchAlerts,
      initWebSocket: s.initWebSocket,
    }))
  );

  useEffect(() => {
    fetchCurrentData();
    fetchDailyData();
    fetchAlerts();
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
