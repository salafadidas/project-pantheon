import { useEffect, useState, useCallback } from 'react';

// ------------------------------------------------------------------ types ---

export interface ModelHealth {
  status: 'ok' | 'error' | 'timeout' | 'skipped' | 'unknown';
  latency_ms: number | null;
  error: string | null;
}

export interface ModelInfo {
  model_id: string;
  display_name: string;
  provider: string;
  provider_color: string;    // Tailwind colour token, e.g. "amber" | "emerald" | "blue"
  price_input_per_1m: number;
  price_output_per_1m: number;
  context_window_k: number;
  strengths: string[];
  estimated_cost_usd: number;
  estimated_tokens: { input: number; output: number };
  available: boolean;
  health: ModelHealth;
  selectable: boolean;
}

interface ModelSelectorProps {
  /** Called whenever the selection changes. */
  onChange: (selectedIds: string[]) => void;
  /** Disable all controls (e.g. while submitting). */
  disabled?: boolean;
}

// --------------------------------------------------------- helper colours ---

const PROVIDER_BADGE: Record<string, string> = {
  amber:   'bg-amber-100   text-amber-800   dark:bg-amber-900/40  dark:text-amber-300',
  emerald: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300',
  blue:    'bg-blue-100    text-blue-800    dark:bg-blue-900/40   dark:text-blue-300',
  violet:  'bg-violet-100  text-violet-800  dark:bg-violet-900/40 dark:text-violet-300',
};

const CARD_RING: Record<string, string> = {
  amber:   'ring-amber-400',
  emerald: 'ring-emerald-400',
  blue:    'ring-blue-400',
  violet:  'ring-violet-400',
};

function providerBadge(color: string) {
  return PROVIDER_BADGE[color] ?? 'bg-gray-100 text-gray-700';
}

function cardRing(color: string) {
  return CARD_RING[color] ?? 'ring-gray-400';
}

// --------------------------------------------------------- health helpers ---

function healthDot(status: ModelHealth['status']): string {
  switch (status) {
    case 'ok':       return 'bg-green-500';
    case 'error':    return 'bg-red-500';
    case 'timeout':  return 'bg-orange-500';
    case 'skipped':  return 'bg-gray-400';
    case 'unknown':  return 'bg-yellow-400';
    default:         return 'bg-gray-400';
  }
}

function healthLabel(h: ModelHealth, available: boolean): string {
  if (!available) return 'No API key';
  switch (h.status) {
    case 'ok':       return h.latency_ms ? `Healthy (${(h.latency_ms / 1000).toFixed(1)}s)` : 'Healthy';
    case 'error':    return 'Error — auto-skipped';
    case 'timeout':  return 'Timeout — auto-skipped';
    case 'skipped':  return 'No API key';
    case 'unknown':  return 'Not yet checked';
    default:         return 'Unknown';
  }
}

function healthTooltip(h: ModelHealth): string {
  if (h.status === 'ok') return `Probe latency: ${h.latency_ms}ms`;
  if (h.error) return h.error;
  return h.status;
}

// ------------------------------------------------------- cost formatting ---

function formatCost(usd: number): string {
  if (usd < 0.001) return '< $0.001';
  return `~$${usd.toFixed(3)}`;
}

function formatTokens(n: number): string {
  return n >= 1000 ? `${(n / 1000).toFixed(0)}k` : String(n);
}

// ---------------------------------------------------------------- component -

