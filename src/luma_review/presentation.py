"""Optional English presentation, tied to the exact brief and assessment inputs.

Source quotes, verdicts, scores, and cached model records are never translated.
"""
import copy


def present_brief(brief, translation):
    if not brief or translation.get("brief_id") != brief.get("id"):
        return brief
    fields = {k: v for k, v in translation.get("brief", {}).items()
              if k in {"work", "looking_for", "connect_with", "can_offer"} and isinstance(v, str)}
    return {**brief, **fields}


def present_criteria(markdown, brief, translation):
    displayed = present_brief(brief, translation)
    if brief and displayed is not brief:
        for key in ("work", "looking_for", "connect_with", "can_offer"):
            markdown = markdown.replace(brief[key], displayed[key])
    return markdown


def present_guide(guide, translation, matching):
    if translation.get("brief_id") != guide["brief"].get("id"):
        return guide
    guide = copy.deepcopy(guide)
    original_brief = guide["brief"]
    guide["brief"] = present_brief(original_brief, translation)
    guide["criteria_markdown"] = present_criteria(guide["criteria_markdown"], original_brief, translation)
    labels = {}
    for person in guide["people"]:
        translated = translation.get("people", {}).get(person["profile_url"], {})
        expected = matching.get(person["profile_url"], {}).get("input_hash")
        if not expected or translated.get("input_hash") != expected:
            continue
        facts = (person.get("professional") or {}).get("facts", [])
        values = translated.get("facts", [])
        if len(values) != len(facts) or any(not isinstance(v, str) for v in values):
            continue
        for fact, value in zip(facts, values):
            labels[fact["value"]] = value
            fact["value"] = value
        if isinstance(translated.get("summary"), str):
            person["summary"] = translated["summary"]
        for assessment in person["assessments"]:
            reason = translated.get("reasons", {}).get(assessment["criterion_id"])
            if isinstance(reason, str):
                assessment["reason"] = reason
        person["why"] = [a["reason"] for a in person["assessments"] if a["verdict"] == "yes"][:3]
        person["uncertainties"] = [a["reason"] for a in person["assessments"] if a["verdict"] in {"unknown", "conflict"}]
        person["your_contribution"] = guide["brief"]["can_offer"]
        projects = [f["value"] for f in facts if f["kind"] == "project"]
        topics = [f["value"] for f in facts if f["kind"] in {"interest", "skill"}]
        if projects:
            person["conversation_starter"] = f"Ask what they learned building {projects[0]}, then compare it with your own work."
        elif topics:
            person["conversation_starter"] = f"Ask what interests them about {topics[0]} and where they see practical challenges."
    for node in guide["graph"]["nodes"]:
        node["label"] = labels.get(node["label"], node["label"])
        if node["type"] == "user":
            node["work"] = guide["brief"]["work"]
    return guide
