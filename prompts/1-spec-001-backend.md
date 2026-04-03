---
status: created
spec: [001-commit-diff-viewer]
created: "2026-04-03T12:00:00Z"
branch: dark-factory/commit-diff-viewer
---

<summary>
- A new `GET /api/compare` endpoint accepts repo, base ref, and head ref query parameters
- The endpoint calls GitHub Compare API and returns a JSON list of changed files with diffs
- Repo and ref inputs are validated server-side: invalid patterns return 400 with a clear error message
- GitHub API error codes are mapped to user-friendly messages: 401 → auth required, 403 → rate limit, 404 → repo/ref not found, timeout → request timed out
- GITHUB_TOKEN is read from the environment and never exposed in any response
- A new GitHub provider module handles all GitHub API interaction via httpx
- A `CompareResult` response model captures file paths, change status (added/modified/deleted/renamed), and raw unified diffs
- When GitHub returns a truncated response (3000-file limit), the response includes a warning flag
- All new code paths are covered by pytest tests using respx to mock httpx
</summary>

<objective>
Build the backend compare API: a FastAPI endpoint at `GET /api/compare` that accepts a GitHub repo and two git refs, fetches the comparison via GitHub's Compare API using GITHUB_TOKEN, and returns structured JSON with changed files and their diffs. All GitHub error cases must be handled and surfaced as meaningful HTTP responses.
</objective>

<context>
Read `CLAUDE.md` for project conventions and `docs/architecture.md` if it exists.

Read these files before making changes:
- `src/pr_viewer/providers/base.py` — existing models (`FileChange`, `FileTreeNode`, `PullRequest`) and `Provider` protocol
- `src/pr_viewer/factory.py` — how routers are registered and app is created
- `src/pr_viewer/config.py` — `Config` and `ServerConfig` dataclasses, `load_config()`
- `src/pr_viewer/__main__.py` — entry point
- `tests/test_factory.py` — existing test style (FastAPI TestClient, no fixtures needed)
- `tests/test_config.py` — existing test style
- `pyproject.toml` — available dependencies (fastapi, httpx, pydantic, respx for tests)

The project uses:
- Python 3.12+, managed by `uv`
- FastAPI with async route handlers
- httpx for HTTP client calls (async)
- pydantic v2 for response models
- pytest with pytest-asyncio (`asyncio_mode = "auto"`)
- respx for mocking httpx in tests
- ruff for linting/formatting (line length 100)
- mypy in strict mode
</context>

<requirements>
1. **Add response models** in `src/pr_viewer/api/compare.py` (new file):
   - `FileChangeResponse(BaseModel)` with fields:
     - `path: str` — full file path
     - `status: str` — one of `"added"`, `"modified"`, `"deleted"`, `"renamed"`
     - `diff: str` — raw unified diff string (empty string if no diff)
   - `CompareResponse(BaseModel)` with fields:
     - `files: list[FileChangeResponse]`
     - `truncated: bool` — True when GitHub capped the result at its 3000-file limit
     - `total_files: int` — total changed files as reported by GitHub

2. **Add input validation** in `src/pr_viewer/api/compare.py`:
   - Validate `repo` matches regex `^[a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+$`
   - Validate `base` and `head` match regex `^[a-zA-Z0-9._/:-]+$` (allows branch names, tags, SHAs)
   - Return HTTP 400 with `{"detail": "<message>"}` for invalid inputs before calling GitHub

3. **Create GitHub provider** in `src/pr_viewer/providers/github.py`:
   - Class `GitHubProvider` with constructor `__init__(self, token: str, http_client: httpx.AsyncClient)`
   - Method: `async def compare(self, repo: str, base: str, head: str) -> CompareResponse`
   - Calls `GET https://api.github.com/repos/{repo}/compare/{base}...{head}`
   - Sets headers: `Authorization: Bearer {token}`, `Accept: application/vnd.github+json`, `X-GitHub-Api-Version: 2022-11-28`
   - Maps GitHub response fields to `CompareResponse`:
     - Each file in `response["files"]` maps to `FileChangeResponse`
     - GitHub `status` field: map `"added"` → `"added"`, `"modified"` → `"modified"`, `"removed"` → `"deleted"`, `"renamed"` → `"renamed"`, anything else → `"modified"`
     - `diff` from `file.get("patch", "")` — may be absent for binary files
     - `truncated` = `True` when GitHub's response has `"truncated": true` or when `total` count > len(files)
     - `total_files` = `response.get("total_commits", 0)` — actually use `len(response["files"])` for returned files and check `response.get("truncated", False)` for the truncated flag
   - Error mapping (raise `fastapi.HTTPException`):
     - `httpx.TimeoutException` → 504, detail `"Request timed out. Please retry."`
     - HTTP 401 → 401, detail `"Authentication required. Set GITHUB_TOKEN environment variable."`
     - HTTP 403 → 429, detail `"GitHub API rate limit exceeded. Try again later."`
     - HTTP 404 → 404, detail `"Repository or ref not found. Check the repo name and refs."`
     - HTTP 422 → 422, detail `"Invalid ref. Refs must be branch names, tags, or commit SHAs."`
     - Any other non-2xx → 502, detail `"GitHub API error: {status_code}"`

