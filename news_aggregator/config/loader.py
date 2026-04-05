from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from news_aggregator.config.schema import AppConfig

_ENV_VAR_PATTERN = re.compile(r"\$\{([^}]+)\}")


class ConfigError(Exception):
    pass


def _expand_env_vars(data: Any) -> Any:
    """Recursively expand ${ENV_VAR} placeholders in string values."""
    if isinstance(data, str):
        def _replace(match: re.Match) -> str:
            var_name = match.group(1)
            value = os.environ.get(var_name)
            if value is None:
                return match.group(0)  # leave unexpanded if not set
            return value

        return _ENV_VAR_PATTERN.sub(_replace, data)
    elif isinstance(data, dict):
        return {k: _expand_env_vars(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [_expand_env_vars(item) for item in data]
    return data


def load_config(path: Path) -> AppConfig:
    """Load and validate a YAML config file, expanding ${ENV_VAR} placeholders."""
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")

    try:
        raw = yaml.safe_load(path.read_text())
    except yaml.YAMLError as e:
        raise ConfigError(f"Failed to parse YAML config: {e}") from e

    if not isinstance(raw, dict):
        raise ConfigError("Config file must contain a YAML mapping at the top level")

    expanded = _expand_env_vars(raw)

    try:
        return AppConfig.model_validate(expanded)
    except ValidationError as e:
        # Re-raise with a cleaner message
        errors = "\n".join(
            f"  - {'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}"
            for err in e.errors()
        )
        raise ConfigError(f"Config validation failed:\n{errors}") from e
