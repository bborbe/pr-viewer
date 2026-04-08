---
status: completed
summary: 'Replaced ''Showing first N of M files (GitHub API limit)'' with ''Diff truncated: showing first N of M files'' in the frontend truncation banner.'
container: pr-viewer-009-fix-truncation-warning-message
dark-factory-version: v0.107.6
created: "2026-04-08T00:00:00Z"
queued: "2026-04-08T13:24:58Z"
started: "2026-04-08T13:25:34Z"
completed: "2026-04-08T13:26:28Z"
---

<summary>
- Truncation warning banner no longer mentions GitHub specifically
- Local provider truncations (raw diff size limit) show an accurate message
- Bitbucket and other providers also show a provider-neutral message
- Behavior unchanged when truncated=false
</summary>

<objective>
Replace the hardcoded "GitHub API limit" wording in the frontend truncation banner with a generic message, since truncation is also triggered by the local provider's diff size cap and is unrelated to GitHub.
</objective>

<context>
Read CLAUDE.md for project conventions.

Files to read before changes:
- `src/pr_viewer/static/index.html` (around line 807, the `if (data.truncated)` block)
- `src/pr_viewer/providers/local.py` lines 120-140 — local provider sets `truncated=true` when raw git diff exceeds `_MAX_DIFF_BYTES`, unrelated to GitHub
- Any frontend tests under `tests/` (currently none reference this string — confirm with grep)
</context>

<requirements>
1. In `src/pr_viewer/static/index.html`, locate the block:
   ```js
   if (data.truncated) {
       showWarning('Showing first ' + data.files.length + ' of ' + data.total_files + ' files (GitHub API limit)');
   }
   ```
2. Replace the warning text with a provider-neutral message:
   ```js
   if (data.truncated) {
       showWarning('Diff truncated: showing first ' + data.files.length + ' of ' + data.total_files + ' files');
   }
   ```
3. Run `grep -rn "GitHub API limit" src/ tests/` and remove/update any other occurrences. There should be zero matches after the change.
4. Run `grep -rn "Showing first" src/ tests/` to find any tests that assert on the old wording. Update them to match the new string.
5. Do not change provider backend code or the `truncated` field semantics.
</requirements>

<constraints>
- Do NOT commit — dark-factory handles git
- Existing tests must still pass
- No backend behavior changes
- Keep the change minimal and scoped to the warning message
</constraints>

<verification>
- `grep -rn "GitHub API limit" src/ tests/` returns no results
- `make precommit` passes (or project equivalent: `make test` + lint)
- Manually confirm the new string appears once in `src/pr_viewer/static/index.html`
</verification>
