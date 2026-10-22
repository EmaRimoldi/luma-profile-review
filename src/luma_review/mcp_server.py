"""Agent-neutral MCP tools. Browsing remains with the host's browser tools."""
from pathlib import Path
from typing import Any

from .core import ReviewError
from .onboarding import QUESTIONS
from .providers import make_backend
from .workspace import Workspace


def create_server(root: Path):
    try:
        from mcp.server.fastmcp import FastMCP
        from mcp.types import ToolAnnotations
    except ImportError:
        raise ReviewError('Install the MCP extra: pip install -e ".[mcp]"') from None
    workspace = Workspace(root)
    server = FastMCP("Luma Profile Review", instructions="Help the user find professionally relevant people at events. Collect only accessible pages using your host browser, preserve evidence, and distinguish unknown facts from negative matches. Start with onboarding_questions.")
    readonly = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)
    local_write = ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=False)

    @server.tool(annotations=readonly)
    def onboarding_questions() -> dict[str, Any]:
        """Get the five short questions and current brief before collecting an event."""
        return {"questions": QUESTIONS, "optional": "Explicit must_haves; do not invent hard filters.", "state": workspace.state()}

    @server.tool(annotations=local_write)
    def save_professional_brief(answers: dict[str, Any]) -> dict[str, Any]:
        """Save the user's work, interests, looking_for, connect_with, can_offer, and optional must_haves. Derive editable criteria."""
        return workspace.save_brief(answers)

    @server.tool(annotations=local_write)
    def create_event(event_url: str, event_name: str) -> dict[str, Any]:
        """Start or resume a local Luma event workspace. This does not register the user for the event."""
        return workspace.create_event(event_url, event_name)

    @server.tool(annotations=local_write)
    def record_attendees(event_id: str, attendees: list[dict[str, Any]], displayed_count: int | None = None,
                         complete: bool = False, scope: str = "Accessible Luma guest list collected by the user's agent.") -> dict[str, Any]:
        """Record observed names and profile_url values. Optional photo_url and contact_links (linkedin, x) must come from the person's published profile, never guesses. Set complete only after exhausting the accessible list."""
        return workspace.capture_attendees(event_id, attendees, displayed_count, complete, scope)

    @server.tool(annotations=readonly)
    def next_profile_sources(event_id: str, limit: int = 5) -> dict[str, Any]:
        """Get the resumable browser research queue: Luma first, then discovered LinkedIn or other professional sources. Never bypass an access restriction."""
        return {"profiles": workspace.source_queue(event_id, limit)}

    @server.tool(annotations=local_write)
    def record_profile_sources(event_id: str, profile_url: str, sources: list[dict[str, Any]],
                               outbound_links: list[str] | None = None, complete: bool = False,
                               attempts: list[dict[str, str]] | None = None) -> dict[str, Any]:
        """Save actually read excerpts with url, title, text, retrieved_at and optional links. Record inaccessible pages in attempts with url and reason. Discovered links alone are not read evidence."""
        return workspace.capture_sources(event_id, profile_url, sources, outbound_links, complete, attempts)

    @server.tool(annotations=readonly)
    def inference_tasks(event_id: str, stage: str = "structure", limit: int = 3) -> dict[str, Any]:
        """Get source-grounded model tasks for structure or matching. Answer using your current model and submit_inference; no extra subscription or API request is needed."""
        return workspace.tasks(event_id, stage, limit)

    @server.tool(annotations=local_write)
    def submit_inference(event_id: str, stage: str, request_hash: str, responses: dict[str, Any]) -> dict[str, Any]:
        """Submit the current agent's schema-conforming results, keyed by profile URL. Validates exact citations and rejects stale inputs."""
        return workspace.submit(event_id, stage, request_hash, responses)

    @server.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=True))
    def run_event_analysis(event_id: str, backend: str = "codex", model: str | None = None,
                           base_url: str = "http://127.0.0.1:11434") -> dict[str, Any]:
        """Run structure and matching with the selected CLI, Ollama, or separately billed API backend (environment key). For your current agent model, use inference_tasks and submit_inference instead."""
        if backend not in {"codex", "claude", "ollama", "openai", "anthropic"}:
            raise ReviewError("Choose codex, claude, ollama, openai, or anthropic; host inference uses inference_tasks")
        provider = make_backend(backend, model, base_url=base_url, work_dir=workspace.root / "work/model-runs")
        guide = workspace.analyze(event_id, provider)
        return {"event_id": event_id, "counts": guide["counts"], "errors": guide["errors"]}

    @server.tool(annotations=readonly)
    def event_guide(event_id: str, limit: int = 10) -> dict[str, Any]:
        """Get the personalized guide, evidence, conversation ideas, graph, and collection coverage. Shared context is not a claim that people know one another."""
        if not 1 <= limit <= 100:
            raise ReviewError("Use a guide limit between 1 and 100")
        guide = workspace.guide(event_id)
        guide["people"] = guide["people"][:limit]
        return guide

    @server.tool(annotations=local_write)
    def record_feedback(event_id: str, profile_url: str, status: str, note: str = "") -> dict[str, Any]:
        """Save local feedback: saved, meet (plan), met (already met), not_relevant, or none. No message is sent to the attendee."""
        return workspace.save_feedback(event_id, profile_url, status, note)

    return server


def serve(root: Path):
    create_server(root).run(transport="stdio")
