from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from pr_viewer.factory import create_app

REPO_PATH = "/workspace"

_VALID_DIFF = (
    "diff --git a/file.py b/file.py\n"
    "index 0000000..1111111 100644\n"
    "--- a/file.py\n"
    "+++ b/file.py\n"
    "@@ -1 +1 @@\n"
    "-old\n"
    "+new\n"
)


def make_result(
    returncode: int = 0, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess[str]:
    r: subprocess.CompletedProcess[str] = MagicMock(spec=subprocess.CompletedProcess)
    r.returncode = returncode
    r.stdout = stdout
    r.stderr = stderr
    return r


def make_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    app = create_app()
    return TestClient(app)


def test_valid_local_diff(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client(monkeypatch)
    with patch("pr_viewer.providers.local._run_subprocess") as mock_run:
        mock_run.side_effect = [
            make_result(stdout=".git\n"),  # rev-parse
            make_result(stdout="M\tfile.py\n"),  # name-status
            make_result(stdout=_VALID_DIFF),  # diff
        ]
        response = client.get(
            f"/api/compare?provider=local&repo={REPO_PATH}&base=main&head=feature"
        )

    assert response.status_code == 200
    data = response.json()
    assert data["truncated"] is False
    assert data["total_files"] == 1
    assert data["files"][0]["path"] == "file.py"
    assert data["files"][0]["status"] == "modified"
    assert "@@" in data["files"][0]["diff"]


def test_added_file(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client(monkeypatch)
    diff = (
        "diff --git a/new.py b/new.py\n"
        "new file mode 100644\n"
        "index 0000000..1111111\n"
        "--- /dev/null\n"
        "+++ b/new.py\n"
        "@@ -0,0 +1 @@\n"
        "+hello\n"
    )
    with patch("pr_viewer.providers.local._run_subprocess") as mock_run:
        mock_run.side_effect = [
            make_result(stdout=".git\n"),
            make_result(stdout="A\tnew.py\n"),
            make_result(stdout=diff),
        ]
        response = client.get(
            f"/api/compare?provider=local&repo={REPO_PATH}&base=main&head=feature"
        )

    assert response.status_code == 200
    files = response.json()["files"]
    assert files[0]["path"] == "new.py"
    assert files[0]["status"] == "added"


def test_deleted_file(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client(monkeypatch)
    diff = (
        "diff --git a/old.py b/old.py\n"
        "deleted file mode 100644\n"
        "index 1111111..0000000\n"
        "--- a/old.py\n"
        "+++ /dev/null\n"
        "@@ -1 +0,0 @@\n"
        "-bye\n"
    )
    with patch("pr_viewer.providers.local._run_subprocess") as mock_run:
        mock_run.side_effect = [
            make_result(stdout=".git\n"),
            make_result(stdout="D\told.py\n"),
            make_result(stdout=diff),
        ]
        response = client.get(
            f"/api/compare?provider=local&repo={REPO_PATH}&base=main&head=feature"
        )

    assert response.status_code == 200
    files = response.json()["files"]
    assert files[0]["path"] == "old.py"
    assert files[0]["status"] == "deleted"


def test_renamed_file(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client(monkeypatch)
    diff = (
        "diff --git a/old.py b/new.py\n"
        "similarity index 100%\n"
        "rename from old.py\n"
        "rename to new.py\n"
    )
    with patch("pr_viewer.providers.local._run_subprocess") as mock_run:
        mock_run.side_effect = [
            make_result(stdout=".git\n"),
            make_result(stdout="R100\told.py\tnew.py\n"),
            make_result(stdout=diff),
        ]
        response = client.get(
            f"/api/compare?provider=local&repo={REPO_PATH}&base=main&head=feature"
        )

    assert response.status_code == 200
    files = response.json()["files"]
    assert files[0]["path"] == "new.py"
    assert files[0]["status"] == "renamed"


def test_relative_path(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client(monkeypatch)
    response = client.get("/api/compare?provider=local&repo=relative/path&base=main&head=feature")
    assert response.status_code == 400
    assert "absolute" in response.json()["detail"]


def test_nonexistent_path(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client(monkeypatch)
    response = client.get(
        "/api/compare?provider=local&repo=/nonexistent/path/xyz123&base=main&head=feature"
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_not_a_directory(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client(monkeypatch)
    with (
        patch("pr_viewer.providers.local.os.path.exists", return_value=True),
        patch("pr_viewer.providers.local.os.path.isdir", return_value=False),
    ):
        response = client.get(
            "/api/compare?provider=local&repo=/some/file.txt&base=main&head=feature"
        )
    assert response.status_code == 400
    assert "Not a directory" in response.json()["detail"]


def test_not_a_git_repo(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client(monkeypatch)
    with patch("pr_viewer.providers.local._run_subprocess") as mock_run:
        mock_run.side_effect = [
            make_result(returncode=1, stderr="fatal: not a git repository\n"),
        ]
        response = client.get(
            f"/api/compare?provider=local&repo={REPO_PATH}&base=main&head=feature"
        )

    assert response.status_code == 400
    assert "Not a git repository" in response.json()["detail"]


def test_git_not_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client(monkeypatch)
    with patch("pr_viewer.providers.local._run_subprocess", side_effect=FileNotFoundError):
        response = client.get(
            f"/api/compare?provider=local&repo={REPO_PATH}&base=main&head=feature"
        )

    assert response.status_code == 500
    assert "git command not found" in response.json()["detail"]


def test_invalid_ref(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client(monkeypatch)
    with patch("pr_viewer.providers.local._run_subprocess") as mock_run:
        mock_run.side_effect = [
            make_result(stdout=".git\n"),
            make_result(
                returncode=128,
                stderr="fatal: unknown revision or path not in the working tree\n",
            ),
        ]
        response = client.get(
            f"/api/compare?provider=local&repo={REPO_PATH}&base=nonexistent&head=feature"
        )

    assert response.status_code == 404
    assert "Ref not found" in response.json()["detail"]


def test_large_diff_truncation(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client(monkeypatch)
    large_diff = (
        "diff --git a/big.py b/big.py\n"
        "index 0000000..1111111 100644\n"
        "--- a/big.py\n"
        "+++ b/big.py\n"
        "@@ -1 +1 @@\n"
    ) + ("+" + "x" * 100 + "\n") * 110000  # > 10 MB

    with patch("pr_viewer.providers.local._run_subprocess") as mock_run:
        mock_run.side_effect = [
            make_result(stdout=".git\n"),
            make_result(stdout="M\tbig.py\n"),
            make_result(stdout=large_diff),
        ]
        response = client.get(
            f"/api/compare?provider=local&repo={REPO_PATH}&base=main&head=feature"
        )

    assert response.status_code == 200
    assert response.json()["truncated"] is True


def test_unknown_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client(monkeypatch)
    response = client.get("/api/compare?provider=bitbucket&repo=x&base=a&head=b")
    assert response.status_code == 400
    assert "Unknown provider" in response.json()["detail"]


@respx.mock
def test_github_provider_param_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    app = create_app()
    client = TestClient(app)
    url = "https://api.github.com/repos/owner/repo/compare/main...feature"
    respx.get(url).mock(
        return_value=httpx.Response(
            200,
            json={
                "truncated": False,
                "files": [
                    {"filename": "a.py", "status": "added", "patch": "@@ +1 @@\n+hello"},
                ],
            },
        )
    )
    response = client.get("/api/compare?provider=github&repo=owner/repo&base=main&head=feature")
    assert response.status_code == 200
    assert response.json()["total_files"] == 1
