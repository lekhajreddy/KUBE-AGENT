# KubeMind AI — System Design

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            KubeMind AI System                                │
│                                                                             │
│  ┌──────────┐   ┌──────────────┐   ┌──────────────┐   ┌─────────────────┐  │
│  │  Agent    │──▶│   Backend    │──▶│  ML Services  │──▶│   AI Engine     │  │
│  │ (K8s Pod) │   │  (FastAPI)   │   │  (FastAPI)    │   │   (FastAPI)     │  │
│  └────┬─────┘   └──────┬───────┘   └──────┬───────┘   └────────┬────────┘  │
│       │                │                  │                     │           │
│       │ WebSocket      │ gRPC/HTTP        │ HTTP                │ HTTP      │
│       ▼                ▼                  ▼                     ▼           │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                     Observability & Data Layer                       │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────┐  │    │
│  │  │PostgreSQL│  │  Redis   │  │Prometheus│  │  Loki    │  │ Tempo│  │    │
│  │  │ (15-alp) │  │ (7-alp)  │  │(latest)  │  │(latest)  │  │(lat) │  │    │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────┘  │    │
│  │  ┌──────────┐  ┌──────────┐  ┌─────────────────────────────────┐    │    │
│  │  │ Grafana  │  │  Ollama  │  │    OpenTelemetry Collector      │    │    │
│  │  │(latest)  │  │(latest)  │  │    (otel-contrib)               │    │    │
│  │  └──────────┘  └──────────┘  └─────────────────────────────────┘    │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                       Frontend (Next.js 14)                          │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────┐  │   │
│  │  │Dashboard │  │ Topology │  │ Metrics  │  │ Timeline │  │  AI  │  │   │
│  │  │  View    │  │  View    │  │  View    │  │  View    │  │Agent │  │   │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────┘  │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Service Breakdown

### 1. Agent (In-Cluster Collector)
- **Purpose**: Runs inside the Kubernetes cluster to collect real-time telemetry
- **Port**: N/A (outbound only)
- **Communication**: WebSocket push to backend (`/ws/agent`)
- **Data Collected**: Pods, nodes, services, events, topology
- **Heartbeat**: Every 30s with cluster_id, agent_version, resource counts
- **Auth**: API key-based registration

### 2. Backend API (FastAPI)
- **Port**: `8000`
- **Framework**: FastAPI with asyncpg, SQLAlchemy (async), OpenTelemetry
- **Core Modules**:
  - **Auth System**: JWT (HS256, 24h expiry), bcrypt hashing, RBAC (`require_role`), API key auth
  - **K8s Collector**: Prometheus PromQL queries + direct K8s API polling
  - **Correlation Engine**: Pearson correlation on 8 metric pairs, health scoring, exhaustion prediction
  - **Alerting Engine**: Multi-channel (Slack, Discord, SMTP, webhook), rule evaluation, deduplication, cooldown
  - **Event Bus**: Redis pub/sub with Upstash REST fallback; Kafka support via aiokafka
- **WebSocket Endpoints**:
  - `/ws` — Dashboard real-time data
  - `/ws/logs/{namespace}/{pod}` — Log streaming
  - `/ws/agent` — Agent telemetry ingestion
- **REST Endpoints**: Auth, clusters, health, metrics, summary, topology, correlation, health score, exhaustion, insights, events, PromQL query, fault injection

### 3. ML Services (FastAPI)
- **Port**: `8001`
- **Anomaly Detection**: Isolation Forest per service, 6 features, adaptive threshold retraining
- **Prediction Engine**: Linear regression + exponential smoothing for failure probability (15/30/60 min)
- **Features**: cpu_percent, memory_mb, network_in_kbps, network_out_kbps, pvc_usage_percent, restart_count

### 4. AI Engine (FastAPI)
- **Port**: `8002`
- **RCA Engine**: NetworkX graph traversal + topological sort for root-cause analysis
- **Recommendation Engine**: 15 fault types mapped to kubectl remediation commands
- **Ollama Client**: Async HTTP client, `llama3.2` model, JSON-only system prompt, graceful fallback
- **Endpoints**: `/api/v1/rca`, `/api/v1/recommendations`, `/api/v1/analyze`

