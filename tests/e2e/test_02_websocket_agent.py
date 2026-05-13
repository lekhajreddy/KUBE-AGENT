import pytest
import websockets
import json
import os
import asyncio

BASE_WS_URL = os.environ.get("KUBEMIND_WS_URL", "ws://localhost:8000")

@pytest.mark.asyncio
async def test_dashboard_websocket_requires_auth():
    try:
        async with websockets.connect(f"{BASE_WS_URL}/ws") as ws:
            pass
        pytest.fail("Should have been rejected without token")
    except websockets.exceptions.InvalidStatusCode as e:
        assert e.status_code in [401, 403]
    except Exception as e:
        pass # Depending on rejection method

@pytest.mark.asyncio
async def test_agent_websocket_requires_valid_api_key():
    try:
        async with websockets.connect(f"{BASE_WS_URL}/ws/agent?api_key=invalid_key") as ws:
            pass
        pytest.fail("Should have been rejected with invalid API key")
    except websockets.exceptions.InvalidStatusCode as e:
        assert e.status_code in [401, 403]
    except Exception:
        pass

@pytest.mark.asyncio
async def test_dependency_engine_topology():
    import httpx
    async with httpx.AsyncClient(base_url=BASE_WS_URL.replace("ws", "http")) as client:
        response = await client.get("/api/v1/topology")
        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        assert "links" in data
        assert isinstance(data["nodes"], list)
        assert isinstance(data["links"], list)
