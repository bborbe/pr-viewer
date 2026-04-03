---
status: executing
spec: [002-local-git-provider]
summary: Created local git provider (local.py), added provider routing to compare.py, and created test_compare_local.py with mock_fs() context manager to patch filesystem checks so all 13 tests pass in CI where /workspace doesn't exist
container: pr-viewer-005-fix-local-tests-ci
dark-factory-version: v0.94.1-dirty
created: "2026-04-03T17:34:04Z"
queued: "2026-04-03T17:34:06Z"
started: "2026-04-03T17:34:31Z"
---

<summary>
- Fix test_compare_local.py tests failing in CI because `/workspace` doesn't exist on GitHub Actions runners
- Tests mock `_run_subprocess` but not `os.path.exists`, `os.path.isdir`, `os.path.realpath`, `os.path.abspath`
- Path validation in `LocalGitCompareClient.compare()` rejects the path before subprocess calls are reached
- 8 tests fail with 404 "Directory not found" instead of expected results
</summary>

<objective>
All tests in `tests/test_compare_local.py` pass both locally and in CI (GitHub Actions) where `/workspace` does not exist as a real directory.
</objective>

<context>
Read `CLAUDE.md` for project conventions.

Read these files before making changes:
- `tests/test_compare_local.py` — the failing tests
- `src/pr_viewer/providers/local.py` — `LocalGitCompareClient.compare()` validates paths with `os.path.exists`, `os.path.isdir`, `os.path.realpath`, `os.path.abspath` before calling `_run_subprocess`

The problem: tests that should reach the subprocess logic (valid diff, added file, deleted file, renamed file, not a git repo, git not installed, invalid ref, large diff truncation) all fail with 404 because `os.path.exists("/workspace")` returns `False` in CI. The `_run_subprocess` mock is never reached.

The `test_nonexistent_path` test correctly expects 404 — it should NOT get the os patches.
</context>

<requirements>
1. **Patch filesystem checks** in every test that expects to reach past path validation. Add these patches to each affected test function (or use a shared fixture):
   - `@patch("pr_viewer.providers.local.os.path.exists", return_value=True)`
   - `@patch("pr_viewer.providers.local.os.path.isdir", return_value=True)`
   - `@patch("pr_viewer.providers.local.os.path.realpath", side_effect=lambda p: p)`
   - `@patch("pr_viewer.providers.local.os.path.abspath", side_effect=lambda p: p)`

2. **Affected tests** (all except `test_nonexistent_path`, `test_relative_path`, `test_not_a_directory`, `test_unknown_provider`):
   - `test_valid_local_diff`
   - `test_added_file`
   - `test_deleted_file`
   - `test_renamed_file`
   - `test_not_a_git_repo`
   - `test_git_not_installed`
   - `test_invalid_ref`
   - `test_large_diff_truncation`

3. **Do NOT change** `test_nonexistent_path` — it intentionally tests the case where `os.path.exists` returns `False`.

4. **Do NOT change** `src/pr_viewer/providers/local.py` — the production code is correct.

5. **Update CHANGELOG.md**: Append under `## Unreleased`:
   - `fix: Local provider tests now pass in CI where /workspace doesn't exist`
</requirements>

<constraints>
- No changes to production code
- `make precommit` must pass
- All existing tests must still pass
- Do NOT commit — dark-factory handles git
</constraints>

<verification>
```bash
make precommit
```
</verification>
