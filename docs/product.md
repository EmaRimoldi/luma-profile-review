# Product: a personal field guide to an event

## Purpose and audience

Help a person attending San Francisco professional events identify a small
number of useful conversations. The primary user is an individual attending
an event, not an organizer assigning meetings between every pair of guests.
The unit of value is a relevant conversation with a clear reason to begin it.

The product begins with the user's work, interests, desired outcomes, hoped-for
connections, and possible contribution. It should find complementary experience
as well as similar interests. It must distinguish professional fit from a
claim that someone is available or interested in the proposed interaction.

## Core loop shipped in 0.2

| Step | User-facing outcome | Implementation |
| --- | --- | --- |
| Onboard | A professional brief and editable criteria | Five-question local form, interactive CLI, and MCP tool |
| Collect | A scoped, resumable attendee list | Agent-browser workflow plus deduplicating capture tools |
| Enrich | Relevant professional facts with sources | Research queue, access-limitation records, exact-quote extraction |
| Understand | Shared topics, organizations, projects and explicit relationships | Evidence graph with distinct context and relationship edges |
| Prepare | Why to meet, what to ask, what remains unknown | Personal guide, source citations and conversation prompts |
| Learn | Which suggestions were useful | Local saved/met/not_relevant feedback and offline relevance labels |

An agent with browser tools performs authenticated browsing. The engine does
not reuse browser cookies in its inference processes and does not pretend that
an unavailable LinkedIn page has been read. A discovered URL and a read source
are different objects. Collection completeness and analysis coverage are
reported separately, including profiles Luma may not display.

The UI is local because CLI subscriptions, browser sessions, and private source
snapshots already live on the user's machine. A hosted multi-tenant account
system would not improve the initial event-preparation loop.

## Matching approaches considered

| Approach | What it could help with | What needs testing | Decision for this alpha |
| --- | --- | --- | --- |
| Literal keyword overlap | Cheap, inspectable baseline | Synonyms, vague bios, and complementary needs can be missed | Implemented only as a comparison baseline |
| Embedding retrieval | Candidate recall for semantic overlap and larger lists | Model choice, multilingual recall, and missed unusual matches | Keep as a future candidate generator; do not silently filter attendees yet |
| Per-criterion model evaluation | Goal-specific reasoning, complementary value, and citations | Evidence quality, consistency, latency, and usefulness judged by the user | Initial replaceable guide strategy |
| Pairwise reranking of a shortlist | Relative choices among otherwise relevant people | Order effects and extra model calls; does it improve user choices? | Defer until a judged shortlist exists |
| Graph-derived ranking | Paths through documented context and relationships | Whether context predicts relevance better than stated goals | Graph explains suggestions; no centrality/popularity ranking |
| Reciprocal matching | Mutual needs between attendees who state their goals | Usually only one user's goals are known; inferred intent would be unreliable | Use explicit source statements when available; do not invent reciprocity |

The choice is deliberately provisional. Preference weights are user-editable,
hard requirements come only from explicit input, and uncertainty remains a
separate state. The ranker functions and comparison command allow changes
without replacing the profile or evidence contracts.

## Graph semantics

People link to professional topics, projects, and organizations through quoted
source evidence. The user's topic edges come from onboarding. Shared-context
groups are derived from these edges and labeled accordingly. The application
does not generate person-to-person relationships from shared employment or
event attendance. An explicit relationship must identify a known attendee URL
and cite a source that references that identity; a reviewer must still check
that the quoted evidence supports the relationship.

No profile-photo recognition or generalized ranking of a person's worth is
needed to prepare a useful professional conversation.

## How to choose the next matching strategy

Run pilots on two or more different events, starting with 30–50 accessible
profiles per event. Ask users to judge the proposed top ten and a sample of
other attendees. Those judgments distinguish recommendation quality from
the amount of data collected. These are proposed pilot sizes, not results.

Measure:

- Precision among the top suggestions, with judged coverage reported.
- Recall over the labeled sample, including people the user would have wanted
  to meet but the tool did not suggest.
- Profiles with relevant readable professional evidence and unresolved identity.
- Unknown/contradictory criteria, failed sources, and source freshness.
- Time and model requests to create a usable guide, including resume behavior.
- User feedback after the event: saved, actually met, and useful conversation.

Compare the implemented keyword baseline with evidence-based matching using
`compare`. Evaluate embeddings only when the baseline reveals a candidate-recall
or scaling problem, and rerankers only when they improve judged choices.
Do not promote an algorithm because it scores the synthetic walkthrough well.

## Release boundary

This alpha includes the complete local workflow and agent bridge. It still
needs multi-event live collection trials, real user relevance judgments,
and client-by-client browser integration testing. Claude CLI and real Ollama
inference have separate verification gaps recorded in validation.md. A polished
demo is not evidence that every profile or host configuration will work.
