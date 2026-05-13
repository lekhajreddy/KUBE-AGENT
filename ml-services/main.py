from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any, List
import logging
import os

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource

from anomaly_detector import anomaly_detector
from prediction_engine import prediction_engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ml-services")

app = FastAPI(title="KubeMind ML Services", version="1.0.0")

# ── OpenTelemetry Setup ───────────────────────────────────────────────────────
resource = Resource.create({"service.name": "kubemind-ml-services"})
tracer_provider = TracerProvider(resource=resource)
otlp_exporter = OTLPSpanExporter(endpoint=os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317"), insecure=True)
tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
trace.set_tracer_provider(tracer_provider)
FastAPIInstrumentor.instrument_app(app)

@app.get("/health")
def health():
    return {"status": "ok", "service": "ml-services"}

@app.post("/api/v1/detect")
def detect_anomaly(body: Dict[str, Any] = Body(...)):
    service = body.get("service")
    if not service:
        raise HTTPException(400, "service field is required")
    # ingest and detect
    anomaly_detector.ingest(service, body)
    return anomaly_detector.detect(service, body)

@app.post("/api/v1/predict")
def predict_failure(body: Dict[str, Any] = Body(...)):
    service = body.get("service")
    if not service:
        raise HTTPException(400, "service field is required")
    prediction_engine.ingest(service, body)
    return prediction_engine.predict_failure_probability(service)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8001)
