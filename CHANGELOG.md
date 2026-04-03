# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

- feat: Local git provider for compare endpoint — runs git diff via subprocess
- feat: Provider routing for /api/compare — new provider= query parameter (github or local)
- fix: Local provider tests now pass in CI where /workspace doesn't exist

## v0.1.0

### Added
- Initial project structure from python-skeleton
- FastAPI web app skeleton with config loading
- Provider interface for pluggable git server backends
- `GET /api/compare` endpoint for GitHub commit/branch/tag comparison with input validation and error mapping
- `GitHubCompareClient` with structured error handling (401/403/404/422/timeout → meaningful HTTP responses)
- Single-page frontend with collapsible hierarchical file tree sidebar
- Single-file diff view (one file at a time, not stacked)
- Side-by-side diff for modified files, line-by-line for added/deleted files
- diff2html integration (v3.4.48 from CDN) with dark theme and compact row layout
- URL sync for repo/base/head/file params (shareable URLs, auto-load on open)
- Inline word-level highlights with readable dark red/green colors
- Long line wrapping (no horizontal scrollbars)
- File status badges and icons: Added, Modified, Deleted, Renamed
- Auto-inject `GITHUB_TOKEN` via `gh auth token` in Makefile
