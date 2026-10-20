import copy
import io
import json
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from luma_review.cli import main
from luma_review.core import (ReviewError, aggregate, load_profiles, parse_criteria,
                              public_url, response_schema, validate_assessment, validate_profiles)
from luma_review.pipeline import evaluate, render_report
from luma_review.providers import BackendError, CLIBackend, HostBackend, OllamaBackend

ROOT = Path(__file__).resolve().parents[1]


class Base(unittest.TestCase):
    def setUp(self):
        self.criteria = parse_criteria((ROOT / "examples/criteria.md").read_text())
        self.data = load_profiles(ROOT / "examples/profiles.json")
        self.responses = json.loads((ROOT / "examples/responses.json").read_text())["responses"]
        self.person = self.data["people"][0]
        self.result = copy.deepcopy(self.responses[self.person["profile_url"]])


class CriteriaTests(Base):
    def test_draft_is_rejected(self):
        with self.assertRaises(ReviewError):
            parse_criteria((ROOT / "criteria.example.md").read_text())

    def test_empty_active_criteria_are_rejected(self):
        with self.assertRaises(ReviewError):
            parse_criteria("Status: active\n## Criteria\n| ID | Type | Weight | Criterion | Evidence |\n")

    def test_duplicate_ids_and_invalid_weights_are_rejected(self):
        for replacement in [("| P1 |", "| M1 |"), ("| prefer | 3 |", "| prefer | 0 |")]:
            with self.assertRaises(ReviewError):
                parse_criteria(self.criteria.markdown.replace(*replacement))

    def test_italian_criteria(self):
        result = parse_criteria("Stato: attivo\n## Criteri\n| M1 | indispensabile | 0 | Ruolo attuale | Bio |\n")
        self.assertEqual(result.rules[0].kind, "must")

    def test_prose_changes_invalidate_hash(self):
        self.assertNotEqual(self.criteria.sha256, parse_criteria(self.criteria.markdown + "\nNew goal.").sha256)


class EvidenceTests(Base):
    def test_valid_response(self):
        validate_assessment(self.result, self.criteria, self.person)
        score = aggregate(self.result, self.criteria)
        self.assertEqual(score["points"], 5)
        self.assertEqual(score["status"], "Meets required criteria")

    def test_missing_is_unknown_not_negative(self):
        for a in self.result["assessments"]:
            a.update(verdict="unknown", reason="Missing evidence", evidence=[])
        validate_assessment(self.result, self.criteria, self.person)
        score = aggregate(self.result, self.criteria)
        self.assertEqual(score["status"], "Needs verification")
        self.assertEqual(score["uncertain_points"], 5)
        self.assertEqual(score["known_criteria"], 0)

    def test_fabricated_quote_or_source_is_rejected(self):
        for key, value in [("quote", "Invented credentials."), ("source_id", "not-read")]:
            result = copy.deepcopy(self.result)
            result["assessments"][0]["evidence"][0][key] = value
            with self.assertRaises(ReviewError):
                validate_assessment(result, self.criteria, self.person)

    def test_no_requires_affirmative_evidence(self):
        self.result["assessments"][0].update(verdict="no", evidence=[])
        with self.assertRaises(ReviewError):
            validate_assessment(self.result, self.criteria, self.person)

    def test_missing_duplicate_and_malformed_assessments(self):
        for variant in [self.result["assessments"][:-1], self.result["assessments"] * 2]:
            with self.assertRaises(ReviewError):
                validate_assessment({"summary": "Example", "assessments": variant}, self.criteria, self.person)
        self.result["assessments"][0]["verdict"] = []
        with self.assertRaises(ReviewError):
            validate_assessment(self.result, self.criteria, self.person)

    def test_conflict_needs_distinct_evidence(self):
        a = self.result["assessments"][0]
        a["verdict"] = "conflict"
        a["evidence"] *= 2
        with self.assertRaises(ReviewError):
            validate_assessment(self.result, self.criteria, self.person)

    def test_explicit_required_failure(self):
        person = self.data["people"][1]
        result = self.responses[person["profile_url"]]
        validate_assessment(result, self.criteria, person)
        self.assertEqual(aggregate(result, self.criteria)["status"], "Outside criteria")


