"""
Agent core — agentic loop where Claude drives the browser via tool calls.

The loop:
1. Send persona system prompt + page context + tools to Claude
2. Claude responds with tool_use blocks or a final text assessment
3. Execute tool calls, feed results back
4. Repeat until Claude produces a final assessment (stop_reason=end_turn)
5. Parse the assessment into Issue objects
"""

import json
import os

import anthropic
from rich.console import Console
from tenacity import retry, stop_after_attempt, wait_exponential

from playwright.sync_api import Page

from accessibility_sweep.models import Issue, Severity
from accessibility_sweep.agent.tools import execute_tool

console = Console()

SEVERITY_MAP = {
    "critical": Severity.CRITICAL,
    "major": Severity.MAJOR,
    "minor": Severity.MINOR,
}

MODEL = "claude-sonnet-4-20250514"
MAX_TURNS = 40  # Safety limit on agent loop iterations


def _get_client() -> anthropic.Anthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set.")
    return anthropic.Anthropic(api_key=api_key)


def run_persona(
    page: Page,
    url: str,
    system_prompt: str,
    tools: list[dict],
    initial_message: str,
    persona_name: str,
    max_turns: int = MAX_TURNS,
) -> list[Issue]:
    """
    Run a single persona agent loop against a page.

    Args:
        page: Live Playwright page (already navigated to url).
        url: The page URL (for context).
        system_prompt: The persona's system prompt.
        tools: List of tool definitions the persona can use.
        initial_message: The opening user message to kick off the persona.
        persona_name: Name for logging (e.g. "keyboard", "screen_reader").
        max_turns: Max tool-call round-trips.

    Returns:
        List of Issue objects found by this persona.
    """
    client = _get_client()
    messages = [{"role": "user", "content": initial_message}]

    console.print(f"    [bold cyan]{persona_name}[/bold cyan] agent starting...")

    for turn in range(max_turns):
        response = _call_claude(client, system_prompt, messages, tools)

        # Collect all content blocks
        tool_uses = []
        text_blocks = []
        for block in response.content:
            if block.type == "tool_use":
                tool_uses.append(block)
            elif block.type == "text":
                text_blocks.append(block.text)

        # If no tool calls, Claude is done — parse the final assessment
        if not tool_uses:
            final_text = "\n".join(text_blocks)
            issues = _parse_assessment(final_text, persona_name)
            console.print(
                f"    [bold cyan]{persona_name}[/bold cyan] "
                f"complete: {len(issues)} issues found ({turn} tool rounds)"
            )
            return issues

        # Execute tool calls and build result messages
        assistant_content = []
        for block in response.content:
            if block.type == "tool_use":
                assistant_content.append({
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                })
            elif block.type == "text":
                assistant_content.append({
                    "type": "text",
                    "text": block.text,
                })

        messages.append({"role": "assistant", "content": assistant_content})

        tool_results = []
        for tool_block in tool_uses:
            result = execute_tool(tool_block.name, tool_block.input, page)

            # Special handling for screenshots — send as image content
            if isinstance(result, dict) and "_screenshot_base64" in result:
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_block.id,
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": result["_screenshot_base64"],
                            },
                        }
                    ],
                })
            else:
                result_text = json.dumps(result, default=str) if isinstance(result, (dict, list)) else str(result)
                # Truncate very large results
                if len(result_text) > 12000:
                    result_text = result_text[:12000] + "\n... [truncated]"
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_block.id,
                    "content": result_text,
                })

        messages.append({"role": "user", "content": tool_results})

    # If we hit max turns, ask Claude to wrap up
    console.print(f"    [yellow]{persona_name}: max turns reached, requesting final assessment[/yellow]")
    messages.append({
        "role": "user",
        "content": (
            "You have reached the maximum number of tool calls. Please provide "
            "your final accessibility assessment now as JSON."
        ),
    })
    response = _call_claude(client, system_prompt, messages, tools=[])
    final_text = "\n".join(b.text for b in response.content if b.type == "text")
    issues = _parse_assessment(final_text, persona_name)
    console.print(
        f"    [bold cyan]{persona_name}[/bold cyan] "
        f"complete: {len(issues)} issues found (max turns)"
    )
    return issues


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def _call_claude(client, system_prompt, messages, tools):
    """Make a single Claude API call with retry logic."""
    kwargs = {
        "model": MODEL,
        "max_tokens": 4096,
        "system": system_prompt,
        "messages": messages,
    }
    if tools:
        kwargs["tools"] = tools
    return client.messages.create(**kwargs)


def _parse_assessment(text: str, source: str) -> list[Issue]:
    """Parse Claude's final JSON assessment into Issue objects."""
    # Try to extract JSON from the response
    json_text = text.strip()

    # Handle markdown code fences
    if "```json" in json_text:
        json_text = json_text.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in json_text:
        json_text = json_text.split("```", 1)[1].split("```", 1)[0].strip()

    try:
        data = json.loads(json_text)
    except json.JSONDecodeError:
        # Try to find JSON object in the text
        start = json_text.find("{")
        end = json_text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                data = json.loads(json_text[start:end])
            except json.JSONDecodeError:
                console.print(f"    [yellow]{source}: could not parse assessment JSON[/yellow]")
                return []
        else:
            console.print(f"    [yellow]{source}: no JSON found in assessment[/yellow]")
            return []

    issues = []
    for item in data.get("issues", []):
        issues.append(Issue(
            type=item.get("type", f"{source}_finding"),
            element=item.get("element", ""),
            description=item.get("description", ""),
            wcag_criterion=item.get("wcag_criterion", ""),
            severity=SEVERITY_MAP.get(item.get("severity", "minor"), Severity.MINOR),
            recommendation=item.get("recommendation", ""),
            source=f"agent:{source}",
            visual_location=item.get("visual_location", ""),
        ))

    return issues
