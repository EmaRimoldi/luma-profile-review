# Discovery redesign · October 2026

The core task is deciding whom to approach in a crowded room. Discovery now
shows one concise card, with an optional scrolling list. Save, Meet, and Not
relevant immediately remove a person from Discover. Feedback is queued to the
local workspace; failed writes roll back. Undo restores the preceding choice.
Meet means a private intention, distinct from the existing `met` status. No
contact or invitation is sent. Saved and Meet collections remain available.

## Visual direction

The reference is Rey Rad's **Ghost Cube Attractor**, a monochrome particle
sculpture, rather than a painted impressionist scene:
[reference](https://www.pinterest.com/pin/939845016016890914/).
Luma's light lavender header wash, small navigation, quiet typography, and
rounded white surfaces inform the structure. An original, deterministic canvas
particle cube adds texture at the edge of the experience. It is drawn locally,
without an animation loop, image generation, copied artwork, font downloads,
or a UI dependency. The product is independent of Luma.

Cards show an observed photo when available, otherwise initials; role/context,
a short professional summary, topics, one reason, and published contact links.
Unknown contact details are visibly unavailable. Supporting excerpts and a
conversation opener stay behind a disclosure. Photos and contact metadata
never become model evidence and do not invalidate existing assessments.

## Setup and Luma access

1. Open Luma sign-in in the same browser the agent can operate.
2. Answer five questions: work, interests, desired outcome, people to meet,
   and what the user can offer. Only explicit must-haves become hard filters.
3. Choose the current agent, a supported official CLI login, Ollama, or an
   explicitly selected API provider. Setup can resume at this connection step.
4. Add an event and copy its task into the connected browser-capable agent,
   or import a collected snapshot.

Luma supports an email verification code **on its own sign-in page**:
[official sign-in help](https://help.luma.com/p/signing-in).
The public API requires Luma Plus and calendar-scoped keys:
[API requirements](https://docs.luma.com/reference/getting-started-with-your-api).
The public docs reviewed do not document an attendee OAuth/device-code flow
that grants access to the events a user attends. OAuth tokens are mentioned
in rate limits, so this is not a claim that Luma has no OAuth anywhere.
We do not fabricate an OAuth connection or collect the code in our own UI.
`browser_handoff` records a user-selected workflow, not verified authentication.
The agent must verify access during collection. This remains an agent-assisted
workflow, not unattended account synchronization.

The connection UI can check official CLI login / local Ollama availability.
API keys stay only in server memory until restart; environment credentials
also work. The browser receives only presence flags. They never enter workspace
settings, guides, logs, exports, or model provenance. API mode requires an
explicit model and is billed separately from a subscription. Provider adapters
use fixed HTTPS endpoints, disable redirects, sanitize transport errors, and
preserve exact-quote validation. See the official
[OpenAI structured-output documentation](https://developers.openai.com/api/docs/guides/structured-outputs)
and [Anthropic structured-output documentation](https://platform.claude.com/docs/en/build-with-claude/structured-outputs).
Provider contracts are tested with mocked HTTP; no live billable API call was
made for this redesign. Official CLIs continue to manage subscription access.

## Distribution decision

| Option | Assessment |
| --- | --- |
| Python core + uvx | Chosen: one command, isolated package, no manual virtualenv; plain JS/CSS requires no build |
| npm wrapper around Python | Adds Node while still requiring Python; little benefit for this implementation |
| Rewrite everything in Node | Could enable a true npm-only package, but adds migration work with no demonstrated product benefit |
| Hosted app / PWA | Does not inherit a user's local browser or CLI credentials; requires a different connection architecture |
| Desktop wrapper | Could package browser access later, with a larger distribution and maintenance surface |

[uvx](https://docs.astral.sh/uv/guides/tools/) provides isolated tool execution
and supports Git sources. Launch the current version from `main`:

```sh
uvx --python 3.13 --from 'luma-profile-review[mcp] @ git+https://github.com/EmaRimoldi/luma-profile-review.git@main' luma-review serve --workspace ~/.luma-profile-review
```

This requires uv; the first run may fetch Python and build the package.
The command includes the optional MCP integration. Omit `[mcp]` for the
dependency-free core. No PyPI or npm publication is claimed. A checkout also runs directly with
`python3 run.py serve`, using Python 3.11+. MCP requires the optional extra.

## Matching and search decision

The system separates **finding text** from **evaluating professional relevance**.

| Approach | Where it fits |
| --- | --- |
| Literal substring scan | Simple baseline; repeatedly serializing profiles is unnecessary work and has weak ranking |
| Inverted index + BM25 | Chosen for instant browser search: useful keyword ranking, no model request, dependency, or server |
| Cached evidence assessments | Chosen for the default personalized order; preserves hard conditions, unknowns, reasons, and sources |
| Embedding retrieval | A useful candidate for paraphrases/multilingual recall; needs an embedding model and separate index, and should earn its place on labeled examples |
| Hybrid retrieval + RRF | Useful if lexical and embedding retrieval both contribute; unnecessary with one retrieval system |
| Cross-encoder reranking | Potentially improves difficult relevance decisions; adds inference and needs evaluation before adoption |

BM25's term-frequency saturation and document-length normalization are described
in [SQLite's BM25 documentation](https://sqlite.org/fts5.html#the_bm25_function).
This implementation uses an in-memory JS inverted index, not a SQLite service.
Names and structured facts get extra term weight. Names normalize Unicode
accents; the final term supports prefix completion. Multiple query terms must
all match. An empty query preserves the existing evidence order. Keyword
matches do not count as professional evidence or silently revise assessments.
RRF combines ranked result lists, as explained in
[Microsoft's documentation](https://learn.microsoft.com/en-us/azure/search/hybrid-search-ranking).
Retrieve/rerank architectures are described by
[Sentence Transformers](https://www.sbert.net/examples/sentence_transformer/applications/retrieve_rerank/README.html).
These alternatives are evaluated architecturally here, not claimed as measured
quality improvements.

Only the current card (or 20 list cards) is rendered. Search indexes are built
once per guide refresh. No cloud request occurs on search or a card decision.
Server guide caching is invalidated by changes to source files, criteria,
brief, structures, assessments, feedback, or errors, including external MCP
writes. Background model progress does not interrupt the browsing UI.
Initial collection and model analysis still take time; existing valid results
are reused, and analysis runs in the background. None of this establishes
recommendation usefulness: the pilot still needs user relevance labels.

## Reproducible verification

```sh
python -m unittest discover -s tests -v
node --test tests/search.test.cjs
node scripts/benchmark-search.cjs
uvx --from . luma-review --version
uv build --wheel --out-dir work/redesign-dist
```

On the development Mac, synthetic index-only search measured approximately
0.3 ms p95 for 1,000 profiles and 1.8 ms p95 for 10,000, with index construction
around 7 / 52 ms respectively. These are local microbenchmarks, exclude DOM,
network, and LLM work, and are not performance guarantees. The Python wheel
built successfully at about 66 KiB, with no core runtime dependencies.

Browser verification uses a separate fictional workspace for onboarding and
feedback; the real pilot's decisions and brief are preserved. API adapters
have transport-contract tests, not live account verification. Touch hardware
and mobile browser gestures require a real-device check beyond desktop
responsive preview.
