"""A loopback-only product UI with no hosted account or database requirement."""
from __future__ import annotations

import json
import base64
import re
import os
import secrets
import shutil
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from .core import ReviewError
from .integrations import integration_config
from .providers import make_backend
from .settings import read_settings, save_settings
from .workspace import Workspace

STATIC = Path(__file__).parent / "static"


def export_guide(guide: dict) -> str:
    data = json.dumps(guide, ensure_ascii=False).replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    fonts = (STATIC / "fonts/fonts.css").read_text()
    def embed_font(match):
        name = match.group(2).removeprefix("./")
        path = (STATIC / "fonts" / name).resolve()
        if not path.is_relative_to((STATIC / "fonts").resolve()) or path.suffix != ".woff2":
            return match.group(0)
        return "url(data:font/woff2;base64," + base64.b64encode(path.read_bytes()).decode() + ")"
    fonts = re.sub(r"url\(([\"']?)([^)\"']+)\1\)", embed_font, fonts)
    scripts = "</script><script>".join((STATIC / name).read_text() for name in
              ("vendor/cytoscape.min.js", "context-graph.js", "ambient.js", "search.js", "app.js"))
    return ("<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>My event guide · People for Luma</title><style>" + fonts + (STATIC / "app.css").read_text() + (STATIC / "polish.css").read_text() +
            "</style></head><body><canvas id='ambient' aria-hidden='true'></canvas><div id='app'></div><div id='toast' role='status'></div>"
            "<script>window.__EXPORTED_GUIDE__=" + data + ";</script><script>" + scripts + "</script></body></html>")


class Application:
    def __init__(self, workspace: Workspace):
        self.workspace = workspace
        self.token = secrets.token_urlsafe(32)
        self.job = {"running": False}
        self.job_lock = threading.Lock()
        self.api_keys = {}
        self.guide_cache = {}
        self.guide_lock = threading.Lock()
        self.agent = None
        self.agent_lock = threading.Lock()

    def agent_runner(self):
        with self.agent_lock:
            if self.agent is None:
                from .agent import AgentRunner
                def update(**values):
                    with self.job_lock:
                        self.job.update(values)
                self.agent = AgentRunner(self.workspace, update)
            return self.agent

    def agent_state(self):
        if self.agent:
            return self.agent.snapshot()
        from .managed_browser import ResearchBrowser
        return {"installed": bool(shutil.which("codex")), "connected": False, "busy": False,
                "browser_available": ResearchBrowser.available(), "luma_connected": False,
                "message": "Connect Codex to prepare your guide here."}

    def agent_action(self, data):
        action = data.get("action")
        if action == "prepare":
            with self.job_lock:
                if self.job.get("running"):
                    raise ReviewError("A guide is already being prepared.")
                self.job = {"running": True, "kind": "agent", "stage": "Connecting your agent", "current": 0, "total": data.get("limit", 10)}
            try:
                return self.agent_runner().action(action, data.get("event_id"), data.get("limit", 10))
            except Exception:
                with self.job_lock:
                    self.job["running"] = False
                raise
        return self.agent_runner().action(action)

    def connection_state(self):
        return {"settings": read_settings(self.workspace),
                "connections": {"codex": {"installed": bool(shutil.which("codex"))},
                                "claude": {"installed": bool(shutil.which("claude"))},
                                "openai": {"key_present": bool(self.api_keys.get("openai") or os.environ.get("OPENAI_API_KEY"))},
                                "anthropic": {"key_present": bool(self.api_keys.get("anthropic") or os.environ.get("ANTHROPIC_API_KEY"))}}}

    def update_settings(self, data):
        key = data.get("api_key")
        provider = data.get("backend")
        if key is not None:
            if provider not in {"openai", "anthropic"} or not isinstance(key, str) or len(key) > 16000 or any(ord(c) < 33 for c in key):
                raise ReviewError("Use a valid key for the selected API provider")
        if "clear_key" in data and (type(data["clear_key"]) is not bool or provider not in {"openai", "anthropic"}):
            raise ReviewError("Choose an API provider to remove its session key")
        if set(data) - {"backend", "model", "luma", "api_key", "clear_key", "setup_complete"}:
            raise ReviewError("Unsupported connection setting")
        save_settings(self.workspace, {k: v for k, v in data.items() if k in {"backend", "model", "luma", "setup_complete"}})
        if data.get("clear_key"):
            self.api_keys.pop(provider, None)
        elif key:
            self.api_keys[provider] = key
        return self.connection_state()

    def guide(self, event_id):
        directory = self.workspace.directory(event_id)
        paths = [self.workspace.root / "brief.json", self.workspace.root / "criteria.md", self.workspace.root / "presentation-en.json"] + [directory / name for name in
                 ("profiles.json", "structure.json", "matching.json", "feedback.json", "errors.json")]
        def signature():
            return tuple((p.stat().st_mtime_ns, p.stat().st_size) if p.exists() else None for p in paths)
        with self.guide_lock:
            version = signature()
            cached = self.guide_cache.get(event_id)
            if cached and cached[0] == version:
                return cached[1]
            guide = self.workspace.guide(event_id)
            if signature() == version:
                self.guide_cache[event_id] = (version, guide)
            return guide

    def start_analysis(self, event_id, backend, model=None):
        if backend not in {"codex", "claude", "ollama", "openai", "anthropic"}:
            raise ReviewError("Choose a model connection; current-agent analysis runs through your agent")
        if model is not None and (not isinstance(model, str) or model.startswith("-") or len(model) > 200):
            raise ReviewError("Invalid model name")
        self.workspace.criteria()
        if not self.workspace.dataset(event_id)["people"]:
            raise ReviewError("Collect or import some attendee profiles first")
        provider = make_backend(backend, model or None, api_key=self.api_keys.get(backend), work_dir=self.workspace.root / "work/model-runs")
        with self.job_lock:
            if self.job["running"] or (self.agent and self.agent.snapshot()["busy"]):
                raise ReviewError("An analysis is already running")
            self.job = {"running": True, "event_id": event_id, "backend": backend}
        def work():
            try:
                def progress(value):
                    with self.job_lock:
                        self.job.update(value)
                guide = self.workspace.analyze(event_id, provider, progress=progress)
                with self.job_lock:
                    self.job.update(running=False, counts=guide["counts"], errors=guide["errors"])
            except Exception as error:
                with self.job_lock:
                    self.job.update(running=False, error=str(error))
        threading.Thread(target=work, daemon=True).start()
        return self.job


