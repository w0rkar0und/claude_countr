import { useStore, type View } from '../store';
import AlertBanner from './AlertBanner';
import CurrentSession from './CurrentSession';
import CostByModelChart from './CostByModelChart';
import ToolUsageChart from './ToolUsageChart';
import ProjectCards from './ProjectCards';
import SessionGrid from './SessionGrid';
import DailyView from './DailyView';
import WeeklyView from './WeeklyView';
import MonthlyView from './MonthlyView';

const TABS: { id: View; label: string }[] = [
  { id: 'current', label: 'Live' },
  { id: 'daily', label: 'Today' },
  { id: 'weekly', label: 'This Week' },
  { id: 'monthly', label: 'This Month' },
];

export default function Dashboard() {
  const activeView = useStore((s) => s.activeView);
  const setView = useStore((s) => s.setView);

  return (
    <div className="flex-1">
      {/* Tab bar */}
      <div className="px-6 pt-4 border-b border-slate-700">
        <nav className="flex gap-1">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setView(tab.id)}
              className={`px-4 py-2 text-sm font-medium rounded-t-lg transition-colors ${
                activeView === tab.id
                  ? 'bg-slate-800 text-white border-b-2 border-indigo-500'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      <AlertBanner />

      {/* View content */}
      {activeView === 'current' && (
        <>
          <CurrentSession />
          <div className="px-6 py-4 grid grid-cols-1 lg:grid-cols-2 gap-4">
            <CostByModelChart />
            <ToolUsageChart />
          </div>
          <ProjectCards />
          <SessionGrid />
        </>
      )}
      {activeView === 'daily' && <DailyView />}
      {activeView === 'weekly' && <WeeklyView />}
      {activeView === 'monthly' && <MonthlyView />}
    </div>
  );
}
