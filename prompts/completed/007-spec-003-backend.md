---
status: completed
spec: [003-bitbucket-server-provider]
summary: Added BitbucketServerCompareClient provider with REST API v1.0 integration, unified diff conversion, env-var auth, full error mapping, and 16 new pytest tests covering all specified scenarios.
container: pr-viewer-007-spec-003-backend
dark-factory-version: v0.94.1-dirty
created: "2026-04-03T17:00:00Z"
queued: "2026-04-03T19:06:26Z"
started: "2026-04-03T19:06:38Z"
completed: "2026-04-03T19:11:08Z"
---

<summary>
- A new `provider=bitbucket` value is accepted by `GET /api/compare` — identical endpoint, new provider
- Repo input for Bitbucket is validated as `PROJECT/repo-slug` format (not `owner/repo`)
- A new Bitbucket Server provider calls the Bitbucket REST API v1.0 to fetch per-file diffs between two refs
- Auth is read from `BITBUCKET_TOKEN` env var (Bearer token); base URL from `BITBUCKET_URL` env var
- Both env vars are checked before any API call; missing either returns a clear 503 error
- `BITBUCKET_URL` is validated as a proper URL; non-URL values return a 503 error
- Bitbucket's JSON diff format (hunks + segments) is converted to unified diff strings compatible with diff2html
- File statuses are derived from source/destination nullness and path equality (added/deleted/renamed/modified)
- All failure modes from the spec return the correct HTTP status and human-readable message
- All new code paths have pytest coverage; GitHub and local provider tests continue to pass
</summary>

<objective>
Add `provider=bitbucket` support to `GET /api/compare` by implementing a `BitbucketServerCompareClient` that authenticates via env vars, fetches diffs from the Bitbucket Server REST API v1.0, and converts Bitbucket's JSON diff format into the existing `CompareResponse` schema. The schema is unchanged; only a new routing branch and a new provider file are added.
</objective>

<context>
Read `CLAUDE.md` for project conventions.

Read these files before making changes:
- `src/pr_viewer/api/compare.py` — current routing: `_VALID_PROVIDERS`, `compare()` handler, how `local` and `github` branches work
- `src/pr_viewer/providers/github.py` — httpx async client pattern, error mapping, response parsing
- `src/pr_viewer/providers/local.py` — provider structure, `TYPE_CHECKING` + deferred import pattern for `CompareResponse`
- `src/pr_viewer/providers/base.py` — `Provider` protocol (do NOT modify)
- `tests/test_compare.py` — existing GitHub test style (respx.mock, monkeypatch.setenv, TestClient)
- `tests/test_compare_local.py` — existing local test style (patch, MagicMock)
- `pyproject.toml` — available dependencies

**Bitbucket Server REST API v1.0 — compare/diff endpoint:**

```
GET {BITBUCKET_URL}/rest/api/1.0/projects/{project}/repos/{slug}/compare/diff
    ?from={base}&to={head}&limit=500
Authorization: Bearer {BITBUCKET_TOKEN}
```

Response shape:
```json
{
  "diffs": [
    {
      "source": {"toString": "path/to/file.py"},
      "destination": {"toString": "path/to/file.py"},
      "hunks": [
        {
          "sourceLine": 1,
          "sourceSpan": 3,
          "destinationLine": 1,
          "destinationSpan": 4,
          "segments": [
            {
              "type": "CONTEXT",
              "lines": [{"source": 1, "destination": 1, "line": "content"}]
            },
            {
              "type": "REMOVED",
              "lines": [{"source": 2, "destination": 0, "line": "old line"}]
            },
            {
              "type": "ADDED",
              "lines": [{"source": 0, "destination": 2, "line": "new line"}]
            }
          ]
        }
      ],
      "truncated": false
    }
  ],
  "isLastPage": true
}
```

Segment types: `"CONTEXT"`, `"ADDED"`, `"REMOVED"`.
`source` is `null` for added files; `destination` is `null` for deleted files.
`source.toString` != `destination.toString` means renamed.
</context>

