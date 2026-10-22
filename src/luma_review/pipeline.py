"""Resumable evaluations and evidence-linked reports."""
from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from .core import (PROMPT_VERSION, Criteria, ReviewError, aggregate, fingerprint,
                   make_prompt, response_schema, validate_assessment)
from .providers import BackendUnavailable


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                     prefix=path.name + ".", suffix=".tmp", delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def evaluate(dataset: dict, criteria: Criteria, backend, output: Path, *, cache: Path,
             refresh=False, limit=None, progress=None) -> dict:
    if limit is not None and limit < 1:
        raise ReviewError("limit must be positive")
    people = dataset["people"][:limit] if limit else dataset["people"]
    run = {"version": 1, "criteria_sha256": criteria.sha256, "backend": backend.identity,
           "created_at": datetime.now(timezone.utc).isoformat(), "event": dataset["event"],
           "input_profile_count": len(dataset["people"]), "selected_profile_count": len(people),
           "people": [{"profile": p, "status": "pending"} for p in people]}
    schema = response_schema(criteria)
    output.mkdir(parents=True, exist_ok=True)
    cache.mkdir(parents=True, exist_ok=True)
    write_json(output / "results.json", run)
    for index, entry in enumerate(run["people"], start=1):
        person = entry["profile"]
        key = fingerprint({"prompt_version": PROMPT_VERSION, "criteria": criteria.sha256,
                           "profile": person, "provider": backend.identity})
        cache_file = cache / f"{key}.json"
        if progress:
            progress(f"Evaluating {index}/{len(people)}")
        try:
            cached = False
            if not refresh and cache_file.exists():
                try:
                    result = validate_assessment(json.loads(cache_file.read_text()), criteria, person)
                    cached = True
                except (ReviewError, json.JSONDecodeError):
                    result = None
            else:
                result = None
            if result is None:
                if not person["sources"]:
                    result = {"summary": "No readable profile sources were collected.", "assessments": [
                        {"criterion_id": c.id, "verdict": "unknown", "reason": "No readable source.",
                         "evidence": []} for c in criteria.rules]}
                else:
                    result = backend.generate(make_prompt(criteria, person), schema, person["profile_url"])
                result = validate_assessment(result, criteria, person)
                write_json(cache_file, result)
            entry.update(status="reviewed", result=result, score=aggregate(result, criteria), cached=cached)
        except BackendUnavailable as error:
            entry.update(status='failed', error=str(error))
            write_json(output / 'results.json', run)
            (output / 'report.md').write_text(render_report(run, criteria), encoding='utf-8')
            raise
        except ReviewError as error:
            entry.update(status="failed", error=str(error))
        write_json(output / "results.json", run)
        (output / "report.md").write_text(render_report(run, criteria), encoding="utf-8")
    return run


def md(value) -> str:
    value = str(value).replace("\\", "\\\\").replace("\n", " ").replace("\r", " ")
    for char in "|[]<>`*_#":
        value = value.replace(char, "\\" + char)
    return value


def link(label, url):
    return f"[{md(label)}]({quote(url, safe=':/?=&%+@#~._-')})"


def render_report(run: dict, criteria: Criteria) -> str:
    if run.get("criteria_sha256") != criteria.sha256:
        raise ReviewError("Criteria changed since this evaluation; evaluate again")
    event = run["event"]
    reviewed = [p for p in run["people"] if p["status"] == "reviewed"]
    failed = [p for p in run["people"] if p["status"] == "failed"]
    pending = [p for p in run["people"] if p["status"] == "pending"]
    # Revalidate on rendering, and recalculate rather than trusting stored scores.
    for entry in reviewed:
        validate_assessment(entry["result"], criteria, entry["profile"])
        entry["score"] = aggregate(entry["result"], criteria)
    order = {"Meets required criteria": 0, "Preference match": 1, "Needs verification": 2,
             "No preferences matched": 3, "Outside criteria": 4}
    reviewed.sort(key=lambda p: (order[p["score"]["status"]], -p["score"]["points"], p["profile"]["name"].casefold()))
    lines = [f"# Profile review — {md(event['name'])}", "", link("Event", event["url"]), "",
             f"Reviewed: {len(reviewed)}. Failed: {len(failed)}. Pending: {len(pending)}. "
             f"Selected: {run['selected_profile_count']} of {run['input_profile_count']} imported profiles.",
             f"Displayed event guest count: {event.get('displayed_guest_count', 'unknown')}. "
             f"Roster collection complete: {event['roster_complete']}.", "",
             f"Collection scope: {md(event['collection_scope'])}", "",
             f"Backend: `{md(run['backend']['backend'])}`. Criteria SHA-256: `{criteria.sha256}`.", "",
             "Points measure confirmed preferences. Uncertain points are shown separately. "
             "Coverage measures available evidence, not confidence or a person's value.", "",
             "| Person | Required criteria / status | Preference points | Uncertain points | Coverage |",
             "| --- | --- | --- | --- | --- |"]
    for entry in reviewed:
        person, score = entry["profile"], entry["score"]
        points = f"{score['points']}/{score['possible_points']}" if score["possible_points"] else "—"
        lines.append(f"| {link(person['name'], person['profile_url'])} | {score['status']} | {points} | "
                     f"{score['uncertain_points']} | {score['known_criteria']}/{score['total_criteria']} |")
    rules = {c.id: c for c in criteria.rules}
    for entry in reviewed:
        person, result = entry["profile"], entry["result"]
        sources = {s["id"]: s for s in person["sources"]}
        lines += ["", f"## {md(person['name'])}", "", link("Luma profile", person["profile_url"]), "",
                  md(result["summary"]), "", "| Criterion | Verdict | Reason | Sources |",
                  "| --- | --- | --- | --- |"]
        for assessment in result["assessments"]:
            evidence = []
            for e in assessment["evidence"]:
                source = sources[e["source_id"]]
                evidence.append(link(e["source_id"], source["url"]) + ": “" + md(e["quote"]) + "”")
            rule = rules[assessment["criterion_id"]]
            lines.append(f"| {md(rule.id + ': ' + rule.condition)} | {assessment['verdict']} | "
                         f"{md(assessment['reason'])} | {'; '.join(evidence) or 'Missing evidence'} |")
        if sources:
            lines += ["", "Sources consulted:", ""]
            for source in sources.values():
                lines.append(f"- {link(source['title'], source['url'])} — accessed {md(source['retrieved_at'])}.")
        if person.get("notes"):
            lines += ["", "Collection notes: " + md(person["notes"])]
        if person.get("outbound_links"):
            lines += ["", "Profile links (not automatically read): " + ", ".join(link("Link", u) for u in person["outbound_links"])]
    if failed or pending:
        lines += ["", "## Not evaluated", ""]
        for entry in failed + pending:
            lines.append(f"- {link(entry['profile']['name'], entry['profile']['profile_url'])}: "
                         f"{md(entry.get('error', 'Pending'))}.")
    return "\n".join(lines) + "\n"
