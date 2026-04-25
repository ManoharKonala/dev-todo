import os
import time
import uuid
from enum import Enum
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from prometheus_client import Counter, Histogram, Gauge, Summary, REGISTRY
from prometheus_fastapi_instrumentator import Instrumentator, metrics

# Support running directly or imported as a package
try:
    from chaos import inject_chaos, chaos_state, enable_slow, enable_errors, reset, get_status
except ImportError:
    from app.chaos import inject_chaos, chaos_state, enable_slow, enable_errors, reset, get_status

START_TIME = time.time()
APP_ENV = os.getenv("APP_ENV", "development")
APP_VERSION = os.getenv("APP_VERSION", "1.0.0")
DEPLOY_COLOR = os.getenv("DEPLOY_COLOR", "blue")
K8S_NAMESPACE = os.getenv("K8S_NAMESPACE", "default")
BUILD_NUMBER = os.getenv("BUILD_NUMBER", "local")

app = FastAPI(title="TodoFlow API", version=APP_VERSION)

base_dir = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(base_dir, "templates"))

# Define custom Prometheus metrics exactly as specified
TODOS_CREATED = Counter('todoflow_todos_created_total', 'Total todos created', ['priority'])
TODOS_DELETED = Counter('todoflow_todos_deleted_total', 'Total todos deleted')
TODOS_COMPLETED = Counter('todoflow_todos_completed_total', 'Total todos completed')
COMPLETION_RATE = Gauge('todoflow_completion_rate', 'Current completion rate 0-1')
PENDING_TODOS = Gauge('todoflow_pending_todos_total', 'Current pending todo count')
HIGH_PRIORITY = Gauge('todoflow_high_priority_pending', 'High priority pending todos')
REQUEST_LATENCY = Histogram('todoflow_request_duration_seconds', 'Request latency', ['endpoint', 'method'])
TODO_AGE = Histogram('todoflow_todo_age_seconds', 'Age of pending todos in seconds',
                     buckets=[60, 300, 900, 3600, 86400])
CHAOS_ACTIVE = Gauge('todoflow_chaos_active', 'Active chaos mode status')

# In-memory store
class Priority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"

class TodoCreate(BaseModel):
    title: str
    priority: Priority = Priority.medium

class TodoUpdate(BaseModel):
    title: Optional[str] = None
    completed: Optional[bool] = None
    priority: Optional[Priority] = None

class TodoItem(BaseModel):
    id: str
    title: str
    completed: bool
    created_at: float
    priority: Priority

todos_store: Dict[str, TodoItem] = {}

def update_gauges():
    total = len(todos_store)
    completed = sum(1 for t in todos_store.values() if t.completed)
    pending = total - completed
    high = sum(1 for t in todos_store.values() if not t.completed and t.priority == Priority.high)
    
    PENDING_TODOS.set(pending)
    HIGH_PRIORITY.set(high)
    rate = (completed / total) if total > 0 else 0.0
    COMPLETION_RATE.set(rate)
    
    now = time.time()
    for t in todos_store.values():
        if not t.completed:
            TODO_AGE.observe(now - t.created_at)
            
    if chaos_state.slow_mode or chaos_state.error_mode:
        CHAOS_ACTIVE.set(1.0)
    else:
        CHAOS_ACTIVE.set(0.0)

# Apply chaos and latency histogram middleware
@app.middleware("http")
async def custom_monitoring_and_chaos_middleware(request: Request, call_next):
    start_time = time.time()
    
    # Intercept via standalone chaos logic
    response = await inject_chaos(request, call_next)
    
    duration = time.time() - start_time
    endpoint = request.url.path
    method = request.method
    
    # Normalize paths to prevent metric cardinality explosion
    if endpoint.startswith("/todos/") and len(endpoint) > 7:
        endpoint = "/todos/{id}"
        
    REQUEST_LATENCY.labels(endpoint=endpoint, method=method).observe(duration)
    return response

