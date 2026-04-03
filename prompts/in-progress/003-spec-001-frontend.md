---
status: approved
spec: [001-commit-diff-viewer]
created: "2026-04-03T12:00:00Z"
queued: "2026-04-03T12:26:01Z"
branch: dark-factory/commit-diff-viewer
---

<summary>
- User opens http://127.0.0.1:8000 and sees an input form with three fields: repo (owner/name), base ref, head ref
- Submitting the form fetches from the backend `/api/compare` endpoint and renders results without a page reload
- A collapsible hierarchical file tree appears in the left sidebar, built from the flat list of file paths
- Each file in the tree shows a colored change-type icon: green "+" for added, orange pencil for modified, red "−" for deleted, grey arrow for renamed
- Folders are shown expanded by default and can be toggled open/closed by clicking
- Clicking a file in the tree scrolls the right panel smoothly to that file's diff
- The right panel renders side-by-side diffs with syntax highlighting using diff2html from CDN
- All error cases show a human-readable message: missing token, repo not found, ref not found, rate limit, timeout
- A loading indicator is shown while the API call is in progress
- The entire frontend is a single `index.html` file with no build step, no npm, vanilla JS only
</summary>

<objective>
Build the single-page frontend for the commit diff viewer: an `index.html` that lets users enter a GitHub repo and two refs, then displays a collapsible file tree sidebar and a side-by-side diff view rendered by diff2html. **Depends on prompt 1 (backend)** — this prompt assumes `src/pr_viewer/api/compare.py` exists with `GET /api/compare` returning `CompareResponse` JSON. If prompt 1 has not completed, this prompt will fail.
</objective>

<context>
Read `CLAUDE.md` for project conventions.

Read these files before making changes:
- `src/pr_viewer/factory.py` — how static files are mounted (`/static` → `src/pr_viewer/static/`, html=True)
- `src/pr_viewer/static/index.html` — check whether a skeleton already exists
- `src/pr_viewer/api/compare.py` — the `CompareResponse` JSON shape:
  ```json
  {
    "files": [
      {"path": "src/foo/bar.py", "status": "modified", "diff": "--- a/...\n+++ b/...\n..."},
      {"path": "README.md", "status": "added", "diff": "..."}
    ],
    "truncated": false,
    "total_files": 2
  }
  ```

The frontend must use:
- diff2html from CDN (pin version): `https://cdn.jsdelivr.net/npm/diff2html@3.4.48/bundles/js/diff2html-ui.min.js`
- diff2html CSS from CDN (pin version): `https://cdn.jsdelivr.net/npm/diff2html@3.4.48/bundles/css/diff2html.min.css`
- No npm, no build step, no frameworks — vanilla JS only
- The static file mount uses `html=True` so `GET /` serves `index.html` automatically

The FastAPI app mounts `/static` as a StaticFiles directory with `html=True`, meaning:
- `GET /` → serves `src/pr_viewer/static/index.html`
- Verify this works by checking `factory.py` — the mount path is `"/"` not `"/static"` if you want root to serve it, OR add a separate root redirect. Check `factory.py` to confirm the current mount path and adjust accordingly.
</context>

