# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## v0.8.0

- feat: add .reviewignore for the PR size gate

## v0.5.0

- fix: Distinguish "files truncated" vs "content truncated" in diff banner with actionable message for byte-cap case
- feat: Raise default local provider diff size limit from 10 MB to 50 MB
- feat: Accept `max_bytes` query parameter on `/compare` endpoint to override diff size limit per-request (local provider only, bounded 1 KB–500 MB)
- feat: Forward `max_bytes` URL parameter from frontend to backend compare API

## v0.4.1

- fix: Replace provider-specific "GitHub API limit" wording in truncation banner with generic message

## v0.4.0

- feat: Bitbucket Server option in provider dropdown with project/repo label and placeholder

## v0.3.0

- feat: Bitbucket Server provider for compare endpoint — calls REST API v1.0 with Bearer token auth
- feat: Extend provider routing to support provider=bitbucket

## v0.2.0

- feat: Local git provider for compare endpoint — runs git diff via subprocess
- feat: Provider routing for /api/compare — new provider= query parameter (github or local)
- fix: Local provider tests now pass in CI where /workspace doesn't exist
- feat: Frontend provider selector — GitHub/Local dropdown with dynamic repo label and shareable URLs

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
