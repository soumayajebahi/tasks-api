import itertools
import json
import logging
import time
from typing import Dict

from fastapi import FastAPI, HTTPException, Request, Response
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pydantic import BaseModel, Field


# --- Logs structures : chaque ligne de log est un objet JSON ---
class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data = {
            "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "message": record.getMessage(),
        }
        data.update(getattr(record, "fields", {}))
        if record.exc_info:
            data["exception"] = self.formatException(record.exc_info)
        return json.dumps(data)


handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
logger = logging.getLogger("tasks-api")
logger.setLevel(logging.INFO)
logger.addHandler(handler)
logger.propagate = False

# --- Tracing : une trace par requete, affichee sur la sortie standard ---
provider = TracerProvider(resource=Resource.create({"service.name": "tasks-api"}))
provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
trace.set_tracer_provider(provider)
tracer = trace.get_tracer("tasks-api")

# --- Metriques Prometheus ---
REQUESTS = Counter(
    "http_requests_total", "Nombre de requetes HTTP", ["method", "path", "status"]
)
LATENCY = Histogram(
    "http_request_duration_seconds", "Duree des requetes (s)", ["method", "path"]
)


# --- Modeles et stockage en memoire ---
class TaskIn(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    done: bool = False


class Task(TaskIn):
    id: int


tasks: Dict[int, Task] = {}
ids = itertools.count(1)

app = FastAPI(title="Tasks API", version="1.0.0")


@app.middleware("http")
async def observe(request: Request, call_next):
    start = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    except Exception:
        logger.exception("unhandled error", extra={"fields": {"path": request.url.path}})
        raise
    finally:
        duration = time.perf_counter() - start
        route = request.scope.get("route")
        path = route.path if route else "unknown"
        REQUESTS.labels(request.method, path, str(status)).inc()
        LATENCY.labels(request.method, path).observe(duration)
        trace_id = format(trace.get_current_span().get_span_context().trace_id, "032x")
        logger.info("request", extra={"fields": {
            "method": request.method, "path": request.url.path, "status": status,
            "duration_ms": round(duration * 1000, 2), "trace_id": trace_id}})


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/tasks", response_model=list[Task])
def list_tasks():
    return list(tasks.values())


@app.post("/tasks", response_model=Task, status_code=201)
def create_task(body: TaskIn):
    with tracer.start_as_current_span("create_task") as span:
        task = Task(id=next(ids), **body.model_dump())
        tasks[task.id] = task
        span.set_attribute("task.id", task.id)
    logger.info("task created", extra={"fields": {"task_id": task.id}})
    return task


@app.get("/tasks/{task_id}", response_model=Task)
def get_task(task_id: int):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    return tasks[task_id]


@app.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: int):
    if tasks.pop(task_id, None) is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return Response(status_code=204)


# Doit rester en dernier : ajoute le middleware OpenTelemetry autour de tout le reste
FastAPIInstrumentor.instrument_app(app)
