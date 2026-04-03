from __future__ import annotations

import subprocess
from collections.abc import Generator
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest
import respx
from fastapi.testclient import TestClient

from pr_viewer.factory import create_app

_FAKE_REPO = "/workspace"
_BASE = "main"
_HEAD = "feature"
_URL = f"/api/compare?provider=local&repo={_FAKE_REPO}&base={_BASE}&head={_HEAD}"

_VALID_UNIFIED_DIFF = (
    "diff --git a/file.py b/file.py\n"
    "index 1234567..abcdefg 100644\n"
    "--- a/file.py\n"
    "+++ b/file.py\n"
    "@@ -1,3 +1,3 @@\n"
    " context\n"
    "-old line\n"
    "+new line\n"
)


def make_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    app = create_app()
    return TestClient(app)


def _ok(stdout: str = "", stderr: str = "", returncode: int = 0) -> MagicMock:
    result = MagicMock(spec=subprocess.CompletedProcess)
    result.stdout = stdout
    result.stderr = stderr
    result.returncode = returncode
    return result


@contextmanager
def mock_fs() -> Generator[None, None, None]:
    """Patch filesystem checks so tests reach subprocess logic."""
    with (
        patch("pr_viewer.providers.local.os.path.exists", return_value=True),
        patch("pr_viewer.providers.local.os.path.isdir", return_value=True),
        patch("pr_viewer.providers.local.os.path.realpath", side_effect=lambda p: p),
        patch("pr_viewer.providers.local.os.path.abspath", side_effect=lambda p: p),
    ):
        yield


