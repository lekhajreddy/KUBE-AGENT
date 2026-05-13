import { create } from 'zustand';
import { Subject, throttleTime } from 'rxjs';
import {
  WSPayload, ServiceMetrics, AnomalyData, RCAResult,
  ClusterSummary, Topology, CorrelationData, HealthScore,
  ExhaustionPrediction,
} from '@/types';

interface KubeMindState {
  // WebSocket
  wsStatus: 'connecting' | 'open' | 'closed';
  lastTs: string;
  token: string | null;

  // Data
  summary: ClusterSummary | null;
  metrics: ServiceMetrics[];
  anomalies: AnomalyData[];
  rca: RCAResult[];
  topology: Topology;
  correlationIntelligence?: CorrelationData;
  healthScore?: HealthScore;
  exhaustionPredictions: ExhaustionPrediction[];

  // Event stream (RxJS)
  event$: Subject<WSPayload>;

  // Actions
  setWsStatus: (status: 'connecting' | 'open' | 'closed') => void;
  setToken: (token: string | null) => void;
  updateFromPayload: (payload: WSPayload) => void;
  setLastTs: (ts: string) => void;
}

export const useKubeMindStore = create<KubeMindState>((set, get) => ({
  wsStatus: 'connecting',
  lastTs: '',
  token: typeof window !== 'undefined' ? localStorage.getItem('kubemind_token') : null,

  summary: null,
  metrics: [],
  anomalies: [],
  rca: [],
  topology: { nodes: [], links: [] },
  correlationIntelligence: undefined,
  healthScore: undefined,
  exhaustionPredictions: [],

  event$: new Subject<WSPayload>(),

  setWsStatus: (status) => set({ wsStatus: status }),

  setToken: (token) => {
    if (token) {
      localStorage.setItem('kubemind_token', token);
    } else {
      localStorage.removeItem('kubemind_token');
    }
    set({ token });
  },

  updateFromPayload: (payload) => {
    set({
      summary: payload.summary ?? null,
      metrics: payload.metrics ?? [],
      anomalies: payload.anomalies ?? [],
      rca: payload.rca ?? [],
      topology: payload.topology ?? { nodes: [], links: [] },
      correlationIntelligence: payload.correlation_intelligence,
      healthScore: payload.health_score,
      exhaustionPredictions: payload.exhaustion_predictions ?? [],
      lastTs: payload.ts,
    });
    get().event$.next(payload);
  },

  setLastTs: (ts) => set({ lastTs: ts }),
}));

// RxJS stream for event-driven side effects
export const eventStream = useKubeMindStore.getState().event$.pipe(
  throttleTime(100)
);
