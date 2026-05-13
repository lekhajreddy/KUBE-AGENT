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
async def test_auth_registration_and_login(client):
    # Registration
    email = f"test_{os.urandom(4).hex()}@example.com"
    resp = await client.post("/api/v1/auth/register", json={
        "email": email,
        "password": "strongpassword123",
        "name": "Test User",
        "organization": "Test Org"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "token" in data
    assert "refresh_token" in data
    token = data["token"]
    
    # Login
    resp2 = await client.post("/api/v1/auth/login", json={
        "email": email,
        "password": "strongpassword123"
    })
    assert resp2.status_code == 200
    assert "token" in resp2.json()

    # Get Me
    resp3 = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp3.status_code == 200
    assert resp3.json()["email"] == email

@pytest.mark.asyncio
async def test_multi_tenant_isolation(client):
    email1 = f"test_{os.urandom(4).hex()}@example.com"
    email2 = f"test_{os.urandom(4).hex()}@example.com"
    
    # Register user 1
    r1 = await client.post("/api/v1/auth/register", json={"email": email1, "password": "pass", "name": "U1", "organization": "Org 1"})
    token1 = r1.json()["token"]
    
    # Register user 2
    r2 = await client.post("/api/v1/auth/register", json={"email": email2, "password": "pass", "name": "U2", "organization": "Org 2"})
    token2 = r2.json()["token"]
    
    # User 1 creates cluster
    c1 = await client.post("/api/v1/clusters", json={"name": "Cluster 1", "provider": "local"}, headers={"Authorization": f"Bearer {token1}"})
    cluster_id = c1.json()["cluster_id"]
    
    # User 2 tries to read user 1's cluster
    c2 = await client.get(f"/api/v1/clusters/{cluster_id}", headers={"Authorization": f"Bearer {token2}"})
    assert c2.status_code == 404

@pytest.mark.asyncio
async def test_ai_insights_endpoint(client):
    # This checks if the coordinator returns a list of insights
    response = await client.get("/api/v1/insights")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

@pytest.mark.asyncio
async def test_alerting_fault_injection_auth_required(client):
    # Fault injection should fail without token
    resp = await client.post("/api/v1/fault/inject?service=test&fault_type=cpu_spike")
    assert resp.status_code in [401, 403, 405]
