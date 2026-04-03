---
status: executing
spec: [002-local-git-provider]
summary: Added GitHub/Local provider dropdown to frontend with dynamic repo label, shareable URL support, and smoke tests.
container: pr-viewer-005-spec-002-frontend
dark-factory-version: v0.94.1-dirty
created: "2026-04-03T15:00:00Z"
queued: "2026-04-03T16:17:05Z"
started: "2026-04-03T16:25:43Z"
branch: dark-factory/local-git-provider
---

<summary>
- A provider dropdown (GitHub / Local) appears in the top bar before the repo input field
- Selecting "Local" changes the repo input label to "Repo path" and updates the placeholder to a local path example (e.g., `/Users/you/your-repo`)
- Selecting "GitHub" restores the original label and placeholder (`owner/repo`)
- The `provider` parameter is included in the API request (`/api/compare?provider=...`)
- The URL is updated to include `provider` so compare links are shareable and bookmarkable
- On page load, the provider dropdown is initialized from the URL `provider` param (defaulting to `github`)
- The repo input value is also restored from the URL on page load
- No new build steps, npm packages, or external JS dependencies are added
- All existing frontend behavior (file tree, diffs, error banners, loading state) is unchanged
</summary>

<objective>
Extend `src/pr_viewer/static/index.html` to support provider selection: add a dropdown before the repo input that switches between "GitHub" and "Local" modes, adjusts the repo input label and placeholder accordingly, sends the `provider` param to the backend, and persists the selection in the URL for shareable links. **Depends on prompt 1 (backend)** — this prompt assumes the backend already accepts `provider=github` and `provider=local`.
</objective>

<context>
Read `CLAUDE.md` for project conventions.

Read these files before making changes:
- `src/pr_viewer/static/index.html` — the entire existing frontend (all JS and CSS is inline in this single file)
- `src/pr_viewer/factory.py` — confirms static files are served from `/`

Key existing JS patterns in `index.html` to understand before editing:
- The `doCompare()` function builds the fetch URL as `/api/compare?repo=...&base=...&head=...` — this must gain `&provider=...`
- The `updateURL()` function uses `history.replaceState` to persist params — this must include `provider`
- The `loadFromURL()` function (called on page load) restores form fields from `URLSearchParams` — `provider` must be included here
- Error clearing and banner logic must remain intact

Do NOT rewrite the file from scratch — make targeted additions to the existing HTML.
</context>

<requirements>
1. **Add provider dropdown** to the `#compare-form` in the top bar:
   - Insert a `<select id="provider-select">` immediately before the repo `<input>` (or before its label if one exists):
     ```html
     <select id="provider-select">
       <option value="github">GitHub</option>
       <option value="local">Local</option>
     </select>
     ```
   - Style the `<select>` to match the existing dark-theme inputs (same background `#0d1117`, border `1px solid #30363d`, border-radius `6px`, color `#c9d1d9`, padding, font-size)

2. **Add repo input label** (if not already present):
   - Add a `<label id="repo-label" for="repo-input">` element immediately before the repo `<input id="repo-input">`
   - Default label text: `"Repo (owner/repo)"`
   - When provider is `local`: label text becomes `"Repo path"`
   - Style: small, muted text (`color: #8b949e`, `font-size: 0.85rem`) inline with the form

3. **Wire provider dropdown change event**:
   - On `change` event of `#provider-select`:
     - If `value === "local"`:
       - Set `#repo-label` text to `"Repo path"`
       - Set `#repo-input` placeholder to `/Users/you/your-repo`
     - If `value === "github"`:
       - Set `#repo-label` text to `"Repo (owner/repo)"`
       - Set `#repo-input` placeholder to `owner/repo`

4. **Include `provider` in the API request**:
   - In the form submit handler (wherever the fetch URL is built), add the provider param:
     ```js
     const provider = document.getElementById('provider-select').value;
     const url = `/api/compare?provider=${encodeURIComponent(provider)}&repo=${encodeURIComponent(repo)}&base=${encodeURIComponent(base)}&head=${encodeURIComponent(head)}`;
     ```
   - No other change to the fetch or error-handling logic

5. **Include `provider` in the URL state**:
   - In the `updateURL()` function (which uses `history.replaceState`), include the `provider` param:
     ```js
     const params = new URLSearchParams({ provider, repo, base, head });
     history.replaceState({}, '', '?' + params.toString());
     ```

6. **Restore `provider` from URL on page load**:
   - In the `loadFromURL()` function (where `repo`, `base`, `head` are restored from `URLSearchParams`), also restore `provider`:
     ```js
     const provider = params.get('provider') || 'github';
     document.getElementById('provider-select').value = provider;
     ```
   - After setting the dropdown value, fire the `change` event handler logic to update the label and placeholder to match the restored provider:
     ```js
     updateProviderUI(provider); // or inline the label/placeholder update
     ```
   - If `provider=local` is in the URL, the repo input must show the local-path placeholder immediately on load

7. **Write a smoke test** in `tests/test_frontend.py` (add a new test, do not remove existing ones):
   - `GET /` still returns 200 and body contains `"PR Viewer"` (existing test — verify it still passes)
   - `GET /` body contains `"provider-select"` (confirms the dropdown was added to the HTML)
   - `GET /` body contains `"Local"` (confirms the Local option is present)

8. **Update CHANGELOG.md**: Append under `## Unreleased`:
   - `feat: Frontend provider selector — GitHub/Local dropdown with dynamic repo label and shareable URLs`
</requirements>

<constraints>
- Frontend is a single `index.html` with no build step, no npm, vanilla JS only
- Do NOT rewrite `index.html` from scratch — make targeted edits
- No new CDN libraries or external JS dependencies
- All existing frontend behavior unchanged: file tree, diff rendering, error banners, loading state, keyboard submit
- `make precommit` must pass (ruff, mypy, pytest — frontend changes don't affect Python linting but tests must pass)
- All existing tests must still pass
- Do NOT commit — dark-factory handles git
</constraints>

<verification>
```bash
# Run all tests including new frontend smoke tests
make test

# Final validation
make precommit

# Manual verification:
# make run
# Open http://127.0.0.1:8001
# Confirm: provider dropdown shows "GitHub" and "Local" options
# Confirm: selecting "Local" changes label to "Repo path" and placeholder to a local path
# Confirm: selecting "GitHub" restores original label and placeholder
# Confirm: Local compare works: select Local, enter /workspace, base=HEAD~3, head=HEAD
# Confirm: URL includes provider=local after compare
# Confirm: reloading the page with ?provider=local&repo=/workspace&... restores the dropdown and label
# Confirm: GitHub still works after provider dropdown added
```
</verification>
