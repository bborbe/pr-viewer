---
status: draft
---

# Scenario 010: Prompt with server-start verification fails in headless container

Validates that a prompt whose verification section starts a web server fails because the container has no exposed ports or browser.

## Setup

- [ ] Project with `.dark-factory.yaml` (`pr: false`, `worktree: false`)
- [ ] Project has a web server startable via `make run`
- [ ] Create prompt with server-dependent verification:
  ```bash
  cat > prompts/server-verify.md << 'PROMPT'
  ---
  status: draft
  ---

  <summary>
  - Add a healthz comment marker to factory.py
  </summary>

  <objective>
  Add the comment `# healthz-marker` to the end of factory.py.
  </objective>

  <context>
  Read `src/pr_viewer/factory.py` — add a single comment line at the end.
  </context>

  <requirements>
  1. Append `# healthz-marker` as the last line of `src/pr_viewer/factory.py`
  </requirements>

  <constraints>
  - Only modify `src/pr_viewer/factory.py`
  - Do NOT commit
  </constraints>

  <verification>
  ```bash
  make run &
  sleep 3
  curl -f http://127.0.0.1:8001/healthz
  kill %1
  ```
  </verification>
  PROMPT
  ```

## Action

- [ ] Approve prompt: `dark-factory prompt approve server-verify`
- [ ] Run prompt: `dark-factory run`
- [ ] Wait for processing to complete

## Expected

- [ ] Prompt status is `failed` or `partial` (not `completed`)
- [ ] Log file exists in `prompts/log/`
- [ ] Log shows `curl` or `make run` failure (connection refused or timeout)
- [ ] The code edit itself was applied (`# healthz-marker` exists in factory.py)

## Cleanup

- [ ] Remove test prompt and revert factory.py