class DataTests(Base):
    def test_luma_alias_and_ticket_keys_are_removed(self):
        self.assertEqual(public_url("https://lu.ma/user/demo?tk=secret#bio", luma=True),
                         "https://luma.com/user/demo")

    def test_same_name_is_not_deduplicated(self):
        self.data["people"][1]["name"] = self.person["name"]
        validate_profiles(self.data)

    def test_duplicate_profile_is_rejected(self):
        self.data["people"].append(copy.deepcopy(self.person))
        with self.assertRaises(ReviewError):
            validate_profiles(self.data)

    def test_unread_link_is_not_a_citable_source(self):
        self.person["outbound_links"] = ["https://example.org/another-profile"]
        self.result["assessments"][0]["evidence"][0]["source_id"] = "outbound_links"
        with self.assertRaises(ReviewError):
            validate_assessment(self.result, self.criteria, self.person)

    def test_missing_timezone_is_rejected(self):
        self.person["sources"][0]["retrieved_at"] = "2026-10-19T12:00:00"
        with self.assertRaises(ReviewError):
            validate_profiles(self.data)


class PipelineTests(Base):
    def test_offline_end_to_end_cache_and_invalidation(self):
        backend = HostBackend(self.responses)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(backend, "generate", wraps=backend.generate) as generate:
                run = evaluate(self.data, self.criteria, backend, root / "run", cache=root / "cache")
                self.assertEqual(generate.call_count, 2)  # No source: no model call.
                self.assertEqual(len(run["people"]), 3)
                self.assertTrue((root / "run/report.md").exists())
                self.assertEqual(run["people"][2]["score"]["status"], "Needs verification")
                evaluate(self.data, self.criteria, backend, root / "run", cache=root / "cache")
                self.assertEqual(generate.call_count, 2)
                self.data["people"][0]["sources"][0]["text"] += " New information."
                evaluate(self.data, self.criteria, backend, root / "run", cache=root / "cache")
                self.assertEqual(generate.call_count, 3)
                changed = parse_criteria(self.criteria.markdown + "\nA new goal.\n")
                evaluate(self.data, changed, backend, root / "run", cache=root / "cache")
                self.assertEqual(generate.call_count, 5)

    def test_model_failure_remains_in_report_and_other_profiles_continue(self):
        backend = HostBackend({})
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run = evaluate(self.data, self.criteria, backend, root / "run", cache=root / "cache")
            self.assertEqual([p["status"] for p in run["people"]], ["failed", "failed", "reviewed"])
            self.assertIn("Failed: 2", (root / "run/report.md").read_text())

    def test_stale_report_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run = evaluate(self.data, self.criteria, HostBackend(self.responses), root / "run", cache=root / "cache")
            changed = parse_criteria(self.criteria.markdown + "\nChanged.\n")
            with self.assertRaises(ReviewError):
                render_report(run, changed)

    def test_cli_offline_pipeline_and_export(self):
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            root = Path(directory)
            args = ["--criteria", str(ROOT / "examples/criteria.md"), "--profiles", str(ROOT / "examples/profiles.json")]
            code = main(["export-prompts", *args, "--out", str(root / "tasks.json")])
            self.assertEqual(code, 0)
            tasks = json.loads((root / "tasks.json").read_text())
            self.assertEqual(tasks["schema"], response_schema(self.criteria))
            code = main(["evaluate", *args, "--backend", "host", "--responses", str(ROOT / "examples/responses.json"),
                         "--output", str(root / "run"), "--cache", str(root / "cache")])
            self.assertEqual(code, 0)
            self.assertEqual(main(["report", "--criteria", str(ROOT / "examples/criteria.md"),
                                   "--results", str(root / "run/results.json"), "--out", str(root / "report.md")]), 0)

    def test_host_rejects_responses_for_old_profile_sources(self):
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            root = Path(directory)
            self.data["people"][0]["sources"][0]["text"] += " Changed source."
            profiles = root / "profiles.json"
            profiles.write_text(json.dumps(self.data))
            code = main(["evaluate", "--criteria", str(ROOT / "examples/criteria.md"),
                         "--profiles", str(profiles), "--backend", "host", "--responses",
                         str(ROOT / "examples/responses.json"), "--output", str(root / "run")])
            self.assertEqual(code, 2)
            self.assertFalse((root / "run/results.json").exists())

    def test_backend_can_be_selected_from_toml(self):
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            root = Path(directory)
            config = root / "settings.toml"
            config.write_text('[inference]\nbackend = "host"\n')
            code = main(["--config", str(config), "evaluate", "--criteria", str(ROOT / "examples/criteria.md"),
                         "--profiles", str(ROOT / "examples/profiles.json"), "--responses",
                         str(ROOT / "examples/responses.json"), "--output", str(root / "run"),
                         "--cache", str(root / "cache")])
            self.assertEqual(code, 0)


