# Validation

Validated locally on October 19, 2026 (America/Los_Angeles).

| Check | Result |
| --- | --- |
| Python unittest suite | 27 passing tests: evidence, scoring, identity, cache invalidation, stale inputs, failures, adapters and CLI |
| Source checkout CLI | Passed |
| Editable package build/install in an isolated venv | Passed |
| Bundled Codex skill structural validator | Passed |
| Offline synthetic three-profile pipeline | Passed; match, explicit failure and missing-data outcomes |
| Codex CLI 0.144.5 live inference | Passed on one fictional profile with saved ChatGPT login; all three citations validated |
| Claude Code 2.1.205 live inference | Attempted; CLI returned Not logged in. Adapter contract tested with synthetic subprocess responses, live inference not confirmed |
| Ollama client 0.17.5 | Installed; no running server. HTTP/schema contract tested against a local synthetic server, real model inference not confirmed |
| Luma browser acquisition | Authenticated event guest list opened; one profile and its external profile links inspected |

No actual attendee was ranked: personal criteria have not been defined. The
real profile used for the access check is in ignored `data/private/`, and is
not part of the source distribution or synthetic examples. Linked profile
URLs were observed, not fetched as part of that access check.

The repository includes CI for Python 3.11 and 3.13; remote CI has not run
because the repository has not been published. Unit tests do not establish
model quality or that an external website will keep the same interface.
