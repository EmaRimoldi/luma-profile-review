"""Persistent event workflow shared by local UI, agents, and command-line clients."""
from __future__ import annotations

import copy
import json
import re
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from .core import (PROMPT_VERSION, ReviewError, aggregate, fingerprint, make_prompt, parse_criteria,
                   public_url, response_schema, text, validate_assessment, validate_profiles)
from .graph import build_graph
from .contact import model_profile, presentation, validate_presentation
from .matching import evidence_ranking, keyword_ranking
from .onboarding import QUESTIONS, criteria_from_brief, make_brief
from .pipeline import write_json
from .professional import referenced_urls, structure_prompt, structure_schema, validate_structure
from .presentation import present_brief, present_criteria, present_guide
from .providers import BackendUnavailable


class Workspace:
    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._thread_lock = threading.RLock()

    @contextmanager
    def locked(self):
        with self._thread_lock, (self.root / ".lock").open("a+b") as stream:
            try:
                import fcntl
            except ImportError:
                import msvcrt
                stream.seek(0)
                stream.write(b"0")
                stream.flush()
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)
                try:
                    yield
                finally:
                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(stream, fcntl.LOCK_UN)

    def read(self, path: Path, default=None):
        try:
            return json.loads(path.read_text(encoding="utf-8")) if path.exists() else copy.deepcopy(default)
        except json.JSONDecodeError:
            raise ReviewError(f'Invalid saved {path.name}. Restore a backup or choose a new workspace; existing files were not overwritten.') from None

    def directory(self, event_id: str):
        if not isinstance(event_id, str) or not re.fullmatch(r"[a-f0-9]{16}", event_id):
            raise ReviewError("Invalid event ID")
        path = self.root / "events" / event_id
        if not (path / "profiles.json").exists():
            raise ReviewError("Event not found")
        return path

    def brief(self):
        return self.read(self.root / "brief.json")

    def criteria(self):
        path = self.root / "criteria.md"
        if not path.exists():
            raise ReviewError("Complete the short onboarding first")
        return parse_criteria(path.read_text(encoding="utf-8"))

    def save_brief(self, answers: dict) -> dict:
        brief = make_brief(answers)
        markdown = criteria_from_brief(brief)
        parse_criteria(markdown)
        with self.locked():
            write_json(self.root / "brief.json", brief)
            path = self.root / "criteria.md"
            temp = self.root / "criteria.md.tmp"
            temp.write_text(markdown, encoding="utf-8")
            temp.replace(path)
        return {"brief": brief, "criteria_markdown": markdown, "criteria_path": str(path)}

    def save_criteria(self, markdown: str):
        criteria = parse_criteria(markdown)
        with self.locked():
            temp = self.root / "criteria.md.tmp"
            temp.write_text(markdown, encoding="utf-8")
            temp.replace(self.root / "criteria.md")
        return {"criteria_sha256": criteria.sha256, "count": len(criteria.rules)}

    def create_event(self, url: str, name="Untitled event"):
        url = public_url(url)
        parsed = urlsplit(url)
        if parsed.hostname != "luma.com" or not parsed.path or parsed.path.startswith("/user/"):
            raise ReviewError("Enter a Luma event URL")
        ident = fingerprint(url)[:16]
        directory = self.root / "events" / ident
        with self.locked():
            if not (directory / "profiles.json").exists():
                dataset = {"version": 1, "event": {"name": text(name, "Event name"), "url": url,
                           "displayed_guest_count": None, "collection_scope": "Collection has not started.",
                           "roster_complete": False}, "people": []}
                write_json(directory / "profiles.json", dataset)
            elif name not in {"My event", "Untitled event"}:
                dataset = self.read(directory / "profiles.json")
                dataset["event"]["name"] = text(name, "Event name")
                write_json(directory / "profiles.json", dataset)
        return {"event_id": ident, "event": self.dataset(ident)["event"]}

    def dataset(self, event_id):
        return self.read(self.directory(event_id) / "profiles.json")

    def import_dataset(self, dataset: dict):
        dataset = validate_profiles(copy.deepcopy(dataset))
        ident = fingerprint(dataset["event"]["url"])[:16]
        with self.locked():
            write_json(self.root / "events" / ident / "profiles.json", dataset)
        return {"event_id": ident, "profiles": len(dataset["people"])}

    def capture_attendees(self, event_id: str, attendees: list[dict], displayed_count=None,
                          complete=False, scope="Accessible guest list collected by the user's agent."):
        with self.locked():
            data = self.dataset(event_id)
            by_url = {p["profile_url"]: p for p in data["people"]}
            for attendee in attendees:
                url = public_url(attendee.get("profile_url"), luma=True)
                person = {"name": text(attendee.get("name"), "Attendee name"), "profile_url": url,
                          "sources": [], "outbound_links": [], "collection_complete": False}
                for field in ("photo_url", "contact_links"):
                    if field in attendee:
                        person[field] = copy.deepcopy(attendee[field])
                validate_presentation(person)
                if url in by_url:
                    by_url[url]["name"] = person["name"]
                    by_url[url].update({k: person[k] for k in ("photo_url", "contact_links") if k in person})
                else:
                    by_url[url] = person
            data["people"] = list(by_url.values())
            data["event"].update(displayed_guest_count=displayed_count,
                                 roster_complete=bool(complete), collection_scope=text(scope, "Collection scope"))
            if data["people"]:
                validate_profiles(data)
            write_json(self.directory(event_id) / "profiles.json", data)
        return {"event_id": event_id, "captured": len(data["people"]), "roster_complete": bool(complete)}

    def capture_sources(self, event_id: str, profile_url: str, sources: list[dict],
                        outbound_links=None, complete=False, attempts=None):
        profile_url = public_url(profile_url, luma=True)
        with self.locked():
            data = self.dataset(event_id)
            person = next((p for p in data["people"] if p["profile_url"] == profile_url), None)
            if person is None:
                raise ReviewError("Capture the attendee before recording their sources")
            by_url = {s["url"]: s for s in person["sources"]}
            for source in sources:
                source = copy.deepcopy(source)
                source["url"] = public_url(source.get("url"))
                source["id"] = "s-" + fingerprint(source["url"])[:12]
                source.setdefault("retrieved_at", datetime.now(timezone.utc).isoformat())
                if len(text(source.get("text"), "Source excerpt")) > 20000:
                    raise ReviewError("Save focused source excerpts, up to 20,000 characters per page")
                source["links"] = [public_url(u) for u in source.get("links", [])]
                by_url[source["url"]] = source
            person["sources"] = list(by_url.values())
            person["outbound_links"] = list(dict.fromkeys(person.get("outbound_links", []) + [public_url(u) for u in (outbound_links or [])]))
            recorded = {a["url"]: a for a in person.get("source_attempts", [])}
            for attempt in attempts or []:
                url = public_url(attempt.get("url"))
                recorded[url] = {"url": url, "reason": text(attempt.get("reason"), "Access limitation")}
            person["source_attempts"] = list(recorded.values())
            person["collection_complete"] = bool(complete)
            validate_profiles(data)
            write_json(self.directory(event_id) / "profiles.json", data)
        return {"profile_url": profile_url, "source_count": len(person["sources"]), "sources": person["sources"]}

    def source_queue(self, event_id, limit=10):
        if not 1 <= limit <= 100:
            raise ReviewError("Use a source queue limit between 1 and 100")
        rows = []
        for p in self.dataset(event_id)["people"]:
            if p.get("collection_complete"):
                continue
            read = {s["url"] for s in p["sources"]}
            attempted = {a["url"] for a in p.get("source_attempts", [])}
            pending = [u for u in [p["profile_url"], *p.get("outbound_links", [])] if u not in read | attempted]
            rows.append({"name": p["name"], "profile_url": p["profile_url"], "pending_urls": pending,
                         "source_attempts": p.get("source_attempts", [])})
        return rows[:limit]

    def _input_hash(self, stage, data, criteria, brief):
        structures = self.read(self.directory(fingerprint(data["event"]["url"])[:16]) / "structure.json", {}) if stage == "matching" else None
        data = {**data, "people": [model_profile(p) for p in data["people"]]}
        return fingerprint({"stage": stage, "data": data, "criteria": criteria.sha256, "brief": brief["id"], "structures": structures, "version": PROMPT_VERSION})

    def _person_hash(self, person, brief, criteria, stage="structure", structures=None):
        base = fingerprint({"person": model_profile(person), "brief": brief["id"], "criteria": criteria.sha256, 'version': PROMPT_VERSION})
        if stage == "matching":
            record = (structures or {}).get(person["profile_url"], {})
            structured = record.get("result") if record.get("input_hash") == base else None
            return fingerprint({"profile_input": base, "professional_profile": structured})
        return base

    def tasks(self, event_id: str, stage: str, limit=10, include_reviewed=False):
        if stage not in {"structure", "matching"} or not 1 <= limit <= 10000:
            raise ReviewError("Use structure or matching and a limit between 1 and 10000")
        data, criteria, brief = self.dataset(event_id), self.criteria(), self.brief()
        records = self.read(self.directory(event_id) / f"{stage}.json", {})
        structures = self.read(self.directory(event_id) / "structure.json", {})
        requests = []
        for person in data["people"]:
            key = self._person_hash(person, brief, criteria, stage, structures)
            record = records.get(person["profile_url"], {})
            if not include_reviewed and record.get("input_hash") == key:
                continue
            if stage == "structure":
                prompt = structure_prompt(person, brief, data["people"])
            else:
                enriched = copy.deepcopy(person)
                record_structure = structures.get(person["profile_url"], {})
                if record_structure.get("input_hash") == self._person_hash(person, brief, criteria):
                    enriched["professional_profile"] = record_structure["result"]
                prompt = make_prompt(criteria, enriched)
            requests.append({"profile_url": person["profile_url"], "input_hash": key, "prompt": prompt})
        selected = {r['profile_url'] for r in requests[:limit]}
        targets = set()
        if stage == 'structure':
            for person in data['people']:
                if person['profile_url'] in selected:
                    targets.update(referenced_urls(person))
            targets.intersection_update(p['profile_url'] for p in data['people'])
        return {"stage": stage, "request_hash": self._input_hash(stage, data, criteria, brief),
                "schema": structure_schema(targets) if stage == "structure" else response_schema(criteria),
                "requests": requests[:limit], "remaining": len(requests)}

    def submit(self, event_id: str, stage: str, request_hash: str, responses: dict, backend=None):
        with self.locked():
            data, criteria, brief = self.dataset(event_id), self.criteria(), self.brief()
            if stage not in {"structure", "matching"}:
                raise ReviewError("Unknown evaluation stage")
            if request_hash != self._input_hash(stage, data, criteria, brief):
                raise ReviewError("Profile data or preferences changed; get fresh model tasks")
            if not isinstance(responses, dict) or not responses:
                raise ReviewError("Supply a nonempty response object keyed by profile URL")
            people = {p["profile_url"]: p for p in data["people"]}
            structures = self.read(self.directory(event_id) / "structure.json", {})
            records = self.read(self.directory(event_id) / f"{stage}.json", {})
            for url, result in responses.items():
                if url not in people:
                    raise ReviewError("Response refers to an unknown attendee")
                person = people[url]
                if stage == "structure":
                    validate_structure(result, person, set(people))
                else:
                    validate_assessment(result, criteria, person)
                records[url] = {"input_hash": self._person_hash(person, brief, criteria, stage, structures),
                                "result": result, "backend": backend or {"backend": "host"}}
            write_json(self.directory(event_id) / f"{stage}.json", records)
            errors_path = self.directory(event_id) / "errors.json"
            errors = self.read(errors_path, {})
            for url in responses:
                errors.pop(stage + ":" + url, None)
            write_json(errors_path, errors)
        return {"accepted": len(responses), "stage": stage}

    def analyze(self, event_id, backend, refresh=False, progress=None, *, profile_urls=None, stop=None):
        def failure(stage, url, error):
            with self.locked():
                path = self.directory(event_id) / "errors.json"
                errors = self.read(path, {})
                errors[stage + ":" + url] = str(error)
                write_json(path, errors)

        def metric(stage, started, characters, count):
            value = {'stage': stage, 'backend': backend.identity, 'profiles': count,
                     'seconds': round(time.monotonic() - started, 3),
                     'prompt_characters': characters, 'usage': getattr(backend, 'last_usage', {})}
            with self.locked():
                path = self.root / 'work/usage.jsonl'
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open('a', encoding='utf-8') as stream:
                    stream.write(json.dumps(value) + '\n')

        for stage in ["structure", "matching"]:
            people = {p['profile_url']: p for p in self.dataset(event_id)['people']}
            if len(people) > 10000:
                raise ReviewError("Process events with more than 10,000 profiles in explicit batches")
            tasks = self.tasks(event_id, stage, limit=max(1, len(people)), include_reviewed=True)
            existing = self.read(self.directory(event_id) / f"{stage}.json", {})
            pending = [request for request in tasks['requests']
                       if (profile_urls is None or request['profile_url'] in profile_urls)
                       and (refresh or existing.get(request['profile_url'], {}).get('input_hash') != request['input_hash']
                            or existing.get(request['profile_url'], {}).get('backend') != backend.identity)]
            size = min(3, max(1, getattr(backend, 'batch_size', 1)))
            for offset in range(0, len(pending), size):
                if stop and stop():
                    return self.guide(event_id)
                batch = pending[offset:offset + size]
                if progress:
                    progress({'stage': stage, 'current': offset + 1, 'total': len(pending)})
                sourced = [request for request in batch if people[request['profile_url']]['sources']]
                results = {}
                if sourced:
                    started = time.monotonic()
                    try:
                        if len(sourced) > 1 and hasattr(backend, 'generate_batch'):
                            results, characters = backend.generate_batch(sourced, tasks['schema'])
                        else:
                            request = sourced[0]
                            suffix = '#structure' if stage == 'structure' else ''
                            results[request['profile_url']] = backend.generate(request['prompt'], tasks['schema'], request['profile_url'] + suffix)
                            characters = len(request['prompt'])
                        metric(stage, started, characters, len(sourced))
                    except BackendUnavailable as error:
                        for request in sourced:
                            failure(stage, request['profile_url'], error)
                        raise
                    except ReviewError as error:
                        for request in sourced:
                            failure(stage, request['profile_url'], error)
                for request in batch:
                    url = request['profile_url']
                    if not people[url]['sources']:
                        result = {'summary': 'No readable professional source.', 'facts': [], 'relationships': []} if stage == 'structure' else {
                            'summary': 'No readable professional source; relevance needs verification.', 'assessments': [
                                {'criterion_id': rule.id, 'verdict': 'unknown', 'reason': 'No readable professional source.', 'evidence': []}
                                for rule in self.criteria().rules]}
                    elif url in results:
                        result = results[url]
                    else:
                        continue
                    try:
                        self.submit(event_id, stage, tasks['request_hash'], {url: result}, backend.identity)
                    except ReviewError as error:
                        failure(stage, url, error)
        return self.guide(event_id)

    def guide(self, event_id: str):
        data, criteria, brief = self.dataset(event_id), self.criteria(), self.brief()
        directory = self.directory(event_id)
        structures = self.read(directory / "structure.json", {})
        assessments = self.read(directory / "matching.json", {})
        feedback = self.read(directory / "feedback.json", {})
        valid_structures, reviewed, cards = {}, [], []
        for person in data["people"]:
            url = person["profile_url"]
            key = self._person_hash(person, brief, criteria)
            structure = structures.get(url, {})
            if structure.get("input_hash") == key:
                validate_structure(structure["result"], person, {p["profile_url"] for p in data["people"]})
                valid_structures[url] = structure["result"]
            record = assessments.get(url, {})
            if record.get("input_hash") != self._person_hash(person, brief, criteria, "matching", structures):
                continue
            result = validate_assessment(record["result"], criteria, person)
            score = aggregate(result, criteria)
            reviewed.append({"profile": person, "result": result})
            reasons = [a["reason"] for a in result["assessments"] if a["verdict"] == "yes"]
            unknowns = [a["reason"] for a in result["assessments"] if a["verdict"] in {"unknown", "conflict"}]
            facts = valid_structures.get(url, {}).get("facts", [])
            topics = [f["value"] for f in facts if f["kind"] in {"interest", "skill", "project"}]
            projects = [f["value"] for f in facts if f["kind"] == "project"]
            question = (f"Ask what they learned building {projects[0]}, then compare it with your own work." if projects else
                        f"Ask what interests them about {topics[0]} and where they see practical challenges." if topics else
                        "Ask what they are working on and whether there is useful professional overlap.")
            cards.append({"name": person["name"], "profile_url": url, "summary": result["summary"],
                          "why": reasons[:3], "uncertainties": unknowns, "conversation_starter": question,
                          "your_contribution": brief["can_offer"], "assessments": result["assessments"],
                          "sources": person["sources"], "professional": valid_structures.get(url),
                          "source_attempts": person.get("source_attempts", []),
                          "provenance": {"structure": structure.get("backend"), "matching": record.get("backend")},
                          "feedback": feedback.get(url, {}), "score": score, **presentation(person)})
        ranking = evidence_ranking(reviewed, criteria)
        positions = {r["profile_url"]: i for i, r in enumerate(ranking)}
        cards.sort(key=lambda c: positions[c["profile_url"]])
        graph = build_graph(brief, data["people"], valid_structures)
        result = {"event_id": event_id, "event": data["event"], "brief": brief,
                  "criteria_markdown": criteria.markdown, "people": cards, "graph": graph,
                  "counts": {"captured": len(data["people"]), "with_sources": sum(bool(p["sources"]) for p in data["people"]),
                             "structured": len(valid_structures), "reviewed": len(cards),
                             "recommended": sum(c["score"]["status"] in {"Preference match", "Meets required criteria"} and c["feedback"].get("status") != "not_relevant" for c in cards)},
                  "keyword_baseline": keyword_ranking(data["people"], brief),
                  "errors": self.read(directory / "errors.json", {}), "demo": bool(data.get("demo")),
                  "matching_note": "Evidence-based matching is the initial experiment. Keyword ranking is a comparison baseline; the graph explains context and does not rank popularity."}
        result = present_guide(result, self.read(self.root / "presentation-en.json", {}), assessments)
        write_json(directory / "guide.json", result)
        return result

    def save_feedback(self, event_id, profile_url, status, note=""):
        if status not in {"saved", "meet", "met", "not_relevant", "none"}:
            raise ReviewError("Unknown feedback status")
        if profile_url not in {p["profile_url"] for p in self.dataset(event_id)["people"]}:
            raise ReviewError("Unknown attendee")
        if not isinstance(note, str) or len(note) > 5000:
            raise ReviewError("Keep feedback notes below 5,000 characters")
        with self.locked():
            path = self.directory(event_id) / "feedback.json"
            feedback = self.read(path, {})
            feedback[profile_url] = {"status": status, "note": note}
            write_json(path, feedback)
        return {"saved": True}

    def state(self):
        events = []
        for path in sorted((self.root / "events").glob("*/profiles.json")):
            data = self.read(path)
            events.append({"event_id": path.parent.name, "event": data["event"], "captured": len(data["people"]), "demo": bool(data.get("demo"))})
        path = self.root / "criteria.md"
        brief = self.brief()
        presentation = self.read(self.root / "presentation-en.json", {})
        markdown = path.read_text(encoding="utf-8") if path.exists() else None
        return {"brief": present_brief(brief, presentation), "questions": QUESTIONS, "events": events,
                "criteria_markdown": present_criteria(markdown, brief, presentation) if markdown else None}
