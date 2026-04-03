from __future__ import annotations

import re
from typing import TYPE_CHECKING, cast

import httpx
from fastapi import HTTPException

if TYPE_CHECKING:
    from pr_viewer.api.compare import CompareResponse, FileChangeResponse

_REPO_RE = re.compile(r"^[A-Z0-9_.-]+/[a-zA-Z0-9._-]+$", re.IGNORECASE)
_URL_RE = re.compile(r"^https?://[^\s/$.?#].[^\s]*$")


def _hunks_to_unified(src_path: str, dst_path: str, hunks: list[dict[str, object]]) -> str:
    if not hunks:
        return ""

    lines: list[str] = [
        f"diff --git a/{src_path} b/{dst_path}",
        f"--- a/{src_path}",
        f"+++ b/{dst_path}",
    ]

    _PREFIX = {"CONTEXT": " ", "ADDED": "+", "REMOVED": "-"}

    for hunk in hunks:
        src_line = hunk.get("sourceLine", 0)
        src_span = hunk.get("sourceSpan", 0)
        dst_line = hunk.get("destinationLine", 0)
        dst_span = hunk.get("destinationSpan", 0)
        lines.append(f"@@ -{src_line},{src_span} +{dst_line},{dst_span} @@")

        segments: list[dict[str, object]] = cast(list[dict[str, object]], hunk.get("segments", []))
        for segment in segments:
            seg_type = str(segment.get("type", "CONTEXT"))
            prefix = _PREFIX.get(seg_type, " ")
            seg_lines: list[dict[str, object]] = cast(
                list[dict[str, object]], segment.get("lines", [])
            )
            for seg_line in seg_lines:
                lines.append(f"{prefix}{seg_line.get('line', '')}")

    return "\n".join(lines)


def _convert_diff(d: dict[str, object]) -> FileChangeResponse:
    from pr_viewer.api.compare import FileChangeResponse

    source: dict[str, object] = cast(dict[str, object], d.get("source") or {})
    destination: dict[str, object] = cast(dict[str, object], d.get("destination") or {})
    src = str(source.get("toString") or "")
    dst = str(destination.get("toString") or "")

    if src == "":
        status = "added"
        path = dst
        unified_src = "/dev/null"
        unified_dst = dst
    elif dst == "":
        status = "deleted"
        path = src
        unified_src = src
        unified_dst = "/dev/null"
    elif src != dst:
        status = "renamed"
        path = dst
        unified_src = src
        unified_dst = dst
    else:
        status = "modified"
        path = src
        unified_src = src
        unified_dst = dst

    hunks: list[dict[str, object]] = cast(list[dict[str, object]], d.get("hunks", []))
    unified = _hunks_to_unified(unified_src, unified_dst, hunks)

    return FileChangeResponse(path=path, status=status, diff=unified)


class BitbucketServerCompareClient:
    def __init__(self, base_url: str, token: str, http_client: httpx.AsyncClient) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._client = http_client

    async def compare(self, repo: str, base: str, head: str) -> CompareResponse:
        from pr_viewer.api.compare import CompareResponse

        if not _REPO_RE.match(repo):
            raise HTTPException(
                status_code=400, detail="Invalid repo format. Expected 'PROJECT/repo-slug'."
            )

        project, slug = repo.split("/", 1)

        url = f"{self._base_url}/rest/api/1.0/projects/{project}/repos/{slug}/compare/diff"
        params: dict[str, str | int] = {"from": base, "to": head, "limit": 500}
        headers = {"Authorization": f"Bearer {self._token}"}

        try:
            response = await self._client.get(url, headers=headers, params=params)
        except httpx.TimeoutException as exc:
            raise HTTPException(status_code=504, detail="Request timed out.") from exc
        except httpx.ConnectError as exc:
            raise HTTPException(
                status_code=502, detail="Cannot reach Bitbucket Server. Check BITBUCKET_URL."
            ) from exc

        if response.status_code == 401:
            raise HTTPException(
                status_code=401, detail="Authentication failed. Check BITBUCKET_TOKEN."
            )
        if response.status_code == 404:
            body = response.text
            if "Repository" in body:
                raise HTTPException(status_code=404, detail="Repository not found.")
            raise HTTPException(status_code=404, detail="Ref not found.")
        if response.status_code >= 300:
            raise HTTPException(
                status_code=502, detail=f"Bitbucket Server error: {response.status_code}"
            )

        data = response.json()
        raw_diffs: list[dict[str, object]] = data.get("diffs", [])

        files = [_convert_diff(d) for d in raw_diffs]
        any_truncated = any(d.get("truncated") is True for d in raw_diffs)

        return CompareResponse(files=files, truncated=any_truncated, total_files=len(files))
