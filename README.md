# TodoFlow — Industrial-Grade DevOps Pipeline

> A production-ready, containerised Todo CRUD application with a fully automated, observability-driven CI/CD pipeline implementing blue-green deployments, automated rollback gates, chaos engineering, and infrastructure as code.

---

## 1. Project Overview

TodoFlow is **not** a basic tutorial project. It implements advanced, enterprise-grade DevOps patterns that go beyond standard CI/CD:

- **Blue-Green Deployments** — zero-downtime releases with instant rollback capability
- **Automated Rollback Gates** — Prometheus-driven pipeline stages that auto-rollback failed deployments
- **Pre-Deploy Health Gates** — refuse to deploy if the current environment is already degraded
- **Chaos Engineering** — built-in fault injection (latency, errors) with real-time Grafana observability
- **Multi-Namespace Promotion** — DEV → manual approval → PROD pipeline with human-in-the-loop gates
- **Dashboard as Code** — Grafana dashboards and Prometheus alerts provisioned automatically
- **HPA Auto-Scaling** — Kubernetes horizontal pod autoscaler based on CPU/memory thresholds
- **SAST + Container Scanning** — Bandit static analysis + Trivy image vulnerability scanning

---

## 2. Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                          JENKINS CI/CD PIPELINE                              │
│                                                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────┐  ┌──────┐  ┌────────┐  ┌──────────┐  │
│  │ Checkout  │→│Pre-deploy│→│ Test  │→│ SAST │→│  Docker  │→│  Trivy   │  │
│  │          │  │  Gate    │  │      │  │Bandit│  │  Build   │→│  Scan    │  │
│  └──────────┘  └──────────┘  └──────┘  └──────┘  └────────┘  └──────────┘  │
│                                                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │
│  │ Push ECR │→│Terraform │→│Deploy DEV│→│ Rollback │→│Manual Approval│  │
│  │          │  │  Apply   │  │ (green)  │  │   Gate   │  │  (PROD gate) │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────────┘  │
│                                                                              │
│  ┌────────────────────┐  ┌────────────────────┐                              │
│  │ Deploy PROD (B/G)  │→│ Post-deploy Check  │                              │
│  │  Atomic Cutover    │  │   Health Verify    │                              │
│  └────────────────────┘  └────────────────────┘                              │
└──────────────────────────────────────────────────────────────────────────────┘
                                    │
                  ┌─────────────────┼─────────────────┐
                  ▼                 ▼                 ▼
          ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
          │  KUBERNETES  │  │  MONITORING  │  │   REGISTRY   │
          │              │  │              │  │              │
          │ ┌──────────┐ │  │ ┌──────────┐ │  │  ┌────────┐ │
          │ │  BLUE    │ │  │ │Prometheus│ │  │  │  ECR   │ │
          │ │ deploy   │ │  │ │          │ │  │  │        │ │
          │ └──────────┘ │  │ └──────────┘ │  │  └────────┘ │
          │ ┌──────────┐ │  │ ┌──────────┐ │  │  ┌────────┐ │
          │ │  GREEN   │ │  │ │ Grafana  │ │  │  │ Docker │ │
          │ │ deploy   │ │  │ │Dashboard │ │  │  │  Hub   │ │
          │ └──────────┘ │  │ └──────────┘ │  │  └────────┘ │
          │ ┌──────────┐ │  │ ┌──────────┐ │  │              │
          │ │ Service  │ │  │ │Alertmgr  │ │  │              │
          │ │ (switch) │ │  │ │          │ │  │              │
          │ └──────────┘ │  │ └──────────┘ │  │              │
          │ ┌──────────┐ │  │              │  │              │
          │ │   HPA    │ │  │              │  │              │
          │ └──────────┘ │  │              │  │              │
          └──────────────┘  └──────────────┘  └──────────────┘
