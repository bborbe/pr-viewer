from fastapi.testclient import TestClient

from pr_viewer.factory import create_app


def test_root_serves_index_html() -> None:
    app = create_app()
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert "PR Viewer" in response.text


def test_root_contains_provider_select() -> None:
    app = create_app()
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert "provider-select" in response.text


def test_root_contains_local_option() -> None:
    app = create_app()
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert "Local" in response.text


def test_root_contains_bitbucket_option() -> None:
    app = create_app()
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert "Bitbucket Server" in response.text


def test_healthz_still_works() -> None:
    app = create_app()
    client = TestClient(app)
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
