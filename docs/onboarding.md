# Your guide, inside the app

People for Luma runs Codex directly through the official CLI's app-server.
The app owns the task, progress, cancellation, and resulting guide. No task
copying, separate chat, MCP setup, or JSON import is needed for this flow.

## One-time launch

Install [Codex CLI](https://developers.openai.com/codex/cli/) and `uv`, then run:

```sh
uvx --python 3.13 --from 'luma-profile-review[app] @ git+https://github.com/EmaRimoldi/luma-profile-review.git@feature/personal-event-guide' luma-review serve --port 8765
```

Open **http://127.0.0.1:8765/** and leave the app running. First-time Luma
connection downloads Chromium through Playwright (roughly 300 MB including
browser support files). Linux installations may also need Playwright's system
dependencies. The Python core and CLI remain usable without this optional extra.

## Onboarding

1. **Connect Codex.** The app detects an existing ChatGPT CLI login. Otherwise,
   select **Sign in with ChatGPT**, then complete the official OpenAI browser
   flow. Credentials remain managed by Codex. The app reads account status,
   never authentication files. API-key accounts are not silently used here.
2. **Connect Luma.** Sign in in the research browser opened by the app, entering
   any code on Luma itself. Return and choose **Check Luma**. This dedicated
   browser retains its session in the local workspace. Sessions in the Codex
   in-app browser or another browser are separate; cookies are not transferred.
3. Answer five questions: your work, interests, desired outcome, people you hope
   to meet, and what you can offer. Must-have requirements are optional.
4. Paste your event URL, then select **Prepare with Codex**. Choose a model and
   a research batch of 10, 30, or 100 profiles. The model catalog is supplied by
   Codex; a successful turn confirms access, rather than the catalog alone.
5. Select **Prepare my guide**. The app collects accessible guests and professional
   sources, structures profiles, validates evidence, and evaluates your criteria.
   Progress appears in Discover; results load automatically when the run ends.
   Coverage remains explicit. **Stop** retains completed work for a later run.
6. If sign-in, a CAPTCHA, or another manual step is required, the run pauses and
   displays the required action in the app. Complete it in the research browser
   and start another batch. The agent never enters credentials, registers for
   events, purchases, or sends messages.
7. Browse profiles with **Skip / Save / Meet** and explore **Context**. Export
   JSON or standalone HTML if you want a backup; export is optional.

## Continuing from the public website

The [public site](https://people-for-luma.poggiolabmit.chatgpt.site) collects the
same profile and event. **Continue in desktop app** carries them directly to
`127.0.0.1:8765` in a URL fragment, which is not sent to the hosting server.
Review the profile in the local app and continue. No chat or manual file transfer
is involved. The public site cannot start an operating-system process itself;
the local app must already be running. The complete agent workflow stays in
that app; it does not synchronize results back to the static public origin.

## Boundaries and current validation

The built-in researcher currently uses Codex with a ChatGPT subscription and
its normal limits. Claude Code, Ollama, and explicit API modes remain available
for analysis of collected sources. MCP and shared skills remain available as
advanced integrations, independent of the default product flow.

Only focused research tools are exposed to the agent: page reading/navigation,
observed attendee and source capture, validated inference tasks, and progress.
Model-controlled shell commands are disabled. Professional source text is sent
to the selected Codex model. The managed browser profile and all actual event
data remain local and are excluded from Git and public builds.

Tests exercise a synthetic complete run through the same validated tool bridge,
stopping and source checks. A live ChatGPT-authenticated app-server turn verifies
account connection and a dynamic tool call. Full live guest collection depends
on completing Luma sign-in and the accessibility of the particular event.

## Build the public website

```sh
python scripts/build-hosted.py --out /absolute/path/to/dist
```

This builds a static public entry point and fictional sample only. It never
reads an existing local workspace. See [asset licenses](third-party-assets.md).
