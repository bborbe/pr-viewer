---
status: completed
spec: [003-bitbucket-server-provider]
summary: Bitbucket Server dropdown option, updateProviderUI branch, and frontend test were already implemented; all 50 tests pass and precommit exits 0.
container: pr-viewer-008-spec-003-frontend
dark-factory-version: v0.94.1-dirty
created: "2026-04-03T17:00:00Z"
queued: "2026-04-03T19:06:29Z"
started: "2026-04-03T19:22:58Z"
completed: "2026-04-03T19:23:46Z"
---

<summary>
- "Bitbucket Server" is added as a third option in the existing provider dropdown (alongside GitHub and Local)
- When "Bitbucket Server" is selected, repo input label changes to "project/repo" and placeholder changes to "PROJ/my-repo"
- The `provider=bitbucket` value is passed in the API URL (the dropdown already sends `provider=` for other options)
- A new pytest confirms "Bitbucket Server" appears in the served HTML
- No other behavior changes — all existing provider functionality is unchanged
</summary>

<objective>
Extend the existing provider dropdown in `index.html` to include "Bitbucket Server" as a third option, update the `updateProviderUI` function to handle the `bitbucket` value, and add a test confirming it appears in the HTML. The dropdown, label, and event wiring already exist; this prompt only adds the new option and its UI metadata. **Depends on prompt 1 (backend)** — assumes `provider=bitbucket` is already valid in `compare.py`.
</objective>

<context>
Read `CLAUDE.md` for project conventions.

Read these files before making changes:
- `src/pr_viewer/static/index.html` — full file; the provider dropdown already exists (lines ~428-431) with GitHub and Local options; `updateProviderUI()` already handles `local` and default (GitHub); the dropdown change event listener is already wired
- `tests/test_frontend.py` — existing tests: `test_root_serves_index_html`, `test_root_contains_provider_select`, `test_root_contains_local_option`, `test_healthz_still_works`

Current state of the relevant HTML (around line 428):
```html
<select id="provider-select">
    <option value="github">GitHub</option>
    <option value="local">Local</option>
</select>
<label id="repo-label" for="repo-input">Repo (owner/repo)</label>
<input id="repo-input" type="text" placeholder="owner/repo" ...>
```

Current state of `updateProviderUI()` (around line 823):
```js
function updateProviderUI(provider) {
    var label = document.getElementById('repo-label');
    var input = document.getElementById('repo-input');
    if (provider === 'local') {
        label.textContent = 'Repo path';
        input.placeholder = '/Users/you/your-repo';
    } else {
        label.textContent = 'Repo (owner/repo)';
        input.placeholder = 'owner/repo';
    }
}
```

These already exist and work. This prompt only extends them.
</context>

<requirements>
1. **Add "Bitbucket Server" option** to the `<select id="provider-select">` in `src/pr_viewer/static/index.html`:
   - Insert after the existing `<option value="local">Local</option>`:
     ```html
     <option value="bitbucket">Bitbucket Server</option>
     ```

2. **Update `updateProviderUI()`** to handle `bitbucket`:
   - Replace the existing `if/else` with a three-branch version:
     ```js
     function updateProviderUI(provider) {
         var label = document.getElementById('repo-label');
         var input = document.getElementById('repo-input');
         if (provider === 'local') {
             label.textContent = 'Repo path';
             input.placeholder = '/Users/you/your-repo';
         } else if (provider === 'bitbucket') {
             label.textContent = 'project/repo';
             input.placeholder = 'PROJ/my-repo';
         } else {
             label.textContent = 'Repo (owner/repo)';
             input.placeholder = 'owner/repo';
         }
     }
     ```

3. **Add a test** to `tests/test_frontend.py` — confirm "Bitbucket Server" appears in the served HTML:
   ```python
   def test_root_contains_bitbucket_option() -> None:
       app = create_app()
       client = TestClient(app)
       response = client.get("/")
       assert response.status_code == 200
       assert "Bitbucket Server" in response.text
   ```

4. **Update CHANGELOG.md**: Add a `## Unreleased` section at the top (if it doesn't already exist) and append:
   - `feat: Bitbucket Server option in provider dropdown with project/repo label and placeholder`
</requirements>

<constraints>
- Frontend remains a single `index.html` with no build step — vanilla JS + CSS only
- Do NOT modify any Python files except `tests/test_frontend.py`
- Do NOT modify `src/pr_viewer/api/compare.py` or any provider files
- No new Python dependencies
- `make precommit` must pass
- All existing tests must still pass
- Do NOT commit — dark-factory handles git
</constraints>

<verification>
```bash
make test
make precommit
```
</verification>
