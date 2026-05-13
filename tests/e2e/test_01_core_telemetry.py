import pytest
import httpx
import os
import asyncio

BASE_URL = os.environ.get("KUBEMIND_API_URL", "http://localhost:8000")

@pytest.fixture(scope="module")
async def client():
    async with httpx.AsyncClient(base_url=BASE_URL) as c:
        yield c

@pytest.mark.asyncio
async def test_health_check(client):
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data

@pytest.mark.asyncio
async def test_cluster_discovery(client):
    # This assumes the backend has discovered the local Minikube/K3s cluster
    response = await client.get("/api/v1/cluster/summary")
    assert response.status_code == 200
    data = response.json()
    assert "total_services" in data
    assert data["total_services"] >= 0

@pytest.mark.asyncio
async def test_metrics_telemetry(client):
    response = await client.get("/api/v1/metrics")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    if data:
        m = data[0]
        assert "cpu_percent" in m
        assert "memory_mb" in m
        assert "namespace" in m
        assert "pod_name" in m
        assert "node_name" in m

@pytest.mark.asyncio
async def test_prometheus_integration(client):
    # Check if Prometheus format endpoint works
    response = await client.get("/metrics")
    assert response.status_code == 200
    text = response.text
    assert "kubemind_cpu_percent" in text
    assert "kubemind_memory_mb" in text

@pytest.mark.asyncio
async def test_node_discovery(client):
    response = await client.get("/api/v1/nodes")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)

@pytest.mark.asyncio
async def test_event_ingestion(client):
    response = await client.get("/api/v1/events")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
