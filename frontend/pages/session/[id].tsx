import { useRouter } from 'next/router';
import Head from 'next/head';
import Link from 'next/link';
import { useSession } from '../../hooks/useSession';
import PhaseTimeline from '../../components/PhaseTimeline';
import DiscussionThread from '../../components/DiscussionThread';
import CostMonitor from '../../components/CostMonitor';

// ------------------------------------------------------------ phase ordering -

const PHASE_ORDER = ['routing', 'research', 'debate', 'vote', 'synthesize'];

function completedPhases(currentPhase: string): string[] {
  const idx = PHASE_ORDER.indexOf(currentPhase.toLowerCase());
  if (idx <= 0) return [];
  return PHASE_ORDER.slice(0, idx);
}

// ---------------------------------------------------------------- component --

export default function SessionPage() {
  const router = useRouter();
  const sessionId = typeof router.query.id === 'string' ? router.query.id : null;

  const {
    phase,
    debateHistory,
    researchResults,
    votes,
    consensus,
    finalReport,
    costSummary,
    isConnected,
    isComplete,
    error,
  } = useSession(sessionId);

  // ---------------------------------------------------------------- render --

  return (
    <>
      <Head>
        <title>Pantheon Session {sessionId ? `— ${sessionId.slice(0, 8)}` : ''}</title>
        <meta name="description" content="Multi-agent collaboration session" />
      </Head>

      <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
        {/* Nav bar */}
        <header className="border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-4 py-3 flex items-center justify-between">
          <Link href="/" className="text-sm font-semibold text-primary-600 dark:text-primary-400 hover:underline">
            ← Pantheon
          </Link>
          <div className="flex items-center gap-2">
            <span
              className={`h-2 w-2 rounded-full ${isConnected ? 'bg-green-400' : 'bg-gray-300 dark:bg-gray-600'}`}
            />
            <span className="text-xs text-gray-500 dark:text-gray-400">
              {isConnected ? 'Live' : isComplete ? 'Complete' : 'Connecting…'}
            </span>
            {sessionId && (
              <span className="ml-2 font-mono text-xs text-gray-400 dark:text-gray-500">
                {sessionId.slice(0, 8)}
              </span>
            )}
          </div>
        </header>

        <main className="max-w-6xl mx-auto px-4 py-6 space-y-6">
          {/* Phase timeline */}
          <section className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-6">
            <PhaseTimeline
              currentPhase={phase}
              completedPhases={completedPhases(phase)}
            />
          </section>

          {/* Error banner */}
          {error && (
            <div className="rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-700 px-4 py-3 text-sm text-red-700 dark:text-red-400">
              {error}
            </div>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Main: discussion */}
            <div className="lg:col-span-2 space-y-6">
              <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-6">
                <h2 className="text-sm font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-4">
                  Agent Discussion
                </h2>
                <DiscussionThread
                  debateHistory={debateHistory}
                  researchResults={researchResults}
                  votes={votes}
                />
              </div>

              {/* Final report */}
              {finalReport && (
                <div className="rounded-xl border border-primary-200 dark:border-primary-700 bg-primary-50 dark:bg-primary-900/20 p-6">
                  <h2 className="text-sm font-semibold text-primary-700 dark:text-primary-300 uppercase tracking-wide mb-3">
                    Final Report
                  </h2>
                  <p className="text-sm text-gray-800 dark:text-gray-200 whitespace-pre-wrap leading-relaxed">
                    {finalReport}
                  </p>
                </div>
              )}

              {/* Consensus */}
              {consensus && !finalReport && (
                <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-6">
                  <h2 className="text-sm font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-3">
                    Consensus
                  </h2>
                  <p className="text-sm text-gray-800 dark:text-gray-200 whitespace-pre-wrap">{consensus}</p>
                </div>
              )}
            </div>

            {/* Sidebar: cost */}
            <aside>
              <CostMonitor costSummary={costSummary} isComplete={isComplete} />
            </aside>
          </div>
        </main>
      </div>
    </>
  );
}
