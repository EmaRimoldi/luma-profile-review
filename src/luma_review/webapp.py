"""A loopback-only product UI with no hosted account or database requirement."""
from __future__ import annotations

import json
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from .core import ReviewError
from .integrations import integration_config
from .providers import make_backend
from .workspace import Workspace

STATIC = Path(__file__).parent / "static"


def export_guide(guide: dict) -> str:
    data = json.dumps(guide, ensure_ascii=False).replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    return ("<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>My event guide · Luma Profile Review</title><style>" + (STATIC / "app.css").read_text() +
            "</style></head><body><div id='app'></div><div id='toast' role='status'></div>"
            "<script>window.__EXPORTED_GUIDE__=" + data + ";</script><script>" +
            (STATIC / "app.js").read_text() + "</script></body></html>")


class Application:
    def __init__(self, workspace: Workspace):
        self.workspace = workspace
        self.token = secrets.token_urlsafe(32)
        self.job = {"running": False}
        self.job_lock = threading.Lock()

    def start_analysis(self, event_id, backend, model=None):
        if backend not in {"codex", "claude", "ollama"}:
            raise ReviewError("Choose Codex, Claude, or a local Ollama model")
        if model is not None and (not isinstance(model, str) or model.startswith("-") or len(model) > 200):
            raise ReviewError("Invalid model name")
        self.workspace.criteria()
        if not self.workspace.dataset(event_id)["people"]:
            raise ReviewError("Collect or import some attendee profiles first")
        provider = make_backend(backend, model or None, work_dir=self.workspace.root / "work/model-runs")
        with self.job_lock:
            if self.job["running"]:
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
                elif parsed.path in {"/app.js", "/app.css"}:
                    name = parsed.path.removeprefix("/")
                    self.send((STATIC / name).read_text(), content_type="text/javascript; charset=utf-8" if name.endswith("js") else "text/css; charset=utf-8")
                elif parsed.path == "/api/state":
                    with app.job_lock:
                        job = dict(app.job)
                    self.send({**workspace.state(), "job": job})
                elif parsed.path == "/api/guide":
                    self.send(workspace.guide(query.get("event", [""])[0]))
                elif parsed.path == "/api/integration":
                    self.send(integration_config(query.get("agent", ["codex"])[0], workspace.root))
                elif parsed.path == "/api/export":
                    self.send(export_guide(workspace.guide(query.get("event", [""])[0])), content_type="text/html; charset=utf-8", attachment="my-event-guide.html")
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
                if route == "/api/onboard":
                    result = workspace.save_brief(data)
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
                    result = app.start_analysis(data["event_id"], data.get("backend", "codex"), data.get("model"))
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
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
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
