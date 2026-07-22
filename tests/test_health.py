from fastapi.testclient import TestClient

from latch.main import app


def test_health_endpoint() -> None:
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "service": "Latch",
        "version": "0.1.0",
        "status": "healthy",
    }
