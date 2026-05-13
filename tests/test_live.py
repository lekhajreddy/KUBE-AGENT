"""
KubeMind -- Live system test with Minikube
"""
import httpx
import json


def main():
    base = "http://localhost:8000"

    # Test metrics
    r = httpx.get(f"{base}/api/v1/metrics", timeout=15)
    metrics = r.json()
    print(f"=== Metrics: {len(metrics)} pods ===")
    for m in metrics:
        ns = m.get("namespace", "")
        if ns in ("kubemind-demo", "default") or "prometheus" in m.get("service", ""):
            print(f"  {m['service']:45s} CPU={m['cpu_percent']:6.1f}%  MEM={m['memory_mb']:6.1f}MB  {m['status']}")

    # Test anomalies
    r = httpx.get(f"{base}/api/v1/anomalies", timeout=15)
    anomalies = r.json()
    print(f"\n=== Anomalies: {len(anomalies)} ===")
    for a in anomalies:
        print(f"  {a['service']:45s} severity={a['severity']:8s} types={a['anomaly_types']}")

    # Test correlation
    r = httpx.get(f"{base}/api/v1/correlation", timeout=15)
    corr = r.json()
    print(f"\n=== Correlation Intelligence ===")
    print(f"  Correlations: {len(corr.get('correlations', []))}")
    for c in corr.get('correlations', [])[:5]:
        print(f"    {c['service']}: {c['metric_a']} vs {c['metric_b']} = {c['correlation']} ({c['strength']})")
    print(f"  Impact Chains: {len(corr.get('impact_chains', []))}")
    for c in corr.get('impact_chains', [])[:3]:
        print(f"    Namespace: {c['namespace']}, Impact: {c['total_impact']}, Anomalies: {c['anomaly_count']}")
    print(f"  Spike Analysis: {len(corr.get('spike_analysis', []))}")
    for s in corr.get('spike_analysis', [])[:5]:
        print(f"    {s['service']}: {s['metric']} = {s['value']} ({s['severity']})")

    # Test health score
    r = httpx.get(f"{base}/api/v1/health-score", timeout=15)
    h = r.json()
    print(f"\n=== Health Score: {h['score']}/100 ({h['level']}) ===")
    for f in h.get('factors', []):
        if f['deduction'] > 0:
            print(f"  {f['factor']}: -{f['deduction']}pts ({f['count']} pods)")

    # Test exhaustion
    r = httpx.get(f"{base}/api/v1/exhaustion", timeout=15)
    exh = r.json()
    print(f"\n=== Exhaustion Predictions: {len(exh)} ===")
    for p in exh[:5]:
        print(f"  {p['service']}: {p['metric']} -> {p['threshold']} in {p['eta_human']}")

    # Test topology
    r = httpx.get(f"{base}/api/v1/topology", timeout=15)
    top = r.json()
    print(f"\n=== Topology: {len(top.get('nodes', []))} nodes, {len(top.get('links', []))} links ===")

    # Test summary
    r = httpx.get(f"{base}/api/v1/cluster/summary", timeout=15)
    s = r.json()
    print(f"\n=== Cluster ===")
    print(f"  Health: {s['cluster_health']}, Pods: {s['total_services']}, Running: {s['running_services']}")
    print(f"  Avg CPU: {s['avg_cpu_percent']}%, Avg MEM: {s['avg_memory_mb']}MB")

    print("\n[OK] All live tests passed!")


if __name__ == "__main__":
    main()
