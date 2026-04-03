from __future__ import annotations

from typing import TYPE_CHECKING

import httpx
from fastapi import HTTPException

if TYPE_CHECKING:
    from pr_viewer.api.compare import CompareResponse

_STATUS_MAP: dict[str, str] = {
    "added": "added",
    "modified": "modified",
    "removed": "deleted",
    "renamed": "renamed",
}


class GitHubCompareClient:
    def __init__(self, token: str, http_client: httpx.AsyncClient) -> None:
        self._token = token
        self._client = http_client

    async def compare(self, repo: str, base: str, head: str) -> CompareResponse:
        from pr_viewer.api.compare import CompareResponse, FileChangeResponse

        url = f"https://api.github.com/repos/{repo}/compare/{base}...{head}"
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        try:
            response = await self._client.get(url, headers=headers)
        except httpx.TimeoutException as exc:
            raise HTTPException(status_code=504, detail="Request timed out. Please retry.") from exc

        if response.status_code == 401:
            raise HTTPException(
                status_code=401,
                detail="Authentication required. Set GITHUB_TOKEN environment variable.",
            )
        if response.status_code == 403:
            raise HTTPException(
                status_code=429,
                detail="GitHub API rate limit exceeded. Try again later.",
            )
        if response.status_code == 404:
            raise HTTPException(
                status_code=404,
                detail="Repository or ref not found. Check the repo name and refs.",
            )
        if response.status_code == 422:
            raise HTTPException(
                status_code=422,
                detail="Invalid ref. Refs must be branch names, tags, or commit SHAs.",
            )
        if response.status_code >= 300:
            raise HTTPException(
                status_code=502,
                detail=f"GitHub API error: {response.status_code}",
            )

        data = response.json()
        raw_files: list[dict[str, object]] = data.get("files", [])
        github_truncated: bool = bool(data.get("truncated", False))

        files = [
            FileChangeResponse(
                path=str(f.get("filename", "")),
                status=_STATUS_MAP.get(str(f.get("status", "")), "modified"),
                diff=str(f.get("patch", "")),
            )
            for f in raw_files
        ]

        return CompareResponse(files=files, truncated=github_truncated, total_files=len(files))