<requirements>
1. **Create `src/pr_viewer/static/index.html`** — a single self-contained HTML file:

   **Layout** (CSS grid or flexbox):
   - Fixed top bar: app title "PR Viewer", input form inline (repo text input, base text input, head text input, "Compare" button)
   - Left sidebar (~280px wide, full height below top bar): scrollable file tree
   - Right main panel (remaining width): scrollable diff view

   **Input form behavior**:
   - Pressing Enter in any input field submits the form
   - "Compare" button triggers the fetch
   - While fetching: disable the button, show a spinner or "Loading…" text inside the button
   - After success or error: re-enable the button

   **API call**:
   - `GET /api/compare?repo={repo}&base={base}&head={head}`
   - On success: render file tree and diffs
   - On error (non-2xx): show the `detail` field from the JSON response body in a red error banner below the top bar
   - If the response has `truncated: true`: show a yellow warning banner: "Showing first N of M files (GitHub API limit)"

   **File tree** (left sidebar):
   - Build a tree from the flat `files[].path` list by splitting on `/`
   - Folders render as `▶ folder-name` when collapsed, `▼ folder-name` when expanded (expanded by default)
   - Files render as `{icon} filename`
   - Change type icons (use Unicode or simple colored text):
     - Added: green `＋` (or `[+]`)
     - Modified: orange `✎` (or `[M]`)
     - Deleted: red `−` (or `[-]`)
     - Renamed: grey `→` (or `[R]`)
   - Clicking a folder toggles its children visible/hidden
   - Clicking a file scrolls the right panel to the corresponding diff section (use `element.scrollIntoView({behavior: "smooth"})`)
   - Each diff section in the right panel must have an `id` attribute derived from the file path (replace `/` and `.` with `-`, prefix with `file-`)

   **Diff view** (right panel):
   - For each file in the response, render a section:
     - Header: `<h3 id="{derived-id}">{file.path}</h3>` with the change type badge
     - Diff body: rendered via diff2html in side-by-side mode
   - Use `Diff2HtmlUI` from diff2html:
     ```js
     const diff2htmlUi = new Diff2HtmlUI(targetElement, diffString, {
       drawFileList: false,
       matching: 'lines',
       outputFormat: 'side-by-side',
       highlight: true,
     });
     diff2htmlUi.draw();
     diff2htmlUi.highlightCode();
     ```
   - Files with empty `diff` string (binary files): show a grey notice "Binary file — no diff available"

   **Error states**:
   - Show error banner (red background, dismissible) for any API error
   - Clear previous results and error banner on each new Compare click
   - Error message text comes from the response `detail` field; fall back to "Unexpected error" if not present

   **Truncation warning**:
   - If `truncated: true` in the response, show a yellow banner: `"Showing first {files.length} of {total_files} files (GitHub API limit)"`

2. **Ensure the root route serves `index.html`**:
   - Check `src/pr_viewer/factory.py`: if `StaticFiles` is mounted at `"/static"`, change the mount to `"/"` so that `GET /` serves the SPA
   - Alternatively, add a redirect: `@app.get("/") → RedirectResponse("/static/index.html")`
   - The existing `/healthz` route must still work — ensure it is registered before the static mount
   - **Important**: `StaticFiles(html=True)` with mount at `"/"` intercepts all unmatched routes. Register all API routers BEFORE mounting static files.

3. **Write a smoke test** in `tests/test_frontend.py`:
   - Test that `GET /` returns 200 and the response body contains `"PR Viewer"` (confirms index.html is served)
   - Test that `GET /healthz` still returns 200 with `{"status": "ok"}` (confirms API routes still work)
   - Use `TestClient` (synchronous, matches existing test style)

4. **Update CHANGELOG.md**: Add entry under `## Unreleased` → `### Added`:
   - Single-page frontend with hierarchical file tree and side-by-side diff view
   - diff2html integration for syntax-highlighted diffs

5. **Do NOT modify**:
   - `src/pr_viewer/providers/base.py`
   - `src/pr_viewer/config.py`
   - `src/pr_viewer/__main__.py`
   - Any existing tests
   - `src/pr_viewer/api/compare.py` (unless fixing the root route requires a factory.py change only)
</requirements>

<constraints>
- No npm, no build step — frontend is vanilla JS + CDN libraries only
- No new Python dependencies
- diff2html loaded from CDN (pinned): `https://cdn.jsdelivr.net/npm/diff2html@3.4.48/bundles/js/diff2html-ui.min.js`
- diff2html CSS from CDN (pinned): `https://cdn.jsdelivr.net/npm/diff2html@3.4.48/bundles/css/diff2html.min.css`
- File tree must remain responsive with 1000+ files — build the tree in a single pass, render lazily (don't re-render on every click; toggle CSS display instead)
- GITHUB_TOKEN must never appear in the frontend code or HTML
- `make precommit` must pass (ruff, mypy, pytest)
- All existing tests must still pass
- Do NOT commit — dark-factory handles git
</constraints>

<verification>
```bash
# Run all tests
make test

# Final validation
make precommit

# Manual smoke test:
# GITHUB_TOKEN=ghp_xxx make run
# Open http://127.0.0.1:8000
# Enter: repo=bborbe/pr-viewer, base=master, head=<any-branch-or-sha>
# Verify: file tree shows in left sidebar, diffs render side-by-side in right panel
# Verify: clicking a file in tree scrolls to its diff
# Verify: folders can be collapsed/expanded
# Verify: error shows when GITHUB_TOKEN is unset
```
</verification>
