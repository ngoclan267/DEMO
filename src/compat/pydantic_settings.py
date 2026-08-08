"""Lightweight fallback for pydantic_settings when the package is unavailable."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel


class SettingsConfigDict(dict):
    """Minimal stand-in for pydantic_settings.SettingsConfigDict."""


class BaseSettings(BaseModel):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    def __init__(self, **values: Any) -> None:
        env_values: dict[str, Any] = {}
        env_file = values.pop("_env_file", None) or self.model_config.get("env_file", ".env")
        env_path = Path(env_file)
        if not env_path.is_absolute():
            env_path = Path.cwd() / env_path
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                env_values[key.strip()] = value.strip().strip('"').strip("'")

        env_values.update({k: v for k, v in os.environ.items() if k in self.__class__.model_fields})
        super().__init__(**{**env_values, **values})
