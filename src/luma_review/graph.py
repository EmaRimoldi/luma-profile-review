"""An evidence graph, not a claim that everyone sharing context knows each other."""
import re

from .core import fingerprint


def build_graph(brief: dict, people: list[dict], structures: dict) -> dict:
    nodes, edges = {}, {}
    def node(ident, kind, label, **properties):
        nodes.setdefault(ident, {"id": ident, "type": kind, "label": label, **properties})
        return ident
    def context(kind, label):
        normalized = re.sub(r"\s+", " ", label.casefold()).strip()
        return node(kind + ":" + fingerprint(normalized)[:16], kind, label)
    def edge(source, target, kind, evidence, derived=False):
        ident = fingerprint([source, target, kind])[:20]
        edges[ident] = {"id": ident, "source": source, "target": target, "type": kind,
                        "evidence": evidence, "derived": derived}
    me = node("user:self", "user", "You", work=brief["work"])
    for interest in brief["interests"]:
        topic = context("topic", interest)
        edge(me, topic, "interested_in", [{"source": "onboarding", "text": interest}])
    for person in people:
        url = person["profile_url"]
        ident = node(url, "person", person["name"], profile_url=url)
        structure = structures.get(url)
        if not structure:
            continue
        for fact in structure["facts"]:
            if fact["kind"] in {"interest", "skill"}:
                kind, relation = "topic", "professional_topic"
            elif fact["kind"] == "organization":
                kind, relation = "organization", "professional_affiliation"
            elif fact["kind"] == "project":
                kind, relation = "project", "works_on"
            else:
                continue
            target = context(kind, fact["value"])
            sources = {s["id"]: s for s in person["sources"]}
            refs = [{"profile_url": url, "source_url": sources[e["source_id"]]["url"], **e} for e in fact["evidence"]]
            edge(ident, target, relation, refs)
    known = {p["profile_url"] for p in people}
    for url, structure in structures.items():
        sources = {s["id"]: s for p in people if p["profile_url"] == url for s in p["sources"]}
        for relationship in structure["relationships"]:
            if relationship["target_profile_url"] in known:
                edge(url, relationship["target_profile_url"], relationship["kind"],
                     [{"profile_url": url, "source_url": sources[e["source_id"]]["url"], **e} for e in relationship["evidence"]])
    adjacency = {}
    for e in edges.values():
        if nodes[e["target"]]["type"] in {"topic", "organization", "project"}:
            adjacency.setdefault(e["target"], []).append(e)
    shared = []
    for target, connections in adjacency.items():
        if len(connections) > 1:
            shared.append({"context": nodes[target], "people": [e["source"] for e in connections],
                           "interpretation": "Shared professional context; does not establish a personal relationship."})
    return {"version": 1, "nodes": list(nodes.values()), "edges": list(edges.values()), "shared_contexts": shared,
            "note": "Shared interests, projects, companies, or event attendance do not imply that people know each other."}
