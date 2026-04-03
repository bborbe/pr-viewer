from fastapi.testclient import TestClient

from pr_viewer.factory import create_app


def test_healthz() -> None:
    app = create_app()
    client = TestClient(app)
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
