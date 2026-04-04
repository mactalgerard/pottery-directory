"""
EnrichmentResearcherAgent — discovers WHAT fields to collect per country.

This agent runs ONCE per country, before enrichment begins. It uses Claude
with tool_use to research pottery/ceramics searcher behaviour in the target
market and then writes `context/enrichment_fields_{COUNTRY}.md` with validated,
market-specific field definitions.

Research is always country-scoped:
  US — r/Pottery, r/Ceramics, US Google Maps review patterns
  CA — r/canadaceramic (or equivalent), Canadian studio review tags
  AU — r/australia craft threads, AU pottery studio reviews.
       Note: AU studios more commonly use "hand building" and "clay classes"
       than "pottery wheel" — adjust search terms accordingly.

The agent is skipped if `context/enrichment_fields_{COUNTRY}.md` already exists,
unless force=True is passed.

Tools available (via Claude tool_use):
  web_search         — Anthropic native web_search_20250305 tool
  get_niche_context  — returns the country + niche string
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import anthropic
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

from src.models import CountryCode

load_dotenv()
console = Console()
logger = logging.getLogger(__name__)

CONTEXT_DIR = Path("context")
MODEL = "claude-opus-4-6"

TOOLS: list[dict] = [
    {
        "type": "web_search_20250305",
        "name": "web_search",
        "max_uses": 10,
    },
    {
        "name": "get_niche_context",
        "description": (
            "Returns the country code and niche name for this research run. "
            "Call this first to confirm the research scope."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "country": {
                    "type": "string",
                    "description": "Country code: US, CA, or AU.",
                }
            },
            "required": ["country"],
        },
    },
]


def _load_system_prompt(country: CountryCode) -> str:
    """
    Load and render the enrichment researcher system prompt.

    Replaces {COUNTRY} and {DATE} placeholders in the markdown file.

    Returns:
        Rendered system prompt string.

    Raises:
        FileNotFoundError: if the prompt file does not exist.
    """
    prompt_path = Path("src/prompts/enrichment_researcher_system.md")
    raw = prompt_path.read_text()
    today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    return raw.replace("{COUNTRY}", country).replace("{DATE}", today)


def _handle_tool_call(tool_name: str, tool_input: dict, country: CountryCode) -> Any:
    """
    Dispatch a custom tool_use call from Claude.

    Only `get_niche_context` is handled here — `web_search` is a native
    Anthropic tool executed server-side.

    Args:
        tool_name:  Name of the tool Claude is calling.
        tool_input: Parsed JSON input from Claude's tool_use block.
        country:    Country code for this pipeline run.

    Returns:
        Tool result as a JSON-serialisable dict.

    Raises:
        ValueError: if an unknown custom tool name is received.
    """
    if tool_name == "get_niche_context":
        return {
            "country": country,
            "niche": "pottery and ceramics studios",
            "description": (
                "A directory of studios that offer pottery classes, "
                "open studio access, or ceramics memberships to the public."
            ),
        }
    raise ValueError(f"Unknown tool: {tool_name}")


def _write_context_file(country: CountryCode, content: str) -> Path:
    """
    Write the researcher's output to context/enrichment_fields_{COUNTRY}.md.

    Args:
        country: Country code — used in the filename.
        content: Markdown content to write.

    Returns:
        Path to the written file.
    """
    CONTEXT_DIR.mkdir(exist_ok=True)
    output_path = CONTEXT_DIR / f"enrichment_fields_{country}.md"
    output_path.write_text(content)
    return output_path


async def run(country: CountryCode, force: bool = False) -> dict:
    """
    Run the EnrichmentResearcherAgent for a given country.

    Checks whether context/enrichment_fields_{COUNTRY}.md already exists.
    If it does and force=False, skips research and returns early.
    If force=True or the file is missing, runs the full Claude agentic loop.

    Args:
        country: Country code — "US", "CA", or "AU".
        force:   If True, re-run research even if the context file exists.

    Returns:
        Dict with keys "path" (output file path) and "status" ("written" or "skipped").

    Raises:
        EnvironmentError: if ANTHROPIC_API_KEY is not set.
        FileNotFoundError: if the system prompt file is missing.
    """
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise EnvironmentError("ANTHROPIC_API_KEY is not set.")

    output_path = CONTEXT_DIR / f"enrichment_fields_{country}.md"

    if output_path.exists() and not force:
        console.print(
            f"[yellow]Skipping research — {output_path} already exists. "
            f"Use --force to re-run.[/yellow]"
        )
        return {"path": str(output_path), "status": "skipped"}

    console.print(
        Panel(
            f"Running EnrichmentResearcherAgent for [bold]{country}[/bold]",
            title="Research Phase",
        )
    )

    client = anthropic.Anthropic()
    system_prompt = _load_system_prompt(country)

    initial_message = (
        f"Research the pottery and ceramics studio market in {country}. "
        f"Start by calling get_niche_context to confirm your scope, then search "
        f"Reddit, Google Maps review patterns, and local pottery communities to "
        f"validate the enrichment fields. Write your full findings in the output "
        f"format specified in your instructions."
    )

    messages: list[dict] = [{"role": "user", "content": initial_message}]

    # Agentic loop — runs until Claude produces a final text response
    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=system_prompt,
            tools=TOOLS,
            messages=messages,
        )

        logger.debug("stop_reason=%s content_blocks=%d", response.stop_reason, len(response.content))

        # Append Claude's turn to the conversation
        messages.append({"role": "assistant", "content": response.content})

        # Collect any custom tool calls that need client-side dispatch
        custom_tool_uses = [
            b for b in response.content
            if b.type == "tool_use" and b.name != "web_search"
        ]

        if custom_tool_uses:
            tool_results = []
            for tool_use in custom_tool_uses:
                console.print(f"  [dim]→ tool: {tool_use.name}({tool_use.input})[/dim]")
                try:
                    result = _handle_tool_call(tool_use.name, tool_use.input, country)
                except ValueError as exc:
                    result = {"error": str(exc)}
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": json.dumps(result),
                })
            messages.append({"role": "user", "content": tool_results})
            continue

        # If stop reason is end_turn, extract the final text block
        if response.stop_reason == "end_turn":
            text_blocks = [b for b in response.content if b.type == "text"]
            if not text_blocks:
                raise RuntimeError("Agent finished but produced no text output.")
            final_text = "\n\n".join(b.text for b in text_blocks)
            break

        # Web search and other server-side tools: loop continues automatically
        # (the API has already executed them and appended results to content)

    output_path = _write_context_file(country, final_text)
    console.print(f"[green]→ Enrichment fields written to {output_path}[/green]")

    return {"path": str(output_path), "status": "written"}
