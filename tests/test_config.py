from pathlib import Path

from pr_viewer.config import load_config


def test_load_config_missing_file() -> None:
    config = load_config(Path("/nonexistent/config.yaml"))
    assert config.servers == []


def test_load_config_from_yaml(tmp_path: Path) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
servers:
  - name: github
    type: github
    url: https://api.github.com
    token_env: GITHUB_TOKEN
""")
    config = load_config(config_file)
    assert len(config.servers) == 1
    assert config.servers[0].name == "github"
    assert config.servers[0].type == "github"