def test_valid_local_diff(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client(monkeypatch)
    rev_parse_ok = _ok(stdout=".git")
    name_status_ok = _ok(stdout="M\tfile.py\n")
    diff_ok = _ok(stdout=_VALID_UNIFIED_DIFF)

    with (
        mock_fs(),
        patch(
            "pr_viewer.providers.local._run_subprocess",
            side_effect=[rev_parse_ok, name_status_ok, diff_ok],
        ),
    ):
        response = client.get(_URL)

    assert response.status_code == 200
    data = response.json()
    assert data["truncated"] is False
    assert data["total_files"] == 1
    assert data["files"][0]["path"] == "file.py"
    assert data["files"][0]["status"] == "modified"


def test_added_file(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client(monkeypatch)
    diff_content = (
        "diff --git a/new.py b/new.py\n"
        "new file mode 100644\n"
        "--- /dev/null\n"
        "+++ b/new.py\n"
        "@@ -0,0 +1 @@\n"
        "+hello\n"
    )
    with (
        mock_fs(),
        patch(
            "pr_viewer.providers.local._run_subprocess",
            side_effect=[_ok(stdout=".git"), _ok(stdout="A\tnew.py\n"), _ok(stdout=diff_content)],
        ),
    ):
        response = client.get(_URL)

    assert response.status_code == 200
    data = response.json()
    assert data["files"][0]["status"] == "added"
    assert data["files"][0]["path"] == "new.py"


def test_deleted_file(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client(monkeypatch)
    diff_content = (
        "diff --git a/old.py b/old.py\n"
        "deleted file mode 100644\n"
        "--- a/old.py\n"
        "+++ /dev/null\n"
        "@@ -1 +0,0 @@\n"
        "-bye\n"
    )
    with (
        mock_fs(),
        patch(
            "pr_viewer.providers.local._run_subprocess",
            side_effect=[_ok(stdout=".git"), _ok(stdout="D\told.py\n"), _ok(stdout=diff_content)],
        ),
    ):
        response = client.get(_URL)

    assert response.status_code == 200
    data = response.json()
    assert data["files"][0]["status"] == "deleted"
    assert data["files"][0]["path"] == "old.py"


def test_renamed_file(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client(monkeypatch)
    diff_content = (
        "diff --git a/old.py b/new.py\n"
        "similarity index 100%\n"
        "rename from old.py\n"
        "rename to new.py\n"
    )
    with (
        mock_fs(),
        patch(
            "pr_viewer.providers.local._run_subprocess",
            side_effect=[
                _ok(stdout=".git"),
                _ok(stdout="R100\told.py\tnew.py\n"),
                _ok(stdout=diff_content),
            ],
        ),
    ):
        response = client.get(_URL)

    assert response.status_code == 200
    data = response.json()
    assert data["files"][0]["status"] == "renamed"
    assert data["files"][0]["path"] == "new.py"


def test_relative_path(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client(monkeypatch)
    response = client.get("/api/compare?provider=local&repo=relative/path&base=main&head=feature")
    assert response.status_code == 400
    assert "absolute" in response.json()["detail"]


def test_nonexistent_path(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client(monkeypatch)
    with patch("pr_viewer.providers.local.os.path.exists", return_value=False):
        response = client.get(
            "/api/compare?provider=local&repo=/does/not/exist&base=main&head=feature"
        )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_not_a_directory(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client(monkeypatch)
    with (
        patch("pr_viewer.providers.local.os.path.exists", return_value=True),
        patch("pr_viewer.providers.local.os.path.isdir", return_value=False),
    ):
        response = client.get("/api/compare?provider=local&repo=/some/file&base=main&head=feature")
    assert response.status_code == 400
    assert "directory" in response.json()["detail"].lower()


def test_not_a_git_repo(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client(monkeypatch)
    with (
        mock_fs(),
        patch(
            "pr_viewer.providers.local._run_subprocess",
            return_value=_ok(returncode=128, stderr="not a git repository"),
        ),
    ):
        response = client.get(_URL)

    assert response.status_code == 400
    assert "git repository" in response.json()["detail"].lower()


def test_git_not_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client(monkeypatch)
    with (
        mock_fs(),
        patch(
            "pr_viewer.providers.local._run_subprocess",
            side_effect=FileNotFoundError("git not found"),
        ),
    ):
        response = client.get(_URL)

    assert response.status_code == 500
    assert "git command not found" in response.json()["detail"]


def test_invalid_ref(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client(monkeypatch)
    with (
        mock_fs(),
        patch(
            "pr_viewer.providers.local._run_subprocess",
            side_effect=[
                _ok(stdout=".git"),
                _ok(
                    returncode=128, stderr="fatal: unknown revision or path not in the working tree"
                ),
                _ok(
                    returncode=128, stderr="fatal: unknown revision or path not in the working tree"
                ),
            ],
        ),
    ):
        response = client.get(_URL)

    assert response.status_code == 404
    assert "Ref not found" in response.json()["detail"]


def test_large_diff_truncation(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client(monkeypatch)
    # Build a diff > 10 MB
    large_diff = "diff --git a/big.py b/big.py\n" + ("+" + "x" * 99 + "\n") * 110_000
    with (
        mock_fs(),
        patch(
            "pr_viewer.providers.local._run_subprocess",
            side_effect=[_ok(stdout=".git"), _ok(stdout="M\tbig.py\n"), _ok(stdout=large_diff)],
        ),
    ):
        response = client.get(_URL)

    assert response.status_code == 200
    assert response.json()["truncated"] is True


def test_unknown_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client(monkeypatch)
    response = client.get("/api/compare?provider=bitbucket&repo=x&base=a&head=b")
    assert response.status_code == 400
    assert "Unknown provider" in response.json()["detail"]


@respx.mock
def test_github_provider_param(monkeypatch: pytest.MonkeyPatch) -> None:
    """provider=github still works identically to the default."""
    import httpx as _httpx

    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    app = create_app()
    client = TestClient(app)

    respx.get("https://api.github.com/repos/owner/repo/compare/main...feature").mock(
        return_value=_httpx.Response(
            200,
            json={
                "truncated": False,
                "files": [{"filename": "a.py", "status": "added", "patch": "+hello"}],
            },
        )
    )

    response = client.get("/api/compare?provider=github&repo=owner/repo&base=main&head=feature")
    assert response.status_code == 200
    assert response.json()["total_files"] == 1
