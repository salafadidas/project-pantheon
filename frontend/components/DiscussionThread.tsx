import React from 'react';
import type { DebateEntry } from '../hooks/useSession';

// Detect quota-exhausted / error placeholder text produced by the backend
function isSkippedEntry(content: string): boolean {
  return (
    content.startsWith('⚠️') ||
    content.startsWith('[ERROR') ||
    content.startsWith('[TIMEOUT') ||
    content.startsWith('[QUOTA')
  );
}

// ------------------------------------------------------------------ types ---

interface DiscussionThreadProps {
  debateHistory: DebateEntry[];
  researchResults: Record<string, string>;
  votes: Record<string, string>;
}

// ----------------------------------------------------------- model colours --

const MODEL_STYLES: Record<string, { bg: string; border: string; badge: string; label: string }> = {
  claude: {
    bg: 'bg-purple-50 dark:bg-purple-900/20',
    border: 'border-purple-200 dark:border-purple-700',
    badge: 'bg-purple-100 text-purple-700 dark:bg-purple-800 dark:text-purple-200',
    label: 'Claude',
  },
  gpt: {
    bg: 'bg-green-50 dark:bg-green-900/20',
    border: 'border-green-200 dark:border-green-700',
    badge: 'bg-green-100 text-green-700 dark:bg-green-800 dark:text-green-200',
    label: 'GPT-4o',
  },
  gemini: {
    bg: 'bg-blue-50 dark:bg-blue-900/20',
    border: 'border-blue-200 dark:border-blue-700',
    badge: 'bg-blue-100 text-blue-700 dark:bg-blue-800 dark:text-blue-200',
    label: 'Gemini',
  },
  deepseek: {
    bg: 'bg-violet-50 dark:bg-violet-900/20',
    border: 'border-violet-200 dark:border-violet-700',
    badge: 'bg-violet-100 text-violet-700 dark:bg-violet-800 dark:text-violet-200',
    label: 'DeepSeek V3',
  },
  kimi: {
    bg: 'bg-violet-50 dark:bg-violet-900/20',
    border: 'border-violet-200 dark:border-violet-700',
    badge: 'bg-violet-100 text-violet-700 dark:bg-violet-800 dark:text-violet-200',
    label: 'Kimi K2.5',
  },
};

const DEFAULT_STYLE = {
  bg: 'bg-gray-50 dark:bg-gray-800',
  border: 'border-gray-200 dark:border-gray-700',
  badge: 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300',
  label: '',
};

function resolveStyle(model: string) {
  const key = model.toLowerCase();
  if (key.includes('claude')) return MODEL_STYLES.claude;
  if (key.includes('gpt') || key.includes('o3') || key.includes('o4')) return MODEL_STYLES.gpt;
  if (key.includes('gemini')) return MODEL_STYLES.gemini;
  if (key.includes('deepseek')) return MODEL_STYLES.deepseek;
  if (key.includes('kimi')) return MODEL_STYLES.kimi;
  return { ...DEFAULT_STYLE, label: model };
}

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  } catch {
    return '';
  }
}

// ------------------------------------------------------- sub-components ----

