import type { CostSummary } from '../hooks/useSession';

// ------------------------------------------------------------------ types ---

interface CostMonitorProps {
  costSummary: CostSummary;
  isComplete: boolean;
}

// ----------------------------------------------------------- model colours --

const MODEL_BADGE: Record<string, string> = {
  claude: 'bg-purple-100 text-purple-700 dark:bg-purple-800 dark:text-purple-200',
  gpt: 'bg-green-100 text-green-700 dark:bg-green-800 dark:text-green-200',
  gemini: 'bg-blue-100 text-blue-700 dark:bg-blue-800 dark:text-blue-200',
};

function modelBadgeClass(model: string): string {
  const key = model.toLowerCase();
  if (key.includes('claude')) return MODEL_BADGE.claude;
  if (key.includes('gpt')) return MODEL_BADGE.gpt;
  if (key.includes('gemini')) return MODEL_BADGE.gemini;
  return 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300';
}

function formatCost(usd: number): string {
  if (usd < 0.001) return '<$0.001';
  return `$${usd.toFixed(4)}`;
}

// -------------------------------------------------------------- bar chart ---

function CostBar({ label, value, max, badgeClass }: { label: string; value: number; max: number; badgeClass: string }) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0;
  return (
    <div className="flex items-center gap-3">
      <span className={`text-xs font-medium px-2 py-0.5 rounded-full whitespace-nowrap ${badgeClass}`}>
        {label}
      </span>
      <div className="flex-1 bg-gray-200 dark:bg-gray-700 rounded-full h-2">
        <div
          className="bg-primary-500 h-2 rounded-full transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs tabular-nums text-gray-600 dark:text-gray-400 w-16 text-right">
        {formatCost(value)}
      </span>
    </div>
  );
}

// ---------------------------------------------------------------- component -

export default function CostMonitor({ costSummary, isComplete }: CostMonitorProps) {
  const total = costSummary.total_cost_usd ?? 0;
  const byModel = costSummary.by_model ?? {};
  const byPhase = costSummary.by_phase ?? {};

  const maxModel = Math.max(...Object.values(byModel), 0.00001);
  const maxPhase = Math.max(...Object.values(byPhase), 0.00001);

  return (
    <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300 uppercase tracking-wide">
          Cost Monitor
        </h2>
        {isComplete && (
          <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-500 dark:bg-gray-700 dark:text-gray-400">
            Final
          </span>
        )}
      </div>

      {/* Total */}
      <div className="text-center py-2">
        <p className="text-3xl font-bold tabular-nums text-gray-900 dark:text-white">
          {formatCost(total)}
        </p>
        <p className="text-xs text-gray-400 mt-0.5">total USD</p>
      </div>

      {/* By model */}
      {Object.keys(byModel).length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide">
            By Model
          </p>
          {Object.entries(byModel).map(([model, cost]) => (
            <CostBar
              key={model}
              label={model}
              value={cost}
              max={maxModel}
              badgeClass={modelBadgeClass(model)}
            />
          ))}
        </div>
      )}

      {/* By phase */}
      {Object.keys(byPhase).length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide">
            By Phase
          </p>
          {Object.entries(byPhase).map(([phase, cost]) => (
            <CostBar
              key={phase}
              label={phase}
              value={cost}
              max={maxPhase}
              badgeClass="bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300"
            />
          ))}
        </div>
      )}

      {total === 0 && (
        <p className="text-xs text-center text-gray-400 dark:text-gray-500">
          Cost data will appear as the session runs.
        </p>
      )}
    </div>
  );
}