4. **Add the router** in `src/pr_viewer/api/compare.py`:
   - `router = APIRouter(prefix="/api")`
   - `@router.get("/compare", response_model=CompareResponse)`
   - `async def compare(repo: str, base: str, head: str) -> CompareResponse:`
   - Read `GITHUB_TOKEN` from `os.environ.get("GITHUB_TOKEN", "")` inside the handler
   - Instantiate `GitHubProvider(token=token, http_client=httpx.AsyncClient())` and call `compare(repo, base, head)`
   - If token is empty, return HTTP 401 with detail `"Authentication required. Set GITHUB_TOKEN environment variable."`
   - Use `async with httpx.AsyncClient() as client:` to manage the client lifecycle

5. **Register the router** in `src/pr_viewer/factory.py`:
   - Import `from pr_viewer.api.compare import router as compare_router`
   - Add `app.include_router(compare_router)` after creating the app

6. **Create `src/pr_viewer/api/__init__.py`** if it does not exist (empty file is fine — it already exists per the skeleton).

7. **Write tests** in `tests/test_compare.py`:
   - Use `respx.mock` to intercept httpx calls — never make real network requests
   - Use `fastapi.testclient.TestClient` for endpoint tests (synchronous, matches existing test style)
   - Test cases to cover:
     a. Happy path: 200 response with files, correct mapping of added/modified/deleted/renamed statuses
     b. Truncated response: `truncated=True` when GitHub returns `"truncated": true`
     c. Missing GITHUB_TOKEN: endpoint returns 401
     d. Invalid repo format (e.g. `"not-a-valid-repo"`): endpoint returns 400
     e. Invalid ref format (e.g. ref containing shell metacharacters): endpoint returns 400
     f. GitHub 401 → endpoint returns 401
     g. GitHub 403 → endpoint returns 429
     h. GitHub 404 → endpoint returns 404
     i. GitHub 422 → endpoint returns 422
     j. File with no patch (binary file): `diff` field is empty string `""`
     k. httpx timeout: endpoint returns 504
   - Minimum 80% statement coverage for `src/pr_viewer/api/compare.py` and `src/pr_viewer/providers/github.py`
   - Use `pytest.mark.asyncio` is NOT needed — `asyncio_mode = "auto"` is already configured
   - Use `monkeypatch.setenv("GITHUB_TOKEN", "test-token")` to inject the token

8. **Do NOT modify**:
   - `src/pr_viewer/providers/base.py`
   - `src/pr_viewer/config.py`
   - `src/pr_viewer/__main__.py`
   - Any existing tests
</requirements>

<constraints>
- No new Python dependencies — use only fastapi, uvicorn, httpx, pydantic, pyyaml (all in pyproject.toml)
- GITHUB_TOKEN must never appear in any response body or log output
- Provider protocol in `providers/base.py` must remain unchanged
- Config loading from config.yaml unchanged
- `make precommit` must pass (ruff format + lint, mypy strict, pytest)
- All existing tests must still pass
- Repo input validated: must match `owner/repo` pattern (alphanumeric, hyphens, dots, underscores)
- Ref input validated: alphanumeric, hyphens, dots, slashes, colons — no shell metacharacters
- Do NOT commit — dark-factory handles git
- Frontend SPA does not exist yet — this prompt is backend only
</constraints>

<verification>
```bash
# Run all tests
make test

# Final validation
make precommit

# Manual smoke test (requires a real token):
# GITHUB_TOKEN=ghp_xxx uvicorn pr_viewer.__main__:app --reload
# curl "http://127.0.0.1:8000/api/compare?repo=bborbe/pr-viewer&base=master&head=master"
# Expected: {"files":[],"truncated":false,"total_files":0}

# Verify token is not in response:
# curl "http://127.0.0.1:8000/api/compare?repo=x/y&base=a&head=b" | grep -v ghp_
```
</verification>
