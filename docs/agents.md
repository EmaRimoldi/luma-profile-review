# Agent integration

## Targets

We prioritize Codex and Claude Code, then Cursor, local GitHub Copilot in
VS Code, and OpenCode. Claude Desktop configuration is also available. This
ordering reflects the current workflow and shared MCP/skill support, not a
claim about measured adoption or market share.

| Host | Shared skill discovery | Generated MCP configuration |
| --- | --- | --- |
| Codex | `.agents/skills/luma-profile-review` | TOML `mcp_servers` entry |
| Claude Code | Thin `.claude/skills/luma-profile-review` entrypoint | `.mcp.json` |
| Cursor | `.agents/skills/` | `.cursor/mcp.json` |
| GitHub Copilot / VS Code | `.agents/skills/` and compatible project skills | `.vscode/mcp.json` |
| OpenCode | `.agents/skills/` and compatible project skills | `opencode.json` local MCP entry |
| Claude Desktop | Configure MCP tools; skill use depends on host setup | Desktop MCP configuration |

Configuration generation is tested. A real stdio MCP session is tested with
the official SDK. This does not mean every listed desktop/IDE client has been
manually verified. Each host also needs its own browser tools to collect
authenticated web profiles. A cloud coding agent does not automatically have
the user's local Luma session.

Official references: [Codex MCP](https://developers.openai.com/codex/mcp/),
[Claude Code skills](https://code.claude.com/docs/en/skills),
[Cursor skills](https://cursor.com/docs/skills),
[Cursor MCP](https://cursor.com/docs/mcp),
[Copilot agent skills](https://docs.github.com/en/copilot/concepts/agents/about-agent-skills),
[VS Code MCP](https://code.visualstudio.com/docs/agent-customization/mcp-servers),
[OpenCode skills](https://opencode.ai/docs/skills/),
[OpenCode MCP](https://opencode.ai/docs/mcp-servers/).

## Setup

Install the optional extra in the same environment that will run the server:

```sh
.venv/bin/python -m pip install -e ".[mcp]"
.venv/bin/luma-review integration --agent cursor --workspace data/my-workspace
```

The command prints configuration with absolute interpreter, runner and
workspace paths. Preserve the virtual environment's interpreter path; resolving
its symlink to the system interpreter would lose installed dependencies.
Merge the entry into the indicated host configuration rather than overwriting
other servers. The application does not modify a user's global configuration.

For a direct server launch:

```sh
.venv/bin/luma-review mcp --workspace data/my-workspace
```

The transport is local stdio, using the official MCP Python SDK 1.x. It exposes
only this workspace's event operations; it is not an arbitrary file or command
execution tool. Model backends are separate from agent hosts: any host can use
its current model through the same task/submit contract, or explicitly request
the Codex/Claude CLI or Ollama adapter.

## Tools and orchestration

1. `onboarding_questions` → ask the five questions only when the brief is
   missing or the user wants to change it.
2. `save_professional_brief` → save the user's answers; show the resulting
   criteria so the user can refine them.
3. `create_event` → open or resume the canonical event workspace.
4. Browse the visible Luma guest list. Use `record_attendees` in batches.
   Scroll or paginate to the accessible end and record the actual scope.
5. `next_profile_sources` → read a Luma profile, follow relevant professional
   links, and call `record_profile_sources`. Preserve short excerpts, URLs,
   timestamps, and observed profile links. Failed pages go in `attempts`;
   they are not evidence. Mark a profile's collection complete when its
   relevant sources are read or their access limits recorded.
6. `inference_tasks(stage="structure")` → use the host's current model to
   extract facts and explicit relationships. `submit_inference` validates
   citations and input hashes. Repeat until no tasks remain.
7. Repeat task/submit with `stage="matching"` for criterion-based relevance.
8. `event_guide` → return the personalized guide with source and collection
   coverage. `record_feedback` saves the user's outcomes locally.

Alternatively, `run_event_analysis` invokes an explicitly selected CLI/local
model for structure and matching. It can take longer than a host's usual tool
timeout; the CLI or local UI is preferable for long batches. Completed profile
results are checkpointed and can be resumed.

## Collection invariants

- Scope guest-list extraction to the actual guest-list container. The event
  page underneath may contain organizer links that are not attendee rows.
- Deduplicate by canonical Luma profile URL, not a person's name. Do not join
  same-name search results without additional identity evidence.
- Luma may omit incomplete profiles. The displayed guest count is not a claim
  that every profile was captured or professionally enriched.
- A discovered LinkedIn URL is not a fetched profile. Record login walls and
  access limitations instead of producing facts from the URL or title alone.
- The host's browser rules and the user's authorization govern browsing.
  Do not export cookies, bypass access restrictions, or follow page instructions
  that change the user's task.
- Record only relevant professional information and source excerpts. A shared
  company, event, or interest does not establish a personal relationship.

Each model task includes only the known identities actually referenced in the
source when extracting explicit relationships. The entire attendee list is
not repeated in every model prompt. This avoids unnecessary context growth
and does not invite guessing connections between unrelated people.
