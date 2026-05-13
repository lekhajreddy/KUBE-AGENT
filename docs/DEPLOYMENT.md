# KubeMind AI — Deployment Guide

## Prerequisites
- Docker & Docker Compose
- Node.js 20+
- Python 3.11+
- (Optional) Kubernetes (Minikube / K3s)
- (Optional) Ollama (for AI insights)

## Option 1: Local Development (Docker Compose)
The easiest way to start the entire stack.

1. Navigate to the `docker` directory:
   ```bash
   cd docker
   ```

2. Start the stack:
   ```bash
   docker-compose up -d
   ```

3. Access the dashboard:
   - Dashboard: [http://localhost:3000](http://localhost:3000)
   - Backend API: [http://localhost:8000](http://localhost:8000)
   - Prometheus: [http://localhost:9090](http://localhost:9090)

## Option 2: Kubernetes Deployment
1. Create the namespace:
   ```bash
   kubectl apply -f k8s/namespace.yaml
   ```

2. Deploy the stack:
   ```bash
   kubectl apply -R -f k8s/
   ```

3. Port forward to access:
   ```bash
   kubectl port-forward svc/frontend -n KubeMind 3000:80
   kubectl port-forward svc/backend -n KubeMind 8000:80
   ```

## Simulating Failures
You can inject faults into the simulated infrastructure to see KubeMind in action.

**Inject CPU Spike:**
```bash
curl -X POST "http://localhost:8000/api/v1/fault/inject?service=traffic-ai-service&fault_type=cpu_spike"
```

**Inject Memory Leak:**
```bash
curl -X POST "http://localhost:8000/api/v1/fault/inject?service=energy-monitor-service&fault_type=memory_leak"
```

**Clear Faults:**
```bash
curl -X POST "http://localhost:8000/api/v1/fault/clear?service=traffic-ai-service"
```

## AI Integration (Ollama)
KubeMind uses Ollama for local LLM insights.
1. Install Ollama: [ollama.com](https://ollama.com)
2. Pull the model:
   ```bash
   ollama pull llama3.2
   ```
3. The backend will automatically connect to Ollama if it's running.
