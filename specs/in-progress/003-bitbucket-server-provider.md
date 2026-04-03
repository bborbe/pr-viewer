---
status: approved
approved: "2026-04-03T16:17:22Z"
generating: "2026-04-03T16:17:23Z"
branch: dark-factory/bitbucket-server-provider
---
Tags: [[Dark Factory Guide]] [[Dark Factory - Write Spec]]

---

## Summary

- New Bitbucket Server provider calls Bitbucket REST API to fetch diffs between refs
- Provider added to the provider routing established by the local-git-provider spec
- Frontend adds "Bitbucket Server" option to the provider dropdown
- Repo input accepts `project/repo` format (Bitbucket project key + repo slug)
- Authenticates via `BITBUCKET_URL` and `BITBUCKET_TOKEN` environment variables

## Problem

Many organizations host code on Bitbucket Server (self-hosted). Bitbucket Server's built-in diff UI has limitations similar to GitHub — no hierarchical file tree for large PRs. With the provider routing in place (from local-git-provider spec), adding Bitbucket Server is the natural next step toward the multi-provider goal.

## Goal

After this work, users can compare two refs on a Bitbucket Server repository using the same PR Viewer UI. The Bitbucket Server provider calls the Bitbucket REST API, fetches per-file diffs, and returns them in the standard `CompareResponse` format. The frontend lets users select "Bitbucket Server" as a provider and enter a project/repo identifier.

## Non-goals

- No Bitbucket Cloud support (different API)
- No PR listing or review actions (approve/reject/comment) — diff viewing only
- No multiple Bitbucket Server instances (single instance via env vars)
- No OAuth — token-based auth only

## Desired Behavior

1. `/api/compare?provider=bitbucket&repo=PROJECT/repo-slug&base=ref1&head=ref2` returns diffs from Bitbucket Server
2. Provider returns diffs for any two valid refs on a Bitbucket Server repository
3. Provider maps Bitbucket file statuses to standard statuses (added/modified/deleted/renamed)
4. Authentication via Bearer token from `BITBUCKET_TOKEN` env var, base URL from `BITBUCKET_URL` env var
5. Frontend shows "Bitbucket Server" in the provider dropdown
6. When "Bitbucket Server" is selected, repo input label shows "project/repo" and placeholder shows example like "PROJ/my-repo"
7. Error handling matches the pattern established by GitHub and local providers

## Assumptions

- Bitbucket Server REST API v1.0 is available at `{BITBUCKET_URL}/rest/api/1.0/`
- Compare endpoint: `GET /rest/api/1.0/projects/{project}/repos/{slug}/compare/diff?from={base}&to={head}` (or equivalent)
- The compare/diff endpoint returns unified diff format or per-file hunks that can be converted to unified diff
- `BITBUCKET_TOKEN` is a personal access token with repo read permissions
- Bitbucket Server uses `project-key/repo-slug` as the repo identifier (not owner/repo like GitHub)
- The provider routing from the local-git-provider spec is already in place

## Constraints

- Must use the provider routing pattern established by the local-git-provider spec
- `CompareResponse` model unchanged — same schema as GitHub and local providers
- No new Python dependencies — httpx already available
- New provider follows the same structural pattern as existing providers
- Frontend remains single `index.html` with no build step
- `make precommit` must pass
- All existing tests (GitHub + local) must still pass

## Failure Modes

| Trigger | Expected behavior | Recovery |
|---------|-------------------|----------|
| `BITBUCKET_URL` not set | API returns 503 "Bitbucket Server URL not configured. Set BITBUCKET_URL env var" | User sets env var |
| `BITBUCKET_TOKEN` not set | API returns 503 "Authentication required. Set BITBUCKET_TOKEN env var" | User sets env var |
| Invalid project/repo format | API returns 400 "Invalid repo format. Expected 'PROJECT/repo-slug'" | User corrects input |
| Project or repo not found | Bitbucket returns 404 → API returns 404 "Repository not found" | User corrects input |
| Invalid ref | Bitbucket returns 404 → API returns 404 "Ref not found" | User corrects input |
| Auth token invalid/expired | Bitbucket returns 401 → API returns 401 "Authentication failed" | User updates token |
| Network timeout | httpx timeout → API returns 504 "Request timed out" | User retries |
| Bitbucket Server unreachable | httpx connection error → API returns 502 "Cannot reach Bitbucket Server" | User checks URL/network |

## Security / Abuse Cases

- Token passed via env var only, never exposed to frontend
- Backend proxies Bitbucket API — frontend never sees the token
- Repo input validated: must match `PROJECT/repo-slug` pattern
- Ref input validated: same regex as other providers
- `BITBUCKET_URL` must be a valid URL (reject non-URL values)

See `docs/architecture.md` for provider pattern, config format, and frontend approach.

## Acceptance Criteria

- [ ] `make precommit` passes
- [ ] `GET /api/compare?provider=bitbucket&repo=PROJECT/slug&base=ref1&head=ref2` returns diff from Bitbucket Server
- [ ] Correct file statuses (added/modified/deleted/renamed)
- [ ] Error message for missing `BITBUCKET_URL` (503)
- [ ] Error message for missing `BITBUCKET_TOKEN` (503)
- [ ] Error message for invalid repo format (400)
- [ ] Error message for repo not found (404)
- [ ] Error message for invalid ref (404)
- [ ] Error message for auth failure (401)
- [ ] Frontend shows "Bitbucket Server" in provider dropdown
- [ ] Selecting "Bitbucket Server" adjusts repo label and placeholder
- [ ] GitHub and local provider tests still pass (no regression)

## Verification

```
# Backend
make precommit

# Manual: Bitbucket Server diff
BITBUCKET_URL=https://bitbucket.example.com BITBUCKET_TOKEN=xxx make run
# Open http://127.0.0.1:8001
# Select provider: Bitbucket Server
# Enter: repo=PROJ/my-repo, base=master, head=feature/branch
# Verify: file tree shows, diffs render

# Manual: GitHub and local still work
# Select provider: GitHub → verify
# Select provider: Local → verify
```

## Do-Nothing Option

Without Bitbucket Server support, users with code on Bitbucket Server cannot use PR Viewer. They must use Bitbucket's built-in diff UI, which lacks the hierarchical file tree. Since many enterprise teams use Bitbucket Server, this is a significant gap. The cost is moderate (2-3 prompts) given the provider routing is already in place.
