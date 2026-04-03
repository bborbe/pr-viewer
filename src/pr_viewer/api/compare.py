from __future__ import annotations

import os
import re

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from pr_viewer.providers.bitbucket_server import BitbucketServerCompareClient
from pr_viewer.providers.github import GitHubCompareClient
from pr_viewer.providers.local import LocalGitCompareClient

_REPO_RE = re.compile(r"^[a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+$")
_REF_RE = re.compile(r"^[a-zA-Z0-9._/:-]+$")
_VALID_PROVIDERS = {"github", "local", "bitbucket"}

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
async def compare(repo: str, base: str, head: str, provider: str = "github") -> CompareResponse:
    if provider not in _VALID_PROVIDERS:
        raise HTTPException(
            status_code=400,
            detail="Unknown provider. Supported: github, local, bitbucket",
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

    if provider == "local":
        local_client = LocalGitCompareClient()
        return await local_client.compare(repo, base, head)

    if provider == "bitbucket":
        bitbucket_url = os.environ.get("BITBUCKET_URL", "")
        if not bitbucket_url:
            raise HTTPException(
                status_code=503,
                detail="Bitbucket Server URL not configured. Set BITBUCKET_URL env var.",
            )
        if not re.match(r"^https?://[^\s/$.?#].[^\s]*$", bitbucket_url):
            raise HTTPException(
                status_code=503,
                detail="BITBUCKET_URL is not a valid URL. Expected format: https://bitbucket.example.com",
            )
        token = os.environ.get("BITBUCKET_TOKEN", "")
        if not token:
            raise HTTPException(
                status_code=503,
                detail="Authentication required. Set BITBUCKET_TOKEN env var.",
            )
        async with httpx.AsyncClient(timeout=30.0) as client:
            bb = BitbucketServerCompareClient(
                base_url=bitbucket_url, token=token, http_client=client
            )
            return await bb.compare(repo, base, head)

    # provider == "github"
    if not _REPO_RE.match(repo):
        raise HTTPException(
            status_code=400,
            detail="Invalid repo format. Expected 'owner/repo'.",
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