export default function ModelSelector({ onChange, disabled = false }: ModelSelectorProps) {
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [checkedAt, setCheckedAt] = useState<string | null>(null);
  const [warning, setWarning] = useState<string | null>(null);

  const loadCatalog = useCallback(async (preserveSelection: boolean) => {
    try {
      const r = await fetch('/api/models');
      const data: {
        models: ModelInfo[];
        default_selected: string[];
        health_checked_at: string | null;
      } = await r.json();

      setModels(data.models ?? []);
      setCheckedAt(data.health_checked_at ?? null);

      if (preserveSelection) {
        // Keep user picks but auto-drop ones that became unhealthy
        setSelected((prev) => {
          const next = new Set<string>();
          const droppedNames: string[] = [];
          (data.models ?? []).forEach((m) => {
            if (prev.has(m.model_id)) {
              if (m.selectable) next.add(m.model_id);
              else droppedNames.push(m.display_name);
            }
          });
          if (droppedNames.length > 0) {
            setWarning(`Auto-deselected unhealthy: ${droppedNames.join(', ')}`);
          } else {
            setWarning(null);
          }
          onChange(Array.from(next));
          return next;
        });
      } else {
        const defaults = new Set<string>(
          (data.default_selected ?? []).filter((id) =>
            (data.models ?? []).find((m) => m.model_id === id && m.selectable),
          ),
        );
        setSelected(defaults);
        onChange(Array.from(defaults));
        setWarning(null);
      }
    } catch (e) {
      setError('Could not load model list');
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Initial load
  useEffect(() => {
    let cancelled = false;
    loadCatalog(false).finally(() => {
      if (!cancelled) setLoading(false);
    });
    return () => { cancelled = true; };
  }, [loadCatalog]);

  async function handleRefresh() {
    setRefreshing(true);
    try {
      // POST /api/health/refresh → backend POST /health/models/refresh
      await fetch('/api/health/refresh', { method: 'POST' });
      await loadCatalog(true);
    } finally {
      setRefreshing(false);
    }
  }

  function toggle(modelId: string) {
    if (disabled) return;
    const m = models.find((x) => x.model_id === modelId);
    if (!m || !m.selectable) return;

    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(modelId)) {
        if (next.size <= 1) return prev;     // keep ≥1 selected
        next.delete(modelId);
      } else {
        next.add(modelId);
      }
      onChange(Array.from(next));
      return next;
    });
  }

  if (loading) {
    return (
      <div className="py-4 text-sm text-gray-400 dark:text-gray-500 text-center animate-pulse">
        Loading models…
      </div>
    );
  }

  if (error) {
    return <p className="text-sm text-red-500 dark:text-red-400">{error}</p>;
  }

  const okCount   = models.filter((m) => m.health.status === 'ok').length;
  const totalProbed = models.filter(
    (m) => m.available && m.health.status !== 'skipped' && m.health.status !== 'unknown'
  ).length;

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
          AI Models&nbsp;
          <span className="text-gray-400 dark:text-gray-500 font-normal">
            (pick ≥ 1)
          </span>
        </label>
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-400 dark:text-gray-500">
            {okCount}/{totalProbed} healthy · {selected.size} selected
          </span>
          <button
            type="button"
            onClick={handleRefresh}
            disabled={refreshing || disabled}
            className="text-xs px-2 py-1 rounded border border-gray-300 dark:border-gray-600 text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-50"
            title="Re-probe all models (~20s)"
          >
            {refreshing ? '↻ Probing…' : '↻ Refresh status'}
          </button>
        </div>
      </div>

      {warning && (
        <div className="mb-2 text-xs px-3 py-2 rounded bg-yellow-50 dark:bg-yellow-900/30 text-yellow-800 dark:text-yellow-200 border border-yellow-200 dark:border-yellow-700/50">
          ⚠️ {warning}
        </div>
      )}

      {checkedAt && (
        <p className="text-[10px] text-gray-400 dark:text-gray-500 mb-2">
          Health last checked: {new Date(checkedAt).toLocaleTimeString()}
        </p>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {models.map((m) => {
          const isSelected = selected.has(m.model_id);
          const isDisabled = disabled || !m.selectable;

          return (
            <button
              key={m.model_id}
              type="button"
              disabled={isDisabled}
              onClick={() => toggle(m.model_id)}
              title={isDisabled ? healthTooltip(m.health) : undefined}
              className={[
                'relative text-left rounded-xl border p-3 transition-all',
                'focus:outline-none focus:ring-2 focus:ring-offset-1',
                isSelected
                  ? `border-transparent ring-2 ${cardRing(m.provider_color)} bg-white dark:bg-gray-800`
                  : 'border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 hover:border-gray-300 dark:hover:border-gray-600',
                isDisabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer',
              ].join(' ')}
              aria-pressed={isSelected}
            >
              {/* Health dot — top-left corner */}
              <span
                className={`absolute top-2 left-2 w-2 h-2 rounded-full ${healthDot(m.health.status)}`}
                title={healthLabel(m.health, m.available)}
              />

              {/* Provider badge */}
              <span
                className={`inline-block text-[10px] font-semibold px-1.5 py-0.5 rounded-full mb-1.5 ml-4 ${providerBadge(m.provider_color)}`}
              >
                {m.provider}
              </span>

              {/* Model name */}
              <p className="text-sm font-semibold text-gray-900 dark:text-white leading-tight">
                {m.display_name}
              </p>

              {/* Health status row */}
              <p className={`text-[11px] mt-0.5 font-medium ${
                m.health.status === 'ok' ? 'text-green-600 dark:text-green-400' :
                m.health.status === 'unknown' ? 'text-yellow-600 dark:text-yellow-400' :
                'text-red-500 dark:text-red-400'
              }`}>
                {healthLabel(m.health, m.available)}
              </p>

              {/* Strengths */}
              <ul className="mt-1.5 space-y-0.5">
                {m.strengths.map((s) => (
                  <li key={s} className="text-[11px] text-gray-500 dark:text-gray-400 flex gap-1">
                    <span className="mt-[1px] shrink-0">·</span>
                    {s}
                  </li>
                ))}
              </ul>

              {/* Pricing row */}
              <div className="mt-2 pt-2 border-t border-gray-100 dark:border-gray-700 flex items-end justify-between gap-2">
                <div>
                  <p className="text-[10px] text-gray-400 dark:text-gray-500 uppercase tracking-wide font-medium mb-0.5">
                    Est. session cost
                  </p>
                  <p className="text-xs font-semibold text-gray-700 dark:text-gray-300">
                    {formatCost(m.estimated_cost_usd)}
                  </p>
                  <p className="text-[10px] text-gray-400 dark:text-gray-500">
                    {formatTokens(m.estimated_tokens.input)} in ·{' '}
                    {formatTokens(m.estimated_tokens.output)} out
                  </p>
                </div>

                <div className="text-right">
                  <p className="text-[10px] text-gray-400 dark:text-gray-500 uppercase tracking-wide font-medium mb-0.5">
                    Context
                  </p>
                  <p className="text-xs font-semibold text-gray-700 dark:text-gray-300">
                    {m.context_window_k >= 1000
                      ? `${m.context_window_k / 1000}M`
                      : `${m.context_window_k}k`}
                  </p>
                  <p className="text-[10px] text-gray-400 dark:text-gray-500">
                    ${m.price_input_per_1m.toFixed(2)} / ${m.price_output_per_1m.toFixed(2)}
                    &nbsp;per 1M
                  </p>
                </div>
              </div>

              {/* Error detail for unhealthy */}
              {!m.selectable && m.health.error && (
                <p className="mt-1 text-[10px] text-red-400 dark:text-red-500 line-clamp-2">
                  {m.health.error}
                </p>
              )}

              {/* Selected checkmark */}
              {isSelected && (
                <span className="absolute top-2 right-2 w-4 h-4 flex items-center justify-center rounded-full bg-current text-white text-[9px] leading-none"
                  style={{ backgroundColor: 'currentColor' }}
                >
                  <svg viewBox="0 0 12 12" fill="white" className="w-2.5 h-2.5">
                    <path d="M2 6l3 3 5-5" stroke="white" strokeWidth="1.8"
                      strokeLinecap="round" strokeLinejoin="round" fill="none" />
                  </svg>
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Global pricing footnote */}
      <p className="mt-2 text-[11px] text-gray-400 dark:text-gray-500">
        Cost estimates assume ~15k input + ~3k output tokens per session across all phases.
        Prices in USD per 1M tokens (in / out).
      </p>
    </div>
  );
}
