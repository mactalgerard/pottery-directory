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

The agent is skipped if `context/enrichment_fields_{COUNTRY}.md` already exists.

Tools available (via Claude tool_use):
  web_search         — Anthropic native web_search_20250305 tool
  get_niche_context  — returns the country + niche string (no-op stub)
"""

import json
import logging
import os
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
MODEL = "claude-sonnet-4-20250514"

# Tool schemas sent to Claude
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


def _load_system_prompt() -> str:
    """
    Load the enrichment researcher system prompt from prompts/enrichment_researcher_system.md.

    Returns:
        The system prompt as a string.

    Raises:
        FileNotFoundError: if the prompt file does not exist.
    """
    prompt_path = Path("src/prompts/enrichment_researcher_system.md")
    return prompt_path.read_text()


def _handle_tool_call(tool_name: str, tool_input: dict, country: CountryCode) -> Any:
    """
    Dispatch a tool_use call from Claude to the appropriate Python function.

    Only `get_niche_context` is handled here — `web_search` is a native
    Anthropic tool handled server-side.

    Args:
        tool_name:  Name of the tool Claude is calling.
        tool_input: Parsed JSON input from Claude's tool_use block.
        country:    Country code for this pipeline run.

    Returns:
        Tool result as a JSON-serialisable dict.
    """
    if tool_name == "get_niche_context":
        # TODO: Return {"country": country, "niche": "pottery and ceramics studios"}
        raise NotImplementedError
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


async def run(country: CountryCode) -> dict:
    """
    Run the EnrichmentResearcherAgent for a given country.

    Checks whether context/enrichment_fields_{COUNTRY}.md already exists.
    If it does, skips research and returns the existing field list.
    If not, runs the full Claude agentic loop with web_search tool_use.

    Args:
        country: Country code — "US", "CA", or "AU".

    Returns:
        Dict mapping field names to their definitions as confirmed by research.
        Example:
            {
                "class_types": "Types of classes offered (wheel, hand building, etc.)",
                "kids_classes": "Whether kids/family classes are offered",
                ...
            }

    Raises:
        EnvironmentError: if ANTHROPIC_API_KEY is not set.
        FileNotFoundError: if the system prompt file is missing.
    """
    output_path = CONTEXT_DIR / f"enrichment_fields_{country}.md"
    if output_path.exists():
        console.print(
            f"[yellow]Skipping research — {output_path} already exists.[/yellow]"
        )
        # TODO: Parse existing file and return field dict
        raise NotImplementedError

    console.print(
        Panel(
            f"Running EnrichmentResearcherAgent for [bold]{country}[/bold]",
            title="Research Phase",
        )
    )

    # TODO: Initialise anthropic.Anthropic() client
    # TODO: Load system prompt
    # TODO: Build initial user message asking agent to research for `country`
    # TODO: Run agentic tool_use loop:
    #         while response has tool_use blocks:
    #           dispatch _handle_tool_call for each block
    #           append tool results to messages
    #           call client.messages.create again
    # TODO: Extract final text from response
    # TODO: Call _write_context_file(country, final_text)
    # TODO: Parse final_text into field dict and return it
    raise NotImplementedError
