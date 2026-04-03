from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass(frozen=True)
class ServerConfig:
    name: str
    type: str
    url: str
    token_env: str

    @property
    def token(self) -> str:
        return os.environ.get(self.token_env, "")


@dataclass(frozen=True)
class Config:
    servers: list[ServerConfig] = field(default_factory=list)


def load_config(path: Path | None = None) -> Config:
    if path is None:
        path = Path("config.yaml")
    if not path.exists():
        return Config()
    with open(path) as f:
        data = yaml.safe_load(f)
    if not data or "servers" not in data:
        return Config()
    servers = [
        ServerConfig(
            name=s["name"],
            type=s["type"],
            url=s["url"],
            token_env=s.get("token_env", ""),
        )
        for s in data["servers"]
    ]
    return Config(servers=servers)
