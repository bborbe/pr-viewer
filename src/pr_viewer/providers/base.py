from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class PullRequest:
    id: str
    title: str
    author: str
    source_branch: str
    target_branch: str
    server_name: str
    url: str


@dataclass(frozen=True)
class FileChange:
    path: str
    status: str  # "added", "modified", "deleted", "renamed"
    diff: str = ""


@dataclass(frozen=True)
class FileTreeNode:
    name: str
    path: str
    status: str = ""  # empty for directories
    children: list[FileTreeNode] = field(default_factory=list)


class Provider(Protocol):
    async def list_pull_requests(self) -> list[PullRequest]: ...

    async def get_pull_request(self, pr_id: str) -> PullRequest: ...

    async def get_changes(self, pr_id: str) -> list[FileChange]: ...

    async def approve(self, pr_id: str) -> None: ...

    async def reject(self, pr_id: str) -> None: ...

    async def comment(self, pr_id: str, body: str) -> None: ...
