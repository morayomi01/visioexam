"""Small helper for loading project-local environment settings."""

import os
from pathlib import Path


def load_env_file(env_file: Path) -> None:
    """Load simple KEY=VALUE entries, without overriding process variables."""
    if not env_file.is_file():
        return
    try:
        lines = env_file.read_text(encoding="utf-8-sig").splitlines()
    except OSError as exc:
        raise RuntimeError(f"Could not read environment file: {env_file}") from exc

    for line in lines:
        entry = line.strip()
        if not entry or entry.startswith("#"):
            continue
        if entry.startswith("export "):
            entry = entry[7:].lstrip()
        name, separator, value = entry.partition("=")
        name = name.strip()
        if not separator or not name or not name.replace("_", "").isalnum():
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        os.environ.setdefault(name, value)
