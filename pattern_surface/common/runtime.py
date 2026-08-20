"""Small runtime helpers shared by workbench commands."""

import importlib
import os


DEV_RELOAD_ENV = "AUZYRON_PATTERNS_DEV_RELOAD"


def maybe_reload(module):
    """Reload a module only when explicit development mode is enabled."""
    if os.environ.get(DEV_RELOAD_ENV, "").strip().lower() in {"1", "true", "yes"}:
        return importlib.reload(module)
    return module
