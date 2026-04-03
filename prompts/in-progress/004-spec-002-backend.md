---
status: executing
spec: [002-local-git-provider]
summary: Added local git provider for /api/compare with provider= query parameter routing, path validation, subprocess-based git diff, and full pytest coverage
container: pr-viewer-004-spec-002-backend
dark-factory-version: v0.94.1-dirty
created: "2026-04-03T15:00:00Z"
queued: "2026-04-03T16:17:02Z"
started: "2026-04-03T16:17:03Z"
branch: dark-factory/local-git-provider
---

<summary>
- `/api/compare` gains a new optional `provider` query parameter (`github` or `local`, default: `github`)
- When `provider=github` (or omitted), behavior is identical to today — no regression
- When `provider=local`, `repo` is an absolute path to a local git checkout, not an `owner/repo` slug
- A new local provider runs `git diff base...head` via subprocess (argument list, never shell=True) and returns the same `CompareResponse` shape as the GitHub provider
- File statuses (added/modified/deleted/renamed) are parsed from `git diff --stat` output
- Invalid provider values return 400 with a clear error listing supported values
- Relative paths, symlinks, non-existent directories, and non-git directories are each rejected with the appropriate 4xx error
- Invalid or unknown refs in the local repo return 404
- `git` not found on PATH returns 500
- Diffs larger than 10 MB are truncated and flagged with `truncated=true`
- All new code paths are covered by pytest tests using subprocess mocking (no real git calls in tests)
</summary>

<objective>
Refactor `GET /api/compare` to route requests to the correct provider based on a new `provider` query parameter, and implement a `local` provider that runs `git diff` on a local repo path via subprocess. The `CompareResponse` schema is unchanged. GitHub behavior is identical to today when `provider=github` or the parameter is omitted.
</objective>

<context>
Read `CLAUDE.md` for project conventions.

Read these files before making changes:
- `src/pr_viewer/api/compare.py` — current endpoint: validates repo/ref, reads GITHUB_TOKEN, calls GitHubCompareClient
- `src/pr_viewer/providers/github.py` — GitHubCompareClient with compare() method and CompareResponse import
- `src/pr_viewer/providers/base.py` — Provider protocol and FileChange/FileTreeNode/PullRequest dataclasses (do NOT modify)
- `tests/test_compare.py` — existing test style (TestClient, respx.mock, monkeypatch.setenv)
- `pyproject.toml` — available dependencies

The current `compare.py` endpoint has hard-coded GitHub logic. The refactor must:
1. Accept `provider: str = "github"` as a new query parameter
2. Validate the provider value before doing anything else
3. For `provider=github`: keep existing GitHub logic unchanged
4. For `provider=local`: skip the `owner/repo` regex, apply path validation instead, run git subprocess
</context>

<requirements>
1. **Add `provider` query parameter** to the `compare` handler in `src/pr_viewer/api/compare.py`:
   - Signature: `async def compare(repo: str, base: str, head: str, provider: str = "github") -> CompareResponse:`
   - First thing in the handler: validate `provider` is one of `{"github", "local"}`; if not, raise `HTTPException(400, detail="Unknown provider. Supported: github, local")`
   - For `provider=github`: apply existing `_REPO_RE` validation on `repo`, check GITHUB_TOKEN, call GitHubCompareClient — unchanged behavior
   - For `provider=local`: skip `_REPO_RE` validation; apply path validation (see requirement 3)

2. **Validate `base` and `head` refs** for both providers:
   - Keep existing `_REF_RE = re.compile(r"^[a-zA-Z0-9._/:-]+$")` validation for both providers
   - Raise 400 for invalid base or head in both code paths

3. **Create local provider** in `src/pr_viewer/providers/local.py`:
   - Class `LocalGitCompareClient` with constructor `__init__(self)` (no injected dependencies)
   - Method: `async def compare(self, repo: str, base: str, head: str) -> CompareResponse`
   - **Path validation** (in order, raise before running any git commands):
     - `repo` must be absolute (starts with `/`); if not, raise `HTTPException(400, detail="Repo path must be absolute, not relative.")`
     - `repo` path must exist (`os.path.exists`); if not, raise `HTTPException(404, detail=f"Directory not found: {repo}")`
     - `repo` must be a directory (`os.path.isdir`); if not, raise `HTTPException(400, detail=f"Not a directory: {repo}")`
     - Resolve symlinks with `os.path.realpath(repo)` and confirm the resolved path equals the input (or begins with a safe prefix) — raise `HTTPException(400, detail="Symlink paths are not allowed.")` if the resolved path differs from `os.path.abspath(repo)`
   - **Git repo check**: run `["git", "-C", repo, "rev-parse", "--git-dir"]`; if the exit code is non-zero, raise `HTTPException(400, detail=f"Not a git repository: {repo}")`
   - **Detect `git` not installed**: catch `FileNotFoundError` from subprocess and raise `HTTPException(500, detail="git command not found. Please install git.")`
   - **Run diff**: `["git", "-C", repo, "diff", f"{base}...{head}"]` (three-dot diff)
   - **Run stat**: `["git", "-C", repo, "diff", "--stat", f"{base}...{head}"]` — parse file statuses from output
   - **Invalid ref detection**: if either git command exits with non-zero code and stderr contains `"unknown revision"` or `"bad revision"` or `"fatal: ambiguous argument"`, raise `HTTPException(404, detail="Ref not found. Check that base and head exist in the repository.")`
   - **Truncation**: if the raw diff output exceeds 10 MB (10 * 1024 * 1024 bytes), truncate to 10 MB, set `truncated=True`; otherwise `truncated=False`
   - **File status detection**: run `["git", "-C", repo, "diff", "--name-status", f"{base}...{head}"]` for status mapping, and the plain diff for content. Parse `--name-status` output: each line is `"{letter}\t{path}"` or `"R{score}\t{old}\t{new}"` for renames. Build a map from path → status string: `A` → `"added"`, `D` → `"deleted"`, `R*` → `"renamed"`, `M` → `"modified"`, anything else → `"modified"`.
   - **Split unified diff by file**: split the output of `git diff` on `\ndiff --git` boundaries to get per-file diff strings (prefix each segment with `diff --git` except the first which already has it). Map each file's diff to its status from the `--name-status` map. Default status to `"modified"` if not found.
   - **Return**: `CompareResponse(files=[...], truncated=truncated, total_files=len(files))`
   - All subprocess calls use `subprocess.run([...], capture_output=True, text=True)` — never `shell=True`

