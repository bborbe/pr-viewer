from __future__ import annotations

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from pr_viewer.factory import create_app

GITHUB_COMPARE_URL = "https://api.github.com/repos/owner/repo/compare/main...feature"


def make_client(monkeypatch: pytest.MonkeyPatch, token: str = "test-token") -> TestClient:
    if token:
        monkeypatch.setenv("GITHUB_TOKEN", token)
    else:
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    app = create_app()
    return TestClient(app)


@respx.mock
def test_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client(monkeypatch)
    respx.get(GITHUB_COMPARE_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "truncated": False,
                "files": [
                    {"filename": "a.py", "status": "added", "patch": "@@ +1 @@\n+hello"},
                    {"filename": "b.py", "status": "modified", "patch": "@@ -1 +1 @@\n-old\n+new"},
                    {"filename": "c.py", "status": "removed", "patch": "@@ -1 @@\n-bye"},
                    {"filename": "d.py", "status": "renamed", "patch": ""},
                ],
            },
        )
    )

    response = client.get("/api/compare?repo=owner/repo&base=main&head=feature")
    assert response.status_code == 200
    data = response.json()
    assert data["truncated"] is False
    assert data["total_files"] == 4
    files = data["files"]
    assert files[0] == {"path": "a.py", "status": "added", "diff": "@@ +1 @@\n+hello"}
    assert files[1] == {"path": "b.py", "status": "modified", "diff": "@@ -1 +1 @@\n-old\n+new"}
    assert files[2] == {"path": "c.py", "status": "deleted", "diff": "@@ -1 @@\n-bye"}
    assert files[3] == {"path": "d.py", "status": "renamed", "diff": ""}


@respx.mock
def test_truncated_response(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client(monkeypatch)
    respx.get(GITHUB_COMPARE_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "truncated": True,
                "files": [
                    {"filename": "x.py", "status": "added", "patch": ""},
                ],
            },
        )
    )

    response = client.get("/api/compare?repo=owner/repo&base=main&head=feature")
    assert response.status_code == 200
    data = response.json()
    assert data["truncated"] is True


def test_missing_github_token(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client(monkeypatch, token="")
    response = client.get("/api/compare?repo=owner/repo&base=main&head=feature")
    assert response.status_code == 401
    assert "GITHUB_TOKEN" in response.json()["detail"]


def test_invalid_repo_format(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client(monkeypatch)
    response = client.get("/api/compare?repo=not-a-valid-repo&base=main&head=feature")
    assert response.status_code == 400


def test_invalid_base_ref(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client(monkeypatch)
    response = client.get("/api/compare?repo=owner/repo&base=ref;rm+-rf&head=feature")
    assert response.status_code == 400


def test_invalid_head_ref(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client(monkeypatch)
    response = client.get("/api/compare?repo=owner/repo&base=main&head=ref$(evil)")
    assert response.status_code == 400


@respx.mock
def test_github_401(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client(monkeypatch)
    respx.get(GITHUB_COMPARE_URL).mock(return_value=httpx.Response(401))

    response = client.get("/api/compare?repo=owner/repo&base=main&head=feature")
    assert response.status_code == 401


@respx.mock
def test_github_403(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client(monkeypatch)
    respx.get(GITHUB_COMPARE_URL).mock(return_value=httpx.Response(403))

    response = client.get("/api/compare?repo=owner/repo&base=main&head=feature")
    assert response.status_code == 429
    assert "rate limit" in response.json()["detail"]


@respx.mock
def test_github_404(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client(monkeypatch)
    respx.get(GITHUB_COMPARE_URL).mock(return_value=httpx.Response(404))

    response = client.get("/api/compare?repo=owner/repo&base=main&head=feature")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


@respx.mock
def test_github_422(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client(monkeypatch)
    respx.get(GITHUB_COMPARE_URL).mock(return_value=httpx.Response(422))

    response = client.get("/api/compare?repo=owner/repo&base=main&head=feature")
    assert response.status_code == 422
    assert "Invalid ref" in response.json()["detail"]


@respx.mock
def test_binary_file_no_patch(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client(monkeypatch)
    respx.get(GITHUB_COMPARE_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "truncated": False,
                "files": [
                    {"filename": "image.png", "status": "added"},
                ],
            },
        )
    )

    response = client.get("/api/compare?repo=owner/repo&base=main&head=feature")
    assert response.status_code == 200
    data = response.json()
    assert data["files"][0]["diff"] == ""


@respx.mock
def test_github_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client(monkeypatch)
    respx.get(GITHUB_COMPARE_URL).mock(side_effect=httpx.TimeoutException("timed out"))

    response = client.get("/api/compare?repo=owner/repo&base=main&head=feature")
    assert response.status_code == 504
    assert "timed out" in response.json()["detail"].lower()


@respx.mock
def test_github_other_error(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client(monkeypatch)
    respx.get(GITHUB_COMPARE_URL).mock(return_value=httpx.Response(500))

    response = client.get("/api/compare?repo=owner/repo&base=main&head=feature")
    assert response.status_code == 502
    assert "500" in response.json()["detail"]
