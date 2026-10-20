import asyncio
import copy
import importlib.util
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from luma_review.core import ReviewError, parse_criteria
from luma_review.demo import DEMO_ANSWERS, load_demo
from luma_review.graph import build_graph
from luma_review.integrations import integration_config
from luma_review.matching import compare_rankings, keyword_ranking
from luma_review.onboarding import criteria_from_brief, make_brief
from luma_review.professional import validate_structure
from luma_review.webapp import export_guide, make_server
from luma_review.workspace import Workspace

ROOT = Path(__file__).resolve().parents[1]


class ProductBase(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.workspace = Workspace(Path(self.temporary.name))
        self.guide = load_demo(self.workspace)
        self.event_id = self.guide["event_id"]


class OnboardingTests(unittest.TestCase):
    def test_all_five_answers_are_required(self):
        for field in ["work", "interests", "looking_for", "connect_with", "can_offer"]:
            answers = dict(DEMO_ANSWERS)
            answers.pop(field)
            with self.assertRaises(ReviewError):
                make_brief(answers)

    def test_only_explicit_conditions_become_musts(self):
        answers = {**DEMO_ANSWERS, "must_haves": []}
        criteria = parse_criteria(criteria_from_brief(make_brief(answers)))
        self.assertFalse(any(r.kind == "must" for r in criteria.rules))
        self.assertEqual(len(criteria.rules), 4)

    def test_pipe_characters_do_not_break_generated_markdown(self):
        answers = {**DEMO_ANSWERS, "connect_with": "engineers | founders"}
        criteria = parse_criteria(criteria_from_brief(make_brief(answers)))
        self.assertIn("engineers | founders", criteria.rules[2].condition)

    def test_interests_are_deduplicated_without_inventing_topics(self):
        brief = make_brief({**DEMO_ANSWERS, "interests": "inference, inference, robotics"})
        self.assertEqual(brief["interests"], ["inference", "robotics"])


class CollectionTests(ProductBase):
    def test_roster_capture_is_resumable_and_preserves_sources(self):
        person = self.workspace.dataset(self.event_id)["people"][0]
        self.workspace.capture_attendees(self.event_id, [{"name": person["name"], "profile_url": person["profile_url"] + "?tk=private"}], 6, False)
        data = self.workspace.dataset(self.event_id)
        self.assertEqual(len(data["people"]), 6)
        self.assertEqual(len(data["people"][0]["sources"]), 1)
        self.assertNotIn("tk=", json.dumps(data))

    def test_omitted_names_are_not_marked_as_collected(self):
        result = self.workspace.create_event("https://luma.com/new-event", "New event")
        ident = result["event_id"]
        self.workspace.capture_attendees(ident, [{"name": "One", "profile_url": "https://luma.com/user/one"}], 310, False)
        data = self.workspace.dataset(ident)
        self.assertEqual(data["event"]["displayed_guest_count"], 310)
        self.assertFalse(data["event"]["roster_complete"])
        self.assertEqual(len(data["people"]), 1)

    def test_source_queue_tracks_read_and_inaccessible_links(self):
        result = self.workspace.create_event("https://luma.com/queue", "Queue")
        ident = result["event_id"]
        url = "https://luma.com/user/queue-person"
        self.workspace.capture_attendees(ident, [{"name": "Queue Person", "profile_url": url}])
        self.assertEqual(self.workspace.source_queue(ident)[0]["pending_urls"], [url])
        self.workspace.capture_sources(ident, url, [{"url": url, "title": "Bio", "text": "Engineer"}],
                                       ["https://linkedin.com/in/queue-person"])
        self.assertEqual(self.workspace.source_queue(ident)[0]["pending_urls"], ["https://linkedin.com/in/queue-person"])
        self.workspace.capture_sources(ident, url, [], attempts=[{"url": "https://linkedin.com/in/queue-person", "reason": "Sign-in required"}], complete=True)
        self.assertEqual(self.workspace.source_queue(ident), [])

    def test_no_cross_event_profile_or_path_injection(self):
        with self.assertRaises(ReviewError):
            self.workspace.directory("../../etc")
        with self.assertRaises(ReviewError):
            self.workspace.capture_sources(self.event_id, "https://luma.com/user/not-an-attendee", [])


class StructureAndGraphTests(ProductBase):
    def test_shared_company_does_not_establish_personal_relationship(self):
        graph = self.guide["graph"]
        self.assertTrue(any(c["context"]["label"] == "BayCompute" and len(c["people"]) == 2 for c in graph["shared_contexts"]))
        self.assertFalse(any(e["type"] in {"knows", "worked_with", "cofounder_with"} for e in graph["edges"]))

    def test_professional_fact_requires_an_exact_source(self):
        person = self.workspace.dataset(self.event_id)["people"][0]
        structure = copy.deepcopy(self.guide["people"][0]["professional"])
        structure["facts"][0]["evidence"][0]["quote"] = "Invented role"
        with self.assertRaises(ReviewError):
            validate_structure(structure, person, {p["profile_url"] for p in self.workspace.dataset(self.event_id)["people"]})

    def test_relationship_needs_a_source_identifying_the_other_person(self):
        data = self.workspace.dataset(self.event_id)
        person, target = data["people"][:2]
        structure = {"summary": "Test", "facts": [], "relationships": [{"target_profile_url": target["profile_url"],
                     "kind": "knows", "evidence": [{"source_id": "s1", "quote": person["sources"][0]["text"]}]}]}
        with self.assertRaises(ReviewError):
            validate_structure(structure, person, {p["profile_url"] for p in data["people"]})
        person["sources"][0]["links"] = [target["profile_url"]]
        validate_structure(structure, person, {p["profile_url"] for p in data["people"]})

    def test_source_changes_invalidate_structures_and_matching(self):
        data = self.workspace.dataset(self.event_id)
        data["people"][0]["sources"][0]["text"] += " Updated bio."
        self.workspace.import_dataset(data)
        guide = self.workspace.guide(self.event_id)
        self.assertEqual(guide["counts"]["structured"], 5)
        self.assertEqual(guide["counts"]["reviewed"], 5)

    def test_changed_structure_invalidates_its_matching(self):
        tasks = self.workspace.tasks(self.event_id, "structure", include_reviewed=True)
        person = self.workspace.dataset(self.event_id)["people"][0]
        structure = copy.deepcopy(self.guide["people"][0]["professional"])
        structure["summary"] = "A revised grounded summary."
        self.workspace.submit(self.event_id, "structure", tasks["request_hash"], {person["profile_url"]: structure})
        self.assertEqual(self.workspace.guide(self.event_id)["counts"]["reviewed"], 5)

    def test_stale_agent_results_are_rejected(self):
        tasks = self.workspace.tasks(self.event_id, "matching", include_reviewed=True)
        self.workspace.save_brief({**DEMO_ANSWERS, "looking_for": "Different goals"})
        result = {self.guide["people"][0]["profile_url"]: {"summary": self.guide["people"][0]["summary"], "assessments": self.guide["people"][0]["assessments"]}}
        with self.assertRaises(ReviewError):
            self.workspace.submit(self.event_id, "matching", tasks["request_hash"], result)


class GuideTests(ProductBase):
    def test_demo_is_explicit_and_unknown_profiles_remain_unknown(self):
        self.assertTrue(self.guide["demo"])
        morgan = next(p for p in self.guide["people"] if "Morgan" in p["name"])
        self.assertEqual(morgan["score"]["status"], "Needs verification")
        self.assertEqual(morgan["sources"], [])

    def test_feedback_removes_irrelevant_people_from_suggestions(self):
        self.workspace.save_feedback(self.event_id, self.guide["people"][0]["profile_url"], "not_relevant")
        self.assertEqual(self.workspace.guide(self.event_id)["counts"]["recommended"], 2)

    def test_reopening_workspace_preserves_the_guide(self):
        reopened = Workspace(self.workspace.root)
        self.assertEqual(reopened.guide(self.event_id)["counts"], self.guide["counts"])

    def test_export_is_self_contained_and_escapes_embedded_data(self):
        guide = copy.deepcopy(self.guide)
        guide["event"]["name"] = "</script><script>alert('unsafe')</script>"
        html = export_guide(guide)
        self.assertNotIn("</script><script>alert('unsafe')", html)
        self.assertIn("window.__EXPORTED_GUIDE__", html)
        self.assertIn("FICTIONAL DEMO", html)
        self.assertNotIn('src="http', html)

    def test_existing_workspace_is_not_overwritten_by_demo(self):
        with self.assertRaises(ReviewError):
            load_demo(self.workspace)


class MatchingExperimentTests(unittest.TestCase):
    def test_unknown_labels_do_not_count_as_negatives(self):
        result = compare_rankings({"a": ["one", "two"]}, {"one": True}, 2)["strategies"]["a"]
        self.assertIsNone(result["precision_at_k"])
        self.assertEqual(result["judged_precision"], 1)
        self.assertEqual(result["judgment_coverage"], .5)

    def test_precision_and_recall_use_judged_data(self):
        value = compare_rankings({"a": ["one", "two"]}, {"one": True, "two": False, "three": True}, 2)["strategies"]["a"]
        self.assertEqual(value["precision_at_k"], .5)
        self.assertEqual(value["recall_at_k"], .5)

    def test_keyword_baseline_is_explicitly_literal(self):
        brief = make_brief(DEMO_ANSWERS)
        rows = keyword_ranking([{"profile_url": "example", "sources": [{"text": "GPU inference engineer"}]}], brief)
        self.assertIn("inference", rows[0]["matched_terms"])


class WebTests(ProductBase):
    def setUp(self):
        super().setUp()
        self.server = make_server(self.workspace, 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.close_server)
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def close_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def test_state_and_guide_http(self):
        with urlopen(self.base + "/api/state") as response:
            self.assertEqual(len(json.load(response)["events"]), 1)
        with urlopen(self.base + "/api/guide?event=" + self.event_id) as response:
            self.assertEqual(json.load(response)["counts"]["recommended"], 3)

    def test_mutations_require_local_token_and_origin(self):
        data = json.dumps({"event_id": self.event_id, "profile_url": self.guide["people"][0]["profile_url"], "status": "saved"}).encode()
        for headers in [{"Content-Type": "application/json"}, {"Content-Type": "application/json", "X-Luma-Token": self.server.application.token, "Origin": "https://unrelated.example"}]:
            with self.assertRaises(HTTPError) as caught:
                urlopen(Request(self.base + "/api/feedback", data=data, headers=headers))
            self.assertEqual(caught.exception.code, 403)
        headers = {"Content-Type": "application/json", "X-Luma-Token": self.server.application.token, "Origin": self.base}
        with urlopen(Request(self.base + "/api/feedback", data=data, headers=headers)) as response:
            self.assertTrue(json.load(response)["saved"])


class AgentIntegrationTests(unittest.TestCase):
    def test_agent_configs_preserve_the_virtual_environment_interpreter(self):
        interpreter = str(Path('work/venv/bin/python').absolute())
        for agent in ["codex", "claude", "cursor", "copilot", "opencode", "claude-desktop"]:
            config = integration_config(agent, Path("data/workspace"), interpreter)
            self.assertIn(interpreter, config["configuration"])
            self.assertIn("mcp", config["configuration"])

    @unittest.skipUnless(importlib.util.find_spec("mcp"), "MCP extra is not installed")
    def test_real_mcp_stdio_client_onboarding_and_roster(self):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        async def exercise():
            with tempfile.TemporaryDirectory() as directory:
                parameters = StdioServerParameters(command=sys.executable, args=[str(ROOT / "run.py"), "mcp", "--workspace", directory])
                async with stdio_client(parameters) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        tools = await session.list_tools()
                        self.assertEqual(len(tools.tools), 11)
                        brief = await session.call_tool("save_professional_brief", {"answers": DEMO_ANSWERS})
                        self.assertFalse(brief.isError)
                        result = await session.call_tool("create_event", {"event_url": "https://luma.com/test-mcp", "event_name": "MCP test"})
                        self.assertFalse(result.isError)
                        payload = result.structuredContent
                        event_id = payload["event_id"]
                        captured = await session.call_tool("record_attendees", {"event_id": event_id, "attendees": [{"name": "Person", "profile_url": "https://luma.com/user/mcp-person"}]})
                        self.assertFalse(captured.isError)
                        queue = await session.call_tool("next_profile_sources", {"event_id": event_id})
                        self.assertEqual(len(queue.structuredContent["profiles"]), 1)
                        person_url = "https://luma.com/user/mcp-person"
                        captured_source = await session.call_tool("record_profile_sources", {"event_id": event_id,
                            "profile_url": person_url, "sources": [{"url": person_url, "title": "MCP synthetic bio",
                            "text": "I currently build LLM inference systems."}], "complete": True})
                        self.assertFalse(captured_source.isError)
                        source_id = captured_source.structuredContent["sources"][0]["id"]
                        tasks = await session.call_tool("inference_tasks", {"event_id": event_id, "stage": "structure"})
                        structure = {"summary": "Synthetic inference builder.", "facts": [{"kind": "interest", "value": "LLM inference",
                                     "evidence": [{"source_id": source_id, "quote": "LLM inference systems"}]}], "relationships": []}
                        result = await session.call_tool("submit_inference", {"event_id": event_id, "stage": "structure",
                                     "request_hash": tasks.structuredContent["request_hash"], "responses": {person_url: structure}})
                        self.assertFalse(result.isError)
                        tasks = await session.call_tool("inference_tasks", {"event_id": event_id, "stage": "matching"})
                        criteria = parse_criteria(brief.structuredContent["criteria_markdown"])
                        response = {"summary": "Relevant inference work; other professional details need checking.", "assessments": [
                            {"criterion_id": rule.id, "verdict": "yes" if rule.id in {"M1", "P1"} else "unknown",
                             "reason": "Current inference work is explicitly stated." if rule.id in {"M1", "P1"} else "Not established.",
                             "evidence": [{"source_id": source_id, "quote": "I currently build LLM inference systems."}] if rule.id in {"M1", "P1"} else []}
                            for rule in criteria.rules]}
                        result = await session.call_tool("submit_inference", {"event_id": event_id, "stage": "matching",
                                     "request_hash": tasks.structuredContent["request_hash"], "responses": {person_url: response}})
                        self.assertFalse(result.isError)
                        guide = await session.call_tool("event_guide", {"event_id": event_id})
                        self.assertEqual(guide.structuredContent["counts"]["captured"], 1)
                        self.assertEqual(guide.structuredContent["counts"]["reviewed"], 1)
                        self.assertEqual(guide.structuredContent["counts"]["recommended"], 1)
        asyncio.run(exercise())


if __name__ == "__main__":
    unittest.main()
