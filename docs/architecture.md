# Architecture

## Overview

PR Viewer is a local web app that provides a unified, professional interface for reviewing pull requests across multiple git servers.

## Motivation

AI agents (dark-factory, Claude Code) produce high volumes of PRs. The human reviewer becomes the bottleneck. GitHub's PR UI lacks a hierarchical file tree and has inferior diff navigation. PR Viewer provides the best review experience regardless of git platform.

## System Diagram

```
┌─────────────────────────────────────────────┐
│                  Browser                     │
│  ┌──────────┐  ┌──────────────────────────┐  │
│  │ File Tree│  │   Side-by-Side Diff      │  │
│  │ Sidebar  │  │   View                   │  │
│  │          │  │                           │  │
│  │ 📁 src/  │  │  - old  │  + new         │  │
│  │  📄 a.go │  │  line 1 │  line 1        │  │
│  │  📄 b.go │  │  line 2 │  line 2 (mod)  │  │
│  └──────────┘  └──────────────────────────┘  │
└─────────────────┬───────────────────────────┘
                  │ REST API
┌─────────────────┴───────────────────────────┐
│              FastAPI Server                   │
│                                              │
│  ┌─────────┐  ┌─────────┐  ┌──────────────┐ │
│  │ PR List │  │ Diff    │  │ Review       │ │
│  │ API     │  │ API     │  │ API          │ │
│  └────┬────┘  └────┬────┘  └──────┬───────┘ │
│       │            │              │          │
│  ┌────┴────────────┴──────────────┴───────┐  │
│  │         Provider Interface             │  │
│  │         (Protocol)                     │  │
│  └────┬──────────┬───────────┬────────────┘  │
│       │          │           │               │
│  ┌────┴───┐ ┌───┴────┐ ┌───┴─────┐         │
│  │ GitHub │ │Bitbuck.│ │ GitLab  │  ...     │
│  │Provider│ │Provider│ │Provider │         │
│  └────┬───┘ └───┬────┘ └───┬─────┘         │
└───────┼─────────┼───────────┼────────────────┘
        │         │           │
   GitHub API  BB Server   GitLab API
               REST API
```

## Components

### Frontend (Static SPA)

Single `index.html` with embedded CSS/JS. No build step.

Key UI components:
- **PR List** — all open PRs across configured servers, filterable
- **File Tree Sidebar** — hierarchical directory tree with change type icons (added/modified/deleted)
- **Diff Viewer** — side-by-side diff with syntax highlighting
- **Review Actions** — approve, reject, comment buttons

### Backend (FastAPI)

- `factory.py` — app creation, provider wiring from config
- `config.py` — YAML config loading (server list, credentials)
- `api/pulls.py` — PR listing and detail endpoints
- `api/reviews.py` — approve/reject/comment endpoints

### Provider Interface

Each git server backend implements the `Provider` protocol:

```python
class Provider(Protocol):
    async def list_pull_requests(self) -> list[PullRequest]: ...
    async def get_pull_request(self, pr_id: str) -> PullRequest: ...
    async def get_changes(self, pr_id: str) -> list[FileChange]: ...
    async def approve(self, pr_id: str) -> None: ...
    async def reject(self, pr_id: str) -> None: ...
    async def comment(self, pr_id: str, body: str) -> None: ...
```

Providers:
- `github.py` — GitHub REST API v3
- `bitbucket.py` — Bitbucket Server REST API (planned)

### Configuration

```yaml
servers:
  - name: github
    type: github
    url: https://api.github.com
    token_env: GITHUB_TOKEN
    repos:
      - bborbe/trading
      - bborbe/pr-reviewer

  # Additional providers planned:
  # - name: work
  #   type: bitbucket-server
  #   url: https://bitbucket.example.com
  #   token_env: BITBUCKET_TOKEN
```

Tokens stored in env vars, referenced by name in config.

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Language | Python | Same as task-orchestrator, fast to build UI apps |
| Framework | FastAPI | Async, fast, good for API + static serving |
| HTTP client | httpx | Async, modern, easy to mock with respx |
| Frontend | Vanilla HTML/CSS/JS | No build step, simple to iterate |
| Config | YAML file | Same pattern as pr-reviewer, supports multiple servers |
| State | None (stateless) | All data from git server APIs, no DB needed |
| Provider pattern | Protocol | Type-safe, easy to add new providers |

## File Tree Construction

Git APIs return flat file lists. We build the tree client-side:

1. API returns `list[FileChange]` with paths like `src/pkg/file.go`
2. Frontend JS builds nested tree from paths
3. Each node shows: folder icon (directory) or change icon (added/modified/deleted)
4. Clicking a file scrolls to its diff

## Diff Rendering

Options:
- **diff2html** — JS library, renders unified/side-by-side diffs from unified diff format
- Git server APIs return unified diff format
- diff2html handles syntax highlighting via highlight.js

## Phases

### Phase 1: MVP (GitHub)
- Config loading
- GitHub provider (list PRs, get diffs)
- File tree sidebar
- Side-by-side diff view
- Approve/reject/comment

### Phase 2: Multi-Provider
- Additional providers (Bitbucket Server, etc.)
- Provider selection in UI
- Dashboard across all servers

### Phase 3: Polish
- GitLab, Gitea providers
- Keyboard navigation
- File tree search/filter
- PR comment threads (inline)
