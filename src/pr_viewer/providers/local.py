from __future__ import annotations

import asyncio
import os
import re
import subprocess
from typing import TYPE_CHECKING

from fastapi import HTTPException

if TYPE_CHECKING:
    from pr_viewer.api.compare import CompareResponse

_MAX_DIFF_BYTES = 10 * 1024 * 1024
_INVALID_REF_MARKERS = ("unknown revision", "bad revision", "fatal: ambiguous argument")
_DIFF_HEADER_RE = re.compile(r"diff --git a/.+ b/(.+)")

_LETTER_TO_STATUS: dict[str, str] = {
    "A": "added",
    "D": "deleted",
    "M": "modified",
}


def _parse_name_status(output: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in output.splitlines():
        if not line:
            continue
        parts = line.split("\t")
        letter = parts[0]
        if letter.startswith("R") and len(parts) >= 3:
            result[parts[2]] = "renamed"
        elif len(parts) >= 2:
            result[parts[1]] = _LETTER_TO_STATUS.get(letter, "modified")
    return result


def _split_diff_by_file(diff_output: str) -> list[tuple[str, str]]:
    if not diff_output.strip():
        return []
    segments = diff_output.split("\ndiff --git ")
    result: list[tuple[str, str]] = []
    for i, segment in enumerate(segments):
        if i > 0:
            segment = "diff --git " + segment
        first_line = segment.split("\n")[0]
        m = _DIFF_HEADER_RE.match(first_line)
        if m:
            result.append((m.group(1), segment))
    return result


def _run_subprocess(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True)


class LocalGitCompareClient:
    def __init__(self) -> None:
        pass

    async def compare(self, repo: str, base: str, head: str) -> CompareResponse:
        from pr_viewer.api.compare import CompareResponse, FileChangeResponse

        # Path validation
        if not repo.startswith("/"):
            raise HTTPException(status_code=400, detail="Repo path must be absolute, not relative.")

        if not os.path.exists(repo):
            raise HTTPException(status_code=404, detail=f"Directory not found: {repo}")

        if not os.path.isdir(repo):
            raise HTTPException(status_code=400, detail=f"Not a directory: {repo}")

        real_path = os.path.realpath(repo)
        abs_path = os.path.abspath(repo)
        if real_path != abs_path:
            raise HTTPException(status_code=400, detail="Symlink paths are not allowed.")

        # Check git repo
        try:
            rev_parse = await asyncio.to_thread(
                _run_subprocess,
                ["git", "-C", repo, "rev-parse", "--git-dir"],
            )
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=500, detail="git command not found. Please install git."
            ) from exc

        if rev_parse.returncode != 0:
            raise HTTPException(status_code=400, detail=f"Not a git repository: {repo}")

        # Run --name-status
        try:
            name_status = await asyncio.to_thread(
                _run_subprocess,
                ["git", "-C", repo, "diff", "--name-status", f"{base}...{head}"],
            )
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=500, detail="git command not found. Please install git."
            ) from exc

        if name_status.returncode != 0:
            if any(marker in name_status.stderr for marker in _INVALID_REF_MARKERS):
                raise HTTPException(
                    status_code=404,
                    detail="Ref not found. Check that base and head exist in the repository.",
                )
            raise HTTPException(
                status_code=500, detail=f"git diff --name-status failed: {name_status.stderr}"
            )

        status_map = _parse_name_status(name_status.stdout)

        # Run diff
        try:
            diff_proc = await asyncio.to_thread(
                _run_subprocess,
                ["git", "-C", repo, "diff", f"{base}...{head}"],
            )
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=500, detail="git command not found. Please install git."
            ) from exc

        if diff_proc.returncode != 0:
            if any(marker in diff_proc.stderr for marker in _INVALID_REF_MARKERS):
                raise HTTPException(
                    status_code=404,
                    detail="Ref not found. Check that base and head exist in the repository.",
                )
            raise HTTPException(status_code=500, detail=f"git diff failed: {diff_proc.stderr}")

        raw_diff = diff_proc.stdout
        truncated = False
        raw_bytes = raw_diff.encode("utf-8")
        if len(raw_bytes) > _MAX_DIFF_BYTES:
            raw_diff = raw_bytes[:_MAX_DIFF_BYTES].decode("utf-8", errors="replace")
            truncated = True

        file_segments = _split_diff_by_file(raw_diff)
        files = [
            FileChangeResponse(
                path=path,
                status=status_map.get(path, "modified"),
                diff=diff_text,
            )
            for path, diff_text in file_segments
        ]

        return CompareResponse(files=files, truncated=truncated, total_files=len(files))
