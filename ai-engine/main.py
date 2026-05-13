"""
KubeMind — AI Engine Main (Real Kubernetes Edition)
"""
from fastapi import FastAPI, HTTPException, Body
from typing import Dict, Any, List
import logging
import os

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource

from rca_engine import rca_engine
from recommendation_engine import recommendation_engine
from ollama_client import ollama_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("kubemind.ai-engine")

app = FastAPI(title="KubeMind AI Engine", version="2.0.0")

# ── OpenTelemetry Setup ───────────────────────────────────────────────────────
resource = Resource.create({"service.name": "kubemind-ai-engine"})
tracer_provider = TracerProvider(resource=resource)
otlp_exporter = OTLPSpanExporter(endpoint=os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317"), insecure=True)
tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
trace.set_tracer_provider(tracer_provider)
FastAPIInstrumentor.instrument_app(app)


@app.get("/health")
def health():
    return {"status": "ok", "service": "ai-engine", "mode": "real-kubernetes"}


@app.post("/api/v1/rca")
def perform_rca(body: Dict[str, Any] = Body(...)):
    anomalies = body.get("anomalies", [])
    metrics   = body.get("metrics", [])
    topology  = body.get("topology")          # NEW: live topology passed in
    return rca_engine.analyze(anomalies, metrics, topology=topology)


@app.post("/api/v1/recommend")
def get_recommendations(body: Dict[str, Any] = Body(...)):
    anomaly    = body.get("anomaly", {})
    prediction = body.get("prediction", {})
    return recommendation_engine.generate(anomaly, prediction)


@app.post("/api/v1/query")
async def ai_query(body: Dict[str, Any] = Body(...)):
    query   = body.get("query")
    context = body.get("context", "")
    if not query:
        raise HTTPException(400, "query field is required")
    response = await ollama_client.generate_insight(context, query)
    return {"response": response, "source": "ollama" if ollama_client.enabled else "rule_engine"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8002)
