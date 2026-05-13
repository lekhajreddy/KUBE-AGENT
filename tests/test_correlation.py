"""
KubeMind -- Correlation Engine Test Script
Tests the correlation intelligence engine with synthetic Kubernetes metrics.
"""
import sys
sys.path.insert(0, 'backend')
sys.path.insert(0, 'backend/app')

from app.core.correlation_engine import correlation_engine

def test_correlation_engine():
    services = ['frontend-pod', 'api-pod', 'db-pod', 'cache-pod', 'worker-pod']
    test_metrics = []

    for svc in services:
        for t in range(60):
            cpu = 20 + (t * 1.2 if svc == 'frontend-pod' else t * 0.3)
            mem = 150 + (t * 6 if svc == 'db-pod' else t * 2)
            pvc = 30 + (t * 1.0 if svc == 'db-pod' else t * 0.1)
            net = 500 + (t * 60 if svc == 'frontend-pod' else t * 5)
            lat = 30 + (t * 4 if svc == 'api-pod' else t * 0.5)
            rst = t * 0.15 if svc == 'frontend-pod' and t > 35 else 0

            m = {
                'service': svc,
                'namespace': 'production',
                'cpu_percent': min(cpu, 95),
                'memory_mb': min(mem, 1200),
                'pvc_usage_percent': min(pvc, 95),
                'network_in_kbps': min(net, 20000),
                'network_out_kbps': min(net * 0.7, 10000),
                'latency_ms': min(lat, 800),
                'restart_count': int(rst),
            }
            correlation_engine.ingest(svc, m)
            test_metrics.append(m)

    result = correlation_engine.analyze(test_metrics, [])
    print("=== CORRELATIONS ===")
    for c in result['correlations'][:8]:
        print(f"  {c['service']}: {c['metric_a']} vs {c['metric_b']} = {c['correlation']} ({c['strength']}, {c['direction']})")
        print(f"    -> {c['interpretation']}")

    print()
    print("=== IMPACT CHAINS ===")
    for chain in result['impact_chains'][:3]:
        print(f"  Namespace: {chain['namespace']}, Impact: {chain['total_impact']}, Anomalies: {chain['anomaly_count']}")
        for item in chain['chain'][:4]:
            print(f"    {item['service']}: triggers={item['triggers']}, score={item['impact_score']}, anomaly={item['is_anomaly']}")

    print()
    health = correlation_engine.get_health_score(test_metrics)
    print(f"=== HEALTH SCORE: {health['score']}/100 ({health['level']}) ===")
    for f in health['factors']:
        print(f"  {f['factor']}: -{f['deduction']}pts ({f['count']} pods)")

    print()
    exhaust = correlation_engine.get_exhaustion_predictions(test_metrics)
    print(f"=== EXHAUSTION PREDICTIONS ({len(exhaust)}) ===")
    for p in exhaust[:5]:
        print(f"  {p['service']}: {p['metric']} -> {p['threshold']} in {p['eta_human']} (current: {p['current_value']}, slope: {p['slope']})")

    # Export results as JSON for verification
    import json
    with open('tests/test_results.json', 'w') as f:
        json.dump({
            'correlations': result['correlations'][:8],
            'impact_chains': result['impact_chains'][:3],
            'health_score': health,
            'exhaustion_predictions': exhaust[:5],
        }, f, indent=2)
    print("\n[OK] Results exported to tests/test_results.json")

    assert result['correlations'], "Correlation engine should produce correlations"
    print("[OK] Correlation engine: PASSED")


if __name__ == '__main__':
    success = test_correlation_engine()
    sys.exit(0 if success else 1)
