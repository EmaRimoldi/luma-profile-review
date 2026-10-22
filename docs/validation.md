# Validation

Validated locally on October 19, 2026 (America/Los_Angeles).

| Check | Result |
| --- | --- |
| Python unittest suite | 53 passing tests with the MCP extra: original engine, onboarding, research queues, professional facts, graph semantics, stale batches, feedback, local HTTP, and MCP |
| Source checkout CLI | Passed |
| Editable package build/install in an isolated venv | Passed |
| Wheel build and fresh isolated installation | Passed; packaged static assets, fictional demo, HTML export and installed-module MCP configuration verified |
| Shared skill and Claude Code entrypoint structural validators | Passed |
| Offline synthetic three-profile pipeline | Passed; match, explicit failure and missing-data outcomes |
| Codex CLI 0.144.5 live inference | Original evaluator passed; product 0.2 also passed complete professional-fact extraction and criterion matching on one fictional profile, using saved ChatGPT login |
| Claude Code 2.1.205 live inference | Attempted; CLI returned Not logged in. Adapter contract tested with synthetic subprocess responses, live inference not confirmed |
| Ollama client 0.17.5 | Installed; no running server. HTTP/schema contract tested against a local synthetic server, real model inference not confirmed |
| Luma browser acquisition | Authenticated event guest list opened; one profile and its external profile links inspected |
| MCP Python SDK 1.30.0 stdio integration | Actual client/server handshake and full onboarding → roster → sources → structure tasks/submission → matching tasks/submission → guide flow passed |
| Local browser product QA | Onboarding save, guide search, saved/irrelevant feedback and reversal, evidence details, graph node interaction and source links verified on the fictional walkthrough |
| Private live-event pilot | Imported 311 other accessible attendee identities; structured and matched a systematic sample of 30, using 30 Luma pages, 28 linked LinkedIn profiles and 5 other linked professional pages |
| Live-pilot display fixes | Browser verified source dates in local time and a graph that omits attendees with no documented context; all connected context nodes remain available |
| Portable guide | Self-contained HTML exports include inline assets and escaped embedded data; read-only mode supports search, filters, evidence and graph |

The initial access check inspected one Luma profile without external enrichment.
A later private pilot used profile-derived professional criteria and the current
agent's task/submit workflow to structure and match 30 real attendees. The
systematic sample spanned an alphabetical roster; it was not random. LinkedIn
headline/About excerpts and selected linked professional pages were read, not
complete employment histories. Real profiles, the user's brief, research extracts,
responses and guide outputs remain under ignored `data/private/` and `work/`.
They are not part of this source distribution or its fictional examples.

The pilot produced 25 profiles with at least one supported preference and 15
ties at the maximum score, exposing that the initial criteria are broad and
overlapping. No user relevance labels or post-event outcomes were collected.
This establishes a live workflow trial, not measured recommendation quality.

The repository includes CI for Python 3.11 and 3.13 with the optional MCP extra
installed. Client configuration generation is tested for Codex, Claude Code,
Cursor, GitHub Copilot/VS Code, OpenCode, and Claude Desktop; this is not a claim
that every client or its browser integration has been manually exercised.
Unit tests and fictional fixtures do not establish recommendation quality or
that external websites will keep the same interface. Multi-event collection,
enrichment and multi-user relevance pilots remain required before broader claims.

## October 21 discovery redesign

- 63 Python tests and 5 Node search tests pass. Additional contracts cover
  durable Meet intent, presentation-only updates without re-analysis, key
  non-persistence/non-disclosure, fixed API endpoints, redirects, sanitized
  failures, incomplete responses, and guide cache invalidation after external
  workspace writes.
- Fresh browser setup traversed Luma handoff, all five questions, and the model
  connection step; incomplete setup resumes after reload. The official Codex
  CLI login check returned Ready without making a model request.
- Browser checks on fictional data cover Save, Meet, Not relevant, immediate
  advancement, undo, reload persistence, saved collections, source disclosures,
  a right-drag swipe, and the scrolling view. Responsive preview at 390 × 844
  checked navigation and reachable decision buttons. Real touch hardware remains
  untested.
- Real pilot search for `neuro` found two documented matches; Next navigated
  between them. All 30 reviewed Luma pages supplied observed portraits on
  October 21. Their 30 existing assessments and the user's brief/feedback were
  preserved; these portrait records remain in ignored private files.
- `uvx --from . luma-review --version`, the local Git-style package requirement
  with the MCP extra, and wheel building succeeded. The built wheel includes
  `search.js` and the new server modules. No npm/PyPI release was published.
- The OpenAI / Anthropic API adapters were checked against their official
  structured-output contracts with mocked HTTP. Live paid API calls were not
  made; prior subscription/Ollama validation limits still apply.
- Reproducible synthetic index microbenchmark: roughly 0.3 / 1.8 ms p95 search
  at 1,000 / 10,000 profiles, excluding DOM, network, and model work. Relevance
  improvement remains unmeasured; the default personalized assessment order
  was not replaced with a lexical score.

## Integrated Codex workflow (October 22, 2026)

- 71 Python and 10 Node tests pass; GitHub CI covers Python 3.11 and 3.13.
- A live ChatGPT-authenticated Codex app-server turn successfully calls the
  platform's dynamic progress tool, with the complete research tool catalog.
- Runtime configuration confirms zero enabled inherited MCP servers and the
  model shell disabled. User configuration is preserved.
- The hosted-to-local flow carries the user's actual profile and event through
  a URL fragment and review screen. No chat or manual file import is required.
- The app's persistent browser reconnects to a completed Luma session after
  restart. The first live event run detects an 82-person guest list gated to
  registered attendees; public profile collection is partial. Authentication
  alone does not establish event-specific roster access.

- The first live run completes inside the platform: four publicly visible profiles
  are collected, structured, and matched, and the guide loads automatically. All
  four remain Needs verification because available professional evidence is
  insufficient for the user’s criteria. No positive matches are invented.
