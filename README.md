# PR Viewer

Universal pull request viewer with professional UX for any git server.

## Status

Under Development

## Features

- Hierarchical file tree sidebar with add/modify/delete icons
- Side-by-side diff view with syntax highlighting
- Approve, reject, and comment on PRs
- Multi-provider: GitHub (Bitbucket Server, GitLab, Gitea planned)

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager

## Usage

Start server:
```bash
make run
```

With auto-reload:
```bash
make watch
```

Then open http://127.0.0.1:8001

## Configuration

Create `config.yaml`:
```yaml
servers:
  - name: github
    type: github
    url: https://api.github.com
    token_env: GITHUB_TOKEN

  # Additional providers planned:
  # - name: work
  #   type: bitbucket-server
  #   url: https://bitbucket.example.com
  #   token_env: BITBUCKET_TOKEN
```

## Development

```bash
make sync        # Install dependencies
make format      # Format code
make lint        # Lint code
make typecheck   # Type check
make test        # Run tests
make precommit   # Run all checks
```

## License

BSD-2-Clause
