from __future__ import annotations

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from pr_viewer.factory import create_app

BB_URL = "http://bitbucket.example.com"
BB_DIFF_URL = f"{BB_URL}/rest/api/1.0/projects/PROJECT/repos/repo/compare/diff"


def make_client(
    monkeypatch: pytest.MonkeyPatch,
    *,
    set_url: bool = True,
    set_token: bool = True,
    url: str = BB_URL,
    token: str = "test-token",
) -> TestClient:
    if set_url:
        monkeypatch.setenv("BITBUCKET_URL", url)
    else:
        monkeypatch.delenv("BITBUCKET_URL", raising=False)
    if set_token:
        monkeypatch.setenv("BITBUCKET_TOKEN", token)
    else:
        monkeypatch.delenv("BITBUCKET_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    app = create_app()
    return TestClient(app)


def bb_response(diffs: list[dict], is_last_page: bool = True) -> dict:
    return {"diffs": diffs, "isLastPage": is_last_page}


def bb_diff(
    src: str | None, dst: str | None, hunks: list[dict] | None = None, truncated: bool = False
) -> dict:
    return {
        "source": {"toString": src} if src else None,
        "destination": {"toString": dst} if dst else None,
        "hunks": hunks or [],
        "truncated": truncated,
    }


def make_hunk() -> dict:
    return {
        "sourceLine": 1,
        "sourceSpan": 3,
        "destinationLine": 1,
        "destinationSpan": 4,
        "segments": [
            {"type": "CONTEXT", "lines": [{"source": 1, "destination": 1, "line": "context line"}]},
            {"type": "REMOVED", "lines": [{"source": 2, "destination": 0, "line": "old line"}]},
            {"type": "ADDED", "lines": [{"source": 0, "destination": 2, "line": "new line"}]},
        ],
    }


@respx.mock
def test_valid_diff(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client(monkeypatch)
    respx.get(BB_DIFF_URL).mock(
        return_value=httpx.Response(
            200,
            json=bb_response([bb_diff("file.py", "file.py", [make_hunk()])]),
        )
    )

    response = client.get(
        "/api/compare?provider=bitbucket&repo=PROJECT/repo&base=main&head=feature"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_files"] == 1
    assert data["files"][0]["status"] == "modified"
    assert data["files"][0]["path"] == "file.py"
    assert "---" in data["files"][0]["diff"]
    assert "+++" in data["files"][0]["diff"]


@respx.mock
def test_added_file(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client(monkeypatch)
    respx.get(BB_DIFF_URL).mock(
        return_value=httpx.Response(
            200,
            json=bb_response([bb_diff(None, "new.py")]),
        )
    )

    response = client.get(
        "/api/compare?provider=bitbucket&repo=PROJECT/repo&base=main&head=feature"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["files"][0]["status"] == "added"
    assert "/dev/null" in data["files"][0]["diff"] or data["files"][0]["diff"] == ""


@respx.mock
def test_deleted_file(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client(monkeypatch)
    respx.get(BB_DIFF_URL).mock(
        return_value=httpx.Response(
            200,
            json=bb_response([bb_diff("old.py", None)]),
        )
    )

    response = client.get(
        "/api/compare?provider=bitbucket&repo=PROJECT/repo&base=main&head=feature"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["files"][0]["status"] == "deleted"


@respx.mock
def test_renamed_file(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client(monkeypatch)
    respx.get(BB_DIFF_URL).mock(
        return_value=httpx.Response(
            200,
            json=bb_response([bb_diff("old.py", "new.py")]),
        )
    )

    response = client.get(
        "/api/compare?provider=bitbucket&repo=PROJECT/repo&base=main&head=feature"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["files"][0]["status"] == "renamed"
    assert data["files"][0]["path"] == "new.py"


def test_missing_bitbucket_url(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client(monkeypatch, set_url=False)
    response = client.get(
        "/api/compare?provider=bitbucket&repo=PROJECT/repo&base=main&head=feature"
    )
    assert response.status_code == 503
    assert "not configured" in response.json()["detail"]


def test_invalid_bitbucket_url(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client(monkeypatch, url="not-a-url")
    response = client.get(
        "/api/compare?provider=bitbucket&repo=PROJECT/repo&base=main&head=feature"
    )
    assert response.status_code == 503
    assert "not a valid URL" in response.json()["detail"]


def test_missing_token(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client(monkeypatch, set_token=False)
    response = client.get(
        "/api/compare?provider=bitbucket&repo=PROJECT/repo&base=main&head=feature"
    )
    assert response.status_code == 503
    assert "BITBUCKET_TOKEN" in response.json()["detail"]


def test_invalid_repo_format(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client(monkeypatch)
    response = client.get("/api/compare?provider=bitbucket&repo=invalid&base=main&head=feature")
    assert response.status_code == 400
    assert "Invalid repo format" in response.json()["detail"]


@respx.mock
def test_auth_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client(monkeypatch)
    respx.get(BB_DIFF_URL).mock(return_value=httpx.Response(401))

    response = client.get(
        "/api/compare?provider=bitbucket&repo=PROJECT/repo&base=main&head=feature"
    )
    assert response.status_code == 401
    assert "Authentication failed" in response.json()["detail"]


@respx.mock
def test_repo_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client(monkeypatch)
    respx.get(BB_DIFF_URL).mock(return_value=httpx.Response(404, text="Repository does not exist"))

    response = client.get(
        "/api/compare?provider=bitbucket&repo=PROJECT/repo&base=main&head=feature"
    )
    assert response.status_code == 404
    assert "Repository not found" in response.json()["detail"]


@respx.mock
def test_ref_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client(monkeypatch)
    respx.get(BB_DIFF_URL).mock(return_value=httpx.Response(404, text="Ref does not exist"))

    response = client.get(
        "/api/compare?provider=bitbucket&repo=PROJECT/repo&base=main&head=feature"
    )
    assert response.status_code == 404
    assert "Ref not found" in response.json()["detail"]


@respx.mock
def test_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client(monkeypatch)
    respx.get(BB_DIFF_URL).mock(side_effect=httpx.TimeoutException("timed out"))

    response = client.get(
        "/api/compare?provider=bitbucket&repo=PROJECT/repo&base=main&head=feature"
    )
    assert response.status_code == 504


@respx.mock
def test_connection_error(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client(monkeypatch)
    respx.get(BB_DIFF_URL).mock(side_effect=httpx.ConnectError("connection refused"))

    response = client.get(
        "/api/compare?provider=bitbucket&repo=PROJECT/repo&base=main&head=feature"
    )
    assert response.status_code == 502
    assert "Cannot reach" in response.json()["detail"]


@respx.mock
def test_truncated_diff(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client(monkeypatch)
    respx.get(BB_DIFF_URL).mock(
        return_value=httpx.Response(
            200,
            json=bb_response([bb_diff("file.py", "file.py", truncated=True)]),
        )
    )

    response = client.get(
        "/api/compare?provider=bitbucket&repo=PROJECT/repo&base=main&head=feature"
    )
    assert response.status_code == 200
    assert response.json()["truncated"] is True


def test_unknown_provider_now_includes_bitbucket(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    app = create_app()
    client = TestClient(app)
    response = client.get("/api/compare?provider=unknown&repo=x/y&base=main&head=feature")
    assert response.status_code == 400
    assert "bitbucket" in response.json()["detail"]


@respx.mock
def test_github_unaffected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    app = create_app()
    client = TestClient(app)
    respx.get("https://api.github.com/repos/owner/repo/compare/main...feature").mock(
        return_value=httpx.Response(
            200,
            json={
                "truncated": False,
                "files": [
                    {"filename": "a.py", "status": "added", "patch": "+hello"},
                ],
            },
        )
    )

    response = client.get("/api/compare?provider=github&repo=owner/repo&base=main&head=feature")
    assert response.status_code == 200
    data = response.json()
    assert data["total_files"] == 1
