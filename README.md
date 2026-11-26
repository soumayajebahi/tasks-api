# Tasks API

![CI](https://github.com/soumayajebahi/tasks-api/actions/workflows/ci.yml/badge.svg)

A small REST API to manage tasks, built to practice DevOps end to end: version control, CI/CD, containers, Kubernetes, observability and security scanning.

## Features

- REST API (FastAPI, under 150 lines): create, list, read and delete tasks
- Prometheus metrics, structured JSON logs and OpenTelemetry tracing
- GitHub Actions pipeline: tests, SAST (Bandit), Docker build and push, deployment to Kubernetes (kind) and DAST (OWASP ZAP)
- Docker image published on Docker Hub: `soumayajbh/tasks-api`
- Kubernetes manifests (Deployment with probes, Service)
- Monitoring stack with Prometheus and Grafana (docker compose)

## Architecture

```text
Developer -> GitHub (issues, pull requests, reviews)
          -> GitHub Actions (tests, SAST, build, push, deploy to kind, DAST)
          -> Docker Hub (image)
          -> Kubernetes (kind)

Prometheus scrapes /metrics from the API, Grafana displays the dashboard.
```

## Prerequisites

Python 3.12, Git, Docker Desktop, kubectl and kind.

## Run locally

```powershell
git clone https://github.com/soumayajebahi/tasks-api.git
cd tasks-api
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

On Linux or macOS, activate the environment with `source .venv/bin/activate`.

Interactive API documentation: http://localhost:8000/docs

## Run the tests

```powershell
pytest -v
ruff check app tests
```

## Docker

Build and run the image:

```powershell
docker build -t tasks-api:local .
docker run --rm -p 8000:8000 tasks-api:local
```

Use the published image instead:

```powershell
docker run --rm -p 8000:8000 soumayajbh/tasks-api:latest
```

Run the API with Prometheus and Grafana:

```powershell
docker compose up --build -d
```

| Service | URL |
| --- | --- |
| API | http://localhost:8000 |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000 (admin / admin) |

Stop everything with `docker compose down`.

## Kubernetes (kind)

```powershell
kind create cluster --name devops
kubectl apply -f k8s/
kubectl rollout status deployment/tasks-api
kubectl get pods
kubectl port-forward svc/tasks-api 8080:80
```

The API is then available on http://localhost:8080. Delete the cluster with `kind delete cluster --name devops`.

## API examples

| Method | Route | Description |
| --- | --- | --- |
| GET | /health | Health check, used by the probes |
| GET | /metrics | Prometheus metrics |
| GET | /tasks | List tasks |
| POST | /tasks | Create a task |
| GET | /tasks/{id} | Get a task |
| DELETE | /tasks/{id} | Delete a task |

```powershell
curl.exe http://localhost:8000/health
curl.exe -X POST http://localhost:8000/tasks -H "Content-Type: application/json" -d "{\"title\": \"Learn DevOps\"}"
curl.exe http://localhost:8000/tasks
curl.exe http://localhost:8000/tasks/1
curl.exe -X DELETE http://localhost:8000/tasks/1
```

## Observability

- **Metrics**: `/metrics` exposes `http_requests_total` (counter) and `http_request_duration_seconds` (histogram). The Grafana dashboard `monitoring/dashboard.json` shows requests per second per route, errors, p95 latency and the total number of requests. Import it in Grafana with Dashboards, New, Import, and select the Prometheus data source.
- **Logs**: one JSON line per request on stdout (method, path, status, duration, `trace_id`). Unhandled errors are logged with their stack trace.
- **Tracing**: OpenTelemetry spans are printed on stdout. The `trace_id` in the logs matches the `trace_id` of the spans.

## CI/CD

The workflow `.github/workflows/ci.yml` runs on every push and pull request to `main`.

| Job | What it does |
| --- | --- |
| Tests et lint | `ruff` and `pytest` |
| SAST (Bandit) | Static scan of the code, report uploaded as an artifact |
| Build et push de l'image | Builds the image; pushes it to Docker Hub only on `main`, tagged `latest` and with the commit SHA |
| Deploy to kind and DAST (ZAP) | Only on `main`: creates a kind cluster, deploys the image of the commit and runs an OWASP ZAP API scan, report uploaded as an artifact |

Required repository secrets: `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN`.

The ZAP scan uses host networking, which works on the Linux runner. On Docker Desktop, use `host.docker.internal` as the target instead of `localhost`.

## Security

- **SAST**: Bandit analyses `app/` in the pipeline (medium and high severity).
- **DAST**: OWASP ZAP scans the API deployed in kind. Reports are kept in `docs/`.

| Level | Before the fix | After the fix |
| --- | --- | --- |
| High | 0 | 0 |
| Medium | 0 | 0 |
| Low | 2 | 0 |
| Informational | 3 | 2 |

The two low alerts were missing HTTP security headers. A middleware now sets `X-Content-Type-Options: nosniff`, `Cross-Origin-Resource-Policy: same-origin` and `Cache-Control: no-store`, and a test protects this behaviour. Reports: `docs/zap-report-before.html` and `docs/zap-report-after.html`.

## Known limitations

- Tasks are stored in memory: they are lost on restart, and each replica has its own list. The Deployment therefore uses a single replica. A production version would use a shared database.
- The Kubernetes manifest uses the `latest` tag for simplicity; the pipeline deploys the commit SHA tag.
- The Grafana credentials are the defaults and the dashboard is not stored in a volume.
- `same-origin` blocks a front-end hosted on another origin.

## Development workflow

Work is split into GitHub issues tracked in a GitHub Project board. Each issue has its own branch and pull request, which is reviewed by a classmate before a squash merge.

## Project structure

```text
app/             FastAPI application
tests/           pytest tests
k8s/             Kubernetes manifests
monitoring/      Prometheus, Grafana datasource and dashboard
docs/            ZAP reports
.github/         CI/CD workflow
Dockerfile
docker-compose.yml
```

