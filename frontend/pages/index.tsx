import Head from 'next/head';
import TaskSubmit from '../components/TaskSubmit';

export default function Home() {
  return (
    <>
      <Head>
        <title>Project Pantheon</title>
        <meta name="description" content="Multi-AI-agent collaboration: Claude × GPT-4o × Gemini" />
        <link rel="icon" href="/favicon.ico" />
      </Head>

      <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
        <header className="border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-6 py-4">
          <h1 className="text-xl font-bold text-gray-900 dark:text-white">
            Project Pantheon
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
            Multi-agent collaboration · Claude × GPT-4o × Gemini
          </p>
        </header>

        <main className="max-w-2xl mx-auto px-4 py-12 space-y-8">
          {/* Flow diagram */}
          <section className="text-center space-y-2">
            <div className="flex items-center justify-center gap-2 text-sm text-gray-600 dark:text-gray-400 flex-wrap">
              {[
                { icon: '🧭', label: 'Route' },
                { icon: '🔬', label: 'Research' },
                { icon: '💬', label: 'Debate' },
                { icon: '🗳️', label: 'Vote' },
                { icon: '📝', label: 'Synthesize' },
              ].map((phase, i, arr) => (
                <span key={phase.label} className="flex items-center gap-2">
                  <span className="flex items-center gap-1 px-3 py-1 rounded-full bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 font-medium">
                    {phase.icon} {phase.label}
                  </span>
                  {i < arr.length - 1 && (
                    <span className="text-gray-400">→</span>
                  )}
                </span>
              ))}
            </div>
            <p className="text-xs text-gray-400 dark:text-gray-500">
              Three AI models collaborate, debate, and reach consensus on your task.
            </p>
          </section>

          {/* Submission form */}
          <TaskSubmit />
        </main>

        <footer className="py-6 text-center text-xs text-gray-400 dark:text-gray-600">
          Project Pantheon — Stage 1 PoC
        </footer>
      </div>
    </>
  );
}
