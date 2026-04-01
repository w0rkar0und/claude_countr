import { useStore } from '../store';

const severityStyles = {
  info: 'bg-blue-500/10 border-blue-500/30 text-blue-400',
  warning: 'bg-amber-500/10 border-amber-500/30 text-amber-400',
  critical: 'bg-red-500/10 border-red-500/30 text-red-400',
};

const EMPTY: never[] = [];

export default function AlertBanner() {
  const currentData = useStore((s) => s.currentData);
  const warnings = currentData?.warnings ?? EMPTY;

  if (warnings.length === 0) return null;

  return (
    <div className="flex flex-col gap-2 px-6 pt-4">
      {warnings.map((w, i) => (
        <div
          key={`${w.sessionId}-${i}`}
          className={`flex items-center gap-3 px-4 py-2.5 rounded-lg border ${severityStyles[w.severity]}`}
        >
          <span className="text-sm font-medium">{w.message}</span>
          <span className="text-xs opacity-70 ml-auto">
            {w.sessionId.split('/').pop()}
          </span>
        </div>
      ))}
    </div>
  );
}
