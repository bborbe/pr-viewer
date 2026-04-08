---
status: completed
summary: Raised local provider default diff limit to 50 MB, added max_bytes query parameter with validation (1 KB–500 MB) forwarded to local provider, and fixed truncation banner to distinguish file-count truncation from byte-cap truncation with actionable message.
container: pr-viewer-010-improve-diff-truncation
dark-factory-version: v0.107.6
created: "2026-04-08T00:00:00Z"
queued: "2026-04-08T14:28:36Z"
started: "2026-04-08T14:28:49Z"
completed: "2026-04-08T14:30:33Z"
---

<summary>
- Truncation banner no longer misleads when all files are listed but diff content was size-capped
- Local provider default diff size limit raised so typical large PRs are no longer truncated
- Users can override the diff size limit per-request via a query parameter (bounded for safety)
- Frontend forwards an optional `max_bytes` URL parameter to the backend
- Tests updated to cover new message logic, new default, and override parameter
</summary>

<objective>
Fix the misleading "Diff truncated: showing first N of M files" banner when N==M (all files listed, only content was byte-capped) in the local provider, raise the default limit, and allow per-request override via `max_bytes`.
</objective>

<context>
Read `CLAUDE.md` and these files before changes:
- `src/pr_viewer/providers/local.py` (constant `_MAX_DIFF_BYTES` at line 13; `compare` method around line 75; truncation block around lines 131-134, return at line 147)
- `src/pr_viewer/api/compare.py` (router `/compare` at line 33, local provider branch around line 54)
- `src/pr_viewer/static/index.html` (truncation banner rendering near line 806)
- `tests/` — find existing tests for `local.py` and `api/compare.py` via `grep -rn "truncated\|_MAX_DIFF_BYTES\|local" tests/`
- Completed prompt `prompts/completed/009-fix-truncation-warning-message.md` for prior context on the banner
</context>

<requirements>

1. **Backend: raise default `_MAX_DIFF_BYTES`** in `src/pr_viewer/providers/local.py`:
   - Change from `10 * 1024 * 1024` to `50 * 1024 * 1024` (50 MB)
   - Keep it as a module-level constant so tests can monkeypatch it

2. **Backend: accept `max_bytes` override** on the local provider `compare` method:
   - Update signature: `async def compare(self, repo: str, base: str, head: str, max_bytes: int | None = None) -> CompareResponse`
   - Inside the method, resolve `effective_limit = max_bytes if max_bytes is not None else _MAX_DIFF_BYTES`
   - Use `effective_limit` in place of `_MAX_DIFF_BYTES` in the truncation check and slice (around lines 131-134)
   - Other providers (`github.py`, `bitbucket_server.py`) must keep working — do NOT change their signatures. The base `Provider` protocol (if any) should remain compatible; only the concrete `LocalGitCompareClient.compare` gains the optional kwarg.

3. **Backend: accept `max_bytes` query param** on `/compare` in `src/pr_viewer/api/compare.py`:
   - Add parameter: `max_bytes: int | None = None`
   - Validate: if provided, must be `>= 1024` and `<= 500 * 1024 * 1024` (500 MB). On violation raise `HTTPException(status_code=400, detail="max_bytes out of range")`
   - Only forward `max_bytes` to the local provider branch (`local_client.compare(repo, base, head, max_bytes=max_bytes)`). Do not pass it to github/bitbucket branches.

4. **Backend: distinguish "files truncated" vs "content truncated"** — acceptable approach: keep the single `truncated: bool` field (frontend distinguishes using `files.length` vs `total_files`). The local provider already sets `total_files=len(files)` — this means for the local provider `files.length == total_files` always, and the frontend can rely on that to pick the correct message. No schema change required.

5. **Frontend: banner logic** in `src/pr_viewer/static/index.html` near line 806, inside the `if (data.truncated)` block:
   - If `data.files.length < data.total_files`: show `"Showing first " + data.files.length + " of " + data.total_files + " files (diff truncated)"`
   - Else: show `"Diff content truncated (size limit exceeded) — add ?max_bytes=<bytes> to URL to increase"`
   - Replace the current single-message branch. Preserve existing CSS classes / element structure.

6. **Frontend: forward `max_bytes` URL param**:
   - Where the frontend builds the `/compare?...` request URL, read `max_bytes` from `new URLSearchParams(window.location.search)` and, if present and non-empty, append `&max_bytes=<value>` to the fetch URL. Do not validate client-side — let backend reject invalid values and surface the error via existing error handling.

7. **Tests** — update and add tests:
   - `tests/` test for `local.py` compare: add a test that passes `max_bytes=1024` and asserts `truncated is True` and returned diff content length reflects the smaller limit
   - Add test asserting default limit is 50 MB (read `_MAX_DIFF_BYTES`)
   - `tests/` test for `/compare` endpoint: add tests that `max_bytes=500` returns HTTP 400, `max_bytes=600_000_000` returns HTTP 400, and a valid `max_bytes` is forwarded to the local provider (mock provider and assert kwarg)
   - Ensure all existing tests still pass. Fix any test that hard-coded the 10 MB value.

</requirements>

<constraints>
- Do NOT change signatures of `github.py` / `bitbucket_server.py` compare methods
- Do NOT add new response fields — frontend distinguishes via `files.length` vs `total_files`
- Do NOT commit — dark-factory handles git
- Existing tests must still pass
- Keep banner DOM structure / classes unchanged; only change the text
</constraints>

<verification>
Run `make precommit` — must pass.
Run `make test` — all tests green.
Manually verify: start server against a repo with a huge diff; banner reads "Diff content truncated (size limit exceeded) — add ?max_bytes=<bytes> to URL to increase" when all files are listed.
</verification>