class ProviderTests(Base):
    def test_codex_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            def fake_run(args, **kwargs):
                self.assertIn("--output-schema", args)
                self.assertIn("--ignore-user-config", args)
                self.assertNotIn("--dangerously-bypass-approvals-and-sandbox", args)
                self.assertEqual(kwargs["input"], "private source prompt")
                output = Path(args[args.index("--output-last-message") + 1])
                output.write_text(json.dumps(self.result))
                return subprocess.CompletedProcess(args, 0, "", "")
            with patch("shutil.which", return_value="/bin/codex"), patch("subprocess.run", side_effect=fake_run):
                backend = CLIBackend("codex", None, Path(directory), 10)
                result = backend.generate("private source prompt", response_schema(self.criteria), self.person["profile_url"])
                self.assertEqual(result, self.result)

    def test_claude_structured_envelope(self):
        with tempfile.TemporaryDirectory() as directory:
            def fake_run(args, **kwargs):
                self.assertIn("--safe-mode", args)
                self.assertEqual(args[args.index("--tools") + 1], "")
                self.assertNotIn("--bare", args)
                return subprocess.CompletedProcess(args, 0, json.dumps({"structured_output": self.result}), "")
            with patch("shutil.which", return_value="/bin/claude"), patch("subprocess.run", side_effect=fake_run):
                backend = CLIBackend("claude", None, Path(directory), 10)
                self.assertEqual(backend.generate("prompt", response_schema(self.criteria), "url"), self.result)

    def test_timeout_and_exit_error_hide_raw_provider_output(self):
        with tempfile.TemporaryDirectory() as directory, patch("shutil.which", return_value="/bin/codex"):
            backend = CLIBackend("codex", None, Path(directory), 1)
            with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("codex", 1)):
                with self.assertRaises(BackendError):
                    backend.generate("prompt", response_schema(self.criteria), "url")
            with patch("subprocess.run", return_value=subprocess.CompletedProcess([], 1, "secret", "private data")):
                with self.assertRaises(BackendError) as caught:
                    backend.generate("prompt", response_schema(self.criteria), "url")
                self.assertNotIn("private data", str(caught.exception))

    def test_ollama_http_contract(self):
        import threading
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        captured = {}
        result = self.result
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                captured.update(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
                body = json.dumps({"message": {"content": json.dumps(result)}}).encode()
                self.send_response(200)
                self.end_headers()
                self.wfile.write(body)
            def log_message(self, *args):
                pass
        with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            backend = OllamaBackend("synthetic-model", f"http://127.0.0.1:{server.server_port}", 5)
            self.assertEqual(backend.generate("prompt", response_schema(self.criteria), "url"), result)
            server.shutdown()
            worker.join()
        self.assertFalse(captured["stream"])
        self.assertEqual(captured["format"], response_schema(self.criteria))


if __name__ == "__main__":
    unittest.main()
