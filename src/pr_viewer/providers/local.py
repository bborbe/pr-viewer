from __future__ import annotations

import asyncio
import os
import subprocess
from typing import TYPE_CHECKING

from fastapi import HTTPException

if TYPE_CHECKING:
    from pr_viewer.api.compare import CompareResponse

_MAX_DIFF_BYTES = 10 * 1024 * 1024  # 10 MB

_NAME_STATUS_MAP: dict[str, str] = {
    "A": "added",
    "D": "deleted",
    "M": "modified",
}


def _run_subprocess(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True)


def _parse_name_status(output: str) -> dict[str, str]:
    status_map: dict[str, str] = {}
    for line in output.splitlines():
        parts = line.split("\t")
        if not parts:
            continue
        letter = parts[0]
        if letter.startswith("R") and len(parts) >= 3:
            # R100\told.py\tnew.py — use new path
            status_map[parts[2]] = "renamed"
        elif letter in _NAME_STATUS_MAP and len(parts) >= 2:
            status_map[parts[1]] = _NAME_STATUS_MAP[letter]
        elif len(parts) >= 2:
            status_map[parts[1]] = "modified"
    return status_map


def _split_diff_by_file(diff_output: str) -> list[tuple[str, str]]:
    """Return list of (path, diff_text) pairs from unified diff output."""
    if not diff_output:
        return []

    segments: list[str] = []
    current: list[str] = []
    for line in diff_output.splitlines(keepends=True):
        if line.startswith("diff --git ") and current:
            segments.append("".join(current))
            current = [line]
        else:
            current.append(line)
    if current:
        segments.append("".join(current))

    result: list[tuple[str, str]] = []
    for seg in segments:
        first_line = seg.split("\n", 1)[0]
        # Extract path from "diff --git a/foo b/foo"
        parts = first_line.split(" ")
        if len(parts) >= 4:
            path = parts[-1]
            if path.startswith("b/"):
                path = path[2:]
        else:
            path = ""
        result.append((path, seg))
    return result


class LocalGitCompareClient:
    async def compare(self, repo: str, base: str, head: str) -> CompareResponse:
        from pr_viewer.api.compare import CompareResponse, FileChangeResponse

        # Path validation
        if not repo.startswith("/"):
            raise HTTPException(status_code=400, detail="Repo path must be absolute, not relative.")
        if not os.path.exists(repo):
            raise HTTPException(status_code=404, detail=f"Directory not found: {repo}")
        if not os.path.isdir(repo):
            raise HTTPException(status_code=400, detail=f"Not a directory: {repo}")
        if os.path.realpath(repo) != os.path.abspath(repo):
            raise HTTPException(status_code=400, detail="Symlink paths are not allowed.")

        # Git repo check
        try:
            rev_parse = await asyncio.to_thread(
                _run_subprocess, ["git", "-C", repo, "rev-parse", "--git-dir"]
            )
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=500, detail="git command not found. Please install git."
            ) from exc

        if rev_parse.returncode != 0:
            raise HTTPException(status_code=400, detail=f"Not a git repository: {repo}")

        ref_range = f"{base}...{head}"

        # Run name-status
        try:
            name_status_result = await asyncio.to_thread(
                _run_subprocess, ["git", "-C", repo, "diff", "--name-status", ref_range]
            )
            diff_result = await asyncio.to_thread(
                _run_subprocess, ["git", "-C", repo, "diff", ref_range]
            )
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=500, detail="git command not found. Please install git."
            ) from exc

        for result in (name_status_result, diff_result):
            if result.returncode != 0:
                stderr = result.stderr
                if any(
                    msg in stderr
                    for msg in ("unknown revision", "bad revision", "fatal: ambiguous argument")
                ):
                    raise HTTPException(
                        status_code=404,
                        detail="Ref not found. Check that base and head exist in the repository.",
                    )

        status_map = _parse_name_status(name_status_result.stdout)

        raw_diff = diff_result.stdout
        truncated = False
        if len(raw_diff.encode()) > _MAX_DIFF_BYTES:
            raw_diff = raw_diff.encode()[:_MAX_DIFF_BYTES].decode(errors="replace")
            truncated = True

        file_diffs = _split_diff_by_file(raw_diff)

        files = [
            FileChangeResponse(
                path=path,
                status=status_map.get(path, "modified"),
                diff=diff_text,
            )
            for path, diff_text in file_diffs
        ]

        return CompareResponse(files=files, truncated=truncated, total_files=len(files))
