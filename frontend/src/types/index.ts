// KubeMind — Extended TypeScript types (Production Edition)

export type Severity = 'normal' | 'warning' | 'critical';
export type RiskLevel = 'low' | 'medium' | 'high' | 'critical';
export type ClusterHealth = 'Healthy' | 'Degraded' | 'Critical' | 'Unknown';
export type FaultType = 'cpu_spike' | 'memory_leak' | 'restart_loop' | 'network_congestion' | 'storage_overload';
export type UserRole = 'admin' | 'operator' | 'viewer';

// ── Auth ─────────────────────────────────────────────────────────────────────
export interface User {
  id: string;
  email: string;
  name: string;
  role: UserRole;
  org_id: string;
}

export interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  loading: boolean;
}

// ── Cluster ──────────────────────────────────────────────────────────────────
export interface ClusterInfo {
  cluster_id: string;
  name: string;
  provider: string;
  connected: boolean;
  agent_connected: boolean;
  agent_version: string;
  is_healthy: boolean;
  last_heartbeat: string | null;
  error: string;
}

export interface ClusterRegistration {
  cluster_id: string;
  api_key: string;
  name: string;
  install_command: string;
  status: string;
}

// ── AI Agent Insights ────────────────────────────────────────────────────────
export interface AIAgentInsight {
  agent: string;
  type: string;
  severity: Severity;
  service: string;
  namespace: string;
  message: string;
  value?: number;
  threshold?: number;
  affected_services?: string[];
  node?: string;
}

// ── Existing types (preserved) ───────────────────────────────────────────────
export interface K8sEvent {
  namespace: string; name: string; reason: string; message: string;
  involved_object: string; involved_kind: string; count: number;
  first_time: string; last_time: string;
}

export interface ThresholdViolation {
  metric: string; type: string; value: number; threshold: number; severity: Severity;
}

export interface AnomalyData {
  service: string; timestamp: string; is_anomaly: boolean; anomaly_score: number;
  confidence: number; severity: Severity; anomaly_types: string[];
  detection_method: string; threshold_violations: ThresholdViolation[];
  domain?: string; namespace?: string; crash_loop?: boolean;
  oom_killed?: boolean; restart_count?: number;
}

export interface RiskFactor {
  metric: string; current: number; threshold: number; ratio: number;
  trend: string; slope_per_min: number; predicted_15m: number;
  predicted_30m: number; predicted_60m: number; breach_expected: boolean;
}

export interface PredictionData {
  service: string; status: string;
  failure_probability_15m: number; failure_probability_30m: number; failure_probability_60m: number;
  risk_level: RiskLevel; risk_factors: RiskFactor[];
  top_risk_metric: string | null; predicted_at: string;
}

export interface Recommendation {
  id: string; service: string; namespace?: string;
  type: string; action: string; priority: string; reason: string;
}

export interface ServiceMetrics {
  service: string; pod_name?: string; namespace: string; node_name?: string;
  domain: string; timestamp: string; status: string; phase?: string;
  replicas: number; ready_replicas: number; container_count?: number;
  cpu_percent: number; memory_mb: number; memory_limit_mb: number;
  network_in_kbps: number; network_out_kbps: number;
  disk_usage_percent: number; pvc_usage_percent?: number;
  restart_count: number; oom_killed?: boolean; crash_loop?: boolean;
  error_rate_percent: number; latency_ms: number;
  events?: K8sEvent[]; active_fault: FaultType | null;
  dependencies: string[]; image: string;
  anomaly?: AnomalyData; prediction?: PredictionData; recommendations?: Recommendation[];
}

export interface ClusterSummary {
  timestamp: string; total_services: number; running_services: number;
  degraded_services: number; active_faults: number; namespaces: string[];
  avg_cpu_percent: number; avg_memory_mb: number;
  cluster_health: ClusterHealth; simulation_mode: false;
}

export interface TopologyNode {
  id: string; namespace: string; domain: string;
  replicas?: number; ready_replicas?: number; type?: string;
}
export interface TopologyLink { source: string; target: string; type?: string; }
export interface Topology { nodes: TopologyNode[]; links: TopologyLink[]; }

export interface RCAResult {
  service: string; namespace?: string; is_root_cause: boolean; reasoning: string;
  severity: Severity; upstream_faulty: string[]; at_risk_downstream: string[];
  cascade_chain?: string[]; anomaly_types: string[];
  crash_loop?: boolean; oom_killed?: boolean; restart_count?: number;
}

export interface NLPInsight {
  id: string; severity: Severity | 'info'; message: string; ts: string; source: string;
}

// ── Correlation Intelligence ──────────────────────────────────────────────────
export interface MetricCorrelation {
  service: string;
  metric_a: string;
  metric_b: string;
  correlation: number;
  strength: 'strong' | 'moderate' | 'weak';
  direction: 'positive' | 'negative';
  interpretation: string;
}

export interface SpikePattern {
  service: string;
  metric: string;
  value: number;
  severity: string;
  detected_at: number;
}

export interface ImpactChainItem {
  service: string;
  impact_score: number;
  triggers: string[];
  is_anomaly: boolean;
}

export interface ImpactChain {
  namespace: string;
  chain: ImpactChainItem[];
  total_impact: number;
  anomaly_count: number;
}

export interface CorrelationData {
  correlations: MetricCorrelation[];
  spike_analysis: SpikePattern[];
  impact_chains: ImpactChain[];
  active_metric_pairs: { metric_a: string; metric_b: string; label: string }[];
}

export interface HealthScore {
  score: number;
  level: 'healthy' | 'degraded' | 'critical';
  factors: { factor: string; deduction: number; count: number }[];
}

export interface ExhaustionPrediction {
  service: string;
  metric: string;
  current_value: number;
  threshold: number;
  slope: number;
  eta_minutes: number;
  eta_human: string;
  severity: string;
}

export interface WSPayload {
  type: 'METRICS_UPDATE' | 'FAULT_ACK' | 'AI_RESPONSE';
  ts: string; summary: ClusterSummary; metrics: ServiceMetrics[];
  anomalies: AnomalyData[]; rca: RCAResult[]; nlp_insights?: NLPInsight[];
  ai_agent_insights?: AIAgentInsight[];
  correlation_intelligence?: CorrelationData;
  health_score?: HealthScore;
  exhaustion_predictions?: ExhaustionPrediction[];
  active_faults: Record<string, any>; topology: Topology;
}