<requirements>
1. **Create `src/pr_viewer/providers/bitbucket_server.py`**:

   - Use `from __future__ import annotations` and `TYPE_CHECKING` guard for `CompareResponse` import (same pattern as `github.py` and `local.py`)
   - Import: `import os, re; import httpx; from fastapi import HTTPException; if TYPE_CHECKING: from pr_viewer.api.compare import CompareResponse`

   - **Validation constants** (module level):
     ```python
     _REPO_RE = re.compile(r"^[A-Z0-9_.-]+/[a-zA-Z0-9._-]+$", re.IGNORECASE)
     _URL_RE = re.compile(r"^https?://[^\s/$.?#].[^\s]*$")
     ```

   - **Class `BitbucketServerCompareClient`**:
     - Constructor: `__init__(self, base_url: str, token: str, http_client: httpx.AsyncClient) -> None`
     - Store `self._base_url = base_url.rstrip("/")`, `self._token = token`, `self._client = http_client`
     - Method: `async def compare(self, repo: str, base: str, head: str) -> CompareResponse`

   - **Inside `compare()`**:

     a. **Deferred import** at top of method body:
        ```python
        from pr_viewer.api.compare import CompareResponse, FileChangeResponse
        ```

     b. **Repo format validation**:
        ```python
        if not _REPO_RE.match(repo):
            raise HTTPException(status_code=400, detail="Invalid repo format. Expected 'PROJECT/repo-slug'.")
        project, slug = repo.split("/", 1)
        ```

     c. **Build URL**:
        ```python
        url = (
            f"{self._base_url}/rest/api/1.0/projects/{project}"
            f"/repos/{slug}/compare/diff"
        )
        params = {"from": base, "to": head, "limit": 500}
        headers = {"Authorization": f"Bearer {self._token}"}
        ```

     d. **HTTP call with error handling** (wrap in try/except):
        ```python
        try:
            response = await self._client.get(url, headers=headers, params=params)
        except httpx.TimeoutException as exc:
            raise HTTPException(status_code=504, detail="Request timed out.") from exc
        except httpx.ConnectError as exc:
            raise HTTPException(status_code=502, detail="Cannot reach Bitbucket Server. Check BITBUCKET_URL.") from exc
        ```

     e. **HTTP status mapping** (in order):
        - `401` → `HTTPException(401, "Authentication failed. Check BITBUCKET_TOKEN.")`
        - `404` → check response body: if `"Repository" in body` → `HTTPException(404, "Repository not found.")`, else → `HTTPException(404, "Ref not found.")`
        - `>=300` → `HTTPException(502, f"Bitbucket Server error: {response.status_code}")`

     f. **Parse JSON**:
        ```python
        data = response.json()
        raw_diffs: list[dict[str, object]] = data.get("diffs", [])
        ```

     g. **Convert each diff to `FileChangeResponse`**:
        Call `_convert_diff(d)` (module-level helper) that returns `FileChangeResponse`.

     h. **Return**:
        ```python
        return CompareResponse(files=files, truncated=any_truncated, total_files=len(files))
        ```
        Where `any_truncated` is `True` if any `d.get("truncated") is True`.

   - **Module-level helper `_convert_diff(d: dict[str, object]) -> FileChangeResponse`**:
     (import `FileChangeResponse` inside the helper using `from pr_viewer.api.compare import FileChangeResponse`)

     a. **Extract paths**:
        ```python
        src = (d.get("source") or {}).get("toString", "") or ""  # type: ignore[union-attr]
        dst = (d.get("destination") or {}).get("toString", "") or ""  # type: ignore[union-attr]
        ```

     b. **Determine status and canonical path**:
        - `src == ""` → `status="added"`, `path=dst`
        - `dst == ""` → `status="deleted"`, `path=src`
        - `src != dst` → `status="renamed"`, `path=dst`
        - else → `status="modified"`, `path=src`

     c. **Build unified diff from hunks** — call `_hunks_to_unified(src, dst, hunks)`:
        ```
        def _hunks_to_unified(src_path: str, dst_path: str, hunks: list[dict[str, object]]) -> str
        ```
        Output format:
        ```
        diff --git a/{src_path} b/{dst_path}
        --- a/{src_path}
        +++ b/{dst_path}
        @@ -{sourceLine},{sourceSpan} +{destinationLine},{destinationSpan} @@
         context line
        -removed line
        +added line
        ```
        - Segment type `"CONTEXT"` → prefix ` ` (space)
        - Segment type `"ADDED"` → prefix `+`
        - Segment type `"REMOVED"` → prefix `-`
        - Other segment types → prefix ` ` (treat as context)
        - If `hunks` is empty, return empty string (binary/no-content file)
        - For added files, `src_path` is `/dev/null`; for deleted files, `dst_path` is `/dev/null`

     d. **Return**:
        ```python
        return FileChangeResponse(path=path, status=status, diff=unified)
        ```

2. **Extend `src/pr_viewer/api/compare.py`**:

   a. Add `"bitbucket"` to `_VALID_PROVIDERS`:
      ```python
      _VALID_PROVIDERS = {"github", "local", "bitbucket"}
      ```
      Update the 400 error message to: `"Unknown provider. Supported: github, local, bitbucket"`

   b. Add import (module-level, below the existing local import):
      ```python
      from pr_viewer.providers.bitbucket_server import BitbucketServerCompareClient
      ```

   c. Add Bitbucket routing branch in `compare()`, after the `local` branch and before the `github` branch:
      ```python
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
      ```
      Note: For the `bitbucket` provider, `_REPO_RE` validation is skipped in `compare()` — repo validation is done inside `BitbucketServerCompareClient.compare()` with the Bitbucket-specific regex.

   d. The `re` module is already imported; the `_REPO_RE` regex in `compare.py` applies only to GitHub (it already exists and is only used in the GitHub branch). For the Bitbucket branch, skip `_REPO_RE` validation at the handler level (as done for `local`).