### 5. Frontend (Next.js 14)
- **Port**: `3000`
- **Framework**: Next.js 14 (React 18), Tailwind CSS dark theme
- **State Management**: Zustand store + RxJS Subject for WebSocket event streams
- **Key Components**:
  - `DependencyGraph` — D3.js force simulation with zoom/drag, anomaly/fault coloring
  - `ClusterMetricsChart` — Domain-categorized AreaChart (5 domain colors)
  - `Sparkline` — Recharts LineChart for compact trend display
- **Views**: Topology, Pods, Timeline, Metrics, Recommendations, AI Assistant, Fault Injection

## Data Flow

```
Agent ──WebSocket──▶ Backend ──HTTP──▶ ML Services (anomaly/prediction)
                           │              │
                           │              └──▶ AI Engine (RCA/recommendation)
                           │
                           ├──▶ PostgreSQL (persist metrics, events, insights)
                           ├──▶ Redis (pub/sub event bus)
                           ├──▶ Prometheus (query historical metrics)
                           ├──▶ WebSocket broadcast to Frontend
                           └──▶ OpenTelemetry ──▶ Tempo (traces)
                                                    │
                                                    └──▶ Grafana (visualization)
```

## Database Schema (14 Tables)

| Table | Description |
|---|---|
| `organizations` | Multi-tenant orgs with name, settings, timestamps |
| `users` | Auth users with org FK, hashed passwords, roles |
| `refresh_tokens` | JWT refresh token rotation |
| `api_keys` | Agent/service API key management |
| `clusters` | Registered Kubernetes clusters |
| `services` | Discovered K8s services by cluster |
| `metrics` | Time-series metric snapshots (hypertable) |
| `anomalies` | Detected anomalies (hypertable) |
| `predictions` | Failure predictions (hypertable) |
| `alert_records` | Triggered alert history |
| `ai_insights` | AI-generated insights from Ollama |
| `topology_snapshots` | Cluster topology snapshots |
| `k8s_events` | Kubernetes events (hypertable) |
| `audit_logs` | User action audit trail |

## AI Agents (5 Domain-Specific)

1. **CPU Agent** — Spike detection, usage trends, throttling analysis
2. **Memory Agent** — Leak detection, OOM analysis, usage patterns
3. **Storage Agent** — PVC saturation, I/O latency, capacity trending
4. **Network Agent** — Traffic anomalies, latency spikes, packet loss
5. **Correlation Agent** — Cascading failure detection, cross-resource impact analysis

## Observability Stack

| Component | Role | Port |
|---|---|---|
| Prometheus | Metrics collection & storage | 9090 |
| Grafana | Metrics/visualization dashboards | 3001 |
| Loki | Log aggregation | 3100 |
| Tempo | Distributed tracing (OTLP gRPC) | 4317 |
| OpenTelemetry Collector | Trace/metric/log pipeline | 4318 |

## Security

- **Auth**: JWT (HS256) with refresh token rotation
- **Password Hashing**: bcrypt
- **RBAC**: `require_role` decorator for endpoint access control
- **API Keys**: UUID-based keys for agent/service auth
- **Database**: SSL mode required, connection pooling with limits
- **Helm**: Secrets template for sensitive values

## Deployment Options

| Method | Description |
|---|---|
| Docker Compose | Full stack for dev/staging (12+ services) |
| Docker Bake | Multi-arch production image builds |
| Kubernetes (raw YAML) | `k8s/` namespace, RBAC, deployment manifests |
| Helm | Umbrella chart with subcharts, HPA, PDB, ingress |

## Key Design Decisions

1. **Microservice separation** — Agent runs in-cluster with minimal footprint; backend handles orchestration; ML/AI are isolated for independent scaling
2. **WebSocket-first** — Real-time push from agent → backend → frontend avoids polling overhead
3. **OpenTelemetry everywhere** — All Python services instrumented for distributed tracing
4. **LLM with fallback** — Ollama provides AI insights; system degrades gracefully when unavailable
5. **TimescaleDB hypertables** — Time-series tables for metrics, anomalies, predictions, events
6. **Multi-cluster support** — Agent-based architecture enables monitoring multiple clusters from a single backend
