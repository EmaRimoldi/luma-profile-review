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
| Portable guide | Self-contained HTML exports include inline assets and escaped embedded data; read-only mode supports search, filters, evidence and graph |

No actual attendee was ranked: personal criteria have not been defined. The
real profile used for the access check is in ignored `data/private/`, and is
not part of the source distribution or synthetic examples. Linked profile
URLs were observed, not fetched as part of that access check.

The repository includes CI for Python 3.11 and 3.13 with the optional MCP extra
installed. Client configuration generation is tested for Codex, Claude Code,
Cursor, GitHub Copilot/VS Code, OpenCode, and Claude Desktop; this is not a claim
that every client or its browser integration has been manually exercised.
Unit tests and fictional fixtures do not establish recommendation quality or
that external websites will keep the same interface. Full live-event collection
and multi-user relevance pilots remain required before broader claims.
