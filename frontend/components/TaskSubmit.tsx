import { useState, type FormEvent } from 'react';
import { useRouter } from 'next/router';
import ModelSelector from './ModelSelector';

// ------------------------------------------------------------------ types ---

interface TaskSubmitProps {
  /** Called after a session is successfully created; receives the new session ID. */
  onSessionCreated?: (sessionId: string) => void;
}

interface CreateSessionResponse {
  session_id: string;
}

// --------------------------------------------------------------- examples ---

const EXAMPLE_TASKS = [
  'Compare the top 3 open-source LLM frameworks for production use.',
  'What are the key trade-offs between microservices and monolithic architectures?',
  'Summarise the latest research on RAG (Retrieval-Augmented Generation).',
];

// ---------------------------------------------------------------- component -

export default function TaskSubmit({ onSessionCreated }: TaskSubmitProps) {
  const router = useRouter();
  const [task, setTask] = useState('');
  const [selectedModels, setSelectedModels] = useState<string[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const trimmed = task.trim();
    if (!trimmed) return;
    if (selectedModels.length === 0) {
      setError('Please select at least one AI model.');
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      // 1. Create session (no body required)
      const createRes = await fetch('/api/v1/sessions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });

      if (!createRes.ok) {
        const body = (await createRes.json().catch(() => ({}))) as { detail?: string };
        throw new Error(body.detail ?? `Server error ${createRes.status}`);
      }

      const { session_id: sessionId } = (await createRes.json()) as CreateSessionResponse;

      // 2. Start session with task + selected models
      const startRes = await fetch(`/api/v1/sessions/${sessionId}/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          task: trimmed,
          user_id: 'web',
          selected_models: selectedModels,
        }),
      });

      if (!startRes.ok) {
        const body = (await startRes.json().catch(() => ({}))) as { detail?: string };
        throw new Error(body.detail ?? `Server error ${startRes.status}`);
      }

      if (onSessionCreated) {
        onSessionCreated(sessionId);
      } else {
        await router.push(`/session/${sessionId}`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create session');
      setIsSubmitting(false);
    }
  }

  return (
    <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-6">
      <h2 className="text-lg font-semibold text-gray-800 dark:text-white mb-4">
        Submit a Task to Pantheon
      </h2>

      <form onSubmit={handleSubmit} className="space-y-5">
        {/* ── Task input ─────────────────────────────────────────────────── */}
        <div>
          <label
            htmlFor="task-input"
            className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
          >
            Task description
          </label>
          <textarea
            id="task-input"
            rows={4}
            value={task}
            onChange={(e) => setTask(e.target.value)}
            disabled={isSubmitting}
            placeholder="Describe what you want the multi-agent system to research and debate…"
            className="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700
                       text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500
                       px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500
                       disabled:opacity-50 resize-none"
          />
        </div>

        {/* ── Example chips ──────────────────────────────────────────────── */}
        <div className="flex flex-wrap gap-2">
          {EXAMPLE_TASKS.map((ex) => (
            <button
              key={ex}
              type="button"
              disabled={isSubmitting}
              onClick={() => setTask(ex)}
              className="text-xs px-2 py-1 rounded-full border border-gray-300 dark:border-gray-600
                         text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700
                         transition-colors disabled:opacity-40 text-left"
            >
              {ex.length > 50 ? ex.slice(0, 50) + '…' : ex}
            </button>
          ))}
        </div>

        {/* ── Model selector ─────────────────────────────────────────────── */}
        <ModelSelector onChange={setSelectedModels} disabled={isSubmitting} />

        {/* ── Error message ──────────────────────────────────────────────── */}
        {error && (
          <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
        )}

        {/* ── Submit ─────────────────────────────────────────────────────── */}
        <button
          type="submit"
          disabled={isSubmitting || !task.trim() || selectedModels.length === 0}
          className="w-full py-2.5 px-4 rounded-lg font-semibold text-sm text-white
                     bg-primary-600 hover:bg-primary-700 active:bg-primary-800
                     disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {isSubmitting ? (
            <span className="flex items-center justify-center gap-2">
              <svg className="animate-spin h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
              </svg>
              Creating session…
            </span>
          ) : (
            `Launch Pantheon Session · ${selectedModels.length} model${selectedModels.length !== 1 ? 's' : ''}`
          )}
        </button>
      </form>
    </div>
  );
}
