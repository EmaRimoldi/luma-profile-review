# Service audit — 0.4

This record distinguishes implemented adapters, actual provider calls, client
connection checks, and simulated acceptance tests. Fictional examples are never
reported as live attendee research. The implementation is on the public review
branch `feature/agent-portability-audit`; `main` changes only after review/merge.

## Findings and changes

The app previously hardwired preparation to Codex app-server, even after Claude
or Ollama was selected. Collection is now a separate service shared by the app
and MCP. All five built-in backends use the same validated analysis pipeline.
Codex app-server remains an authentication/catalog adapter, not the collector.

The previous browser bridge already returned DOM text, not screenshots. It
opened a headed browser for every source and could return 24,000 characters,
800 links, and 150 controls per read. Public sources now use bounded HTTP reads
and a one-hour private workspace cache. JavaScript/authenticated content uses
headless Chromium; sign-in remains interactive. Images, fonts, and media are
blocked during headless research. No image input is used by the researcher.

Additional fixes include:

- Luma's attendee-name-labelled guest button, dialog-scoped extraction, canonical
  deduplication, explicit partial coverage, and protection against capturing hosts
  from the event page as guests.
- Bounded redirects/response size, DNS-address validation and pinned HTTP
  connections, private-address blocking, readable text extraction, and corrupt
  cache recovery. No cookies or model credentials enter public HTTP requests.
- A cross-process browser-profile lease, automatic release after checking Luma
  or finishing research, and source checkpoints before analysis. MCP runs the
  entire synchronous Playwright lifetime on one worker, outside its async loop.
- Three-profile CLI batches with per-person validation/checkpoints, reported
  usage/timing records, cache reuse, and owned-process cancellation.
- Explicit Ollama context/output limits; relationship schemas prohibit target
  placeholders when no identified attendee is referenced by a source. Exact
  relationship targets replace prefix-based identity matching.
- Invalid settings/model/timeouts/ports fail clearly; damaged JSON is reported
  without overwriting it. Connection-check failures cannot clear an unrelated
  running analysis job. Cache hashes include the prompt-contract version.
- Provider/account/transport outages stop after one failed batch, retaining
  retryable checkpoints. A nonexistent local model was tested against the actual
  installed service: one HTTP 404, not a request for every remaining profile.
- Referenced-identity cache dependencies update when a cited attendee is newly
  collected; unrelated roster additions do not rerun existing assessments.
- Public install instructions use `main`, distinguish Git distribution from a
  registry package, and explain backend selection, sign-in, recovery, and limits.

## Agent coverage

| Integration | Implementation | Verification |
| --- | --- | --- |
| Codex CLI 0.144.5 | App connection, model catalog, batched structure/matching, MCP | Real subscription-backed inference on public fictional inputs; all three profiles reviewed; positive, explicit negative, and missing-source cases checked |
| Claude Code 2.1.205 | App/CLI analysis and shared collection; MCP | Structured-output transport and complete app path tested with fixtures; actual CLI reports no authenticated account here, so live inference is unverified |
| Ollama | App/CLI/MCP analysis and shared collection | Real local calls with `llama3.2:1b` and `qwen2.5:3b`; the installed Qwen pipeline/export/cache passed, but it failed the explicit-negative quality check |
| Gemini CLI 0.65.0 | Generated stdio MCP configuration; host-model inference contract | Real client connects to the server after project trust; no authenticated Gemini inference account used |
| Copilot CLI 1.0.102 | Generated local MCP configuration | Actual CLI parses/lists the server; authenticated inference and tool execution are unverified |
| Cursor, VS Code Copilot, OpenCode, Zed, Claude Desktop | Host-specific MCP configuration plus shared tools | Configuration contract tests and official documentation; no manual end-to-end client certification |
| OpenAI / Anthropic APIs | Explicit key/model modes in app, CLI, MCP | Mocked structured-output, refusal, failure, and secret-handling tests; no paid API credentials available for live calls |

MCP exposes collection plus tasks/submission, so a compatible host uses its
current model. It does not imply that its subscription can be called directly
from arbitrary software. These CLI/IDE integrations require the native host,
its account permissions, and local process access. Cloud agents and browser-only
chats cannot inherit a local session. See [agent setup](agents.md).

## Efficiency measurements

Single-run measurements on this development Mac, using the public fictional
three-profile fixture (two with sources, one without). They are not latency
SLAs or general model-quality benchmarks.

| Measurement | Before | After |
| --- | ---: | ---: |
| Codex model requests | 4 | 2 |
| Codex reported input tokens | 48,449 | 24,887 |
| End-to-end CLI smoke elapsed time | 33.724 s | 26.192 s |
| Repeat-run model requests | 0 | 0 |
| Synthetic navigation-heavy page tool payload | 76,702 characters | 1,393 characters |

The batch comparison used the same fictional inputs and produced the same
review/recommendation counts. Input tokens decreased **48.6%** and elapsed time
**22.3%** in this pair of runs. Other prompt/schema refinements and later calls
can change absolute counts. Provider-reported tokens include CLI system context;
prompt character counts are not token counts.

A separate search stress run indexed **10,000 synthetic profiles** in **35.6 ms**;
100 queries had a **2.33 ms p95** (5,000 matches per query). This measures the
existing local search index, not LLM matching latency.

