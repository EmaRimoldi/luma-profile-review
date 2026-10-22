"""CLI entrypoints for the complete personal event workflow."""
import json
import sys
from pathlib import Path

from .core import ReviewError
from .integrations import AGENTS, integration_config
from .matching import compare_rankings
from .onboarding import QUESTIONS
from .pipeline import write_json
from .providers import make_backend
from .workspace import Workspace

PRODUCT_COMMANDS = {"onboard", "event", "import", "tasks", "submit", "analyze", "guide", "compare", "demo", "serve", "mcp", "integration"}


def add_commands(commands):
    for name in sorted(PRODUCT_COMMANDS):
        p = commands.add_parser(name)
        p.add_argument("--workspace", type=Path, default=Path("data/workspace"))
        if name == "onboard":
            p.add_argument("--answers", type=Path)
        if name == "event":
            p.add_argument("--url", required=True)
            p.add_argument("--name", default="My event")
        if name == "import":
            p.add_argument("--profiles", type=Path, required=True)
        if name in {"tasks", "submit", "analyze", "guide", "compare"}:
            p.add_argument("--event", required=True)
        if name in {"tasks", "submit"}:
            p.add_argument("--stage", choices=["structure", "matching"], required=True)
        if name == "tasks":
            p.add_argument("--limit", type=int, default=5)
            p.add_argument("--out", type=Path, required=True)
        if name == "submit":
            p.add_argument("--responses", type=Path, required=True)
        if name == "analyze":
            p.add_argument("--backend", choices=["codex", "claude", "ollama", "openai", "anthropic"])
            p.add_argument("--model")
            p.add_argument("--base-url")
            p.add_argument("--refresh", action="store_true")
        if name == "guide":
            p.add_argument("--out", type=Path)
            p.add_argument("--format", choices=["html", "json"], default="html")
        if name == "compare":
            p.add_argument("--labels", type=Path, required=True)
            p.add_argument("--k", type=int, default=10)
        if name == "serve":
            p.add_argument("--port", type=int, default=8765)
            p.add_argument("--demo", action="store_true")
        if name == "integration":
            p.add_argument("--agent", choices=AGENTS, required=True)


def run(args, config):
    if args.command == "integration":
        configuration = integration_config(args.agent, args.workspace)
        print(configuration["configuration"])
        print("Configuration destination: " + configuration["location"], file=sys.stderr)
        return 0
    if args.command == "mcp":
        from .mcp_server import serve
        serve(args.workspace)
        return 0
    workspace = Workspace(args.workspace)
    if args.command == "serve":
        from .webapp import serve
        if args.demo and not workspace.brief():
            from .demo import load_demo
            load_demo(workspace)
        serve(workspace, args.port)
        return 0
    if args.command == "onboard":
        if args.answers:
            answers = json.loads(args.answers.read_text())
        else:
            answers = {q["id"]: input(q["label"] + "\n> ") for q in QUESTIONS}
            answers["must_haves"] = input("Any indispensable professional requirements? Separate with semicolons, or leave blank.\n> ").split(";")
            answers["must_haves"] = [v.strip() for v in answers["must_haves"] if v.strip()]
        result = workspace.save_brief(answers)
    elif args.command == "event":
        result = workspace.create_event(args.url, args.name)
    elif args.command == "import":
        result = workspace.import_dataset(json.loads(args.profiles.read_text()))
    elif args.command == "tasks":
        result = workspace.tasks(args.event, args.stage, args.limit)
        write_json(args.out, result)
        result = {"tasks": len(result["requests"]), "remaining": result["remaining"], "out": str(args.out)}
    elif args.command == "submit":
        envelope = json.loads(args.responses.read_text())
        result = workspace.submit(args.event, args.stage, envelope["request_hash"], envelope["responses"])
    elif args.command == "analyze":
        backend = make_backend(args.backend or config.get("backend", "codex"), args.model or config.get("model"),
                               base_url=args.base_url or config.get("base_url", "http://127.0.0.1:11434"),
                               work_dir=workspace.root / "work/model-runs")
        guide = workspace.analyze(args.event, backend, args.refresh,
                                  progress=lambda value: print(json.dumps(value), file=sys.stderr, flush=True))
        result = {"event_id": args.event, "counts": guide["counts"], "errors": guide["errors"]}
    elif args.command == "guide":
        result = workspace.guide(args.event)
        if args.out:
            from .webapp import export_guide
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) if args.format == "json" else export_guide(result), encoding="utf-8")
            result = {"guide": str(args.out), "counts": result["counts"]}
    elif args.command == "compare":
        guide = workspace.guide(args.event)
        labels = json.loads(args.labels.read_text())
        rankings = {"evidence": [p["profile_url"] for p in guide["people"]],
                    "keyword": [p["profile_url"] for p in guide["keyword_baseline"]]}
        result = compare_rankings(rankings, labels, args.k)
    elif args.command == "demo":
        from .demo import load_demo
        guide = load_demo(workspace)
        result = {"event_id": guide["event_id"], "counts": guide["counts"], "note": "Fictional fixture results, not live inference."}
    else:
        raise ReviewError("Unknown product command")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 1 if args.command == "analyze" and result.get("errors") else 0
