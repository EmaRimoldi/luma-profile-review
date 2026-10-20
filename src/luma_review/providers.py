"""Model adapters. Use official CLI authentication; never read credential files."""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .core import ReviewError, SYSTEM_PROMPT, public_url


class BackendError(ReviewError):
    pass


def run_cli(args: list[str], prompt: str, cwd: Path, timeout: float) -> str:
    try:
        result = subprocess.run(args, input=prompt, text=True, capture_output=True,
                                cwd=cwd, timeout=timeout, check=False)
    except FileNotFoundError:
        raise BackendError(f"{args[0]} is not installed or not on PATH") from None
    except subprocess.TimeoutExpired:
        raise BackendError(f"{args[0]} timed out; no fallback backend was used") from None
    if result.returncode:
        # Provider diagnostics can contain prompt text or account identifiers.
        if "not logged in" in (result.stdout + result.stderr).lower():
            raise BackendError("CLI is not logged in. Run codex login or claude auth login for the selected backend")
        raise BackendError(f"{args[0]} exited with code {result.returncode}. Check its login and usage limits")
    return result.stdout


def decode_json(raw: str) -> dict:
    try:
        value = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        raise BackendError("Backend did not return valid JSON") from None
    if not isinstance(value, dict):
        raise BackendError("Backend returned a non-object JSON value")
    return value


class CLIBackend:
    def __init__(self, name: str, model: str | None, work_dir: Path, timeout: float):
        self.name, self.model, self.work_dir, self.timeout = name, model, work_dir, timeout
        executable = shutil.which(name)
        if not executable:
            raise BackendError(f"Install and sign in to {name} first")
        self.executable = executable

    @property
    def identity(self):
        return {"backend": self.name, "model": self.model or "cli-default"}

    def generate(self, prompt: str, schema: dict, profile_url: str) -> dict:
        self.work_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="model-", dir=self.work_dir.resolve()) as temporary:
            directory = Path(temporary)
            if self.name == "codex":
                schema_path, output = directory / "schema.json", directory / "result.json"
                schema_path.write_text(json.dumps(schema), encoding="utf-8")
                args = [self.executable, "exec", "--ephemeral", "--sandbox", "read-only",
                        "--skip-git-repo-check", "--ignore-user-config", "--color", "never",
                        "-c", "features.shell_tool=false", "-c", 'web_search="disabled"',
                        "--output-schema", str(schema_path), "--output-last-message", str(output)]
                if self.model:
                    args += ["--model", self.model]
                args += ["-"]
                run_cli(args, prompt, directory, self.timeout)
                if not output.exists():
                    raise BackendError("Codex completed without a structured response file")
                return decode_json(output.read_text(encoding="utf-8"))
            args = [self.executable, "--print", "--safe-mode", "--output-format", "json",
                    "--json-schema", json.dumps(schema), "--tools", "", "--strict-mcp-config",
                    "--mcp-config", '{"mcpServers":{}}', "--disable-slash-commands",
                    "--no-session-persistence", "--permission-mode", "dontAsk",
                    "--system-prompt", SYSTEM_PROMPT]
            if self.model:
                args += ["--model", self.model]
            envelope = decode_json(run_cli(args, prompt, directory, self.timeout))
            if envelope.get("is_error"):
                raise BackendError("Claude reported an evaluation error; check login and usage limits")
            if isinstance(envelope.get("structured_output"), dict):
                return envelope["structured_output"]
            return decode_json(envelope.get("result", ""))


class OllamaBackend:
    name = "ollama"

    def __init__(self, model: str, base_url: str, timeout: float):
        if not model:
            raise BackendError("Ollama needs --model <installed-model-name>")
        self.model, self.base_url, self.timeout = model, public_url(base_url).rstrip("/"), timeout

    @property
    def identity(self):
        return {"backend": "ollama", "model": self.model, "base_url": self.base_url}

    def generate(self, prompt: str, schema: dict, profile_url: str) -> dict:
        payload = {"model": self.model, "stream": False, "format": schema,
                   "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                                {"role": "user", "content": prompt}]}
        request = Request(self.base_url + "/api/chat", data=json.dumps(payload).encode(),
                          headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urlopen(request, timeout=self.timeout) as response:
                envelope = decode_json(response.read().decode())
        except (URLError, TimeoutError, OSError) as error:
            code = f" (HTTP {error.code})" if isinstance(error, HTTPError) else ""
            raise BackendError(f"Ollama request failed{code}; check the server and installed model") from None
        if envelope.get("error") or not isinstance(envelope.get("message"), dict):
            raise BackendError("Ollama returned an error or missing message")
        return decode_json(envelope["message"].get("content", ""))


class HostBackend:
    """Validated responses authored by the current assistant, keyed by profile URL."""
    name = "host"

    def __init__(self, responses: dict):
        if not isinstance(responses, dict):
            raise BackendError("Host responses must be an object keyed by canonical profile URL")
        self.responses = responses

    @property
    def identity(self):
        from .core import fingerprint
        return {"backend": "host", "responses_sha256": fingerprint(self.responses)}

    def generate(self, prompt: str, schema: dict, profile_url: str) -> dict:
        if profile_url not in self.responses:
            raise BackendError("No host response for this profile")
        return self.responses[profile_url]


def make_backend(name: str, model=None, *, work_dir=Path("work/model-runs"), timeout=180,
                 base_url="http://127.0.0.1:11434", responses=None):
    if name in {"codex", "claude"}:
        return CLIBackend(name, model, work_dir, timeout)
    if name == "ollama":
        return OllamaBackend(model, base_url, timeout)
    if name == "host":
        if responses is None:
            raise BackendError("host needs --responses <responses.json>; see export-prompts")
        return HostBackend(responses)
    raise BackendError(f"Unknown backend: {name}")
