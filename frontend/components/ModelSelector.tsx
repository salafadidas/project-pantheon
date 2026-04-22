import { useEffect, useState } from 'react';

// ------------------------------------------------------------------ types ---

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
};

const CARD_RING: Record<string, string> = {
  amber:   'ring-amber-400',
  emerald: 'ring-emerald-400',
  blue:    'ring-blue-400',
};

function providerBadge(color: string) {
  return PROVIDER_BADGE[color] ?? 'bg-gray-100 text-gray-700';
}

function cardRing(color: string) {
  return CARD_RING[color] ?? 'ring-gray-400';
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
  const [error, setError] = useState<string | null>(null);

  // Fetch model catalog on mount
  useEffect(() => {
    let cancelled = false;
    fetch('/api/models')
      .then((r) => r.json())
      .then((data: { models: ModelInfo[]; default_selected: string[] }) => {
        if (cancelled) return;
        setModels(data.models ?? []);
        const defaults = new Set<string>(
          (data.default_selected ?? []).filter((id) =>
            (data.models ?? []).find((m) => m.model_id === id && m.available),
          ),
        );
        setSelected(defaults);
        onChange(Array.from(defaults));
      })
      .catch(() => {
        if (!cancelled) setError('Could not load model list');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function toggle(modelId: string) {
    if (disabled) return;
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(modelId)) {
        // Must keep at least 1 selected
        if (next.size <= 1) return prev;
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
    return (
      <p className="text-sm text-red-500 dark:text-red-400">{error}</p>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
          AI Models&nbsp;
          <span className="text-gray-400 dark:text-gray-500 font-normal">
            (pick ≥ 1)
          </span>
        </label>
        <span className="text-xs text-gray-400 dark:text-gray-500">
          {selected.size} selected
        </span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {models.map((m) => {
          const isSelected = selected.has(m.model_id);
          const isDisabled = disabled || !m.available;

          return (
            <button
              key={m.model_id}
              type="button"
              disabled={isDisabled}
              onClick={() => toggle(m.model_id)}
              className={[
                'relative text-left rounded-xl border p-3 transition-all',
                'focus:outline-none focus:ring-2 focus:ring-offset-1',
                isSelected
                  ? `border-transparent ring-2 ${cardRing(m.provider_color)} bg-white dark:bg-gray-800`
                  : 'border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 hover:border-gray-300 dark:hover:border-gray-600',
                isDisabled ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer',
              ].join(' ')}
              aria-pressed={isSelected}
            >
              {/* Provider badge */}
              <span
                className={`inline-block text-[10px] font-semibold px-1.5 py-0.5 rounded-full mb-1.5 ${providerBadge(m.provider_color)}`}
              >
                {m.provider}
              </span>

              {/* Model name */}
              <p className="text-sm font-semibold text-gray-900 dark:text-white leading-tight">
                {m.display_name}
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

              {/* Unavailable overlay hint */}
              {!m.available && (
                <p className="mt-1 text-[10px] text-red-400 dark:text-red-500">
                  API key not configured
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
