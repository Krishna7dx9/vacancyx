from fastapi.testclient import TestClient

from vacancyx.main import create_app


def test_liveness_endpoint_reports_alive() -> None:
    client = TestClient(create_app())
    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


def test_readiness_endpoint_reports_ready() -> None:
    client = TestClient(create_app())
    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
