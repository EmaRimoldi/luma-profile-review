"""Non-secret workspace preferences. Provider credentials live only in the server process."""
from .core import ReviewError
from .pipeline import write_json

BACKENDS = {"agent", "codex", "claude", "ollama", "openai", "anthropic"}
DEFAULTS = {"backend": "agent", "model": "", "luma": "browser", "setup_complete": True}


def read_settings(workspace):
    return {**DEFAULTS, **workspace.read(workspace.root / "settings.json", {})}


def save_settings(workspace, value):
    if set(value) - {"backend", "model", "luma", "setup_complete"}:
        raise ReviewError("Unsupported setting")
    settings = {**read_settings(workspace), **value}
    if settings["backend"] not in BACKENDS:
        raise ReviewError("Choose a supported model connection")
    model = settings["model"]
    if not isinstance(model, str) or model.startswith("-") or len(model) > 200 or any(ord(c) < 32 for c in model):
        raise ReviewError("Invalid model name")
    if settings["luma"] not in {"browser", "browser_handoff", "snapshot"}:
        raise ReviewError("Choose browser sign-in or a profile snapshot")
    if type(settings["setup_complete"]) is not bool:
        raise ReviewError("Invalid setup state")
    with workspace.locked():
        write_json(workspace.root / "settings.json", settings)
    return settings
