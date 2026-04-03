---
spec: ["003"]
status: created
created: "2026-04-03T16:30:00Z"
---

<summary>
- A provider dropdown appears in the top bar form alongside the existing repo, base, and head inputs
- The dropdown lists three options: "GitHub" (default), "Local Git", "Bitbucket Server"
- When "GitHub" is selected, repo input shows label "owner/repo" and placeholder "owner/repo" — unchanged from today
- When "Local Git" is selected, repo input label changes to "repo path" and placeholder changes to "/path/to/repo"
- When "Bitbucket Server" is selected, repo input label changes to "project/repo" and placeholder changes to "PROJ/my-repo"
- The selected provider value is passed as the `provider` query parameter in every API call
- No page reload, no build step — all changes are in the single `index.html` file
- All existing behavior (GitHub diff view, file tree, error banners) is unchanged
</summary>

<objective>
Extend the `index.html` frontend to let users select a provider (GitHub, Local Git, or Bitbucket Server) from a dropdown. The chosen provider is sent as the `provider` query parameter to `GET /api/compare`, and the repo input's label/placeholder adapts to reflect the expected format for each provider. **Depends on prompt 1 (backend)** — this prompt assumes `provider=bitbucket` is already wired in `compare.py`.
</objective>

<context>
Read `CLAUDE.md` for project conventions.

Read these files before making changes:
- `src/pr_viewer/static/index.html` — full file; understand the existing form structure (around `<form id="compare-form">`), the CSS for inputs and buttons, and how `doCompare()` builds the API URL
- `src/pr_viewer/api/compare.py` — confirms valid provider values: `github`, `local`, `bitbucket`

The existing form HTML (from `index.html`):
```html
<form id="compare-form" onsubmit="return false;">
    <input id="repo-input" type="text" placeholder="owner/repo" autocomplete="off" spellcheck="false">
    <input id="base-input" type="text" placeholder="base ref" autocomplete="off" spellcheck="false">
    <input id="head-input" type="text" placeholder="head ref" autocomplete="off" spellcheck="false">
    <button id="compare-btn" type="button">Compare</button>
</form>
```

The API call (in the JS `doCompare()` function) currently builds a URL like:
```js
const url = `/api/compare?repo=${encodeURIComponent(repo)}&base=${encodeURIComponent(base)}&head=${encodeURIComponent(head)}`;
```

This prompt adds a `provider` dropdown and threads its value into both the API call and the repo input's UX.
</context>

<requirements>
1. **Add a provider `<select>` to the form** in `src/pr_viewer/static/index.html`:

   Insert the `<select>` as the **first element** inside `<form id="compare-form">`, before `#repo-input`:
   ```html
   <select id="provider-select" autocomplete="off">
       <option value="github">GitHub</option>
       <option value="local">Local Git</option>
       <option value="bitbucket">Bitbucket Server</option>
   </select>
   ```

2. **Style the `<select>`** — add CSS so it matches the existing dark theme inputs:
   ```css
   #provider-select {
       background: #0d1117;
       border: 1px solid #30363d;
       border-radius: 6px;
       color: #c9d1d9;
       padding: 5px 10px;
       font-size: 0.875rem;
       outline: none;
       cursor: pointer;
   }
   #provider-select:focus {
       border-color: #58a6ff;
       box-shadow: 0 0 0 2px rgba(88,166,255,0.2);
   }
   ```

3. **Add a `<label>` for the repo input** that updates dynamically:

   Replace the bare `<input id="repo-input" ...>` with:
   ```html
   <label id="repo-label" for="repo-input" style="font-size:0.875rem;color:#8b949e;white-space:nowrap;">owner/repo</label>
   <input id="repo-input" type="text" placeholder="owner/repo" autocomplete="off" spellcheck="false">
   ```
   The label text and input placeholder both change when the provider changes (step 4).

4. **Add a JS `updateProviderUX()` function** — called once on load and on every `change` event on `#provider-select`:

   ```js
   var PROVIDER_META = {
       github:    { label: 'owner/repo',  placeholder: 'owner/repo' },
       local:     { label: 'repo path',   placeholder: '/path/to/repo' },
       bitbucket: { label: 'project/repo', placeholder: 'PROJ/my-repo' },
   };

   function updateProviderUX() {
       var provider = document.getElementById('provider-select').value;
       var meta = PROVIDER_META[provider] || PROVIDER_META['github'];
       document.getElementById('repo-label').textContent = meta.label;
       document.getElementById('repo-input').placeholder = meta.placeholder;
   }

   document.getElementById('provider-select').addEventListener('change', updateProviderUX);
   updateProviderUX(); // set initial state on page load
   ```

5. **Thread `provider` into the API call**:

   In the existing `doCompare()` function, read the selected provider and append it to the URL:
   ```js
   var provider = document.getElementById('provider-select').value;
   var url = '/api/compare?provider=' + encodeURIComponent(provider)
       + '&repo=' + encodeURIComponent(repo)
       + '&base=' + encodeURIComponent(base)
       + '&head=' + encodeURIComponent(head);
   ```
   (Replace the existing URL construction — do not append `&provider=` twice.)

6. **Update `tests/test_frontend.py`** — add one test confirming the dropdown is present in the served HTML:
   ```python
   def test_provider_select_present(client: TestClient) -> None:
       resp = client.get("/")
       assert resp.status_code == 200
       assert 'id="provider-select"' in resp.text
       assert "Bitbucket Server" in resp.text
   ```
   (If the file already uses a `client` fixture, reuse it; otherwise create a `TestClient` the same way the existing tests do.)

7. **Do NOT modify**:
   - Any Python files other than `tests/test_frontend.py`
   - `src/pr_viewer/providers/base.py`
   - `src/pr_viewer/api/compare.py`
   - Existing test files beyond the addition in step 6
</requirements>

<constraints>
- Frontend remains a single `index.html` with no build step — vanilla JS + CSS only
- No new Python dependencies
- `make precommit` must pass (ruff, mypy, pytest)
- All existing tests must still pass — this prompt only adds UI; it does not break any existing backend behavior
- Do NOT commit — dark-factory handles git
- The `provider` parameter must be URL-encoded when appended to the query string
- The `GITHUB_TOKEN`, `BITBUCKET_TOKEN`, and `BITBUCKET_URL` values must never appear in the HTML or JS
</constraints>

<verification>
```bash
# Run all tests
make test

# Final validation
make precommit

# Manual smoke test:
# GITHUB_TOKEN=ghp_xxx make run
# Open http://127.0.0.1:8001
# Verify: dropdown shows "GitHub", "Local Git", "Bitbucket Server"
# Select GitHub → repo label shows "owner/repo", placeholder "owner/repo"
# Select Local Git → repo label shows "repo path", placeholder "/path/to/repo"
# Select Bitbucket Server → repo label shows "project/repo", placeholder "PROJ/my-repo"
# With GitHub selected: repo=bborbe/pr-viewer, base=master, head=v0.1.0 → diff loads
# With Local Git selected: repo=/workspace, base=HEAD~1, head=HEAD → diff loads
# Check browser DevTools Network tab: provider= param is present in the request URL
```
</verification>
