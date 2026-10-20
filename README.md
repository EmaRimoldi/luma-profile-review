# Luma Profile Review

Review event participants against criteria you write in Markdown. Get a
shortlist with per-criterion evidence, missing information, and source links.
MIT licensed. Python 3.11+. No runtime Python dependencies.

**The project is a CLI/library plus a bundled Codex skill.** Codex handles
authenticated browsing; the application handles model adapters, validation,
resumable evaluation, scoring, and reports. It runs locally and does not need
a hosted service.

## Why this structure?

| Option | Strength | Limitation |
| --- | --- | --- |
| Skill alone | Fast integration with Codex browsing | Provider adapters, cache behavior and scoring are difficult to test and reuse |
| Standalone application alone | Portable and testable | Needs its own browser authentication and orchestration integration |
| Repository plus skill — chosen | Reusable engine with Codex as an orchestrator | Browser collection still requires a compatible Codex browser tool |

The engine does not depend on Codex to evaluate imported datasets. The skill
uses Codex's existing browser capabilities to collect the accessible guest
list and professional profile excerpts. The evaluator does not crawl pages:
it only receives collected sources. This makes source acquisition and model
selection independent.

## Quick start

Run directly from a checkout:

```sh
python3 run.py doctor
python3 run.py evaluate --criteria examples/criteria.md --profiles examples/profiles.json --backend codex --output data/demo-codex
```

Or install into a virtual environment:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/luma-review --help
```

Change only the backend flag to use Claude:

```sh
python3 run.py evaluate --criteria examples/criteria.md --profiles examples/profiles.json --backend claude --output data/demo-claude
```

Use an already installed open-weight model through a running Ollama server:

```sh
python3 run.py evaluate --criteria examples/criteria.md --profiles examples/profiles.json --backend ollama --model YOUR_INSTALLED_MODEL --output data/demo-local
```

The Ollama adapter sends source excerpts to `http://127.0.0.1:11434` by default.
`--base-url` can select another Ollama server. No model is downloaded or server
started automatically. Model choice and local hardware affect quality and speed.

To try the entire pipeline without making a model request, use the supplied
synthetic responses. This tests the pipeline, not model quality:

```sh
python3 run.py evaluate --criteria examples/criteria.md --profiles examples/profiles.json --backend host --responses examples/responses.json --output data/demo-offline
```

Each run writes `results.json` and `report.md`. Failures remain visible in the
report, and the command exits nonzero when a profile fails. Successful results
are cached by criteria, profile sources, backend and selected model. Repeating
the same command resumes from validated cache entries. Use `--refresh` after
changing a CLI's default model or updating an Ollama tag in place.

## Subscription authentication

| Backend | Setup | Authentication used |
| --- | --- | --- |
| `codex` | Install the official Codex CLI; run `codex login` | Saved Codex CLI login, including ChatGPT subscription access |
| `claude` | Install Claude Code; run `claude auth login` | Claude Code login, including eligible Claude subscription access |
| `ollama` | Start Ollama and install a model | Local model server; no subscription required |
| `host` | Use the bundled skill to author a response file | The current assistant session; no nested inference process |

Subscription access is through the official CLIs, not extracted OAuth tokens
or a replacement API endpoint. Requests consume the selected account's normal
allowance. Provider policies, model entitlements and limits still apply. Existing
environment credentials can affect CLI authentication; `doctor` reports the
method without exposing account identifiers. The tool never reads auth files
or automatically falls back to another provider or API billing.

The Codex adapter ignores user config for its isolated evaluation subprocess,
while retaining CLI authentication; use `--model` to select a model explicitly.
The Claude adapter uses safe mode and disables built-in and configured MCP
tools. The installed CLIs must support the flags in [backend documentation](docs/backends.md).

References: [Codex non-interactive execution](https://developers.openai.com/codex/noninteractive/),
[Codex authentication](https://developers.openai.com/codex/auth/),
[Claude programmatic execution](https://code.claude.com/docs/en/headless),
[Claude authentication](https://code.claude.com/docs/en/authentication),
[Ollama structured chat](https://docs.ollama.com/api/chat).

## Use with Codex

Open this repository as a Codex project. The skill lives at
[.agents/skills/luma-profile-review/SKILL.md](.agents/skills/luma-profile-review/SKILL.md).
It can also be used by giving Codex that file explicitly. For example:

> Use the luma-profile-review skill in this repository. Read my criteria.md,
> collect accessible profiles from this Luma event, and evaluate the first
> 10 profiles using the host backend. Show evidence and missing information.

The skill collects sources using the browser tools available in the current
host. A bare CLI session without browser tools cannot automatically collect
authenticated Luma profiles; provide a dataset or use a browser-enabled Codex
session. This release does not ship an unattended scraper, access hidden lists,
or obtain attendee email addresses.

For `host`, export self-contained tasks, let the current assistant answer them,
then validate and score those answers:

```sh
python3 run.py export-prompts --criteria criteria.md --profiles data/profiles.json --out data/tasks.json
python3 run.py evaluate --criteria criteria.md --profiles data/profiles.json --backend host --responses data/responses.json --output data/run
```

The response file has `criteria_sha256` and `profiles_sha256` from `tasks.json`, and a `responses`
object keyed by canonical profile URL. See [the data contract](docs/data-format.md).

## Your own criteria and data

```sh
cp criteria.example.md criteria.md
python3 run.py criteria --criteria criteria.md
```

The initial draft is deliberately rejected until you add actual criteria and
set `Status: active`. Add `must` conditions and weighted `prefer` conditions.
Example rows are in [examples/criteria.md](examples/criteria.md); they are demo
criteria, not a recommendation about whom you should meet.

Collection records, local criteria, configuration, caches and reports belong
in ignored `data/` and `work/` folders. Public examples use fictional people
and reserved example.org sources. No real participant data belongs in examples
or commits. The live pilot data, if present in a local checkout, is ignored.

Copy `luma-review.example.toml` to `luma-review.toml` for optional defaults.
Command flags override TOML. `--config PATH` selects another file. Use `--limit`
to evaluate a subset. The report states both sample size and collection scope.

## Evaluation behavior

- Missing evidence produces `unknown`, not `no`.
- Confirmed failures of required criteria produce `Outside criteria`.
- Incomplete required criteria produce `Needs verification`.
- Preferences produce confirmed points and separate uncertain points.
- Every conclusive verdict needs a quote present in a cited source excerpt.
- Coverage measures available evidence, not probability of correctness.

Exact-quote validation establishes traceability. It does not establish source
truth or prove that a model interpreted a quote correctly. Review important
matches and mismatches. Ranking can reflect how much information was available.

## Development

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Tests use synthetic data and mocked CLI/HTTP responses. They do not require
subscriptions, start browsers, or download models. CI runs them on Python 3.11
and 3.13. Backend smoke-test results for this checkout are in
[docs/validation.md](docs/validation.md).

To add a model provider, implement `generate(prompt, schema, profile_url)` and
an `identity` property, then route it in `make_backend`. Providers return the
same schema; the evaluator owns validation and scoring. To add a collector,
emit the existing versioned profile format. No model-specific data schema is
required.
