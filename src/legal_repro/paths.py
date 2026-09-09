"""Installed resources and non-overwriting output paths."""
from pathlib import Path

ASSETS = Path(__file__).resolve().parent / "assets"


def fresh_directory(path: Path) -> Path:
    absolute = path.expanduser().absolute()
    resolved = absolute.resolve()
    if absolute != resolved or resolved.exists() or resolved.is_relative_to(ASSETS):
        raise PermissionError("Output must be a fresh, non-symlink directory outside packaged resources")
    resolved.mkdir(parents=True, exist_ok=False)
    return resolved
