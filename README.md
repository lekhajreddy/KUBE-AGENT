# KubeMind AI

> AI-powered Kubernetes observability platform with real-time monitoring, anomaly detection, failure prediction, and root-cause analysis.

## Architecture

```
Agent (in-cluster) ──WebSocket──▶ Backend API ──HTTP──▶ ML Services
                                      │                    │
                                      │                    └──▶ AI Engine (Ollama LLM)
                                      │
                                      ├──▶ PostgreSQL + Redis
                                      ├──▶ WebSocket ──▶ Frontend (Next.js 14)
                                      └──▶ OpenTelemetry ──▶ Grafana / Loki / Tempo
```

## Services Overview

| Service | Tech | Port | Purpose |
|---|---|---|---|
| **Frontend** | Next.js 14 (React 18) | `3000` | Dashboard, topology graph, metrics, AI assistant |
| **Backend API** | FastAPI (Python 3.11) | `8000` | REST + WebSocket, auth, orchestration, alerting |
| **ML Services** | FastAPI (scikit-learn) | `8001` | Anomaly detection (Isolation Forest), failure prediction |
| **AI Engine** | FastAPI (Ollama LLM) | `8002` | Root-cause analysis, recommendations, NLP insights |
| **Agent** | Python (kubernetes client) | — | In-cluster telemetry collector, WebSocket push |
| **PostgreSQL** | 15-alpine | `5432` | Primary database (14 tables, TimescaleDB hypertables) |
| **Redis** | 7-alpine | `6379` | Event bus, caching, pub/sub |
| **Ollama** | llama3.2 | `11434` | Local LLM for AI-generated insights |
| **Prometheus** | latest | `9090` | Metrics storage & PromQL queries |
| **Grafana** | latest | `3001` | Observability dashboards |
| **Loki** | latest | `3100` | Log aggregation |
| **Tempo** | latest | `4317` | Distributed tracing (OTLP gRPC) |
| **OTel Collector** | contrib | `4318` | Telemetry pipeline |

## Quick Start

### Prerequisites

- Docker & Docker Compose
- 8GB+ RAM allocated to Docker

### 1. Clone & Configure

```bash
git clone https://github.com/lekhajreddy/KUBE-AGENT.git
cd kubemind
cp .env.example .env
# Edit .env as needed (defaults work for local dev)
```

### 2. Start the Stack

```bash
docker compose up --build -d
```

This builds and starts all 12+ services.

### 3. Verify

```bash
docker compose ps
```

All services should show `Up` status.

| Endpoint | URL |
|---|---|
| Frontend Dashboard | http://localhost:3000 |
| Backend API Health | http://localhost:8000/api/v1/health |
| Grafana | http://localhost:3001 (admin:kubemind) |
| Prometheus | http://localhost:9090 |
| ML Services | http://localhost:8001 |
| AI Engine | http://localhost:8002 |

### 4. Stop

```bash
docker compose down
# To also remove volumes:
docker compose down -v
```

## Working Demonstration

### User Flow

```
1. Open http://localhost:3000
   └── Login/Register page loads

2. Register an account
   └── JWT token issued, stored in Zustand state

3. Connect a Kubernetes cluster
   └── Backend validates → cluster registered in PostgreSQL

4. Dashboard loads with 7 views:
   ├── Topology Graph — Live D3.js force simulation of cluster resources
   │                    Anomalous nodes glow red, faults pulse
   ├── Pod List — Real-time pod status with color-coded health
   ├── Timeline — K8s events in chronological order
   ├── Metrics — Domain-categorized charts (CPU, Memory, Network, Storage)
   │              with sparklines for every service
   ├── Recommendations — AI-generated remediation actions for detected faults
   │                      (15 fault types → kubectl commands)
   ├── AI Assistant — Ollama-powered natural language insights
   │                   (severity, confidence, actionable steps)
   └── Fault Injection — Simulate CPU spikes, memory leaks,
                          restart loops, network congestion

5. Real-time updates via WebSocket
   └── Agent pushes telemetry → Backend processes → Broadcasts to dashboard
   └── ML models detect anomalies → Predictions appear in real-time
   └── AI engine generates RCA → Recommendations shown instantly
```

### Fault Injection Demo

Simulate issues to see the system react:

```bash
# CPU spike in default namespace
curl -X POST http://localhost:8000/api/v1/fault/inject \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"type": "cpu_spike", "namespace": "default", "duration": 120}'

# Watch the dashboard update in real-time:
#   - Topology graph: affected pod glows red
#   - ML Services: anomaly detected within 30s
#   - AI Engine: RCA generated with severity & confidence
#   - Recommendations: kubectl commands to resolve
#   - Metrics: CPU spike visible on charts

# Clear the fault
curl -X POST http://localhost:8000/api/v1/fault/clear \
  -H "Authorization: Bearer <token>"
```

Available faults: `cpu_spike`, `memory_leak`, `restart_loop`, `network_congestion`, `storage_overload`

### Observability

Access the full observability stack:

