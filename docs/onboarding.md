# Get ready for the room

Open [People for Luma](https://people-for-luma.poggiolabmit.chatgpt.site).
The public app starts with an empty browser workspace. **Explore the fictional
demo** is an optional preview; sample profiles are clearly labeled.

1. Choose **Open Luma**, sign in there, and return. Enter verification codes
   only on Luma. **I’m signed in** continues setup; it does not verify a token
   or give the hosted website account access. Your browser-capable agent must
   use the same authenticated browser. You can also bring an existing file.
2. Answer five questions: what you work on, what interests you, what would make
   the evening worthwhile, whom you hope to meet, and what you can offer.
   Optional must-have requirements are separate from weighted preferences.
3. Choose **My current agent**. **Set up my agent** provides MCP configuration
   for Codex, Claude Code, Cursor, Copilot, OpenCode, or Claude Desktop. Install
   `uv` first. Configure the server in your agent and enable browser tools.
   Exact configuration placement and browser support depend on that client;
   only Codex's end-to-end MCP path is currently covered by integration tests.
4. Choose **Find my people**, paste a Luma event URL, and select **Add event**.
5. Open **Collect with my agent** and **Copy event task**. Give it to your
   configured agent. It collects the accessible roster, reads professional
   sources, records evidence and limitations, and uses its current model to
   evaluate your criteria. It exports `my-event-guide.json`.
6. In the same dialog, expand **Import a reviewed guide** and select that JSON.
   Import adopts the profile and criteria that produced the guide. Existing
   profile changes invalidate earlier recommendations until a new guide is
   prepared. Source quotes stay in their original language; generated summaries
   and explanations are in English.
7. Browse **Discover**. **X / Skip** dismisses a person, **Save** sets them aside,
   and **Meet** adds them to your meeting list. Undo reverses the last choice.
   Search runs locally. Explore **Context** by dragging, zooming, selecting a
   topic, or opening its supporting sources. **View card** returns to a person.
8. **Export guide** downloads a JSON backup with your profile, choices, and
   source excerpts. Browser data is specific to this device and origin. Clearing
   site data removes it; export a backup first.

## Local companion

The hosted app has no backend account, credential store, browser-session
bridge, or inference proxy. For API keys, saved CLI logins, or Ollama, run:

```sh
uvx --python 3.13 --from 'luma-profile-review[mcp] @ git+https://github.com/EmaRimoldi/luma-profile-review.git@feature/personal-event-guide' luma-review quickstart
```

The local UI has the same discovery experience and direct model configuration.
API keys entered there stay in server memory. Export a reviewed guide for the
public browser app with:

```sh
luma-review guide --workspace data/my-workspace --event EVENT_ID --format json --out my-event-guide.json
```

Standalone HTML exports remain available with `--format html` (the default).
The public deployment contains only static assets and a fictional sample;
it never reads or publishes an existing local workspace.

## Build the hosted app

```sh
python scripts/build-hosted.py --out /absolute/path/to/public
```

Serve that directory for preview or use it as the static hosting directory.
The build uses a temporary fictional workspace, self-hosted fonts and Cytoscape,
and a browser-only adapter for the shared interface. No runtime npm dependency
or Python server is required by visitors. See [asset licenses](third-party-assets.md).
