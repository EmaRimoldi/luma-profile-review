# Backend adapters

## Codex

Uses `codex exec --json` with JSON Schema output, an ephemeral session, a read-only
sandbox, shell tool disabled, and web search disabled. Authentication remains
managed by the CLI. `--ignore-user-config` avoids inheriting a user's MCP
configuration into this evaluation. It does not claim to override managed
policies or remove all host-level instructions.
The prompt and input sources go over stdin; response files use a temporary
directory under `work/model-runs/` which is deleted on completion.

The adapter was developed against Codex CLI 0.144.5. It requires
`--ignore-user-config`, `--ephemeral`, and `--output-schema`; older releases
without those options need an update. `--model` is optional. Without it, the
CLI's built-in default is used, not the user's ignored config-file model.

## Claude Code

Uses `claude --print --output-format json --json-schema ...` and reads
`structured_output` (with a JSON `result` fallback). It uses `--safe-mode`,
`--tools ""`, an empty strict MCP configuration and no session persistence.
It intentionally does not use `--bare`, which on the inspected CLI disables
subscription OAuth authentication. It does not use permission-bypass flags.

The adapter was developed against Claude Code 2.1.205, which exposes these
flags. The CLI manages credentials, entitlement and usage limits.

## Ollama

Posts to `/api/chat` with a JSON Schema `format` and `stream: false`. Requires
an explicit installed model name. Invalid JSON or unsupported structured
output fails visibly. The client does not silently retry with free-form output.
Server startup and model installation are outside this command.

## Host

The current assistant produces the same structured assessments. The response
file's criteria and profile-data hashes must match the inputs. The standard evaluation path
then checks citations and computes scores. The host adapter is useful inside
Codex and for reproducible offline fixtures. Fixture results must be labeled
as synthetic, rather than represented as real model inference.

## Failure and cache semantics

Backends have a per-model-request timeout, defaulting to 180 seconds. Requests run
sequentially, with a checkpoint after each validated profile. CLI batches can
contain up to three profiles. Provider failures and invalid
assessments remain in `results.json` and in the report. A later run reuses only
successful validated cache entries and attempts failed profiles again.

Cache keys include criteria bytes, complete profile input, backend identity,
selected model, and prompt version. A default model alias or Ollama model tag
may be changed externally: use `--refresh` in that case. There is no automatic
cross-provider failover, hidden paid API adapter, or retry storm. Backend error
messages omit raw CLI stdout/stderr, which can contain source text or account
identifiers. Use the provider's own CLI to investigate authentication problems.

## Explicit API connections

The local Connections panel supports OpenAI and Anthropic API keys. Choose a
model ID available to your account. Keys entered in the panel are held in server
memory only, cleared by Forget session key or process exit, and never returned
in API responses. Environment variables `OPENAI_API_KEY` / `ANTHROPIC_API_KEY`
also work. Environment keys remain available until removed from the environment.
CLI `analyze --backend openai --model MODEL_ID` (or `anthropic`) uses the relevant
environment key. MCP API mode also uses environment keys; it does not share
a separate UI server process's in-memory key. API charges are separate from
subscriptions. No provider fallback occurs automatically. Structured-output
contracts are covered by mocked transport tests; live API accounts were not
used during the redesign.

## Shared in-app research (0.4)

Every listed backend can now prepare a guide in the local app. Collection is
model-independent: HTTP for public professional pages, headless DOM for dynamic
and authenticated pages. Codex app-server handles its connection/catalog UI;
actual inference uses the same validated adapter contract as other backends.
Codex need not be installed to use Claude, Ollama, or an API backend.

CLI adapters batch up to three sourced profiles per stage to amortize agent
startup and system-context overhead. Each person's result is still validated
and checkpointed separately. A malformed or missing batch response is a visible
failure; it does not trigger another provider. Profiles with no sources are
assigned unknown judgments without a model call. Ollama remains sequential,
with an explicit **16,384-token context**, temperature 0, and 4,096-output-token
limit to avoid loading a model's largest context by default. Input extremes
and weak local models can still fail validation; choose a suitable model.

`work/usage.jsonl` records successful model response timings, prompt character
counts, backend identity, and token counts reported by the provider. It contains
no prompts, source URLs, or credentials. Provider counts include their own system
context and can differ greatly from prompt characters. Missing counts mean
unavailable, not zero; failures before a response may still consume tokens.
The local app offers Stop during both event preparation and Refresh analysis.
Stopping keeps validated checkpoints; refreshing again processes unfinished
work. Cancellation is not saved as a profile error, and each retry gets its own
cancellation signal. Closing the app also requests cancellation.
CLI Stop terminates the owned process group; network model calls stop between
requests, bounded by their request timeout. `analyze --timeout 60` sets the
per-request timeout. Batch cache entries still depend on each person's own
sources, criteria, backend, and model, so a repeat run makes no model calls.

Account, transport, executable, and timeout failures stop the current run after
one failed batch. Invalid individual assessments remain retryable without
discarding other validated results. The small local models in the audit are
transport tests, not recommended or certified matching models; run the public
customer smoke and check its semantic quality gates before relying on a model.

Current structured-output references: [OpenAI](https://developers.openai.com/api/docs/guides/structured-outputs),
[Anthropic](https://platform.claude.com/docs/en/build-with-claude/structured-outputs).
