from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
import sys
import tomllib
from dataclasses import asdict
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from . import __version__
from .core import ReviewError, fingerprint, load_profiles, make_prompt, parse_criteria, public_url, response_schema
from .pipeline import evaluate, render_report, write_json
from .providers import make_backend


def doctor(name: str, base_url: str) -> dict:
    if name == "host":
        return {"backend": "host", "available": True, "note": "Uses responses from the current assistant"}
    if name == "ollama":
        try:
            with urlopen(public_url(base_url).rstrip("/") + "/api/tags", timeout=3) as response:
                value = json.load(response)
            return {"backend": name, "available": True, "models": [m["name"] for m in value.get("models", [])]}
        except (URLError, TimeoutError, OSError, ValueError):
            return {"backend": name, "available": False, "note": "Start Ollama and install a model"}
    if name in {'openai', 'anthropic'}:
        return {'backend': name, 'available': bool(os.environ.get(name.upper() + '_API_KEY')),
                'note': 'Checks key presence only; model access is verified by an actual request.'}
    if name not in {'codex', 'claude'}:
        return {'backend': name, 'available': False, 'note': 'Unsupported backend'}
    if not shutil.which(name):
        return {"backend": name, "available": False, "note": f"Install {name} and sign in"}
    args = [name, "login", "status"] if name == "codex" else [name, "auth", "status"]
    try:
        result = subprocess.run(args, text=True, capture_output=True, timeout=10)
        info = {"backend": name, "available": result.returncode == 0}
        if name == "claude" and result.returncode == 0:
            status = json.loads(result.stdout)
            info["available"] = bool(status.get("loggedIn"))
            info["auth_method"] = status.get("authMethod", "unknown")
        elif name == "codex" and result.returncode == 0:
            info["auth_method"] = "ChatGPT" if "chatgpt" in (result.stdout + result.stderr).lower() else "CLI-managed"
        return info
    except (subprocess.TimeoutExpired, OSError, ValueError):
        return {"backend": name, "available": False, "note": "Could not confirm CLI authentication"}


def parser():
    p = argparse.ArgumentParser(prog="luma-review", description="Review networking profiles against Markdown criteria")
    p.add_argument("--version", action="version", version=__version__)
    p.add_argument("--config", type=Path, help="Optional TOML file; defaults to ./luma-review.toml when present")
    commands = p.add_subparsers(dest="command", required=True)
    from .product_cli import add_commands
    add_commands(commands)
    for name in ["criteria", "export-prompts", "evaluate", "report"]:
        command = commands.add_parser(name)
        command.add_argument("--criteria", type=Path, default=Path("criteria.md"))
        if name in {"export-prompts", "evaluate"}:
            command.add_argument("--profiles", type=Path, required=True)
            command.add_argument("--limit", type=int)
        if name in {"export-prompts", "report"}:
            command.add_argument("--out", type=Path, required=True)
        if name == "report":
            command.add_argument("--results", type=Path, required=True)
        if name == "evaluate":
            command.add_argument("--backend", choices=["codex", "claude", "ollama", "openai", "anthropic", "host"])
            command.add_argument("--model")
            command.add_argument("--base-url")
            command.add_argument("--timeout", type=float)
            command.add_argument("--responses", type=Path)
            command.add_argument("--output", type=Path, default=Path("data/run"))
            command.add_argument("--cache", type=Path, default=Path("work/cache"))
            command.add_argument("--work-dir", type=Path, default=Path("work/model-runs"))
            command.add_argument("--refresh", action="store_true")
    check = commands.add_parser("doctor")
    check.add_argument("--backend", choices=["codex", "claude", "ollama", "openai", "anthropic", "host", "all"], default="all")
    check.add_argument("--base-url", default="http://127.0.0.1:11434")
    return p


