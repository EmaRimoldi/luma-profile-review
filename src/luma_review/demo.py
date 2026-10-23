"""Fictional, deterministic product walkthrough. Never represents live inference."""
from .core import ReviewError

DEMO_ANSWERS = {
    "work": "I build an open-source tool for efficient LLM inference on GPUs.",
    "interests": ["LLM inference", "GPU infrastructure", "open source"],
    "looking_for": "Technical feedback and collaborators for an inference project.",
    "connect_with": "AI infrastructure engineers, researchers, and technical founders.",
    "can_offer": "Hands-on inference engineering, benchmarks, and open-source contributions.",
    "must_haves": ["Currently works on AI systems or infrastructure"],
}


def load_demo(workspace):
    if workspace.brief() or workspace.state()["events"]:
        raise ReviewError("Use a separate empty workspace for the fictional demo")
    workspace.save_brief(DEMO_ANSWERS)
    specifications = [
        ("Avery Chen", "avery", "I am cofounder of BayCompute. I build LLM inference systems and an open-source GPU scheduler. We are seeking technical feedback and infrastructure collaborators.",
         [("role", "Cofounder", "cofounder of BayCompute"), ("organization", "BayCompute", "cofounder of BayCompute"),
          ("interest", "LLM inference", "I build LLM inference systems"), ("interest", "GPU infrastructure", "open-source GPU scheduler"),
          ("project", "Open-source GPU scheduler", "open-source GPU scheduler"), ("seeking", "Technical feedback", "seeking technical feedback")]),
        ("Jordan Park", "jordan", "I am an infrastructure engineer at BayCompute. I work on LLM inference benchmarks and GPU infrastructure. I am looking for open-source contributors to improve serving performance.",
         [("role", "Infrastructure engineer", "infrastructure engineer at BayCompute"), ("organization", "BayCompute", "infrastructure engineer at BayCompute"),
          ("interest", "LLM inference", "LLM inference benchmarks"), ("interest", "GPU infrastructure", "GPU infrastructure"),
          ("interest", "open source", "looking for open-source contributors")]),
        ("Casey Rao", "casey", "I research AI agent evaluation and build agent tooling. My current project studies tool-use reliability. I publish evaluation code as open source.",
         [("role", "AI researcher", "research AI agent evaluation"), ("interest", "Agent evaluation", "AI agent evaluation"),
          ("interest", "open source", "publish evaluation code as open source"), ("project", "Tool-use evaluation", "tool-use reliability")]),
        ("Riley Brooks", "riley", "I organize community events for AI builders. I connect founders with developer communities and host open-source project demos.",
         [("role", "Community organizer", "organize community events"), ("interest", "open source", "open-source project demos")]),
        ("Taylor Quinn", "taylor", "I work exclusively in jewelry design and retail. I do not work on AI systems, software engineering, or infrastructure.",
         [("role", "Jewelry designer", "work exclusively in jewelry design and retail")]),
        ("Morgan Lee", "morgan", None, []),
    ]
    people = []
    for name, slug, excerpt, facts in specifications:
        sources = [] if excerpt is None else [{"id": "s1", "url": f"https://example.org/people/{slug}",
                    "title": "Fictional professional bio", "retrieved_at": "2026-10-19T12:00:00-07:00", "text": excerpt}]
        people.append({"name": name + " (demo)", "profile_url": f"https://luma.com/user/demo-{slug}",
                       "sources": sources, "outbound_links": [], "collection_complete": True})
    dataset = {"version": 1, "demo": True, "event": {"name": "AI Builders — fictional demo",
               "url": "https://luma.com/demo-ai-builders", "displayed_guest_count": len(people),
               "collection_scope": "Six fictional profiles. Demo assessments are curated fixtures, not live model outputs.",
               "roster_complete": True}, "people": people}
    event_id = workspace.import_dataset(dataset)["event_id"]
    structures = {}
    for person, spec in zip(people, specifications):
        structures[person["profile_url"]] = {"summary": spec[2] or "No readable professional source.",
            "facts": [{"kind": kind, "value": value, "evidence": [{"source_id": "s1", "quote": quote}]} for kind, value, quote in spec[3]],
            "relationships": []}
    tasks = workspace.tasks(event_id, "structure")
    workspace.submit(event_id, "structure", tasks["request_hash"], structures, {"backend": "curated-demo"})
    results = {}
    for index, person in enumerate(people):
        quote = person["sources"][0]["text"] if person["sources"] else None
        values = ["yes"] * 5 if index < 2 else (["yes", "yes", "yes", "unknown", "unknown"] if index == 2 else
                 ["unknown", "yes", "unknown", "unknown", "unknown"] if index == 3 else
                 ["no", "no", "no", "unknown", "unknown"] if index == 4 else ["unknown"] * 5)
        reasons = {
            "M1": "Current work in AI systems or infrastructure is explicitly documented.",
            "P1": "Their work overlaps with the professional topics in your brief.",
            "P2": "Their stated professional role fits the backgrounds you hope to meet.",
            "P3": "Their concrete inference work gives you a relevant technical feedback partner.",
            "P4": "Their project could benefit from the engineering and open-source contribution you can offer.",
        }
        assessments = []
        for rule, verdict in zip(workspace.criteria().rules, values):
            reason = reasons[rule.id] if verdict == "yes" else "The source explicitly excludes AI systems and infrastructure work." if verdict == "no" else "The source does not establish this condition; clarify it in conversation."
            assessments.append({"criterion_id": rule.id, "verdict": verdict, "reason": reason,
                                "evidence": [{"source_id": "s1", "quote": quote}] if verdict in {"yes", "no"} else []})
        results[person["profile_url"]] = {"summary": structures[person["profile_url"]]["summary"], "assessments": assessments}
    tasks = workspace.tasks(event_id, "matching")
    workspace.submit(event_id, "matching", tasks["request_hash"], results, {"backend": "curated-demo"})
    return workspace.guide(event_id)
