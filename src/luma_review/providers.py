"""Model adapters. Use official CLI authentication; never read credential files."""
from __future__ import annotations

import json
import math
import os
import shutil
import signal
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen

from .core import ReviewError, SYSTEM_PROMPT, public_url


class BackendError(ReviewError):
    pass


def run_cli(args: list[str], prompt: str, cwd: Path, timeout: float, cancel=None) -> str:
    env = {k: v for k, v in os.environ.items() if k not in {'OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'CODEX_API_KEY'}}
    try:
        if cancel is None:
            result = subprocess.run(args, input=prompt, text=True, capture_output=True,
                                    cwd=cwd, timeout=timeout, check=False, env=env)
        else:
            process = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       text=True, cwd=cwd, env=env, start_new_session=os.name != 'nt')
            deadline, first = time.monotonic() + timeout, True
            try:
                while True:
                    if cancel.is_set():
                        raise BackendError('Stopped. Completed work is saved.')
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise subprocess.TimeoutExpired(args, timeout)
                    try:
                        stdout, stderr = process.communicate(input=prompt if first else None, timeout=min(.2, remaining))
                        result = subprocess.CompletedProcess(args, process.returncode, stdout, stderr)
                        break
                    except subprocess.TimeoutExpired:
                        first = False
            finally:
                if process.poll() is None:
                    if os.name == 'nt':
                        process.terminate()
                    else:
                        os.killpg(process.pid, signal.SIGTERM)
                    try:
                        process.communicate(timeout=2)
                    except subprocess.TimeoutExpired:
                        if os.name == 'nt':
                            process.kill()
                        else:
                            os.killpg(process.pid, signal.SIGKILL)
                        process.communicate()
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


def token_usage(envelope):
    """Keep reported counts, never provider responses, prompts, or credentials."""
    usage = envelope.get('usage') or {}
    if not isinstance(usage, dict):
        return {}
    return {key: value for key, value in usage.items() if key in {
        'input_tokens', 'output_tokens', 'cached_input_tokens', 'cache_read_input_tokens',
        'cache_creation_input_tokens', 'total_tokens'} and type(value) is int and value >= 0}


class CLIBackend:
    batch_size = 3
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
                args = [self.executable, "exec", "--json", "--ephemeral", "--sandbox", "read-only",
                        "--skip-git-repo-check", "--ignore-user-config", "--color", "never",
                        "-c", "features.shell_tool=false", "-c", 'web_search="disabled"',
                        "--output-schema", str(schema_path), "--output-last-message", str(output)]
                if self.model:
                    args += ["--model", self.model]
                args += ["-"]
                raw = run_cli(args, prompt, directory, self.timeout, getattr(self, 'cancel', None))
                self.last_usage = {}
                for line in raw.splitlines():
                    try:
                        event = json.loads(line)
                        if isinstance(event, dict) and event.get('type') == 'turn.completed':
                            self.last_usage = token_usage(event)
                    except ValueError:
                        continue
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
            envelope = decode_json(run_cli(args, prompt, directory, self.timeout, getattr(self, 'cancel', None)))
            self.last_usage = token_usage(envelope)
            if envelope.get("is_error"):
                raise BackendError("Claude reported an evaluation error; check login and usage limits")
            if isinstance(envelope.get("structured_output"), dict):
                return envelope["structured_output"]
            return decode_json(envelope.get("result", ""))

    def generate_batch(self, tasks, schema):
        urls = [task['profile_url'] for task in tasks]
        result_schema = {'type': 'object', 'properties': {url: schema for url in urls},
                         'required': urls, 'additionalProperties': False}
        prompt = ('Complete each independent professional-profile task using only its own supplied evidence. '
                  'Return one JSON object keyed by the exact profile URLs. Do not mix facts between people.\n'
                  + json.dumps({'tasks': tasks}, ensure_ascii=False))
        result = self.generate(prompt, result_schema, 'batch')
        if set(result) != set(urls):
            raise BackendError('Backend returned an incomplete profile batch; completed work remains saved')
        return result, len(prompt)


class OllamaBackend:
    name = "ollama"

    def __init__(self, model: str, base_url: str, timeout: float):
        if not model:
            raise BackendError("Ollama needs --model <installed-model-name>")
        self.model, self.base_url, self.timeout = model, public_url(base_url).rstrip("/"), timeout

    @property
    def identity(self):
        return {"backend": "ollama", "model": self.model, "base_url": self.base_url, 'context_tokens': 16384}

    def generate(self, prompt: str, schema: dict, profile_url: str) -> dict:
        payload = {"model": self.model, "stream": False, "format": schema,
                   'options': {'temperature': 0, 'num_ctx': 16384, 'num_predict': 4096},
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
        if envelope.get('done_reason') == 'length':
            raise BackendError('Ollama reached the output limit. Choose a model with reliable structured output and retry.')
        self.last_usage = {target: envelope[key] for key, target in [('prompt_eval_count', 'input_tokens'), ('eval_count', 'output_tokens')]
                           if type(envelope.get(key)) is int and envelope[key] >= 0}
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


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # A provider key must never be forwarded to a redirect destination.
        return None


class APIBackend:
    """Explicit, separately billed API mode. No SDK dependency or token extraction."""
    def __init__(self, name, model, api_key, timeout):
        if not model:
            raise BackendError("Enter a model ID supported by your API account")
        if not api_key:
            raise BackendError("Add an API key in Connections or set the provider environment variable")
        self.name, self.model, self._api_key, self.timeout = name, model, api_key, timeout

    @property
    def identity(self):
        return {"backend": self.name, "model": self.model}

    def generate(self, prompt, schema, profile_url):
        headers = {"Content-Type": "application/json"}
        if self.name == "openai":
            url = "https://api.openai.com/v1/responses"
            headers["Authorization"] = "Bearer " + self._api_key
            payload = {"model": self.model, "store": False, "instructions": SYSTEM_PROMPT,
                       "input": prompt, "max_output_tokens": 8192,
                       "text": {"format": {"type": "json_schema", "name": "professional_profile",
                                            "strict": True, "schema": schema}}}
        else:
            url = "https://api.anthropic.com/v1/messages"
            headers.update({"x-api-key": self._api_key, "anthropic-version": "2023-06-01"})
            payload = {"model": self.model, "max_tokens": 8192, "system": SYSTEM_PROMPT,
                       "messages": [{"role": "user", "content": prompt}],
                       "output_config": {"format": {"type": "json_schema", "schema": schema}}}
        request = Request(url, data=json.dumps(payload).encode(), headers=headers, method="POST")
        try:
            with build_opener(NoRedirect()).open(request, timeout=self.timeout) as response:
                envelope = decode_json(response.read().decode())
        except (URLError, TimeoutError, OSError, ValueError):
            # Never surface provider bodies, request headers, keys, or excerpts.
            raise BackendError("API request failed. Check your key, model access, balance, and provider limits; no fallback was used") from None
        if self.name == "openai":
            if envelope.get("status") != "completed":
                raise BackendError("API response was incomplete or refused")
            content = [block for item in envelope.get("output", []) if item.get("type") == "message"
                       for block in item.get("content", [])]
            output = "".join(block.get("text", "") for block in content if block.get("type") == "output_text")
        else:
            if envelope.get("stop_reason") != "end_turn":
                raise BackendError("API response was incomplete or refused")
            output = "".join(block.get("text", "") for block in envelope.get("content", []) if block.get("type") == "text")
        self.last_usage = token_usage(envelope)
        return decode_json(output)


def make_backend(name: str, model=None, *, work_dir=Path("work/model-runs"), timeout=180,
                 base_url="http://127.0.0.1:11434", responses=None, api_key=None):
    if model is not None and (not isinstance(model, str) or model.startswith('-') or len(model) > 200 or any(ord(c) < 32 for c in model)):
        raise BackendError('Invalid model name')
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
        raise BackendError('Timeout must be a positive, finite number')
    if name in {"codex", "claude"}:
        return CLIBackend(name, model, work_dir, timeout)
    if name == "ollama":
        return OllamaBackend(model, base_url, timeout)
    if name in {"openai", "anthropic"}:
        key = api_key or os.environ.get("OPENAI_API_KEY" if name == "openai" else "ANTHROPIC_API_KEY")
        return APIBackend(name, model, key, timeout)
    if name == "host":
        if responses is None:
            raise BackendError("host needs --responses <responses.json>; see export-prompts")
        return HostBackend(responses)
    raise BackendError(f"Unknown backend: {name}")
