"""Replaceable ranking strategies and offline relevance evaluation."""
import re

from .core import aggregate

STOP_WORDS = {"the", "and", "with", "for", "that", "from", "this", "have", "your", "into", "what", "work", "who", "are", "you", "our"}


def tokens(value: str) -> set[str]:
    return {v for v in re.findall(r"[a-z0-9]+", value.casefold()) if len(v) > 2 and v not in STOP_WORDS}


def keyword_ranking(people: list[dict], brief: dict) -> list[dict]:
    query = tokens(" ".join(brief["interests"]) + " " + brief["connect_with"] + " " + brief["looking_for"])
    rows = []
    for person in people:
        terms = tokens(" ".join(s["text"] for s in person["sources"]))
        overlap = sorted(query & terms)
        rows.append({"profile_url": person["profile_url"], "score": len(overlap), "matched_terms": overlap,
                     "has_sources": bool(person["sources"])})
    return sorted(rows, key=lambda row: (-row["score"], row["profile_url"]))


def evidence_ranking(results: list[dict], criteria) -> list[dict]:
    priority = {"Meets required criteria": 0, "Preference match": 0, "Needs verification": 1,
                "No preferences matched": 2, "Outside criteria": 3}
    rows = []
    for entry in results:
        score = aggregate(entry["result"], criteria)
        rows.append({"profile_url": entry["profile"]["profile_url"], **score})
    return sorted(rows, key=lambda row: (priority[row["status"]], -row["points"], row["profile_url"]))


def compare_rankings(rankings: dict[str, list[str]], labels: dict[str, bool], k=10) -> dict:
    if k < 1 or not labels or any(type(v) is not bool for v in labels.values()):
        raise ValueError("Use a positive k and explicit true/false relevance labels")
    results = {}
    relevant = sum(labels.values())
    for name, ranking in rankings.items():
        top = list(dict.fromkeys(ranking))[:k]
        judged = [url for url in top if url in labels]
        hits = sum(labels[url] for url in judged)
        results[name] = {"k": k, "returned": len(top), "judged": len(judged), "relevant": hits,
                         "precision_at_k": hits / len(top) if top and len(judged) == len(top) else None,
                         "judged_precision": hits / len(judged) if judged else None,
                         "recall_at_k": hits / relevant if relevant else None,
                         "judgment_coverage": len(judged) / len(top) if top else 0}
    return {"strategies": results, "note": "Unjudged people are not negative labels. Recall refers only to the labeled sample."}