The synthetic HTTP extraction benchmark reduced payload characters **98.18%**
and took about **4.6 ms of local CPU per page** over 100 iterations. This compares
the previous tool response shape with a bounded excerpt, not real vision-token
costs. A public professional homepage read took **0.2164 s cold / 0.0002 s from
cache**, transferred 11,471 bytes, and started **zero browsers**. These are local
observations, not a claim that every site supports HTTP extraction.

The 1B Ollama model initially loaded a 131,072-token context and reported about
**14 GB**. Loading the **same `llama3.2:1b` model with the adapter’s 16,384-token
context** reported **2,974,197,760 bytes (about 2.97 GB)** through `/api/ps`.
The adapter also caps output at 4,096 tokens. A real `qwen2.5:3b` run used about
3.1 GB with that context. These are model-process memory observations, not
hosted-model compute measurements or proof of matching quality.

Reproduce with the scripts in the public repository:

```sh
.venv/bin/python scripts/benchmark-research.py --url https://jamiesimon.io/
.venv/bin/python scripts/customer-smoke.py --workspace data/check --backend codex
```

`work/usage.jsonl` contains successful-response timings and available token
counts without prompts or credentials. Missing/failed-response usage is unknown,
not zero. Hosted model CPU/GPU usage is not exposed and was not measured.

## Customer installation and failure testing

The original public README command was run with a fresh HOME, isolated uv
cache/Python location, no provider keys, no copied browser session, and an empty
workspace. Installation and five-question onboarding succeeded. Selecting Claude
reproduced the forced-Codex preparation path. The fixed public branch was cloned
into a second fresh HOME and installed
**non-editably** with `.[app,mcp]`. Imports were verified to resolve to that venv's
`site-packages`, not the developer checkout. The UI process had **no Codex or
Claude executable on PATH**.

The installed checks completed:

- First-time Chromium download, opening Luma without Codex, signed-out checking
  and recovery, all five onboarding questions, Ollama server/model configuration,
  adding an event, and preparing with the chosen backend retained.
- Installed-package MCP startup, 13-tool discovery, all nine generated config
  envelopes, blocked local URLs, and actual Gemini connection / Copilot config
  parsing with the installed venv interpreter. An initial sync/async Playwright
  failure was fixed, reinstalled from GitHub, and retested. The headless MCP run
  then reached Luma's explicit sign-in/registration gate; no roster was invented.
- CLI onboarding, public fictional snapshot import, live structure/matching,
  portable HTML export, and a second run making zero model calls. The separate
  Codex run used the existing official CLI login with fictional inputs; no
  credential file or browser session was copied into the sandbox. It reviewed
  three profiles, recommended one, passed all three semantic checks, and took
  25.478 seconds / two requests in that installed run.
- Local Qwen completed the same three-profile workflow in 56.967 seconds / four
  requests and reused the cache on repeat. It recognized the positive and missing
  source cases, but returned unknown for an explicit negative. The smoke script
  exited unsuccessfully on that quality gate, despite valid output/citations.
- A separate, documented fictional demo workspace verified Save and Meet stack
  removal, Undo, reload persistence, graph node navigation, zoom, and fit.
  Attempting to load the demo into an existing workspace was correctly rejected.

**94 Python tests and 10 JavaScript tests pass**. CI covers Python 3.11 and 3.13
on Linux and installs the non-editable package outside the checkout to check its
bundled fonts, graph code, and standalone guide. The shared skill validator passes.
The sandbox is configuration/data isolation on the same macOS account, not an
independent human or a container. Live gated guest collection remains unverified.

Automated acceptance tests use synthetic guest dialogs and sources to exercise
collection → structure → matching → guide, backend selection, partial batches,
missing sources, citation rejection, retry/cache recovery, stop, concurrency,
URL restrictions, settings failures, and MCP stdio calls. These fixtures do not
establish live access to a gated Luma guest list.

## Remaining limits

- No fresh Luma test-account credentials were provided. No developer cookies,
  account files, or actual attendee datasets are copied into the customer sandbox.
  Restricted guest collection therefore cannot be certified as a complete fresh
  customer live run. A public event's registration gate was inspected; it remains
  a user action. Luma UI changes can require collector updates.
- Luma's [official API](https://docs.luma.com/reference/getting-started-with-your-api)
  needs Plus and a calendar-scoped key; it is not general attendee access to other
  organizers' guest lists. It is not silently used or replaced with a private API.
- LinkedIn's [Profile API](https://learn.microsoft.com/en-us/linkedin/shared/integrations/people/profile-api)
  is restricted. Accessible public professional sources are used; sign-in walls
  are recorded. No claim of unrestricted LinkedIn enrichment is made.
- `llama3.2:1b` produced invalid citations/targets that were rejected. Small local
  models can also return valid JSON and conservative but incorrect relevance
  judgments. Quote validation proves traceability, not logical entailment or
  truth. The customer smoke includes positive/negative/missing-source quality
  checks so this cannot be mistaken for full model certification.
- Network requests stop at request boundaries. CLI processes can be terminated
  promptly; Ollama/API calls may finish or time out after Stop. No retry storm or
  automatic provider change occurs.
- This sandbox isolates configuration/data/environment on the same OS account;
  it is not a container or security boundary. Docker was installed but its daemon
  was unavailable. Linux CI and manual macOS testing do not certify Windows GUI
  sign-in. The hosted entry point remains static and is deployed separately.
