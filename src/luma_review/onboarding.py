"""A small professional brief, shared by the UI, CLI, and agent integrations."""
from .core import ReviewError, fingerprint, text

QUESTIONS = [
    {"id": "work", "label": "What are you working on?", "hint": "Your role, project, or company in a sentence."},
    {"id": "interests", "label": "What are you interested in?", "hint": "A few professional topics, separated by commas."},
    {"id": "looking_for", "label": "What would make this event worthwhile?", "hint": "For example: feedback, customers, collaborators, or learning."},
    {"id": "connect_with", "label": "Who would you like to meet?", "hint": "Describe relevant backgrounds, roles, or experience."},
    {"id": "can_offer", "label": "What can you bring to the conversation?", "hint": "Your experience, a useful introduction, feedback, or a collaboration."},
]


def make_brief(answers: dict) -> dict:
    if not isinstance(answers, dict):
        raise ReviewError("Onboarding answers must be an object")
    brief = {"version": 1, "region": "San Francisco Bay Area"}
    for question in QUESTIONS:
        key = question["id"]
        value = answers.get(key)
        if key == "interests":
            if isinstance(value, str):
                value = value.split(",")
            if not isinstance(value, list) or not value:
                raise ReviewError("Add at least one professional interest")
            brief[key] = list(dict.fromkeys(text(v, "Interest") for v in value if isinstance(v, str) and v.strip()))
            if not brief[key] or len(brief[key]) > 20:
                raise ReviewError("Use between 1 and 20 interests")
        else:
            brief[key] = text(value, question["label"])
            if len(brief[key]) > 3000:
                raise ReviewError("Keep each onboarding answer below 3,000 characters")
    must = answers.get("must_haves", [])
    if isinstance(must, str):
        must = [v.strip() for v in must.splitlines() if v.strip()]
    if not isinstance(must, list) or len(must) > 20:
        raise ReviewError("must_haves must be a list of up to 20 explicit requirements")
    brief["must_haves"] = [text(v, "Required condition") for v in must]
    brief["id"] = fingerprint(brief)
    return brief


def criteria_from_brief(brief: dict) -> str:
    def cell(value):
        return str(value).replace("|", r"\|").replace("\n", " ").replace("\r", " ")
    lines = ["# My event networking brief", "", "Status: active", "", "## Context", "",
             f"My work: {brief['work']}", "", f"My goal: {brief['looking_for']}", "",
             f"People I hope to meet: {brief['connect_with']}", "", f"What I can offer: {brief['can_offer']}",
             "", "## Criteria", "", "| ID | Type | Weight | Criterion | Required evidence |",
             "| --- | --- | --- | --- | --- |"]
    for index, condition in enumerate(brief["must_haves"], 1):
        lines.append(f"| M{index} | must | 0 | {cell(condition)} | Explicit relevant professional evidence; missing information is unknown |")
    preferences = [
        ("P1", 4, "Has professional work or interests relevant to: " + ", ".join(brief["interests"]),
         "A specific professional role, project, or declared interest; attendance alone is insufficient"),
        ("P2", 5, "Has a professional background relevant to the people I hope to meet: " + brief["connect_with"],
         "A stated role, experience, or professional activity; avoid guessing seniority"),
        ("P3", 5, "Has professional experience that could contribute to my goal: " + brief["looking_for"],
         "Concrete relevant professional experience; this does not imply availability or willingness"),
        ("P4", 2, "Has professional context in which my contribution could be useful: " + brief["can_offer"],
         "A concrete project, role, or stated need; do not infer interest in receiving an offer"),
    ]
    for ident, weight, condition, evidence in preferences:
        lines.append(f"| {ident} | prefer | {weight} | {cell(condition)} | {evidence} |")
    lines += ["", "## Rules", "", "These are editable preferences derived from my own answers. Only explicit must_haves are hard requirements.",
              "Missing evidence means unknown, not no. Potential professional relevance is not proof of willingness to meet, buy, invest, or collaborate.",
              "Distinguish current and past work. Base decisions on source excerpts, not a person's popularity or event attendance."]
    return "\n".join(lines) + "\n"
