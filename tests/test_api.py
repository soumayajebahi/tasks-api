from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_and_get_task():
    response = client.post("/tasks", json={"title": "Learn DevOps"})
    assert response.status_code == 201
    task_id = response.json()["id"]

    response = client.get(f"/tasks/{task_id}")
    assert response.status_code == 200
    assert response.json()["title"] == "Learn DevOps"


def test_get_unknown_task_returns_404():
    assert client.get("/tasks/9999").status_code == 404


def test_empty_title_is_rejected():
    assert client.post("/tasks", json={"title": ""}).status_code == 422


def test_delete_task():
    task_id = client.post("/tasks", json={"title": "temporary"}).json()["id"]
    assert client.delete(f"/tasks/{task_id}").status_code == 204
    assert client.get(f"/tasks/{task_id}").status_code == 404


def test_metrics_endpoint_exposes_request_counter():
    client.get("/health")
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "http_requests_total" in response.text


def test_delete_unknown_task_returns_404():
    assert client.delete("/tasks/9999").status_code == 404


def test_too_long_title_is_rejected():
    assert client.post("/tasks", json={"title": "x" * 101}).status_code == 422


def test_security_headers_are_set():
    response = client.get("/health")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["cross-origin-resource-policy"] == "same-origin"
    assert response.headers["cache-control"] == "no-store"


def test_security_headers_are_set_on_errors():
    response = client.get("/tasks/9999")
    assert response.status_code == 404
    assert response.headers["x-content-type-options"] == "nosniff"
