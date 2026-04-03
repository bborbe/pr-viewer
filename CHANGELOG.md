# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Added
- Initial project structure from python-skeleton
- FastAPI web app skeleton with config loading
- Provider interface for pluggable git server backends
- feat: `GET /api/compare` endpoint for GitHub commit/branch/tag comparison with input validation and error mapping
- feat: `GitHubCompareClient` with structured error handling (401/403/404/422/timeout → meaningful HTTP responses)