```

---

## 3. Tech Stack

| Technology | Purpose | Category |
|---|---|---|
| **Python 3.11 / FastAPI** | Application runtime & REST API | Application |
| **Docker** | Containerisation & multi-stage builds | Containerisation |
| **Docker Compose** | Local multi-service orchestration | Orchestration |
| **Kubernetes / Minikube** | Production container orchestration | Orchestration |
| **Jenkins** | CI/CD pipeline automation (12 stages) | CI/CD |
| **Terraform** | Infrastructure as Code (ECR + Docker) | IaC |
| **Prometheus** | Metrics collection & alerting rules | Monitoring |
| **Grafana** | Dashboard visualisation (10 panels) | Monitoring |
| **Alertmanager** | Alert routing & notification | Monitoring |
| **Trivy** | Container image vulnerability scanning | Security |
| **Bandit** | Python SAST (Static Application Security Testing) | Security |
| **AWS ECR** | Container image registry | Registry |
| **pytest / httpx** | Async unit & integration testing | Testing |

---

## 4. Advanced Features

### Pre-Deploy Health Gate
Before any deployment, the pipeline queries Prometheus for the current 5xx error rate. If it exceeds 5%, the pipeline **refuses to deploy** — preventing you from deploying on top of a broken service.

### Automated Rollback Gate
After deploying to DEV, the pipeline waits 90 seconds for metrics to stabilise, then checks the green deployment's error rate. If elevated → **automatic rollback + build failure**. No human intervention needed.

### Blue-Green Cutover
Two identical deployments (`blue` and `green`) run in parallel. The Kubernetes Service selector points to the active color. On promotion, `promote.sh` patches the selector atomically — **zero downtime, instant rollback** by switching back.

### Chaos Engineering
Built-in fault injection via `/chaos/*` endpoints:
- **Slow mode**: Adds 2-second latency to all `/todos` requests
- **Error mode**: Returns HTTP 500 for the next 10 requests
- **Reset**: Restores normal operation
- Observable in real-time on the Grafana dashboard

### HPA Auto-Scaling
The HorizontalPodAutoscaler scales the green deployment from 2 to 5 replicas based on CPU (70%) and memory (80%) utilisation thresholds.

### Alert Rules
Four production alert rules fire automatically:
1. **HighErrorRate** — 5xx rate > 5% for 1 min (critical)
2. **SlowResponseTime** — p95 latency > 2s for 2 min (warning)
3. **LowCompletionRate** — completion rate < 10% for 5 min (info)
4. **PodDown** — service unreachable for 30s (critical)

### Dashboard as Code
The Grafana dashboard is provisioned automatically via JSON — no manual setup. 10 panels covering request rates, error rates, latency heatmaps, blue/green traffic splits, chaos status, and firing alerts.

### Multi-Namespace Promotion
DEV and PROD use separate Kubernetes namespaces with distinct ConfigMaps. The pipeline promotes through environments with a mandatory manual approval gate before production.

---

## 5. Quick Start

### Prerequisites
- Docker & Docker Compose installed
- Python 3.11+ (for local development/testing)

### Launch the full stack
```bash
docker compose up -d --build
```

### Access the services
| Service | URL |
|---|---|
| TodoFlow Blue | http://localhost:8000 |
| TodoFlow Green | http://localhost:8001 |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000 (admin/admin) |
| Alertmanager | http://localhost:9093 |

### Run tests locally
```bash
pip install -r app/requirements.txt
pytest tests/ -v
```

---

## 6. Blue-Green Deployment Guide

### How it works locally (Docker Compose)
- **Blue** runs on port `8000`, **Green** on port `8001`
- Both emit metrics with their `deploy_color` label
- Grafana shows traffic split between blue and green in real-time

### How it works in Kubernetes
1. Both `deployment-blue.yaml` and `deployment-green.yaml` run simultaneously
2. `service.yaml` initially points to `deploy_color: blue`
3. Pipeline deploys new code to **green** first
4. After health validation, `promote.sh` switches the service selector to **green**
5. Blue remains idle — instant rollback by running: `bash scripts/promote.sh todoflow-prod blue`

### Manual rollback
```bash
bash scripts/rollback.sh todoflow-prod
# or switch back to blue:
bash scripts/promote.sh todoflow-prod blue
```

---

## 7. Chaos Engineering Guide

### Enable slow mode (2s delay on all /todos requests)
```bash
curl http://localhost:8000/chaos/slow
```

### Enable error mode (next 10 /todos requests return 500)
```bash
curl http://localhost:8000/chaos/errors
```

### Check chaos status
```bash
curl http://localhost:8000/chaos/status
```

### Reset to normal
```bash
curl http://localhost:8000/chaos/reset
```

### What to observe in Grafana
1. **Error Rate panel** — spikes when error mode is active
2. **Request Latency heatmap** — shifts right when slow mode is active
3. **Active Chaos Mode stat** — shows ACTIVE/NORMAL
4. **Alert list** — HighErrorRate or SlowResponseTime alerts may fire

---

## 8. Monitoring Guide

### Dashboard Panels

| # | Panel | Metric | Purpose |
|---|---|---|---|
| 1 | Total Todos Created | `todoflow_todos_created_total` | Business KPI — total task creation volume |
| 2 | Completion Rate % | `todoflow_completion_rate * 100` | Business KPI — team productivity gauge |
| 3 | Request Rate by Color | `rate(http_requests_total[1m]) by deploy_color` | Traffic split visibility for blue-green |
| 4 | Error Rate (5xx) | `rate(http_requests_total{status=~"5.."}[1m])` | Service reliability indicator |
| 5 | Latency Distribution | `todoflow_request_duration_seconds_bucket` | Performance heatmap for latency analysis |
| 6 | High Priority Pending | `todoflow_high_priority_pending` | Business KPI — urgent task backlog |
| 7 | Blue vs Green Traffic | `rate(http_requests_total[1m]) by deploy_color` | Deployment cutover verification |
| 8 | Active Chaos Mode | `todoflow_chaos_active` | Chaos engineering status indicator |
| 9 | Todo Age Distribution | `todoflow_todo_age_seconds` | Business KPI — task staleness tracking |
| 10 | Firing Alerts | Grafana alertlist | Active alert visibility |

---

## 9. Pipeline Guide — All 12 Stages

| Stage | Agent | Purpose |
|---|---|---|
| 1. Checkout | alpine/git | Clone repo, generate build tag from commit hash |
| 2. Pre-deploy gate | curlimages/curl | Query Prometheus — block if current error rate > 5% |
| 3. Test | python:3.11-slim | Run pytest suite, publish JUnit XML results |
| 4. SAST — Bandit | python:3.11-slim | Static security scan — fail on HIGH severity findings |
| 5. Docker build | any | Multi-stage build with cache optimisation |
| 6. Trivy scan | any | Container vulnerability scan — fail on HIGH/CRITICAL |
| 7. Push to ECR | any | Tag and push to AWS ECR registry |
| 8. Terraform | hashicorp/terraform:1.8 | Init, plan, apply infrastructure changes |
| 9. Deploy DEV (green) | any | Apply green deployment to dev namespace |
| 10. Rollback gate | curlimages/curl | Wait 90s, check green error rate — auto-rollback if bad |
| 11. Manual approval | none | Human-in-the-loop production promotion gate |
| 12. Deploy PROD (B/G) | any | Apply to prod, switch service selector to green |
| 13. Post-deploy check | curlimages/curl | Verify /health and /version endpoints respond |

---

## 10. File Structure & Coverage

```
todoflow/
├── app/
│   ├── main.py              # FastAPI app, CRUD, Prometheus metrics, chaos endpoints
│   ├── chaos.py              # Chaos engineering module & middleware
│   ├── requirements.txt      # Pinned Python dependencies
│   └── templates/
│       └── index.html        # Complete UI with chaos panel & live health stats
├── tests/
│   ├── conftest.py           # Test path configuration
│   └── test_main.py          # 10 async tests (pytest + httpx)
├── Dockerfile                # Multi-stage, non-root, health-checked
├── docker-compose.yml        # 5-service local stack (blue, green, prom, grafana, alertmgr)
├── Jenkinsfile               # 12-stage observability-driven CI/CD pipeline
├── terraform/
│   ├── main.tf               # AWS ECR + Docker provider resources
│   ├── variables.tf          # Configurable infrastructure parameters
│   └── outputs.tf            # ECR URL & network ID outputs
├── k8s/
│   ├── namespace-dev.yaml    # Dev namespace with labels
│   ├── namespace-prod.yaml   # Prod namespace with labels
│   ├── deployment-blue.yaml  # Blue deployment (stable)
│   ├── deployment-green.yaml # Green deployment (canary/new)
│   ├── service.yaml          # NodePort service with color selector
│   ├── configmap-dev.yaml    # Dev environment configuration
│   ├── configmap-prod.yaml   # Prod environment configuration
│   └── hpa.yaml              # Horizontal Pod Autoscaler
├── monitoring/
│   ├── prometheus.yml        # Prometheus scrape config
│   ├── alert-rules.yml       # 4 production alert rules
│   └── grafana-provisioning/
│       ├── datasources/
│       │   └── prometheus.yml  # Auto-provisioned datasource
│       └── dashboards/
│           ├── dashboard.yml           # Dashboard provider config
│           └── todoflow-dashboard.json # 10-panel production dashboard
├── scripts/
│   ├── rollback.sh           # K8s deployment rollback
│   ├── promote.sh            # Blue-green service cutover
│   └── health-gate.sh        # Prometheus-driven health check gate
└── README.md                 # This file
```

---

## Before Running

Replace placeholder values in the following files:

| Placeholder | Replace With | Files |
|---|---|---|
| `yourdockerhub` | Your Docker Hub username | `Jenkinsfile` |
| `123456789` | Your AWS account ID | `Jenkinsfile`, `k8s/deployment-*.yaml` |
| `you/todoflow` | Your GitHub repo URL | `Jenkinsfile` |

---

## License

This project is built for educational and demonstration purposes, showcasing industrial-grade DevOps patterns on a single laptop.
