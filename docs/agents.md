# Agent integrations

The data and matching pipeline is independent of an agent vendor. There are
two ways to use it:

- **Local app:** automatic HTTP/headless collection with Codex CLI, Claude Code,
  Ollama, or explicit OpenAI/Anthropic APIs. All five use the same evidence and
  matching contracts. Codex app-server is used for its login/catalog UI only.
- **Your agent interface:** local stdio MCP provides collection, validated
  inference tasks, and saved guides. The host's current model can perform the
  inference; another model process or subscription is not required.

## Configure MCP

Install `.[app,mcp]` in a stable virtual environment, then generate an entry:

```sh
.venv/bin/luma-review integration --agent gemini --workspace data/my-workspace
```

Merge the printed entry into the indicated configuration. Existing servers and
global settings are never overwritten by the generator. Keep the printed venv
interpreter path; resolving its symlink to a system Python loses dependencies.
A `uvx` environment works until its cache is removed; prefer a stable venv for
long-lived MCP configurations. Restart or reconnect your host after editing.

| `--agent` | Destination | Host requirement |
| --- | --- | --- |
| `codex` | Codex TOML `mcp_servers` | MCP-enabled local CLI/app |
| `claude` | `.mcp.json` | Claude Code; approve the server as required |
| `cursor` | `.cursor/mcp.json` | Cursor agent with MCP enabled |
| `copilot` | `.vscode/mcp.json` | VS Code agent mode; `servers` envelope |
| `copilot-cli` | `~/.copilot/mcp-config.json` | Copilot CLI; `mcpServers` local entry |
| `gemini` | `.gemini/settings.json` | Gemini CLI; trust the project before connecting |
| `opencode` | `opencode.json` | OpenCode local MCP; its selected model must support tools |
| `zed` | Zed `settings.json` | Native Zed agent `context_servers`; external agents have their own ACP/MCP behavior |
| `claude-desktop` | Claude Desktop MCP configuration | Local desktop client; approve tools as required |

The configuration schemas and a real SDK stdio session are tested. This is not
an end-to-end certification of nine applications. Live/model, host-connection,
and contract-only coverage are separated in the [audit](service-audit.md).
There is no automatic account linking for Cursor, Copilot, Gemini, or OpenCode
inside the standalone app. Those integrations use their native agent interfaces.

## Workflow

1. `onboarding_questions` → `save_professional_brief` if the brief is missing or
   needs changing. Save the user's answers, not a sample brief.
2. `create_event` → retain its event ID for resuming.
3. Sign in to Luma through the local app using the same workspace. **Check Luma**
   closes the sign-in window. `collect_event_profiles(limit=3)` collects a bounded
   batch with no model calls. App/MCP collection share a browser lease and must
   not run concurrently in the same workspace.
4. `research_page(url)` reads additional public professional pages by HTTP,
   with bounded excerpts and a one-hour workspace cache. For a wall, use an
   authorized host browser or record an access limitation. No cookie transfer.
5. `inference_tasks(stage="structure", limit=3)` → answer the supplied schema →
   `submit_inference`. Repeat for `matching`. Exact citations and current input
   hashes are validated; no whole-roster context is repeated per profile.
6. `event_guide` → explain useful connections, uncertainty, and coverage.
   `record_feedback` saves Skip/Save/Meet locally and sends no messages.

Alternatively, `run_event_analysis` explicitly invokes a configured CLI, local
model, or API. Use CLI `analyze` for long runs that exceed a host tool timeout.
Completed results are checkpointed, and successful cache entries are reused.

When using host browsing, `record_attendees`, `next_profile_sources`, and
`record_profile_sources` remain available. Only collect from the actual guest
list. Deduplicate by canonical Luma profile URL. A discovered LinkedIn link is
not a fetched source. An exact quote establishes traceability, not that a claim
logically follows; models and reviewers must still judge the evidence.
Shared company, event, or topic does not establish a personal relationship.

## Limits

Local stdio needs a local process and workspace. Remote/cloud agents and
browser-only chats without local MCP cannot inherit your Luma session. Restricted
LinkedIn profiles and event guest lists remain restricted; neither MCP nor
another model grants access. Sign-in, CAPTCHA, registration, purchases, and
outreach are never performed by model-controlled tools. Unknown clients can use
the standard stdio contract, but are unverified until tested in that client.

Official integration references: [Codex](https://developers.openai.com/codex/mcp/),
[Claude Code](https://code.claude.com/docs/en/mcp),
[Cursor](https://cursor.com/docs/mcp),
[VS Code](https://code.visualstudio.com/docs/agent-customization/mcp-servers),
[Copilot CLI](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-mcp-servers),
[Gemini CLI](https://geminicli.com/docs/tools/mcp-server/),
[OpenCode](https://opencode.ai/docs/mcp-servers/),
[Zed](https://zed.dev/docs/ai/mcp).