| Tool | URL | Purpose |
|---|---|---|
| Grafana | http://localhost:3001 | Pre-built dashboards for metrics, logs, traces |
| Prometheus | http://localhost:9090 | Raw metric queries with PromQL |
| Loki (logs) | Accessed via Grafana | Cluster-wide log aggregation |
| Tempo (traces) | Accessed via Grafana | Distributed tracing across all services |

## Tech Stack

| Layer | Technologies |
|---|---|
| **Frontend** | Next.js 14, React 18, TypeScript, Tailwind CSS, Zustand, RxJS, D3.js, Recharts, ReactFlow, Framer Motion, Lucide React |
| **Backend** | Python 3.11, FastAPI, SQLAlchemy (async), asyncpg, Alembic, OpenTelemetry, Pydantic |
| **ML/AI** | scikit-learn (Isolation Forest, Linear Regression), NetworkX, Ollama (llama3.2 LLM) |
| **Infrastructure** | PostgreSQL 15, Redis 7, TimescaleDB hypertables |
| **Observability** | Prometheus, Grafana, Loki, Tempo, OpenTelemetry Collector |
| **Deployment** | Docker Compose, Docker Bake, Kubernetes YAML, Helm 3 |

## API Endpoints

### REST

| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/auth/register` | Register user |
| POST | `/api/v1/auth/login` | Login, returns JWT |
| POST | `/api/v1/auth/refresh` | Refresh access token |
| GET | `/api/v1/auth/me` | Current user info |
| GET | `/api/v1/clusters` | List registered clusters |
| POST | `/api/v1/clusters` | Register a cluster |
| GET | `/api/v1/health` | Health check |
| GET | `/api/v1/metrics` | Current cluster metrics |
| GET | `/api/v1/summary` | Cluster summary |
| GET | `/api/v1/topology` | Cluster topology |
| GET | `/api/v1/correlation` | Metric correlations |
| GET | `/api/v1/healthscore` | Health scores |
| GET | `/api/v1/exhaustion` | Resource exhaustion predictions |
| GET | `/api/v1/insights` | AI-generated insights |
| GET | `/api/v1/events` | Kubernetes events |
| POST | `/api/v1/query` | Raw PromQL query |
| POST | `/api/v1/fault/inject` | Inject fault |
| POST | `/api/v1/fault/clear` | Clear active faults |

### WebSocket

| Path | Purpose |
|---|---|
| `/ws` | Dashboard real-time data stream |
| `/ws/logs/{namespace}/{pod}` | Live log streaming |
| `/ws/agent` | Agent telemetry ingestion |

## ML Capabilities

### Anomaly Detection
- **Algorithm**: Isolation Forest (per-service models)
- **Features**: CPU%, memory MB, network in/out kbps, PVC usage%, restart count
- **Output**: Normal/Warning/Critical severity levels
- **Adaptive**: Models retrained with sliding window data

### Failure Prediction
- **Technique**: Linear regression + exponential smoothing
- **Horizons**: 15, 30, and 60-minute failure probability
- **Thresholds**: CPU >90%, memory >1500MB, disk >95%, error rate >25%, restarts >8

### AI Root-Cause Analysis
- **Graph**: NetworkX directed graph of resource dependencies
- **Algorithm**: Topological sort for root cause identification
- **Cascading**: Detects failure propagation chains

### Recommendations
- **15 fault types** mapped to kubectl remediation commands
- Includes: CPU spike, memory leak, crash loop, OOMKilled, network surge, PVC full, config error, pod unschedulable, node pressure, image pull failure, RBAC denied, DNS resolution, TLS cert expiry, resource quota, and HPA scaling

## Project Structure

```
kubemind/
├── agent/              # In-cluster K8s telemetry collector
│   ├── main.py
│   └── Dockerfile
├── ai-engine/          # RCA, recommendations, Ollama LLM
│   ├── main.py
│   ├── rca_engine.py
│   ├── recommendation_engine.py
│   ├── ollama_client.py
│   └── Dockerfile
├── backend/            # FastAPI backend (REST + WebSocket)
│   ├── app/
│   │   ├── main.py
│   │   ├── core/       # Config, DB, Auth, collectors
│   │   └── routers/    # Auth, clusters, dashboard, WS
│   ├── services/       # Metrics, K8s clients, alerting
│   ├── migrations/     # Alembic (14 tables)
│   └── Dockerfile
├── frontend/           # Next.js 14 dashboard
│   ├── src/
│   │   ├── app/
│   │   ├── components/ # Charts, graphs, dashboard
│   │   ├── hooks/      # WebSocket, data fetching
│   │   ├── lib/        # API client, Zustand store
│   │   └── types/
│   └── Dockerfile
├── ml-services/        # Anomaly detection, prediction
│   ├── main.py
│   ├── anomaly_detector.py
│   ├── prediction_engine.py
│   └── Dockerfile
├── docker/             # Observability configs
│   ├── prometheus.yml
│   ├── loki.yml
│   ├── tempo.yml
│   ├── otel-collector.yml
│   └── grafana/
├── helm/               # Helm charts (umbrella + subcharts)
├── k8s/                # Raw Kubernetes manifests
├── docs/
├── docker-compose.yml  # Full dev/staging stack
├── docker-bake.hcl     # Production multi-arch builds
└── .env.example
```