def make_server(workspace: Workspace, port=8765):
    app = Application(workspace)
    class Handler(BaseHTTPRequestHandler):
        server_version = "LumaReviewLocal/0.2"

        def valid_host(self):
            return self.headers.get("Host") in {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}

        def send(self, value, status=200, content_type="application/json; charset=utf-8", attachment=None):
            body = json.dumps(value, ensure_ascii=False).encode() if content_type.startswith("application/json") else value.encode() if isinstance(value, str) else value
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            if attachment:
                self.send_header("Content-Disposition", f'attachment; filename="{attachment}"')
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if not self.valid_host():
                self.send({"error": "Invalid host"}, 403)
                return
            parsed = urlsplit(self.path)
            query = parse_qs(parsed.query)
            try:
                if parsed.path == "/":
                    page = (STATIC / "index.html").read_text().replace("__LOCAL_TOKEN__", app.token)
                    self.send(page, content_type="text/html; charset=utf-8")
                elif parsed.path in {"/app.js", "/app.css", "/search.js", "/polish.css", "/context-graph.js", "/ambient.js"} or parsed.path.startswith(("/fonts/", "/vendor/")):
                    name = parsed.path.removeprefix("/")
                    path = (STATIC / name).resolve()
                    if not path.is_relative_to(STATIC.resolve()) or not path.is_file():
                        self.send({"error": "Not found"}, 404)
                        return
                    types = {".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8", ".woff2": "font/woff2", ".txt": "text/plain; charset=utf-8"}
                    self.send(path.read_bytes(), content_type=types.get(path.suffix, "application/octet-stream"))
                elif parsed.path == "/api/state":
                    with app.job_lock:
                        job = dict(app.job)
                    self.send({**workspace.state(), "job": job, "agent": app.agent_state(), **app.connection_state()})
                elif parsed.path == "/api/guide":
                    self.send(app.guide(query.get("event", [""])[0]))
                elif parsed.path == "/api/agent":
                    self.send(app.agent_state())
                elif parsed.path == "/api/integration":
                    self.send(integration_config(query.get("agent", ["codex"])[0], workspace.root))
                elif parsed.path == "/api/export":
                    guide = app.guide(query.get("event", [""])[0])
                    if query.get("format", [""])[0] == "json":
                        self.send(guide, attachment="my-event-guide.json")
                    else:
                        self.send(export_guide(guide), content_type="text/html; charset=utf-8", attachment="my-event-guide.html")
                else:
                    self.send({"error": "Not found"}, 404)
            except (ReviewError, ValueError, KeyError, TypeError) as error:
                self.send({"error": str(error)}, 400)

        def do_POST(self):
            if not self.valid_host() or self.headers.get("X-Luma-Token") != app.token:
                self.send({"error": "Reload the local app before continuing"}, 403)
                return
            origin = self.headers.get("Origin")
            if origin and origin not in {f"http://127.0.0.1:{self.server.server_port}", f"http://localhost:{self.server.server_port}"}:
                self.send({"error": "Requests must originate from the local app"}, 403)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length < 1 or length > 4 * 1024 * 1024:
                    raise ReviewError("Choose a JSON input below 4 MB")
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict):
                    raise ReviewError("Expected a JSON object")
                route = urlsplit(self.path).path
                if route == "/api/agent":
                    result = app.agent_action(data)
                elif route == "/api/handoff":
                    from .onboarding import make_brief
                    from .core import parse_criteria, public_url
                    make_brief(data["brief"])
                    if data.get("criteria_markdown"):
                        parse_criteria(data["criteria_markdown"])
                    if data.get("event"):
                        incoming = urlsplit(public_url(data["event"]["url"]))
                        if incoming.hostname != "luma.com" or not incoming.path or incoming.path.startswith("/user/"):
                            raise ReviewError("Enter a Luma event URL")
                    workspace.save_brief(data["brief"])
                    if data.get("criteria_markdown"):
                        workspace.save_criteria(data["criteria_markdown"])
                    event = data.get("event")
                    result = workspace.create_event(event["url"], event.get("name") or "My event") if event else {"saved": True}
                elif route == "/api/onboard":
                    result = workspace.save_brief(data)
                elif route == "/api/settings":
                    result = app.update_settings(data)
                elif route == "/api/check":
                    from .cli import doctor
                    backend = data.get("backend")
                    if backend not in {"codex", "claude", "ollama"}:
                        raise ReviewError("Choose Codex, Claude, or Ollama to check locally")
                    result = doctor(backend, "http://127.0.0.1:11434")
                elif route == "/api/criteria":
                    result = workspace.save_criteria(data["markdown"])
                elif route == "/api/events":
                    result = workspace.create_event(data["url"], data.get("name") or "My event")
                elif route == "/api/import":
                    result = workspace.import_dataset(data)
                elif route == "/api/demo":
                    from .demo import load_demo
                    result = load_demo(workspace)
                elif route == "/api/analyze":
                    settings = read_settings(workspace)
                    result = app.start_analysis(data["event_id"], data.get("backend", settings["backend"]), data.get("model", settings["model"]))
                elif route == "/api/feedback":
                    result = workspace.save_feedback(data["event_id"], data["profile_url"], data["status"], data.get("note", ""))
                else:
                    self.send({"error": "Not found"}, 404)
                    return
                self.send(result)
            except (ReviewError, ValueError, KeyError, TypeError) as error:
                self.send({"error": str(error)}, 400)

        def log_message(self, *args):
            # URLs can contain private event identifiers. Do not log request paths.
            pass
    class LocalServer(ThreadingHTTPServer):
        def server_close(self):
            if app.agent:
                app.agent.close()
            super().server_close()
    server = LocalServer(("127.0.0.1", port), Handler)
    server.application = app
    return server


def serve(workspace: Workspace, port=8765):
    server = make_server(workspace, port)
    print(f"Local: http://127.0.0.1:{server.server_port}", flush=True)
    print("Data stays in this local workspace. Selected cloud model backends receive the source excerpts used for analysis.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