3. **Write tests in `tests/test_compare_bitbucket.py`**:

   - Use `respx` to mock httpx calls (same as GitHub tests)
   - Use `TestClient` from `fastapi.testclient`
   - Use `monkeypatch.setenv` to set `BITBUCKET_URL` and `BITBUCKET_TOKEN`
   - All tests use base URL `http://bitbucket.example.com`
   - All tests set `BITBUCKET_URL=http://bitbucket.example.com` and `BITBUCKET_TOKEN=test-token`

   **Helper** to build a minimal Bitbucket diff response:
   ```python
   def bb_response(diffs: list[dict], is_last_page: bool = True) -> dict:
       return {"diffs": diffs, "isLastPage": is_last_page}

   def bb_diff(src: str | None, dst: str | None, hunks: list[dict] | None = None) -> dict:
       return {
           "source": {"toString": src} if src else None,
           "destination": {"toString": dst} if dst else None,
           "hunks": hunks or [],
           "truncated": False,
       }
   ```

   **Test cases** (each is a standalone `def test_*` function):

   a. `test_valid_diff` — single modified file with one hunk (CONTEXT + REMOVED + ADDED segments); assert 200, status="modified", path correct, diff contains `---` and `+++`

   b. `test_added_file` — `source=None`, `destination="new.py"`; assert status="added", diff header has `/dev/null`

   c. `test_deleted_file` — `source="old.py"`, `destination=None`; assert status="deleted"

   d. `test_renamed_file` — `source="old.py"`, `destination="new.py"`; assert status="renamed", path="new.py"

   e. `test_missing_bitbucket_url` — do NOT set `BITBUCKET_URL` env var; assert 503 "not configured"

   f. `test_invalid_bitbucket_url` — set `BITBUCKET_URL=not-a-url`; assert 503 "not a valid URL"

   g. `test_missing_token` — set URL but not TOKEN; assert 503 "BITBUCKET_TOKEN"

   h. `test_invalid_repo_format` — set both env vars; send `repo=invalid`; assert 400 "Invalid repo format"

   i. `test_auth_failure` — Bitbucket returns 401; assert response 401 "Authentication failed"

   j. `test_repo_not_found` — Bitbucket returns 404 with body containing "Repository"; assert 404 "Repository not found"

   k. `test_ref_not_found` — Bitbucket returns 404 with body containing "Ref"; assert 404 "Ref not found"

   l. `test_timeout` — raise `httpx.TimeoutException` from the mock; assert 504

   m. `test_connection_error` — raise `httpx.ConnectError` from the mock; assert 502 "Cannot reach"

   n. `test_truncated_diff` — response has `"truncated": True` on one diff; assert `response["truncated"] is True`

   o. `test_unknown_provider_now_includes_bitbucket` — send `provider=unknown`; assert 400 and detail contains "bitbucket"

   p. `test_github_unaffected` — send `provider=github` with valid GITHUB_TOKEN; mock GitHub API returns a file; assert 200 (regression guard)

4. **Update `CHANGELOG.md`**: Add a `## Unreleased` section at the top (if it doesn't already exist) and append:
   - `feat: Bitbucket Server provider for compare endpoint — calls REST API v1.0 with Bearer token auth`
   - `feat: Extend provider routing to support provider=bitbucket`
</requirements>

<constraints>
- Must use the `provider=bitbucket` routing pattern established in `compare.py` — do not change the endpoint path or schema
- `CompareResponse` model unchanged — same `files`, `truncated`, `total_files` shape
- No new Python dependencies — httpx already available; use only stdlib (`os`, `re`)
- New provider follows the same structural pattern as `github.py`: constructor receives `base_url`, `token`, `http_client`; `compare()` is async
- All subprocess calls (if any) must never use `shell=True` — N/A for this provider (uses httpx)
- `BITBUCKET_URL` and `BITBUCKET_TOKEN` env vars are read in `compare.py` and passed to the provider constructor (mirrors how `GITHUB_TOKEN` is read in the handler and passed to `GitHubCompareClient`)
- Token must never be exposed to the frontend or appear in logs
- `make precommit` must pass (ruff, mypy strict, pytest)
- All existing GitHub and local provider tests must still pass
- Do NOT modify `src/pr_viewer/providers/base.py`
- Do NOT commit — dark-factory handles git
- Frontend changes are out of scope for this prompt
</constraints>

<verification>
```bash
make test
make precommit
```
</verification>
