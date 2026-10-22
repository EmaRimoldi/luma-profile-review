# Your guide, inside the app

Choose your model connection once. Collection, progress, matching, and results
stay in the local app; no chat handoff or manual JSON transfer is required.

## Launch

Install [uv](https://docs.astral.sh/uv/), then run:

```sh
uvx --python 3.13 --from 'luma-profile-review[app] @ git+https://github.com/EmaRimoldi/luma-profile-review.git@main' luma-review serve --port 8765
```

Open **http://127.0.0.1:8765/** and leave the terminal running. This is a Git
installation, not a package published on npm or PyPI. To test a review candidate,
replace `@main` with its public branch or commit SHA. A commit SHA is reproducible.
First-time Luma connection downloads Playwright Chromium. Linux may also need
[system dependencies](https://playwright.dev/python/docs/browsers#install-system-dependencies).
Use `--port 8766` if 8765 is occupied; website handoff requires 8765.

## Connect and prepare

1. **Connect Luma.** Sign in in the browser opened by the app. Enter codes only
   on Luma. Return and choose **Check Luma**. This closes the sign-in window and
   saves this workspace's session. Other browsers' sessions are separate.
2. **Answer the five questions.** Describe your work, interests, goal, ideal
   connections, and contribution. Only explicit must-haves become hard filters.
   Review or edit the resulting Markdown through **Edit preferences**.
3. **Choose your backend in Connections.**

   | Connection | Setup |
   | --- | --- |
   | Codex | Install the [official CLI](https://developers.openai.com/codex/cli/). Choose **Sign in with ChatGPT** or use an existing CLI login. |
   | Claude Code | Install the [official CLI](https://code.claude.com/docs/en/setup), run `claude auth login`, then **Check login**. No Codex installation is required. |
   | Ollama | Install [Ollama](https://ollama.com/), start `ollama serve`, install a model with `ollama pull MODEL`, and enter that model name. The app uses `127.0.0.1:11434`. |
   | OpenAI / Anthropic API | Enter an available model ID and API key. Keys remain in server memory; API charges are separate from subscriptions. |

4. **Add your event URL → Prepare my guide.** Choose a model and 10, 30, or 100
   profiles. Public professional pages use cached HTTP excerpts; dynamic pages
   and the guest dialog use headless Chromium. Model calls only structure and
   match collected evidence. No model controls shell commands or website actions.
5. **Browse → Skip / Save / Meet.** Open sources and conversation starters,
   search, and explore Context. **Meet** records a plan; it sends no message.
   Export JSON or standalone HTML for a portable backup.

The Codex catalog and a configured API key are not proof of model entitlement.
A successful request confirms access. Claude CLI authentication, billing, and
organization policies remain controlled by Claude. See [backends](backends.md).

## Recover without starting over

| What happened | What to do |
| --- | --- |
| Sign-in or event registration required | Complete the required steps yourself on Luma, **Check Luma**, then prepare again. Signing in alone does not unlock a registered-attendee list. |
| Partial list | Review the stated coverage. The collector reads only the guest dialog, with a 30-scroll / 1,000-profile bound. Missing rows are never presented as complete coverage. |
| Login wall or inaccessible profile | The attempt is recorded without inventing facts. **Needs context** means insufficient evidence. It is not a negative judgment. |
| Wrong model, expired CLI login, quota, or invalid citation | Check the selected connection and run again. Valid results are cached; failed profiles remain visible and can be retried. No paid fallback is attempted. |
| Stop | CLI model processes are terminated. HTTP and Ollama/API calls stop at the next request boundary (up to their timeout). Completed source writes and assessments remain saved. |
| Research browser already in use | Finish the other app/MCP run, or choose **Check Luma** to close its sign-in window. A workspace lease prevents two processes from opening the same browser profile. |
| Corrupt saved JSON | Restore an exported backup or launch with `--workspace data/new-workspace`. The app reports the damaged filename without silently replacing it. |
| App restarted | CLI login and the Luma session persist. Re-enter session-only API keys; environment keys still apply. Choose the same `--workspace` to resume. |

Preparing another batch prioritizes unfinished analysis and then uncollected
profiles. **Refresh analysis** re-evaluates collected evidence after a backend
change. Editing your brief or criteria invalidates outdated recommendations.

## Start from the public website

The [public site](https://people-for-luma.poggiolabmit.chatgpt.site) can collect
your profile and event and open **Continue in desktop app**. It transfers them
in a URL fragment to an already-running app on `127.0.0.1:8765`; review and accept
them locally. The site cannot launch a local process or run your subscriptions.
Results do not synchronize back to the static site. Previously deployed site
copy may still say **Prepare with Codex**; the installed app selects the backend.

## Use your existing agent interface

[Agent integrations](agents.md) covers nine MCP configurations and using the
host's current model. The MCP extra is optional for the standalone app. Local
stdio clients need to run on the machine holding the workspace and Luma session;
a cloud agent cannot automatically use your local browser.

## Repeat the public customer check

From a public repository checkout, install a non-editable distribution and run:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install '.[app,mcp]'
.venv/bin/python scripts/customer-smoke.py --workspace data/customer-check --backend codex
# Or: --backend ollama --model YOUR_INSTALLED_MODEL
```

This uses only the fictional files in `examples/`: onboarding, import, live
structure/matching, export, and a second run that must make zero model requests.
It never copies a developer workspace or credentials. A model must pass evidence
validation; a small model's failure is reported, not replaced with a fixture.
See the [audit record](service-audit.md) for tested configurations and limits.

## Build the public website

```sh
python scripts/build-hosted.py --out /absolute/path/to/dist
```

The build uses fictional data only and does not deploy automatically.
