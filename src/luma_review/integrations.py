"""Generate explicit local MCP configuration for the user's chosen agent."""
import json
import sys
from pathlib import Path

from .core import ReviewError

AGENTS = ["codex", "claude", "cursor", "copilot", "opencode", "claude-desktop"]


def integration_config(agent: str, workspace: Path, executable=None):
    if agent not in AGENTS:
        raise ReviewError("Unknown agent integration")
    # Resolving a venv's python symlink would select the base interpreter and lose MCP dependencies.
    python = str(Path(executable or sys.executable).absolute())
    checkout_runner = Path(__file__).resolve().parents[2] / "run.py"
    args = [str(checkout_runner)] if checkout_runner.exists() else ["-m", "luma_review"]
    args += ["mcp", "--workspace", str(workspace.resolve())]
    server = {"command": python, "args": args}
    if agent == "codex":
        value = '[mcp_servers.luma-profile-review]\ncommand = ' + json.dumps(python) + "\nargs = " + json.dumps(args) + "\n"
        return {"agent": agent, "format": "toml", "configuration": value, "location": "Your Codex MCP configuration"}
    if agent == "copilot":
        value = {"servers": {"luma-profile-review": {"type": "stdio", **server}}}
        location = ".vscode/mcp.json"
    elif agent == "opencode":
        value = {"mcp": {"luma-profile-review": {"type": "local", "command": [python, *args], "enabled": True}}}
        location = "opencode.json"
    else:
        value = {"mcpServers": {"luma-profile-review": server}}
        location = ".cursor/mcp.json" if agent == "cursor" else ".mcp.json" if agent == "claude" else "Claude Desktop MCP configuration"
    return {"agent": agent, "format": "json", "configuration": json.dumps(value, indent=2), "location": location}