4. **Wire local provider** in `src/pr_viewer/api/compare.py`:
   - Import: `from pr_viewer.providers.local import LocalGitCompareClient`
   - In the `compare` handler, when `provider == "local"`:
     ```python
     local_client = LocalGitCompareClient()
     return await local_client.compare(repo, base, head)
     ```
   - Note: `LocalGitCompareClient.compare` must be `async`. Since `subprocess.run` is blocking, wrap calls with `asyncio.to_thread` to avoid blocking the event loop. Follow the same `TYPE_CHECKING` + deferred import pattern from `github.py` for importing `CompareResponse` from `pr_viewer.api.compare` (to avoid circular imports).

5. **Write tests** in `tests/test_compare_local.py`:
   - Use `unittest.mock.patch` to mock `subprocess.run` — never call real git
   - Use `fastapi.testclient.TestClient` (synchronous)
   - Test cases to cover:
     a. Valid local diff: mock `git rev-parse` (success), mock `git diff --name-status` (returns `"M\tfile.py\n"`), mock `git diff` (returns a valid unified diff); assert 200 with correct `files` list
     b. Added file: `--name-status` returns `"A\tnew.py"`, assert `status="added"`
     c. Deleted file: `D\told.py`, assert `status="deleted"`
     d. Renamed file: `R100\told.py\tnew.py`, assert `status="renamed"`, path is `new.py`
     e. Relative path: assert 400 "must be absolute"
     f. Non-existent path: mock `os.path.exists` to return False, assert 404
     g. Not a directory: mock `os.path.isdir` to return False, assert 400
     h. Not a git repo: mock `git rev-parse` exits with code 1, assert 400 "Not a git repository"
     i. git not installed: mock subprocess raises `FileNotFoundError`, assert 500 "git command not found"
     j. Invalid ref: mock `git diff` exits with code 128 and stderr `"fatal: unknown revision"`, assert 404
     k. Large diff truncation: mock diff output > 10 MB, assert `truncated=True`
     l. Unknown provider: `GET /api/compare?provider=bitbucket&repo=x&base=a&head=b`, assert 400 "Unknown provider"
     m. `provider=github` still works: existing behavior unchanged (uses existing respx mocks or a simple sanity check)
   - Also add a test to `tests/test_compare.py` verifying `provider=github` param is accepted and behaves the same as no param (can reuse one existing test case with the added `&provider=github` query string)

6. **Update CHANGELOG.md**: Append under `## Unreleased`:
   - `feat: Local git provider for compare endpoint — runs git diff via subprocess`
   - `feat: Provider routing for /api/compare — new provider= query parameter (github or local)`
</requirements>

<constraints>
- Existing GitHub behavior unchanged — `provider=github` (or omitted) works exactly as before
- `CompareResponse` model unchanged — local provider returns same schema as GitHub provider
- No new Python dependencies — use only stdlib subprocess, os, asyncio
- Local provider subprocess calls must never use `shell=True`
- Repo path must be absolute (reject relative paths with 400)
- No symlink traversal — reject if `os.path.realpath(repo) != os.path.abspath(repo)`
- `make precommit` must pass (ruff, mypy strict, pytest)
- All existing tests must still pass
- Do NOT modify `src/pr_viewer/providers/base.py`
- Do NOT commit — dark-factory handles git
- Frontend changes are out of scope for this prompt
</constraints>

<verification>
```bash
# Run tests
make test

# Final validation
make precommit

# Manual verification (with a local repo):
# make run
# curl "http://127.0.0.1:8001/api/compare?provider=local&repo=/workspace&base=HEAD~3&head=HEAD"
# Expected: JSON with files list, diffs, statuses

# Regression check — GitHub still works:
# curl "http://127.0.0.1:8001/api/compare?repo=bborbe/pr-viewer&base=master&head=v0.1.0"
# curl "http://127.0.0.1:8001/api/compare?provider=github&repo=bborbe/pr-viewer&base=master&head=v0.1.0"

# Error cases:
# curl "http://127.0.0.1:8001/api/compare?provider=local&repo=relative/path&base=a&head=b"
# Expected: 400 "must be absolute"
# curl "http://127.0.0.1:8001/api/compare?provider=local&repo=/nonexistent&base=a&head=b"
# Expected: 404 "Directory not found"
# curl "http://127.0.0.1:8001/api/compare?provider=bitbucket&repo=x&base=a&head=b"
# Expected: 400 "Unknown provider. Supported: github, local"
```
</verification>
