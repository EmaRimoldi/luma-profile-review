<div align="center">

# people for Luma

### Arrive prepared. Know who to meet.

Turn a crowded San Francisco event into a personal guide to your next good conversation.

[Explore the demo](https://people-for-luma.poggiolabmit.chatgpt.site) · [Get started](#your-first-guide) · [Setup help](docs/onboarding.md) · [Contribute](#build-with-us)

[![Tests](https://github.com/EmaRimoldi/luma-profile-review/actions/workflows/test.yml/badge.svg?branch=feature%2Fpersonal-event-guide)](https://github.com/EmaRimoldi/luma-profile-review/actions/workflows/test.yml)
[MIT licensed](LICENSE) · Open source · Local app · Early alpha

<img src="docs/images/guide.jpg" alt="People for Luma: a fictional profile card with a reason to connect and Skip, Save, and Meet actions" width="960">

<sub>Fictional sample profiles. The demo uses curated assessments, with no live model calls.</sub>

</div>

Tell the app what you work on and whom you hope to meet. Connect Luma and Codex.
Your agent researches accessible professional profiles, explains the overlap,
and brings the results straight into the app.

**Your interests → your criteria → your people.** Research, progress, and results
stay in one workflow.

## Your first guide

### 1. Launch the app

You need [uv](https://docs.astral.sh/uv/),
[Codex CLI](https://developers.openai.com/codex/cli/), a ChatGPT account with
Codex access, and a Luma account that can view the event's guest list.

Run this in your terminal:

```sh
uvx --python 3.13 --from 'luma-profile-review[app] @ git+https://github.com/EmaRimoldi/luma-profile-review.git@feature/personal-event-guide' luma-review serve --port 8765
```

Open **[http://127.0.0.1:8765](http://127.0.0.1:8765/)**. Keep the terminal
running while you use the app.

> **Want a look first?** Open the [public demo](https://people-for-luma.poggiolabmit.chatgpt.site)
> and choose **Explore the fictional demo**. The complete agent workflow runs
> in the local app on your computer.

This command runs the active review branch. The product is an early alpha.

### 2. Connect once

Select **Connect Luma** on the welcome screen to open the connection panel.

| Connection | What to do |
| --- | --- |
| **Codex** | The app detects your existing ChatGPT CLI login. If needed, choose **Sign in with ChatGPT** and complete the official sign-in flow. |
| **Luma** | Choose **Connect Luma** in the panel. Sign in in the research browser it opens, return to the app, and select **Check Luma**. |

The first Luma connection installs Chromium through Playwright. Allow for a
roughly 300 MB download. Your research browser has its own saved session, so
sign in there even if Luma is already open in another browser. Keep it open
while your agent works.

Close the panel and choose **Continue**.

### 3. Give your guide a point of view

Five short answers are enough to start. A sentence for each works well.

| The app asks | Example answer |
| --- | --- |
| **What are you working on?** | “I'm building an open-source inference tool.” |
| **What catches your curiosity?** | “GPU infrastructure, LLM serving, open source.” |
| **What would make the evening worthwhile?** | “Practical feedback and a potential collaborator.” |
| **Who would you love to meet?** | “Engineers running inference systems in production.” |
| **What can you bring to the conversation?** | “Benchmarking experience and thoughtful technical feedback.” |

Add any **must-have criteria**, choose **Create profile**, and keep **Codex**
selected for the built-in researcher. Finish with **Find my people**.

Your answers become an editable professional profile and Markdown matching
criteria. Change them anytime through **Your profile** or **Edit preferences**.

### 4. Bring the room into focus

Paste a Luma event URL and choose **Add event**. In the agent panel, choose your
model and start with **10 profiles**. Select **Prepare my guide**.

Your agent will:

1. Collect the attendee list your account can access.
2. Read Luma profiles and relevant accessible LinkedIn, company, GitHub, or personal pages.
3. Build professional profiles and evaluate them against your criteria.
4. Load the reviewed cards and context graph automatically.

Watch progress in **Discover**. **Stop** retains completed work; run another
batch when you want to explore more people. No task copying or manual guide
import is needed.

### 5. Make your shortlist

Each card gives you the professional context, a reason to connect when the
evidence supports one, and a conversation starter. Open **Conversation starter
& sources** to inspect the evidence and what still needs checking.

| Action | What happens |
| --- | --- |
| **X / Skip** | Removes the person from your active stack. |
| **Save** | Keeps the person in **Saved** for another look. |
| **Meet** | Adds the person to your meeting list. No message is sent. |

Each choice reveals the next card. **Undo** reverses your last choice. Search
by name, company, or interest, or switch to the scrolling list.

In **Context**, zoom, pan, and follow shared interests, companies, and projects.
Select a node to inspect its sources or return to a person's card.

<details>
<summary><strong>See the context graph</strong></summary>

![An interactive graph of fictional people and their documented professional context](docs/images/graph.jpg)

Shared context is a conversation starter. A shared company or topic alone
does not establish that two people know each other.

</details>

## When the picture is incomplete

**Needs context** means the available professional evidence is insufficient to
confirm a match. It does not mean the person is irrelevant. Use that filter or
**All reviewed** to inspect those profiles.

**Partial list** means the collected profiles do not establish complete roster
coverage. Some events restrict their guest lists to registered attendees.
Signing in to Luma and having access to an event's full guest list are separate
requirements. Complete any required event steps yourself, then prepare another
batch.

If a sign-in or CAPTCHA interrupts research, the app shows the required action.
Complete it in the research browser and resume. The agent does not register you
for events or send invitations.

## Started on the website?

You can answer the five questions and add an event on the
[public website](https://people-for-luma.poggiolabmit.chatgpt.site). With your
local app running on port **8765**, choose **Prepare with Codex → Continue in
desktop app**, then **Use this profile & continue**.

Your profile and event come with you automatically. Research and results live
in the local app; they do not sync back to the public website.

## Your data and your model

The built-in researcher runs **Codex through its official CLI app-server**, using
your ChatGPT subscription and its normal limits. Authentication stays with Codex;
the app never reads its credential files or silently switches to a paid API.

Your workspace, Luma browser session, sources, and choices stay on your computer.
Your professional brief and the excerpts used for analysis are sent to the
selected model. **Export guide** creates an optional JSON or standalone HTML
backup containing that information.

Claude Code, Ollama, and explicit OpenAI/Anthropic API modes are available for
**analysis of already collected sources**. API modes are billed separately.
MCP and shared skills support advanced integrations with Codex, Claude Code,
Cursor, Copilot, OpenCode, and Claude Desktop. See [model backends](docs/backends.md)
and [agent integrations](docs/agents.md).

## Build with us

Help make the next introduction more useful. Try the app at an event and tell
us where the suggestions helped, which context was missing, or where setup
slowed you down. Use fictional or redacted examples in public issues.

<details>
<summary><strong>Run from source</strong></summary>

Python **3.11+** is required. The core has no Python dependencies; the `app`
extra adds Playwright, and `mcp` adds the official MCP Python SDK.

```sh
git clone --branch feature/personal-event-guide https://github.com/EmaRimoldi/luma-profile-review.git
cd luma-profile-review
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[app,mcp]"
.venv/bin/luma-review serve --workspace data/dev --port 8765
```

On Windows, use `.venv\Scripts\python.exe` and `.venv\Scripts\luma-review.exe`.
Linux may also need [Playwright system dependencies](https://playwright.dev/python/docs/browsers#install-system-dependencies).

For a local fictional demo, use a separate empty workspace:

```sh
.venv/bin/luma-review serve --workspace data/demo --demo --port 8766
```

Run the checks (Node.js is needed for JavaScript tests):

```sh
.venv/bin/python -m unittest discover -s tests -v
node --check src/luma_review/static/app.js
node --test tests/*.test.cjs
```

</details>

| Go deeper | Read |
| --- | --- |
| Setup, connections, and troubleshooting | [Complete onboarding](docs/onboarding.md) |
| Matching approach and alternatives | [Product decisions](docs/product.md) |
| What has been verified | [Validation record](docs/validation.md) |
| Source and model contracts | [Data formats](docs/data-format.md) |
| Related tools and launch scope | [Related projects](docs/related-projects.md) |

---

[MIT licensed](LICENSE). Independent project; not affiliated with Luma or LinkedIn.
Screenshots and public demo data are fictional. Bundled fonts and graph library
retain their [respective licenses](docs/third-party-assets.md).
