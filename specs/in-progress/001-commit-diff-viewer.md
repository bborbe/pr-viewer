---
status: verifying
tags:
    - dark-factory
    - spec
approved: "2026-04-03T11:51:21Z"
generating: "2026-04-03T11:54:37Z"
prompted: "2026-04-03T11:57:06Z"
verifying: "2026-04-03T12:31:41Z"
branch: dark-factory/commit-diff-viewer
---
Tags: [[Dark Factory Guide]] [[Dark Factory - Write Spec]]

---

## Summary

- Web app shows diff between two commits/branches/tags on a GitHub repository
- Hierarchical file tree sidebar with add/modify/delete icons
- Side-by-side diff view with syntax highlighting
- User provides repo owner/name and two refs via the UI
- Read-only — no approve/reject/comment yet

## Problem

Reviewing large diffs on GitHub is painful. GitHub lacks a hierarchical file tree in its diff view, making it hard to navigate PRs with many changed files. Bitbucket Server has a superior file tree with nested folders and change type icons, but not everyone uses Bitbucket. As AI agents produce more PRs, humans need a fast way to review diffs regardless of git platform.

## Goal

After this work, the system has a local web app that accepts a GitHub repo and two git refs, fetches the comparison via GitHub API, and displays the diff with a Bitbucket Server-quality file tree sidebar and side-by-side diff view. The app runs locally with `make run` and opens at http://127.0.0.1:8000.

## Non-goals

- No PR listing or dashboard
- No approve/reject/comment actions
- No Bitbucket Server provider (GitHub only for v0.1)
- No authentication UI (token via env var only)
- No inline comments or comment threads
- No persistence or caching

## Desired Behavior

1. User opens http://127.0.0.1:8000 and sees an input form: repo (owner/name), base ref, head ref
2. User submits the form and the app fetches the comparison from GitHub API
3. Left sidebar shows a hierarchical file tree built from changed file paths
4. Each file in the tree shows an icon indicating change type: added (green +), modified (orange pencil), deleted (red -)
5. Folders are collapsible, expanded by default
6. Clicking a file in the tree scrolls the right panel to that file's diff
7. Right panel shows side-by-side diff with syntax highlighting (using diff2html JS library)
8. The app reads `GITHUB_TOKEN` from environment for API authentication

## Assumptions

- GitHub Compare API (`GET /repos/{owner}/{repo}/compare/{base}...{head}`) returns unified diff format per file, suitable for diff2html rendering
- Refs must be branch names, tags, or full commit SHAs (not relative refs like `HEAD~1`)
- The existing FastAPI project skeleton (`src/pr_viewer/`, `tests/`, `Makefile`) is in place
- GitHub API returns up to 3000 files per comparison; larger diffs are truncated by GitHub

## Constraints

- Existing project structure unchanged: FastAPI backend, static SPA frontend (see `docs/architecture.md`)
- No new Python dependencies beyond what's in pyproject.toml (fastapi, uvicorn, httpx, pydantic, pyyaml)
- Frontend uses vanilla JS + diff2html from CDN (no npm/build step)
- Config loading from config.yaml unchanged
- Provider protocol in `providers/base.py` unchanged (implementations must conform)
- File tree must remain responsive with 1000+ files (lazy rendering or pagination)
- `make precommit` must pass
- All existing tests must still pass

## Failure Modes

| Trigger | Expected behavior | Recovery |
|---------|-------------------|----------|
| Invalid repo name | API returns 404 → UI shows "Repository not found" | User corrects input |
| Invalid ref (branch/tag/SHA) | API returns 404/422 → UI shows "Ref not found" | User corrects input |
| No GITHUB_TOKEN set | API returns 401 → UI shows "Authentication required. Set GITHUB_TOKEN env var" | User sets env var, restarts |
| Rate limit exceeded | API returns 403 → UI shows "GitHub API rate limit exceeded. Try again later" | User waits |
| Diff too large (GitHub truncates at 3000 files) | UI shows warning "Showing first N of M files (GitHub API limit)" | Informational only |
| Network timeout | httpx timeout → UI shows "Request timed out" | User retries |

## Security / Abuse Cases

- Token passed via env var only, never exposed to frontend
- Backend proxies GitHub API — frontend never sees the token
- Repo input validated: must match `owner/repo` pattern (alphanumeric, hyphens, dots, underscores)
- Ref input validated: alphanumeric, hyphens, dots, slashes, no shell metacharacters
- No file system access — all data from GitHub API

## Acceptance Criteria

- [ ] `make precommit` passes
- [ ] GET /api/compare?repo=owner/name&base=ref1&head=ref2 returns JSON with file list and diffs
- [ ] UI renders hierarchical file tree from flat file paths
- [ ] File tree shows correct change type icons (added/modified/deleted)
- [ ] Folders are collapsible
- [ ] Clicking a file scrolls to its diff
- [ ] Side-by-side diff renders with syntax highlighting via diff2html
- [ ] Error message shown for invalid repo (404)
- [ ] Error message shown for invalid ref (404/422)
- [ ] Error message shown for missing GITHUB_TOKEN (401)
- [ ] Error message shown for rate limit exceeded (403)
- [ ] Works with refs that are branches, tags, or commit SHAs

## Verification

```
# Backend
make precommit

# Manual: start server and compare two commits
GITHUB_TOKEN=ghp_xxx make run
# Open http://127.0.0.1:8000
# Enter: repo=bborbe/pr-viewer, base=master, head=<feature-branch-or-sha>
# Verify: file tree shows, diffs render side-by-side
```

## Do-Nothing Option

Without this, reviewing diffs means using GitHub's web UI which lacks hierarchical file navigation. For small diffs this is acceptable. For AI-generated PRs with 50+ files, this becomes a significant productivity bottleneck. The cost of building this is moderate (3-5 prompts) and the tool will be used daily.