# Setup Prometheus Fastapi Instrumentator with custom label function for auto-metrics
instrumentator = Instrumentator()
instrumentator.instrument(app)

# Replace auto-generated http_requests_total to inject deploy_color label dynamically
try:
    if "http_requests_total" in REGISTRY._names_to_collectors:
        REGISTRY.unregister(REGISTRY._names_to_collectors["http_requests_total"])
except Exception:
    pass

CUSTOM_HTTP_REQUESTS = Counter(
    "http_requests_total",
    "Total HTTP requests with deploy_color label",
    labelnames=("handler", "status", "method", "deploy_color")
)

def labeled_auto_metric(info: metrics.Info) -> None:
    handler = info.modified_handler
    status = str(info.response.status_code)
    method = info.request.method
    CUSTOM_HTTP_REQUESTS.labels(
        handler=handler, status=status, method=method, deploy_color=DEPLOY_COLOR
    ).inc()

instrumentator.add(labeled_auto_metric)
instrumentator.expose(app, endpoint="/metrics")

# Endpoints
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "app_env": APP_ENV,
        "app_version": APP_VERSION,
        "deploy_color": DEPLOY_COLOR,
        "build_number": BUILD_NUMBER
    })

@app.get("/todos", response_model=List[TodoItem])
async def get_todos():
    return list(todos_store.values())

@app.post("/todos", response_model=TodoItem)
async def create_todo(todo: TodoCreate):
    todo_id = str(uuid.uuid4())
    item = TodoItem(
        id=todo_id,
        title=todo.title,
        completed=False,
        created_at=time.time(),
        priority=todo.priority
    )
    todos_store[todo_id] = item
    TODOS_CREATED.labels(priority=item.priority.value).inc()
    update_gauges()
    return item

@app.put("/todos/{todo_id}", response_model=TodoItem)
async def update_todo(todo_id: str, todo_update: TodoUpdate):
    if todo_id not in todos_store:
        raise HTTPException(status_code=404, detail="Todo not found")
    
    item = todos_store[todo_id]
    was_completed = item.completed
    
    if todo_update.title is not None:
        item.title = todo_update.title
    if todo_update.completed is not None:
        item.completed = todo_update.completed
    if todo_update.priority is not None:
        item.priority = todo_update.priority
        
    if not was_completed and item.completed:
        TODOS_COMPLETED.inc()
        
    update_gauges()
    return item

@app.delete("/todos/{todo_id}")
async def delete_todo(todo_id: str):
    if todo_id not in todos_store:
        raise HTTPException(status_code=404, detail="Todo not found")
    
    del todos_store[todo_id]
    TODOS_DELETED.inc()
    update_gauges()
    return {"detail": "Todo deleted successfully", "id": todo_id}

@app.get("/health")
async def health_check():
    total = len(todos_store)
    completed = sum(1 for t in todos_store.values() if t.completed)
    rate = (completed / total) if total > 0 else 0.0
    uptime = time.time() - START_TIME
    return {
        "status": "healthy",
        "total_todos": total,
        "completed_todos": completed,
        "completion_rate": rate,
        "uptime_seconds": uptime,
        "environment": APP_ENV,
        "version": APP_VERSION
    }

@app.get("/version")
async def get_version_metadata():
    return {
        "version": APP_VERSION,
        "color": DEPLOY_COLOR,
        "namespace": K8S_NAMESPACE,
        "build_number": BUILD_NUMBER
    }

# Chaos endpoints
@app.get("/chaos/slow")
async def trigger_chaos_slow():
    enable_slow()
    update_gauges()
    return {"status": "slow_mode_enabled", "state": get_status()}

@app.get("/chaos/errors")
async def trigger_chaos_errors():
    enable_errors(10)
    update_gauges()
    return {"status": "error_mode_enabled", "state": get_status()}

@app.get("/chaos/reset")
async def trigger_chaos_reset():
    reset()
    update_gauges()
    return {"status": "chaos_reset", "state": get_status()}

@app.get("/chaos/status")
async def get_chaos_status():
    return get_status()
