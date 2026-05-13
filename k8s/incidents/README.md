# KubeMind Demo Incident Scenarios

These Kubernetes manifests create controlled chaos for demonstrating KubeMind's AI operational intelligence.

## Quick Start

```bash
# 1. Create namespace
kubectl apply -f k8s/incidents/00-namespace.yaml

# 2. Deploy cascade demo (3-tier app)
kubectl apply -f k8s/incidents/05-cascade-demo.yaml

# 3. Inject incidents (run in separate terminals)

# CPU Spike
kubectl apply -f k8s/incidents/01-cpu-stress.yaml

# Memory Leak
kubectl apply -f k8s/incidents/02-memory-stress.yaml

# PVC Overload (requires PV provisioner)
kubectl apply -f k8s/incidents/03-pvc-stress.yaml

# Network Burst
kubectl apply -f k8s/incidents/04-network-stress.yaml
```

## Demo Flow

1. **Healthy cluster** — Open KubeMind dashboard, show green health score
2. **Inject CPU stress** — `kubectl apply -f 01-cpu-stress.yaml`
3. **Watch detection** — KubeMind detects anomaly within seconds
4. **Dependency graph lights up** — Red nodes show impacted services
5. **AI explains impact** — Correlation engine shows cascading effects
6. **Recommendations generated** — AI suggests actions to mitigate

## Cleanup

```bash
kubectl delete namespace kubemind-demo
```
