"""
KubeMind — FastAPI Backend (Production Edition)
Auth · Multi-cluster · Agent WebSocket · AI Agents · Alerting
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query, Body, Depends
from fastapi.middleware.cors import CORSMiddleware
import asyncio, json, logging, sys, os, secrets
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from fastapi.responses import PlainTextResponse
from prometheus_client import Gauge, Counter, generate_latest, CONTENT_TYPE_LATEST

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
from app.core.k8s_collector import (
    collect_all_metrics, get_cluster_summary, get_metric_history,
    build_live_topology, inject_fault, clear_fault, list_faults,
    set_prometheus_url, _last_snapshot, _collect_events, _collect_node_metrics,
    _collect_pods, _collect_services, _collect_pvcs, _collect_deployments,
)
from app.core.microservice_clients import ml_client, ai_client
from app.core.auth import (
    hash_password, verify_password, create_access_token, decode_token,
    generate_api_key, generate_cluster_id, get_current_user, get_optional_user,
    get_ws_user, require_role,
)
from app.core.cluster_manager import cluster_manager
from app.core.ai_agents.agent_coordinator import agent_coordinator
from app.core.correlation_engine import correlation_engine
from app.core.alerting import check_and_alert, create_alert, fire_alert

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("kubemind")

# ── Prometheus Gauges ─────────────────────────────────────────────────────────
PROM_CPU = Gauge("kubemind_cpu_percent", "CPU usage percent", ["pod", "namespace"])
PROM_MEM = Gauge("kubemind_memory_mb", "Memory usage MB", ["pod", "namespace"])
PROM_NET_IN = Gauge("kubemind_network_rx_kbps", "Network RX kbps", ["pod", "namespace"])
PROM_NET_OUT = Gauge("kubemind_network_tx_kbps", "Network TX kbps", ["pod", "namespace"])
PROM_RESTARTS = Gauge("kubemind_restarts_total", "Total pod restarts", ["pod", "namespace"])
PROM_PVC = Gauge("kubemind_pvc_usage_percent", "PVC usage percent", ["pod", "namespace"])

app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION,
              description="AI-powered real-time Kubernetes observability platform")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

# ── OpenTelemetry Setup ───────────────────────────────────────────────────────
resource = Resource.create({"service.name": settings.APP_NAME})
tracer_provider = TracerProvider(resource=resource)
otlp_exporter = OTLPSpanExporter(endpoint=os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317"), insecure=True)
tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
trace.set_tracer_provider(tracer_provider)
FastAPIInstrumentor.instrument_app(app)

# ── In-memory stores (replaced by DB when DB_ENABLED) ────────────────────────
_users_store: Dict[str, Dict] = {}
_orgs_store: Dict[str, Dict] = {}
_clusters_store: Dict[str, Dict] = {}
_api_keys_store: Dict[str, str] = {}  # api_key -> cluster_id


# ── WebSocket Manager ─────────────────────────────────────────────────────────
class ConnectionManager:
    def __init__(self):
        self.active: List[WebSocket] = []
        self.agent_connections: Dict[str, WebSocket] = {}  # cluster_id -> ws

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, payload: str):
        dead = []
        for ws in self.active:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    async def connect_agent(self, cluster_id: str, ws: WebSocket):
        await ws.accept()
        self.agent_connections[cluster_id] = ws
        cluster_manager.update_agent_heartbeat(cluster_id)

    def disconnect_agent(self, cluster_id: str):
        self.agent_connections.pop(cluster_id, None)


manager = ConnectionManager()
_broadcast_task: Optional[asyncio.Task] = None
_cached_metrics: List[Dict] = []


# ── Payload builder ───────────────────────────────────────────────────────────
async def _build_payload(raw_metrics: List[Dict]) -> Dict[str, Any]:
    anomalies, enriched = [], []
    for m in raw_metrics:
        svc = m["service"]
        detection = await ml_client.detect_anomaly(svc, m)
        prediction = await ml_client.predict_failure(svc, m)
        recs = await ai_client.get_recommendations(detection, prediction)
        m["anomaly"], m["prediction"], m["recommendations"] = detection, prediction, recs
        enriched.append(m)
        if detection.get("is_anomaly"):
            anomalies.append({**detection, "domain": m.get("domain", m["namespace"]), "namespace": m["namespace"]})

    topology = build_live_topology(raw_metrics)
    rca_results = await ai_client.perform_rca(anomalies, enriched, topology=topology)
    summary = get_cluster_summary(raw_metrics)
    nlp_insights = _generate_nlp_insights(rca_results, anomalies, summary)

    # Run AI agents
    ai_insights = agent_coordinator.analyze_all(raw_metrics, anomalies, topology)

    # Correlation intelligence
    correlation_data = correlation_engine.analyze(raw_metrics, anomalies)
    health_score = correlation_engine.get_health_score(raw_metrics)
    exhaustion = correlation_engine.get_exhaustion_predictions(raw_metrics)

    return {
        "type": "METRICS_UPDATE",
        "ts": datetime.now(timezone.utc).isoformat(),
        "summary": summary, "metrics": enriched, "anomalies": anomalies,
        "rca": rca_results, "nlp_insights": nlp_insights,
        "ai_agent_insights": ai_insights,
        "correlation_intelligence": correlation_data,
        "health_score": health_score,
        "exhaustion_predictions": exhaustion,
        "active_faults": list_faults(), "topology": topology,
    }


def _generate_nlp_insights(rca, anomalies, summary):
    insights, ts = [], datetime.now(timezone.utc).isoformat()
    health = summary.get("cluster_health", "Unknown")
    if health == "Critical":
        insights.append({"id": "cluster-critical", "severity": "critical",
            "message": f"Cluster CRITICAL — {summary.get('degraded_services',0)} pods degraded, avg CPU {summary.get('avg_cpu_percent',0):.1f}%",
            "ts": ts, "source": "correlation-engine"})
    elif health == "Degraded":
        insights.append({"id": "cluster-degraded", "severity": "warning",
            "message": f"Cluster degrading — {summary.get('degraded_services',0)} pods non-running.",
            "ts": ts, "source": "correlation-engine"})
    for r in rca[:5]:
        svc = r.get("service", "unknown")
        if r.get("is_root_cause"):
            types = ", ".join(r.get("anomaly_types", []))
            downstream = r.get("at_risk_downstream", [])
            msg = f"Root cause in {svc}: {types}."
            if downstream:
                msg += f" {len(downstream)} downstream at risk: {', '.join(downstream[:3])}."
            insights.append({"id": f"rca-root-{svc}", "severity": r.get("severity", "warning"),
                "message": msg, "ts": ts, "source": "rca-engine"})
    oom_pods = [m["service"] for m in anomalies if "OOMKilled" in str(m.get("anomaly_types", []))]
    if oom_pods:
        insights.append({"id": "oom-alert", "severity": "critical",
            "message": f"OOMKilled: {', '.join(oom_pods[:3])}. Increase memory limits.",
            "ts": ts, "source": "memory-agent"})
    return insights[:10]


# ── Broadcast loop ────────────────────────────────────────────────────────────
async def _broadcast_agent_data(agent_metrics: List[Dict]):
    """Build payload from agent-sourced metrics and broadcast to dashboard clients."""
    try:
        payload_dict = await _build_payload(agent_metrics)
        await manager.broadcast(json.dumps(payload_dict, default=str))
        logger.info(f"Agent metrics broadcast: {len(agent_metrics)} services, {len(payload_dict.get('metrics',[]))} enriched")
    except Exception as e:
        logger.error(f"Agent metrics broadcast error: {e}")

async def _broadcast_loop():
    global _cached_metrics
    logger.info("Real-time K8s metrics broadcast loop started.")
    # Yield control so uvicorn can finish its lifespan startup
    await asyncio.sleep(0)
    if settings.DB_ENABLED:
        from app.core.database import save_metrics_batch, save_anomaly
    while True:
        try:
            raw_metrics = await asyncio.wait_for(collect_all_metrics(), timeout=30)
            if raw_metrics:
                _cached_metrics = raw_metrics
            if _cached_metrics and manager.active:
                payload_dict = await _build_payload(_cached_metrics)
                await manager.broadcast(json.dumps(payload_dict, default=str))
                # Alerting
                asyncio.create_task(check_and_alert(
                    _cached_metrics, payload_dict.get("anomalies", [])))
                if settings.DB_ENABLED:
                    default_cluster = cluster_manager.get_default_cluster()
                    cluster_id = default_cluster.cluster_id if default_cluster else "local"
                    org_id = next(iter(_orgs_store.keys()), "default-org")
                    asyncio.create_task(save_metrics_batch(
                        payload_dict.get("metrics", []), org_id, cluster_id))
                    for a in payload_dict.get("anomalies", []):
                        asyncio.create_task(save_anomaly(a, org_id, cluster_id))
        except Exception as exc:
            logger.error(f"Broadcast error: {exc}", exc_info=True)
        await asyncio.sleep(settings.WS_METRICS_BROADCAST_INTERVAL)


# ── Lifecycle ─────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    global _broadcast_task
    logger.info("🚀 KubeMind AI backend starting…")
    set_prometheus_url(settings.PROMETHEUS_URL)

    # Init Event bus
    from app.core.event_bus import init_event_bus
    await init_event_bus()

    if settings.DB_ENABLED:
        from app.core.database import init_db
        try:
            await init_db(enable_timescale=settings.TIMESCALE_ENABLED)
        except Exception as e:
            logger.error(f"DB init failed — falling back to in-memory: {e}")
            settings.DB_ENABLED = False

    # Init default local cluster
    try:
        cluster_manager.init_default_cluster()
    except Exception as e:
        logger.warning(f"Default cluster init: {e}")

    _broadcast_task = asyncio.create_task(_broadcast_loop())


@app.on_event("shutdown")
async def shutdown():
    if _broadcast_task:
        _broadcast_task.cancel()
    from app.core.event_bus import close_event_bus
    await close_event_bus()
    if settings.DB_ENABLED:
        from app.core.database import close_db
        await close_db()


# ═══════════════════════════════════════════════════════════════════════════════
# AUTH ROUTES
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/api/v1/auth/register")
async def register(body: Dict[str, Any] = Body(...)):
    email = body.get("email", "").strip().lower()
    password = body.get("password", "")
    name = body.get("name", "")
    org_name = body.get("organization", "Default Org")
    if not email or not password:
        raise HTTPException(400, "email and password required")
    
    if settings.DB_ENABLED:
        from app.core.database import get_user_by_email, create_user, create_organization
        existing = await get_user_by_email(email)
        if existing:
            raise HTTPException(409, "User already exists")
        user_id = generate_cluster_id()
        org_id = generate_cluster_id()
        await create_organization(org_id, org_name)
        await create_user(user_id, email, name, hash_password(password), "admin", org_id)
    else:
        if email in _users_store:
            raise HTTPException(409, "User already exists")
        user_id = generate_cluster_id()
        org_id = generate_cluster_id()
        _users_store[email] = {
            "id": user_id, "email": email, "name": name,
            "password_hash": hash_password(password),
            "role": "admin", "org_id": org_id,
        }
        _orgs_store[org_id] = {"id": org_id, "name": org_name, "owner": user_id}

    token = create_access_token({"sub": user_id, "email": email, "role": "admin", "org_id": org_id})
    refresh_token = secrets.token_urlsafe(32)
    if settings.DB_ENABLED:
        from app.core.database import create_refresh_token
        await create_refresh_token(refresh_token, user_id, datetime.now(timezone.utc) + timedelta(days=7))

    return {"token": token, "refresh_token": refresh_token, "user": {"id": user_id, "email": email, "name": name, "role": "admin", "org_id": org_id}}


@app.post("/api/v1/auth/login")
async def login(body: Dict[str, Any] = Body(...)):
    email = body.get("email", "").strip().lower()
    password = body.get("password", "")
    if not email or not password:
        raise HTTPException(400, "email and password required")

    if settings.DB_ENABLED:
        from app.core.database import get_user_by_email
        user = await get_user_by_email(email)
    else:
        user = _users_store.get(email)

    if not user or not verify_password(password, user["password_hash"]):
        raise HTTPException(401, "Invalid credentials")

    token = create_access_token({"sub": user["id"], "email": user["email"], "role": user["role"], "org_id": user["org_id"]})
    refresh_token = secrets.token_urlsafe(32)
    if settings.DB_ENABLED:
        from app.core.database import create_refresh_token
        await create_refresh_token(refresh_token, user["id"], datetime.now(timezone.utc) + timedelta(days=7))
    
    return {"token": token, "refresh_token": refresh_token, "user": {"id": user["id"], "email": user["email"], "name": user["name"], "role": user["role"], "org_id": user["org_id"]}}

@app.post("/api/v1/auth/refresh")
async def refresh_auth(body: Dict[str, Any] = Body(...)):
    refresh_token = body.get("refresh_token")
    if not refresh_token:
        raise HTTPException(400, "refresh_token required")
    
    if not settings.DB_ENABLED:
        raise HTTPException(501, "Refresh tokens require DB")
    
    from app.core.database import get_refresh_token, delete_refresh_token
    token_record = await get_refresh_token(refresh_token)
    
    if not token_record or token_record["expires_at"] < datetime.now(timezone.utc):
        if token_record:
            await delete_refresh_token(refresh_token)
        raise HTTPException(401, "Invalid or expired refresh token")
        
    await delete_refresh_token(refresh_token)
    
    # Normally we should fetch the user from DB to get the latest role and org_id
    # But for simplicity in this example, we just issue a new token with generic info or fetch it.
    from app.core.database import AsyncSessionLocal
    from sqlalchemy import text
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("SELECT id, email, name, role, org_id FROM users WHERE id = :id"),
            {"id": token_record["user_id"]}
        )
        row = result.fetchone()
        if not row:
            raise HTTPException(401, "User no longer exists")
        user = dict(row._mapping)
        
    token = create_access_token({"sub": user["id"], "email": user["email"], "role": user["role"], "org_id": user["org_id"]})
    new_refresh_token = secrets.token_urlsafe(32)
    from app.core.database import create_refresh_token
    await create_refresh_token(new_refresh_token, user["id"], datetime.now(timezone.utc) + timedelta(days=7))
    
    return {"token": token, "refresh_token": new_refresh_token, "user": {"id": user["id"], "email": user["email"], "name": user["name"], "role": user["role"], "org_id": user["org_id"]}}



@app.get("/api/v1/auth/me")
async def get_me(user: Dict = Depends(get_current_user)):
    return user


# ═══════════════════════════════════════════════════════════════════════════════
# CLUSTER MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/v1/clusters")
async def list_clusters(user: Dict = Depends(require_role("viewer"))):
    if settings.DB_ENABLED:
        from app.core.database import get_clusters_by_org
        clusters = await get_clusters_by_org(user["org_id"])
        return [
            {**cluster_manager.get_cluster_dict(c["id"]), **c, "cluster_id": c["id"]} for c in clusters
        ]
    else:
        return [c for c in cluster_manager.get_all_clusters() if c.get("org_id") == user["org_id"] or not c.get("org_id")]


@app.post("/api/v1/clusters")
async def register_cluster(body: Dict[str, Any] = Body(...), user: Dict = Depends(require_role("admin"))):
    name = body.get("name", "New Cluster")
    provider = body.get("provider", "unknown")

    cluster_id = generate_cluster_id()
    api_key = generate_api_key()
    
    if settings.DB_ENABLED:
        from app.core.database import create_cluster_db, create_api_key
        await create_cluster_db(cluster_id, name, provider, user["org_id"])
        await create_api_key(api_key, cluster_id, user["org_id"])
    else:
        _api_keys_store[api_key] = cluster_id
        _clusters_store[cluster_id] = {"api_key": api_key, "name": name, "provider": provider, "org_id": user.get("org_id")}

    # The cluster manager is an in-memory cache for live state (websockets)
    cluster_manager.register_agent_cluster(cluster_id, name, provider)

    helm_cmd = (
        f"helm install kubemind-agent kubemind/kubemind-agent \\\n"
        f"  --set agent.apiKey={api_key} \\\n"
        f"  --set agent.backendUrl=ws://<YOUR_KUBEMIND_HOST>:8000/ws/agent \\\n"
        f"  --set agent.clusterId={cluster_id} \\\n"
        f"  --namespace kubemind-agent --create-namespace"
    )

    return {"cluster_id": cluster_id, "api_key": api_key, "name": name,
            "install_command": helm_cmd, "status": "awaiting_agent"}


@app.get("/api/v1/clusters/{cluster_id}")
async def get_cluster(cluster_id: str, user: Dict = Depends(require_role("viewer"))):
    if settings.DB_ENABLED:
        from app.core.database import get_cluster_db
        c = await get_cluster_db(cluster_id)
        if not c or c["org_id"] != user["org_id"]:
            raise HTTPException(404, "Cluster not found")
        # merge with live state
        live = cluster_manager.get_cluster(cluster_id)
        if live:
            c.update(live.to_dict())
        c["cluster_id"] = c["id"]
        return c
    else:
        c = cluster_manager.get_cluster(cluster_id)
        if not c:
            raise HTTPException(404, "Cluster not found")
        return c.to_dict()


@app.delete("/api/v1/clusters/{cluster_id}")
async def delete_cluster(cluster_id: str, user: Dict = Depends(require_role("admin"))):
    if settings.DB_ENABLED:
        from app.core.database import get_cluster_db, delete_cluster_db
        c = await get_cluster_db(cluster_id)
        if not c or c["org_id"] != user["org_id"]:
            raise HTTPException(404, "Cluster not found")
        await delete_cluster_db(cluster_id, user["org_id"])

    cluster_manager.remove_cluster(cluster_id)
    _clusters_store.pop(cluster_id, None)
    return {"status": "deleted", "cluster_id": cluster_id}


@app.get("/api/v1/clusters/{cluster_id}/install-command")
async def cluster_install_cmd(cluster_id: str, user: Dict = Depends(require_role("viewer"))):
    if settings.DB_ENABLED:
        from app.core.database import get_cluster_db, get_api_key_by_cluster
        c = await get_cluster_db(cluster_id)
        if not c or c["org_id"] != user["org_id"]:
            raise HTTPException(404, "Cluster not found")
        key_record = await get_api_key_by_cluster(cluster_id)
        api_key = key_record["key_hash"] if key_record else "<YOUR_API_KEY>"
    else:
        info = _clusters_store.get(cluster_id)
        if not info:
            raise HTTPException(404, "Cluster not found")
        api_key = info.get('api_key', '<YOUR_API_KEY>')

    return {"install_command": (
        f"helm install kubemind-agent kubemind/kubemind-agent "
        f"--set agent.apiKey={api_key} "
        f"--set agent.backendUrl=ws://<YOUR_HOST>:8000/ws/agent "
        f"--set agent.clusterId={cluster_id} "
        f"--namespace kubemind-agent --create-namespace"
    )}


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT WEBSOCKET
# ═══════════════════════════════════════════════════════════════════════════════

@app.websocket("/ws/logs/{namespace}/{pod_name}")
async def pod_logs_ws(ws: WebSocket, namespace: str, pod_name: str):
    token = ws.query_params.get("token")
    if not token:
        await ws.close(code=4001, reason="Missing token")
        return
    
    try:
        user = decode_token(token)
    except HTTPException:
        await ws.close(code=4001, reason="Invalid token")
        return

    await ws.accept()
    from kubernetes import client
    try:
        core_v1 = client.CoreV1Api()
        # Ensure pod exists
        core_v1.read_namespaced_pod(name=pod_name, namespace=namespace)
    except Exception as e:
        await ws.send_text(f"Error accessing pod: {e}")
        await ws.close()
        return

    main_loop = asyncio.get_running_loop()
    def tail_logs():
        try:
            from kubernetes.watch import Watch
            w = Watch()
            for line in w.stream(core_v1.read_namespaced_pod_log, name=pod_name, namespace=namespace, tail_lines=100, follow=True):
                # We need to send this to the main loop
                asyncio.run_coroutine_threadsafe(ws.send_text(line), main_loop)
        except Exception as e:
            pass

    log_task = asyncio.create_task(asyncio.to_thread(tail_logs))
    
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        log_task.cancel()

@app.websocket("/ws/agent")
async def agent_ws(ws: WebSocket):
    api_key = ws.query_params.get("api_key", "")
    
    if settings.DB_ENABLED:
        from app.core.database import get_api_key
        key_record = await get_api_key(api_key)
        if not key_record:
            await ws.close(code=4001, reason="Invalid API key")
            return
        cluster_id = key_record["cluster_id"]
    else:
        cluster_id = _api_keys_store.get(api_key)
        if not cluster_id:
            await ws.close(code=4001, reason="Invalid API key")
            return

    # Ensure cluster is registered in the manager (survives restarts)
    if not cluster_manager.get_cluster(cluster_id):
        cluster_manager.register_agent_cluster(cluster_id, f"cluster-{cluster_id[:8]}", "agent")
    await manager.connect_agent(cluster_id, ws)
    logger.info(f"Agent connected: cluster={cluster_id}")

    try:
        while True:
            data = await ws.receive_text()
            try:
                msg = json.loads(data)
                msg_type = msg.get("type", "")
                if msg_type == "heartbeat":
                    cluster_manager.update_agent_heartbeat(cluster_id, msg.get("agent_info"))
                    await ws.send_text(json.dumps({"type": "heartbeat_ack"}))
                elif msg_type == "metrics":
                    # Agent pushing metrics — broadcast to dashboard clients
                    from app.core.event_bus import publish_metrics
                    asyncio.create_task(publish_metrics(msg.get("data", {}), cluster_id))
                    # Also update cached metrics and broadcast to dashboard WebSocket clients
                    agent_data = msg.get("data", {}).get("metrics", [])
                    if agent_data:
                        _cached_metrics = agent_data
                        asyncio.create_task(_broadcast_agent_data(agent_data))
                elif msg_type == "topology":
                    from app.core.event_bus import publish_topology
                    asyncio.create_task(publish_topology(msg.get("data", {}), cluster_id))
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        manager.disconnect_agent(cluster_id)
        logger.info(f"Agent disconnected: cluster={cluster_id}")


# ═══════════════════════════════════════════════════════════════════════════════
# DASHBOARD WEBSOCKET
# ═══════════════════════════════════════════════════════════════════════════════

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    token = ws.query_params.get("token")
    if not token:
        await ws.close(code=4001, reason="Missing token")
        return

    try:
        user = decode_token(token)
    except HTTPException:
        await ws.close(code=4001, reason="Invalid token")
        return

    # Accept FIRST — before any send/receive
    await ws.accept()
    manager.active.append(ws)
    logger.info("WebSocket accepted")

    # Send initial snapshot
    try:
        raw = _cached_metrics
        if raw is None:
            try:
                raw = await asyncio.wait_for(collect_all_metrics(), timeout=30)
            except asyncio.TimeoutError:
                raw = []
        payload_dict = await _build_payload(raw)
        await ws.send_text(json.dumps(payload_dict, default=str))
    except (WebSocketDisconnect, RuntimeError):
        # Client disconnected during the slow _build_payload — exit cleanly
        manager.disconnect(ws)
        return
    except Exception as e:
        logger.warning(f"Initial snapshot error: {e}")

    # Receive loop
    try:
        while True:
            data = await ws.receive_text()
            try:
                cmd = json.loads(data)
                action = cmd.get("action")
                if action == "inject_fault":
                    ok = inject_fault(cmd["service"], cmd["fault_type"], cmd.get("duration", 120))
                    await ws.send_text(json.dumps({"type": "FAULT_ACK", "success": ok, **cmd}))
                elif action == "clear_fault":
                    ok = clear_fault(cmd["service"])
                    await ws.send_text(json.dumps({"type": "FAULT_ACK", "success": ok, **cmd}))
                elif action == "ai_query":
                    resp = await _run_ai_query(cmd.get("query", ""))
                    await ws.send_text(json.dumps({"type": "AI_RESPONSE", **resp}))
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except RuntimeError:
        logger.info("WebSocket client disconnected during initial snapshot")
    except Exception:
        logger.exception("WebSocket error")
    finally:
        manager.disconnect(ws)


# ── AI Query ──────────────────────────────────────────────────────────────────
async def _run_ai_query(query: str) -> Dict[str, Any]:
    raw = _cached_metrics or await collect_all_metrics()
    anomaly_ctx = []
    for m in raw:
        det = await ml_client.detect_anomaly(m["service"], m)
        if det.get("is_anomaly"):
            anomaly_ctx.append(f"{m['service']} ({m['namespace']}): {det.get('anomaly_types', [])}")
    summary = get_cluster_summary(raw)
    context = f"Anomalies: {'; '.join(anomaly_ctx) or 'None'}. Health: {summary['cluster_health']}. Pods: {summary['total_services']}"
    res = await ai_client.ai_query(query, context)
    return {"query": query, "response": res.get("response", "No response."),
            "context": context, "source": res.get("source", "unknown")}


# ═══════════════════════════════════════════════════════════════════════════════
# REST API
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/v1/health")
async def health():
    return {"status": "ok", "ts": datetime.now(timezone.utc).isoformat(),
            "version": settings.APP_VERSION, "db_enabled": settings.DB_ENABLED,
            "ws_clients": len(manager.active), "clusters": cluster_manager.cluster_count,
            "healthy_clusters": cluster_manager.healthy_count,
            "agents_connected": len(manager.agent_connections)}

@app.get("/metrics", response_class=PlainTextResponse)
async def prometheus_metrics():
    raw = _cached_metrics or await collect_all_metrics()
    for m in raw:
        pod, ns = m["service"], m["namespace"]
        PROM_CPU.labels(pod=pod, namespace=ns).set(m["cpu_percent"])
        PROM_MEM.labels(pod=pod, namespace=ns).set(m["memory_mb"])
        PROM_NET_IN.labels(pod=pod, namespace=ns).set(m.get("network_in_kbps", 0))
        PROM_NET_OUT.labels(pod=pod, namespace=ns).set(m.get("network_out_kbps", 0))
        PROM_RESTARTS.labels(pod=pod, namespace=ns).set(m["restart_count"])
        PROM_PVC.labels(pod=pod, namespace=ns).set(m.get("pvc_usage_percent", 0))
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.get("/api/v1/cluster/summary")
async def cluster_summary():
    raw = _cached_metrics or await collect_all_metrics()
    return get_cluster_summary(raw)

@app.get("/api/v1/metrics")
async def all_metrics():
    raw = await collect_all_metrics()
    for m in raw:
        svc = m["service"]
        m["anomaly"] = await ml_client.detect_anomaly(svc, m)
        m["prediction"] = await ml_client.predict_failure(svc, m)
        m["recommendations"] = await ai_client.get_recommendations(m["anomaly"], m["prediction"])
    return raw

@app.get("/api/v1/metrics/{service}")
async def service_metrics(service: str):
    raw = _cached_metrics or await collect_all_metrics()
    for m in raw:
        if m["service"] == service:
            m["anomaly"] = await ml_client.detect_anomaly(service, m)
            m["prediction"] = await ml_client.predict_failure(service, m)
            m["recommendations"] = await ai_client.get_recommendations(m["anomaly"], m["prediction"])
            m["history"] = get_metric_history(service)
            return m
    raise HTTPException(404, "Pod not found")

@app.get("/api/v1/services")
async def list_services():
    raw = _cached_metrics or await collect_all_metrics()
    return [{"service": m["service"], "namespace": m["namespace"], "node_name": m.get("node_name", ""),
             "status": m["status"], "replicas": m["replicas"], "domain": m.get("domain", m["namespace"])} for m in raw]

@app.get("/api/v1/topology")
async def topology():
    return build_live_topology()

@app.get("/api/v1/namespaces")
async def namespaces():
    raw = _cached_metrics or await collect_all_metrics()
    return list({m["namespace"] for m in raw})

@app.get("/api/v1/anomalies")
async def live_anomalies():
    raw = _cached_metrics or await collect_all_metrics()
    result = []
    for m in raw:
        det = await ml_client.detect_anomaly(m["service"], m)
        if det.get("is_anomaly"):
            result.append({**det, "domain": m.get("domain", m["namespace"]), "namespace": m["namespace"]})
    return result

@app.get("/api/v1/anomalies/history")
async def anomaly_history(limit: int = Query(50)):
    if settings.DB_ENABLED:
        from app.core.database import get_recent_anomalies
        return await get_recent_anomalies(limit)
    return []

@app.get("/api/v1/rca")
async def root_cause_analysis():
    raw = _cached_metrics or await collect_all_metrics()
    anomalies = []
    for m in raw:
        det = await ml_client.detect_anomaly(m["service"], m)
        if det.get("is_anomaly"):
            anomalies.append({**det, "domain": m.get("domain", m["namespace"]), "namespace": m["namespace"]})
    return await ai_client.perform_rca(anomalies, raw)

@app.get("/api/v1/events")
async def cluster_events():
    return _collect_events()

@app.get("/api/v1/nodes")
async def cluster_nodes():
    return _collect_node_metrics()

@app.get("/api/v1/insights")
async def ai_insights():
    """Get AI agent insights from all specialized agents."""
    raw = _cached_metrics or await collect_all_metrics()
    anomalies = []
    for m in raw:
        det = await ml_client.detect_anomaly(m["service"], m)
        if det.get("is_anomaly"):
            anomalies.append({**det, "namespace": m["namespace"]})
    topology = build_live_topology()
    return agent_coordinator.analyze_all(raw, anomalies, topology)

@app.get("/api/v1/correlation")
async def correlation_analysis():
    """Get cross-metric correlation intelligence."""
    raw = _cached_metrics or await collect_all_metrics()
    anomalies = []
    for m in raw:
        det = await ml_client.detect_anomaly(m["service"], m)
        if det.get("is_anomaly"):
            anomalies.append({**det, "namespace": m["namespace"]})
    return correlation_engine.analyze(raw, anomalies)

@app.get("/api/v1/health-score")
async def cluster_health_score():
    """Get cluster health score with factor breakdown."""
    raw = _cached_metrics or await collect_all_metrics()
    return correlation_engine.get_health_score(raw)

@app.get("/api/v1/exhaustion")
async def exhaustion_predictions():
    """Get resource exhaustion predictions."""
    raw = _cached_metrics or await collect_all_metrics()
    return correlation_engine.get_exhaustion_predictions(raw)

@app.get("/api/v1/faults")
async def active_faults():
    return list_faults()

@app.post("/api/v1/fault/inject")
async def fault_inject(service: str = Query(...), fault_type: str = Query(...), duration: int = Query(120)):
    valid = {"cpu_spike", "memory_leak", "restart_loop", "network_congestion", "storage_overload"}
    if fault_type not in valid:
        raise HTTPException(400, f"Invalid. Choose from: {valid}")
    ok = inject_fault(service, fault_type, duration)
    if not ok:
        raise HTTPException(500, f"Failed to inject fault: deployment '{service}' not found")
    return {"status": "injected", "service": service, "fault_type": fault_type}

@app.post("/api/v1/fault/clear")
async def fault_clear(service: str = Query(...)):
    ok = clear_fault(service)
    return {"status": "cleared" if ok else "not_found", "service": service}

@app.post("/api/v1/ai/query")
async def ai_query_route(body: Dict[str, Any] = Body(...)):
    query = body.get("query", "").strip()
    if not query:
        raise HTTPException(400, "query field required")
    return await _run_ai_query(query)

# ── Live Kubernetes API Proxies (production validation) ─────────────
@app.get("/api/pods")
async def api_pods():
    """Live pod list from Kubernetes — no mock data."""
    pods = _collect_pods()
    return [{
        "name": p["name"], "namespace": p["namespace"],
        "node": p.get("node_name", ""), "status": p["status"],
        "restart_count": p.get("restart_count", 0),
        "ready_containers": p.get("ready_containers", 0),
        "total_containers": p.get("total_containers", 1),
        "creation_timestamp": str(p.get("creation_timestamp", "")),
        "labels": p.get("labels", {}),
    } for p in pods]

@app.get("/api/services")
async def api_services():
    """Live service list from Kubernetes."""
    return _collect_services()

@app.get("/api/namespaces")
async def api_namespaces():
    """Live namespace list from Kubernetes."""
    from app.core.k8s_collector import _core_v1
    try:
        if _core_v1:
            items = _core_v1.list_namespace().items
            return sorted([ns.metadata.name for ns in items])
    except Exception:
        pass
    namespaces = set()
    for m in (_cached_metrics or []):
        ns = m.get("namespace", "")
        if ns:
            namespaces.add(ns)
    return sorted(list(namespaces))

@app.get("/api/pvcs")
async def api_pvcs():
    """Live PVC list from Kubernetes."""
    return _collect_pvcs()

@app.get("/api/events")
async def api_events_live():
    """Live K8s warning events."""
    return _collect_events()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT,
                reload=settings.DEBUG, log_level="info")
