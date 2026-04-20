import { useCallback, useEffect, useRef, useState } from 'react';

// ------------------------------------------------------------------ types ---

export interface DebateEntry {
  round: number;
  model: string;
  content: string;
  timestamp: string;
}

export interface CostSummary {
  total_cost_usd?: number;
  by_model?: Record<string, number>;
  by_phase?: Record<string, number>;
}

export interface SessionState {
  phase: string;
  debateHistory: DebateEntry[];
  researchResults: Record<string, string>;
  votes: Record<string, string>;
  consensus: string | null;
  finalReport: string | null;
  costSummary: CostSummary;
  isConnected: boolean;
  isComplete: boolean;
  error: string | null;
}

// --------------------------------------------------------------- constants --

const WS_BASE =
  typeof window !== 'undefined'
    ? `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${
        process.env.NEXT_PUBLIC_API_HOST || window.location.hostname + ':8000'
      }`
    : 'ws://localhost:8000';

const RECONNECT_DELAY_MS = 3000;
const MAX_RECONNECTS = 5;

// ------------------------------------------------------------------- hook ---

export function useSession(sessionId: string | null): SessionState {
  const [state, setState] = useState<SessionState>({
    phase: '',
    debateHistory: [],
    researchResults: {},
    votes: {},
    consensus: null,
    finalReport: null,
    costSummary: {},
    isConnected: false,
    isComplete: false,
    error: null,
  });

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectCount = useRef(0);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);

  const connect = useCallback(() => {
    if (!sessionId || !mountedRef.current) return;

    const url = `${WS_BASE}/api/v1/sessions/${sessionId}/stream`;
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      if (!mountedRef.current) return;
      reconnectCount.current = 0;
      setState((s) => ({ ...s, isConnected: true, error: null }));
    };

    ws.onmessage = (evt) => {
      if (!mountedRef.current) return;
      try {
        const event = JSON.parse(evt.data as string);
        handleEvent(event);
      } catch {
        // ignore malformed messages
      }
    };

    ws.onerror = () => {
      if (!mountedRef.current) return;
      setState((s) => ({ ...s, isConnected: false }));
    };

    ws.onclose = () => {
      if (!mountedRef.current) return;
      setState((s) => ({ ...s, isConnected: false }));
      scheduleReconnect();
    };
  }, [sessionId]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleEvent = useCallback((event: Record<string, unknown>) => {
    const type = event.event as string;

    if (type === 'phase_complete') {
      const phase = event.phase as string;
      const data = (event.data ?? {}) as Record<string, unknown>;

      setState((s) => {
        const next = { ...s, phase };
        if (data.research_results)
          next.researchResults = data.research_results as Record<string, string>;
        if (data.debate_round !== undefined) {
          // debateHistory is accumulated via model_response events; nothing extra here
        }
        if (data.votes) next.votes = data.votes as Record<string, string>;
        if (data.consensus !== undefined) next.consensus = data.consensus as string | null;
        return next;
      });
    } else if (type === 'model_response') {
      const entry: DebateEntry = {
        round: (event.round as number) ?? 0,
        model: (event.model as string) ?? '',
        content: (event.content as string) ?? '',
        timestamp: (event.timestamp as string) ?? new Date().toISOString(),
      };
      setState((s) => ({ ...s, debateHistory: [...s.debateHistory, entry] }));
    } else if (type === 'session_complete') {
      setState((s) => ({
        ...s,
        phase: 'complete',
        finalReport: (event.final_report as string) ?? null,
        isComplete: true,
      }));
    } else if (type === 'session_error') {
      setState((s) => ({
        ...s,
        error: (event.error as string) ?? 'Unknown error',
        isComplete: true,
      }));
    } else if (type === 'session_cancelled') {
      setState((s) => ({ ...s, phase: 'cancelled', isComplete: true }));
    }
  }, []);

  const scheduleReconnect = useCallback(() => {
    if (reconnectCount.current >= MAX_RECONNECTS) return;
    reconnectCount.current += 1;
    reconnectTimer.current = setTimeout(() => {
      if (mountedRef.current) connect();
    }, RECONNECT_DELAY_MS);
  }, [connect]);

  useEffect(() => {
    mountedRef.current = true;
    connect();
    return () => {
      mountedRef.current = false;
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [connect]);

  return state;
}
