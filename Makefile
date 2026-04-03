.PHONY: sync
sync:
	uv sync --all-extras

.PHONY: format
format:
	uv run ruff format .
	uv run ruff check --fix . || true

.PHONY: lint
lint:
	uv run ruff check .

.PHONY: typecheck
typecheck:
	uv run mypy src

.PHONY: check
check: lint typecheck

.PHONY: test
test: sync
	uv run pytest || test $$? -eq 5

.PHONY: precommit
precommit: sync format test check
	@echo "✓ All precommit checks passed"

.PHONY: run
run: sync
	uv run pr-viewer

.PHONY: watch
watch: sync
	uv run uvicorn pr_viewer.__main__:app --reload --host 127.0.0.1 --port 8000
