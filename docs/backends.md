# Backend adapters

## Codex

Uses `codex exec` with JSON Schema output, an ephemeral session, a read-only
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

Backends have a per-person timeout, defaulting to 180 seconds. Requests run
sequentially, with a checkpoint after each profile. Provider failures and invalid
assessments remain in `results.json` and in the report. A later run reuses only
successful validated cache entries and attempts failed profiles again.

Cache keys include criteria bytes, complete profile input, backend identity,
selected model, and prompt version. A default model alias or Ollama model tag
may be changed externally: use `--refresh` in that case. There is no automatic
cross-provider failover, hidden paid API adapter, or retry storm. Backend error
messages omit raw CLI stdout/stderr, which can contain source text or account
identifiers. Use the provider's own CLI to investigate authentication problems.
