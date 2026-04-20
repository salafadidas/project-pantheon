import React from 'react';

// ------------------------------------------------------------------ types ---

interface PhaseTimelineProps {
  currentPhase: string;
  completedPhases: string[];
  phaseTimes?: Record<string, number>; // seconds per phase
}

// ------------------------------------------------------------ phase config --

const PHASES = [
  { key: 'routing', label: 'PM Router', icon: '🧭' },
  { key: 'research', label: 'Research', icon: '🔬' },
  { key: 'debate', label: 'Debate', icon: '💬' },
  { key: 'voting', label: 'Vote', icon: '🗳️' },
  { key: 'synthesis', label: 'Synthesize', icon: '📝' },
];

function formatSeconds(s: number): string {
  if (s < 60) return `${s}s`;
  return `${Math.floor(s / 60)}m ${s % 60}s`;
}

// ---------------------------------------------------------------- component -

export default function PhaseTimeline({
  currentPhase,
  completedPhases,
  phaseTimes = {},
}: PhaseTimelineProps) {
  const isComplete = currentPhase === 'complete';

  return (
    <div className="w-full">
      <div className="flex items-center justify-between relative">
        {/* connector line */}
        <div className="absolute top-5 left-0 right-0 h-0.5 bg-gray-200 dark:bg-gray-700 z-0" />

        {PHASES.map((phase, idx) => {
          const done = completedPhases.includes(phase.key) || isComplete;
          const active = currentPhase === phase.key;
          const elapsed = phaseTimes[phase.key];

          return (
            <div key={phase.key} className="flex flex-col items-center z-10 flex-1">
              {/* circle */}
              <div
                className={[
                  'w-10 h-10 rounded-full flex items-center justify-center text-lg border-2 transition-all duration-500',
                  done
                    ? 'bg-green-500 border-green-500 text-white'
                    : active
                    ? 'bg-blue-500 border-blue-500 text-white animate-pulse'
                    : 'bg-white dark:bg-gray-800 border-gray-300 dark:border-gray-600 text-gray-400',
                ].join(' ')}
              >
                {done ? '✓' : phase.icon}
              </div>

              {/* label */}
              <span
                className={[
                  'mt-2 text-xs font-medium text-center',
                  done
                    ? 'text-green-600 dark:text-green-400'
                    : active
                    ? 'text-blue-600 dark:text-blue-400'
                    : 'text-gray-400 dark:text-gray-500',
                ].join(' ')}
              >
                {phase.label}
              </span>

              {/* elapsed time */}
              {elapsed !== undefined && (
                <span className="mt-0.5 text-xs text-gray-400 dark:text-gray-500">
                  {formatSeconds(elapsed)}
                </span>
              )}

              {/* connector segment (hide last) */}
              {idx < PHASES.length - 1 && (
                <div
                  className={[
                    'absolute h-0.5 transition-all duration-700',
                    done ? 'bg-green-400' : 'bg-transparent',
                  ].join(' ')}
                  style={{
                    left: `${(idx / (PHASES.length - 1)) * 100}%`,
                    width: `${(1 / (PHASES.length - 1)) * 100}%`,
                    top: '20px',
                  }}
                />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
