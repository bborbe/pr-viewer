---
status: prompted
approved: "2026-04-03T14:58:49Z"
generating: "2026-04-03T14:58:54Z"
prompted: "2026-04-03T15:01:21Z"
branch: dark-factory/local-git-provider
---
Tags: [[Dark Factory Guide]] [[Dark Factory - Write Spec]]

---

## Summary

- Refactor compare API from hardcoded GitHub to provider-based routing
- Add `provider` query parameter to `/api/compare` (default: `github`)
- New `local` provider runs `git diff` on a local checkout — no HTTP API needed
- Frontend adds provider selector dropdown (github / local)
- Local provider accepts repo path instead of owner/repo

## Problem

The compare API is hardcoded to GitHub. Users with local git checkouts (e.g., worktrees, local-only repos, or repos on unsupported servers) cannot use PR Viewer at all. Adding any new provider requires refactoring the hardcoded GitHub wiring first. This blocks all multi-provider work.

## Goal

After this work, the system routes compare requests to the correct provider based on a `provider` parameter. A new `local` provider runs `git diff base...head` on a local repo path and returns the same `CompareResponse` as GitHub. The frontend lets the user choose between `github` and `local`, and adjusts the repo input label accordingly ("owner/repo" vs "local path").

## Non-goals

- No PR listing for local repos (no concept of PRs in plain git)
- No approve/reject/comment for local repos
- No remote git operations (fetch, pull) — user manages their checkout
- No Bitbucket Server support (separate spec)
- No config.yaml changes — local provider needs no server config

## Desired Behavior

1. `/api/compare` accepts new query parameter `provider` (`github` or `local`, default `github`)
2. When `provider=github`, behavior is identical to current (no regression)
3. When `provider=local`, `repo` parameter is an absolute path to a local git checkout (e.g., `/Users/bborbe/Documents/workspaces/trading`)
4. Local provider runs `git diff base...head` in the specified repo directory and returns unified diff output
5. Local provider parses `git diff --stat` output to determine file statuses (added/modified/deleted/renamed)
6. Frontend shows a provider dropdown (GitHub / Local) above the repo input
7. When "Local" is selected, repo input label changes to "Repo path" and placeholder shows a local path example
8. URL includes `provider` param for shareable links

## Assumptions

- `git` is installed and available on `PATH` on the host machine
- The local repo path exists and is a valid git repository
- Base and head refs are valid in the local repo (branches, tags, or commit SHAs)
- `git diff base...head` returns unified diff format compatible with diff2html

## Constraints

- Existing GitHub behavior unchanged — `provider=github` (or omitted) works exactly as before
- `CompareResponse` model unchanged — local provider returns same schema
- No new Python dependencies — git commands executed via subprocess with argument list (no shell)
- Local provider follows the same structural pattern as the existing GitHub provider
- Frontend remains single `index.html` with no build step
- `make precommit` must pass
- All existing tests must still pass

## Failure Modes

| Trigger | Expected behavior | Recovery |
|---------|-------------------|----------|
| Invalid provider value | API returns 400 "Unknown provider. Supported: github, local" | User corrects input |
| Repo path does not exist | API returns 404 "Directory not found: /path" | User corrects path |
| Path is not a git repo | API returns 400 "Not a git repository: /path" | User corrects path |
| Invalid ref in local repo | git returns non-zero exit → API returns 404 "Ref not found" | User corrects ref |
| git not installed | subprocess fails → API returns 500 "git command not found" | User installs git |
| Diff too large (>10MB output) | Truncate output, set `truncated=true` | Informational |
| Path traversal attempt (e.g., `../../etc`) | Validate path is absolute, reject relative paths with 400 | User corrects input |

## Security / Abuse Cases

- Local provider only reads from the filesystem via `git diff` — no writes
- Repo path must be an absolute path (reject relative paths)
- No shell injection: use subprocess with argument list, never shell=True
- Repo path must not be a symlink or contain symlinks that escape the intended directory
- Refs validated with same regex as GitHub provider
- No token needed for local repos

See `docs/architecture.md` for provider pattern and frontend approach.

## Acceptance Criteria

- [ ] `make precommit` passes
- [ ] `GET /api/compare?provider=github&repo=owner/name&base=ref1&head=ref2` works (regression)
- [ ] `GET /api/compare?repo=owner/name&base=ref1&head=ref2` works without provider param (defaults to github)
- [ ] `GET /api/compare?provider=local&repo=/absolute/path&base=ref1&head=ref2` returns diff from local git
- [ ] Local provider correctly identifies added/modified/deleted/renamed files
- [ ] Error message for non-existent path (404)
- [ ] Error message for non-git directory (400)
- [ ] Error message for invalid ref (404)
- [ ] Error message for unknown provider (400)
- [ ] Frontend shows provider dropdown
- [ ] Selecting "Local" changes repo input label and placeholder
- [ ] URL includes `provider` param
- [ ] Existing GitHub tests still pass

## Verification

```
# Backend
make precommit

# Manual: local git diff
make run
# Open http://127.0.0.1:8001
# Select provider: Local
# Enter: repo=/Users/bborbe/Documents/workspaces/pr-viewer, base=HEAD~3, head=HEAD
# Verify: file tree shows, diffs render

# Manual: GitHub still works
# Select provider: GitHub
# Enter: repo=bborbe/pr-viewer, base=master, head=v0.1.0
# Verify: same behavior as before
```

## Do-Nothing Option

Without this refactor, every new provider requires ad-hoc wiring in the compare endpoint. The local provider is the simplest possible second provider — it validates the routing pattern before adding HTTP-based providers like Bitbucket Server. Users with local checkouts (worktrees, unreachable servers) have no way to use PR Viewer.
