from __future__ import annotations

import os
import re

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from pr_viewer.providers.github import GitHubCompareClient

_REPO_RE = re.compile(r"^[a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+$")
_REF_RE = re.compile(r"^[a-zA-Z0-9._/:-]+$")

router = APIRouter(prefix="/api")


class FileChangeResponse(BaseModel):
    path: str
    status: str
    diff: str


class CompareResponse(BaseModel):
    files: list[FileChangeResponse]
    truncated: bool
    total_files: int


@router.get("/compare", response_model=CompareResponse)
async def compare(repo: str, base: str, head: str) -> CompareResponse:
    if not _REPO_RE.match(repo):
        raise HTTPException(
            status_code=400,
            detail="Invalid repo format. Expected 'owner/repo'.",
        )
    if not _REF_RE.match(base):
        raise HTTPException(
            status_code=400,
            detail="Invalid base ref. Allowed: alphanumeric, hyphens, dots, slashes, colons.",
        )
    if not _REF_RE.match(head):
        raise HTTPException(
            status_code=400,
            detail="Invalid head ref. Allowed: alphanumeric, hyphens, dots, slashes, colons.",
        )

    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Set GITHUB_TOKEN environment variable.",
        )

    async with httpx.AsyncClient() as client:
        gh = GitHubCompareClient(token=token, http_client=client)
        return await gh.compare(repo, base, head)
