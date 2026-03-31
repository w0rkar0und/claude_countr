import { create } from 'zustand';
import {
  api,
  connectWebSocket,
  type CurrentData,
  type DailyData,
  type WeeklyData,
  type MonthlyData,
  type Alert,
} from './api/client';

export type View = 'current' | 'daily' | 'weekly' | 'monthly';

interface DashboardState {
  // Data
  currentData: CurrentData | null;
  dailyData: DailyData | null;
  weeklyData: WeeklyData | null;
  monthlyData: MonthlyData | null;
  alerts: Alert[];

  // UI
  activeView: View;
  lastUpdate: string | null;
  isLoading: boolean;
  error: string | null;
  wsConnected: boolean;
  settingsOpen: boolean;
  darkMode: boolean;

  // Actions
  setView: (view: View) => void;
  setSettingsOpen: (open: boolean) => void;
  toggleDarkMode: () => void;
  fetchCurrentData: () => Promise<void>;
  fetchDailyData: (date?: string) => Promise<void>;
  fetchWeeklyData: (start?: string, end?: string) => Promise<void>;
  fetchMonthlyData: (month?: string) => Promise<void>;
  fetchAlerts: () => Promise<void>;
  refreshAll: () => Promise<void>;
  initWebSocket: () => () => void;
}

export const useStore = create<DashboardState>((set, get) => ({
  currentData: null,
  dailyData: null,
  weeklyData: null,
  monthlyData: null,
  alerts: [],

  activeView: 'current',
  lastUpdate: null,
  isLoading: false,
  error: null,
  wsConnected: false,
  settingsOpen: false,
  darkMode: true,

  setView: (view) => {
    set({ activeView: view });
    // Auto-fetch data for the view
    const s = get();
    if (view === 'current') s.fetchCurrentData();
    else if (view === 'daily') s.fetchDailyData();
    else if (view === 'weekly') s.fetchWeeklyData();
    else if (view === 'monthly') s.fetchMonthlyData();
  },

  setSettingsOpen: (open) => set({ settingsOpen: open }),

  toggleDarkMode: () => set((s) => ({ darkMode: !s.darkMode })),

  fetchCurrentData: async () => {
    try {
      set({ isLoading: true, error: null });
      const data = await api.getCurrent();
      set({ currentData: data, lastUpdate: data.lastUpdate, isLoading: false });
    } catch (e: any) {
      set({ error: e.message, isLoading: false });
    }
  },

  fetchDailyData: async (date?: string) => {
    try {
      set({ isLoading: true, error: null });
      const data = await api.getDaily(date);
      set({ dailyData: data, isLoading: false });
    } catch (e: any) {
      set({ error: e.message, isLoading: false });
    }
  },

  fetchWeeklyData: async (start?: string, end?: string) => {
    try {
      set({ isLoading: true, error: null });
      const data = await api.getWeekly(start, end);
      set({ weeklyData: data, isLoading: false });
    } catch (e: any) {
      set({ error: e.message, isLoading: false });
    }
  },

  fetchMonthlyData: async (month?: string) => {
    try {
      set({ isLoading: true, error: null });
      const data = await api.getMonthly(month);
      set({ monthlyData: data, isLoading: false });
    } catch (e: any) {
      set({ error: e.message, isLoading: false });
    }
  },

  fetchAlerts: async () => {
    try {
      const alerts = await api.getAlerts();
      set({ alerts });
    } catch { /* silent */ }
  },

  refreshAll: async () => {
    try {
      set({ isLoading: true, error: null });
      await api.refresh();
      const s = get();
      await s.fetchCurrentData();
      if (s.activeView === 'daily') await s.fetchDailyData();
      if (s.activeView === 'weekly') await s.fetchWeeklyData();
      if (s.activeView === 'monthly') await s.fetchMonthlyData();
      await s.fetchAlerts();
      set({ isLoading: false });
    } catch (e: any) {
      set({ error: e.message, isLoading: false });
    }
  },

  initWebSocket: () => {
    const disconnect = connectWebSocket(
      (msg) => {
        if (msg.event === 'update' && msg.data) {
          set({
            currentData: msg.data,
            lastUpdate: msg.timestamp,
          });
        }
      },
      (connected) => {
        set({ wsConnected: connected });
      },
    );
    return disconnect;
  },
}));