function ResearchSection({ results }: { results: Record<string, string> }) {
  const entries = Object.entries(results);
  if (entries.length === 0) return null;

  return (
    <div className="mb-6">
      <h3 className="text-sm font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-3">
        Research Results
      </h3>
      <div className="space-y-3">
        {entries.map(([model, content]) => {
          if (isSkippedEntry(content)) {
            return (
              <div
                key={model}
                className="rounded-lg border border-amber-200 dark:border-amber-700 bg-amber-50 dark:bg-amber-900/20 px-3 py-2 flex items-start gap-2"
              >
                <span className="text-amber-500 mt-0.5 shrink-0" aria-hidden>⚠️</span>
                <div>
                  <span className="text-xs font-semibold text-amber-700 dark:text-amber-300">
                    {model} — skipped
                  </span>
                  <p className="text-xs text-amber-600 dark:text-amber-400 mt-0.5 whitespace-pre-wrap">
                    {content.replace(/^⚠️\s*/, '')}
                  </p>
                </div>
              </div>
            );
          }
          const style = resolveStyle(model);
          return (
            <div
              key={model}
              className={`rounded-lg border p-3 ${style.bg} ${style.border}`}
            >
              <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${style.badge}`}>
                {style.label || model}
              </span>
              <p className="mt-2 text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap">{content}</p>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function VotingSection({ votes }: { votes: Record<string, string> }) {
  const entries = Object.entries(votes);
  if (entries.length === 0) return null;

  return (
    <div className="mb-6">
      <h3 className="text-sm font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-3">
        Voting Results
      </h3>
      <div className="flex flex-wrap gap-2">
        {entries.map(([model, vote]) => {
          const style = resolveStyle(model);
          return (
            <div
              key={model}
              className={`flex items-center gap-2 rounded-lg border px-3 py-2 ${style.bg} ${style.border}`}
            >
              <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${style.badge}`}>
                {style.label || model}
              </span>
              <span className="text-sm text-gray-700 dark:text-gray-300">{vote}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- component -

export default function DiscussionThread({
  debateHistory,
  researchResults,
  votes,
}: DiscussionThreadProps) {
  const hasResearch = Object.keys(researchResults).length > 0;
  const hasVotes = Object.keys(votes).length > 0;
  const hasDebate = debateHistory.length > 0;

  if (!hasResearch && !hasDebate && !hasVotes) {
    return (
      <div className="text-center py-8 text-gray-400 dark:text-gray-500 text-sm">
        Discussion will appear here as agents work through the phases…
      </div>
    );
  }

  // Group debate entries by round
  const rounds = debateHistory.reduce<Record<number, DebateEntry[]>>((acc, entry) => {
    const r = entry.round ?? 0;
    if (!acc[r]) acc[r] = [];
    acc[r].push(entry);
    return acc;
  }, {});

  return (
    <div className="space-y-2">
      <ResearchSection results={researchResults} />

      {Object.entries(rounds).map(([round, entries]) => (
        <div key={round} className="mb-6">
          <h3 className="text-sm font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-3">
            Debate — Round {round}
          </h3>
          <div className="space-y-3">
            {entries.map((entry, i) => {
              const skipped = isSkippedEntry(entry.content);
              if (skipped) {
                // Render quota/error entries as a compact warning notice
                return (
                  <div
                    key={i}
                    className="rounded-lg border border-amber-200 dark:border-amber-700 bg-amber-50 dark:bg-amber-900/20 px-3 py-2 flex items-start gap-2"
                  >
                    <span className="text-amber-500 mt-0.5 shrink-0" aria-hidden>⚠️</span>
                    <div>
                      <span className="text-xs font-semibold text-amber-700 dark:text-amber-300">
                        {entry.model} — skipped
                      </span>
                      <p className="text-xs text-amber-600 dark:text-amber-400 mt-0.5 whitespace-pre-wrap">
                        {entry.content.replace(/^⚠️\s*/, '')}
                      </p>
                    </div>
                  </div>
                );
              }

              const style = resolveStyle(entry.model);
              return (
                <div
                  key={i}
                  className={`rounded-lg border p-3 ${style.bg} ${style.border}`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${style.badge}`}>
                        {style.label || entry.model}
                      </span>
                      {entry.modelRequested && (
                        <span
                          className="text-xs text-gray-400 dark:text-gray-500 italic"
                          title={`Originally requested: ${entry.modelRequested}`}
                        >
                          (fallback for {entry.modelRequested})
                        </span>
                      )}
                    </div>
                    <span className="text-xs text-gray-400 dark:text-gray-500 shrink-0 ml-2">
                      {formatTime(entry.timestamp)}
                    </span>
                  </div>
                  <p className="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap">
                    {entry.content}
                  </p>
                </div>
              );
            })}
          </div>
        </div>
      ))}

      <VotingSection votes={votes} />
    </div>
  );
}