def safe_output(output: Path, inputs: list[Path]):
    if output.resolve() in {p.resolve() for p in inputs}:
        raise ReviewError("Output would overwrite an input file; choose a different output")


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    try:
        config_path = args.config or Path("luma-review.toml")
        if args.config or config_path.exists():
            with config_path.open("rb") as stream:
                config = tomllib.load(stream).get("inference", {})
            if set(config) - {"backend", "model", "base_url", "timeout"}:
                raise ReviewError("Unknown inference configuration key")
        else:
            config = {}
        from .product_cli import PRODUCT_COMMANDS, run
        if args.command in PRODUCT_COMMANDS:
            return run(args, config)
        if args.command == "doctor":
            names = ["codex", "claude", "ollama", "openai", "anthropic", "host"] if args.backend == "all" else [args.backend]
            statuses = [doctor(n, args.base_url) for n in names]
            print(json.dumps(statuses, indent=2))
            return 0 if any(s["available"] and (s['backend'] != 'host' or args.backend == 'host') for s in statuses) else 1
        criteria = parse_criteria(args.criteria.read_text(encoding="utf-8"))
        if args.command == "criteria":
            print(json.dumps({"sha256": criteria.sha256, "criteria": [asdict(c) for c in criteria.rules]}, indent=2))
            return 0
        if args.command == "report":
            safe_output(args.out, [args.criteria, args.results])
            run = json.loads(args.results.read_text())
            for person in run.get("people", []):
                if person.get("status") not in {"reviewed", "failed", "pending"}:
                    raise ReviewError("Unknown evaluation status")
            # Validate source records again when consuming an existing run.
            loadable = {"version": 1, "event": run["event"], "people": [p["profile"] for p in run["people"]]}
            # No new file is needed: load_profiles' in-memory counterpart is shared here.
            from .core import validate_profiles
            validate_profiles(loadable)
            report = render_report(run, criteria)
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(report, encoding="utf-8")
            print(f"Report: {args.out}")
            return 0
        dataset = load_profiles(args.profiles)
        if args.limit is not None and args.limit < 1:
            raise ReviewError("limit must be positive")
        if args.command == "export-prompts":
            safe_output(args.out, [args.criteria, args.profiles])
            people = dataset["people"][:args.limit] if args.limit else dataset["people"]
            write_json(args.out, {"version": 1, "criteria_sha256": criteria.sha256,
                       "profiles_sha256": fingerprint(dataset),
                       "schema": response_schema(criteria), "requests": [
                           {"profile_url": p["profile_url"], "prompt": make_prompt(criteria, p)} for p in people]})
            print(f"Exported {len(people)} prompts: {args.out}")
            return 0
        name = args.backend or config.get("backend", "codex")
        model = args.model or config.get("model")
        if model is not None and (not isinstance(model, str) or not model.strip() or model.startswith("-")):
            raise ReviewError("Invalid model name")
        timeout = args.timeout if args.timeout is not None else config.get("timeout", 180)
        if type(timeout) not in {int, float} or not math.isfinite(timeout) or timeout <= 0:
            raise ReviewError("timeout must be a positive finite number")
        responses = None
        inputs = [args.criteria, args.profiles] + ([args.responses] if args.responses else [])
        for target in [args.output / "report.md", args.output / "results.json"]:
            safe_output(target, inputs)
        if args.responses:
            if name != "host":
                raise ReviewError("--responses is only supported by the host backend")
            envelope = json.loads(args.responses.read_text())
            if envelope.get("criteria_sha256") != criteria.sha256:
                raise ReviewError("Host responses use different criteria; regenerate them")
            if envelope.get("profiles_sha256") != fingerprint(dataset):
                raise ReviewError("Host responses use different profile sources; regenerate them")
            responses = envelope.get("responses")
        backend = make_backend(name, model, work_dir=args.work_dir, timeout=timeout,
                               base_url=args.base_url or config.get("base_url", "http://127.0.0.1:11434"),
                               responses=responses)
        result = evaluate(dataset, criteria, backend, args.output, cache=args.cache,
                          refresh=args.refresh, limit=args.limit,
                          progress=lambda message: print(message, file=sys.stderr, flush=True))
        failed = sum(p["status"] == "failed" for p in result["people"])
        print(f"Results: {args.output / 'results.json'}\nReport: {args.output / 'report.md'}\nFailed: {failed}")
        return 1 if failed else 0
    except (ReviewError, OSError, json.JSONDecodeError, tomllib.TOMLDecodeError, KeyError, TypeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
