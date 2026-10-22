"""Cancellation through the same HTTP entry points a customer uses."""
import json
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from luma_review.core import ReviewError
from luma_review.demo import DEMO_ANSWERS
from luma_review.providers import BackendError, run_cli
from luma_review.webapp import make_server
from luma_review.workspace import Workspace

ROOT = Path(__file__).resolve().parents[1]


class PausingBackend:
    identity = {"backend": "cancellation-fixture"}
    batch_size = 1

    def __init__(self, pause_at=2, cli=False):
        self.pause_at, self.cli = pause_at, cli
        self.calls = 0
        self.entered = threading.Event()

    def generate(self, prompt, schema, url):
        self.calls += 1
        if self.calls == self.pause_at:
            self.entered.set()
            if self.cli:
                with tempfile.TemporaryDirectory() as directory:
                    marker = str(self.marker)
                    run_cli([sys.executable, "-c", "from pathlib import Path; import time; "
                             f"Path({marker!r}).write_text('started'); time.sleep(30)"],
                            "", Path(directory), 30, self.cancel)
            elif self.cancel.wait(5):
                raise BackendError("Stopped. Completed work is saved.")
            else:
                raise ReviewError("Test cancellation was never delivered")
        if "facts" in schema["properties"]:
            return {"summary": "Fictional fixture", "facts": [], "relationships": []}
        rules = schema["properties"]["assessments"]["items"]["properties"]["criterion_id"]["enum"]
        return {"summary": "Fictional fixture", "assessments": [
            {"criterion_id": rule, "verdict": "unknown", "reason": "Insufficient evidence", "evidence": []}
            for rule in rules]}


class CancellationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.workspace = Workspace(Path(temporary.name))
        self.workspace.save_brief(DEMO_ANSWERS)
        data = json.loads((ROOT / "examples/profiles.json").read_text())
        self.event = self.workspace.import_dataset(data)["event_id"]
        self.server = make_server(self.workspace, 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.close)
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)

    def post(self, path, data):
        request = Request(self.base + path, json.dumps(data).encode(), headers={
            "Content-Type": "application/json", "Origin": self.base,
            "X-Luma-Token": self.server.application.token})
        with urlopen(request, timeout=5) as response:
            return json.load(response)

    def finish(self):
        thread = self.server.application.analysis_thread
        thread.join(timeout=5)
        self.assertFalse(thread.is_alive(), "analysis failed to finish after Stop")
        with urlopen(self.base + "/api/state", timeout=5) as response:
            return json.load(response)["job"]

    def test_refresh_stop_preserves_checkpoint_and_retry_only_runs_unfinished_work(self):
        backend = PausingBackend()
        with patch("luma_review.webapp.make_backend", return_value=backend):
            self.post("/api/analyze", {"event_id": self.event, "backend": "codex"})
            self.assertTrue(backend.entered.wait(3))
            with self.assertRaises(HTTPError) as caught:
                self.post("/api/analyze", {"event_id": self.event, "backend": "codex"})
            self.assertEqual(caught.exception.code, 400)
            self.post("/api/stop", {})
            job = self.finish()
        self.assertFalse(job["running"])
        self.assertTrue(job["stopped"])
        self.assertNotIn("error", job)
        partial = self.workspace.guide(self.event)
        self.assertEqual(partial["counts"]["structured"], 1)
        self.assertEqual(partial["errors"], {})
        resumed = PausingBackend(pause_at=999)
        with patch("luma_review.webapp.make_backend", return_value=resumed):
            self.post("/api/analyze", {"event_id": self.event, "backend": "codex"})
            job = self.finish()
            self.assertFalse(job["stopped"])
            self.assertEqual(job["counts"]["reviewed"], 3)
            self.assertEqual(resumed.calls, 3)  # one remaining structure + two sourced matches
            self.post("/api/analyze", {"event_id": self.event, "backend": "codex"})
            self.finish()
            self.assertEqual(resumed.calls, 3)

    def test_legacy_stop_cancels_refresh_and_terminates_its_cli_child(self):
        backend = PausingBackend(pause_at=1, cli=True)
        backend.marker = self.workspace.root / 'child-started'
        with patch("luma_review.webapp.make_backend", return_value=backend):
            self.post("/api/analyze", {"event_id": self.event, "backend": "claude"})
            self.assertTrue(backend.entered.wait(3))
            deadline = time.monotonic() + 3
            while not backend.marker.exists() and time.monotonic() < deadline:
                time.sleep(.01)
            self.assertTrue(backend.marker.exists(), 'CLI child did not start')
            started = time.monotonic()
            self.post("/api/agent", {"action": "stop"})
            job = self.finish()
            self.assertLess(time.monotonic() - started, 3)
        self.assertTrue(job["stopped"])
        self.assertEqual(backend.calls, 1)
        self.assertEqual(job["errors"], {})

    def test_idle_stop_does_not_start_an_agent_or_change_results(self):
        before = self.workspace.dataset(self.event)
        self.assertFalse(self.post("/api/stop", {})["running"])
        self.assertIsNone(self.server.application.agent)
        self.assertEqual(self.workspace.dataset(self.event), before)

    def test_repeated_stop_restart_does_not_reuse_a_cancelled_run_token(self):
        for attempt in range(20):
            with self.subTest(attempt=attempt):
                backend = PausingBackend(pause_at=1)
                with patch("luma_review.webapp.make_backend", return_value=backend):
                    self.post("/api/analyze", {"event_id": self.event, "backend": "codex"})
                    self.assertTrue(backend.entered.wait(3))
                    self.post("/api/stop", {})
                    self.assertTrue(self.finish()["stopped"])
                self.assertEqual(backend.calls, 1)
                self.assertEqual(self.workspace.guide(self.event)["errors"], {})
        final = PausingBackend(pause_at=999)
        with patch("luma_review.webapp.make_backend", return_value=final):
            self.post("/api/analyze", {"event_id": self.event, "backend": "codex"})
            self.assertFalse(self.finish()["stopped"])
        self.assertEqual(final.calls, 4)

    def test_server_shutdown_stops_active_analysis(self):
        backend = PausingBackend(pause_at=1)
        with patch("luma_review.webapp.make_backend", return_value=backend):
            self.post("/api/analyze", {"event_id": self.event, "backend": "codex"})
            self.assertTrue(backend.entered.wait(3))
            self.server.application.close()
            self.assertTrue(self.finish()["stopped"])

    def test_already_cancelled_cli_does_not_spawn(self):
        cancel = threading.Event()
        cancel.set()
        with patch("luma_review.providers.subprocess.Popen") as launch:
            with self.assertRaisesRegex(BackendError, "Stopped"):
                run_cli(["never-run"], "", self.workspace.root, 10, cancel)
        launch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
