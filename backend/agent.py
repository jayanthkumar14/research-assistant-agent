"""
Research Assistant Agent – a minimal ReAct (Reason + Act) agent.

The agent loops:
  Thought → Action → Observation
until it produces a final research report (Answer).

Works with any OpenAI-compatible chat API (OpenAI, xAI Grok, Groq, Together, etc.).
"""

from __future__ import annotations

import os
import re
from typing import Optional

from openai import OpenAI

from tools import run_tool, tool_descriptions


# ---------------------------------------------------------------------------
# System prompt specialised for research
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a careful Research Assistant Agent. Your job is to produce a well-structured research report on the topic the user gives you.

You run in a loop of Thought, Action, Observation.
At the end of the loop you output an Answer that is the complete research report.

Available tools:
{tools}

=== How to work ===
1. Clarify the topic in a Thought.
2. Use web_search (and optionally wikipedia) to discover relevant sources. Run 2–4 searches with different angles if needed.
3. Use browse_url on the most promising 2–4 pages to obtain deeper content.
4. After you have enough material, write a final research report.

=== Strict format rules ===
- When you want to use a tool, output exactly:
Thought: <your reasoning>
Action: <tool_name>: <argument>
- Do NOT invent tools. Only use the ones listed above.
- After receiving an Observation, continue with another Thought / Action or give the Answer.
- When finished, output:
Thought: <final reasoning>
Answer: <the complete research report>

=== Research report format (use this structure in the Answer) ===
# Research Report: <Topic>

## Executive Summary
2–4 sentence overview of the key findings.

## Key Findings
- Bullet points of the most important facts, results or arguments (cite sources inline).

## Detailed Analysis
Several short paragraphs synthesising the information from multiple sources. Mention agreements, disagreements and open questions.

## Sources & References
Numbered list of the sources you actually used, with title and full URL when available.
Example:
1. "Title of the page" – https://example.com/page
2. Wikipedia – CRISPR gene editing – https://en.wikipedia.org/wiki/CRISPR

Be accurate, neutral and cite only sources you observed. If information is incomplete, say so.
"""


# Regex to extract the first Action line
ACTION_RE = re.compile(r"^Action:\s*(\w+):\s*(.*)$", re.MULTILINE)


class ReActAgent:
    def __init__(
        self,
        model: str = "gpt-4o-mini",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        max_turns: int = 12,
        verbose: bool = True,
    ):
        """
        Args:
            model:      Model name (e.g. "gpt-4o-mini", "grok-3", "llama-3.3-70b-versatile")
            api_key:    API key. Falls back to OPENAI_API_KEY / XAI_API_KEY env vars.
            base_url:   Optional base URL for OpenAI-compatible providers
                        (e.g. "https://api.x.ai/v1" for Grok).
            max_turns:  Safety limit on the number of Thought→Action cycles.
            verbose:    Print intermediate thoughts and observations.
        """
        self.model = model
        self.max_turns = max_turns
        self.verbose = verbose

        # Resolve credentials
        key = api_key or os.getenv("OPENAI_API_KEY") or os.getenv("XAI_API_KEY")
        if not key:
            raise ValueError(
                "No API key found. Set OPENAI_API_KEY or XAI_API_KEY, "
                "or pass api_key=..."
            )

        client_kwargs = {"api_key": key}
        if base_url:
            client_kwargs["base_url"] = base_url
        elif os.getenv("XAI_API_KEY") and not os.getenv("OPENAI_API_KEY"):
            # Convenience: if only XAI key is present, point at xAI
            client_kwargs["base_url"] = "https://api.x.ai/v1"
            if model.startswith("gpt-"):
                self.model = "grok-3"  # sensible default

        self.client = OpenAI(**client_kwargs)

        # Conversation history for this agent instance
        self.messages: list[dict] = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT.format(tools=tool_descriptions()),
            }
        ]

    def _chat(self, user_content: str) -> str:
        self.messages.append({"role": "user", "content": user_content})
        response = self.client.chat.completions.create(
            model=self.model,
            messages=self.messages,
            temperature=0.2,
        )
        content = response.choices[0].message.content or ""
        self.messages.append({"role": "assistant", "content": content})
        return content

    def run(self, question: str) -> str:
        """
        Run the ReAct loop on a research topic and return the final report.
        """
        if self.verbose:
            print(f"\n{'='*60}")
            print(f"RESEARCH TOPIC: {question}")
            print(f"{'='*60}")

        next_prompt = (
            f"Research topic: {question}\n\n"
            "Please research this topic thoroughly using the available tools "
            "and produce a structured research report with sources."
        )

        for turn in range(1, self.max_turns + 1):
            if self.verbose:
                print(f"\n--- Turn {turn} ---")

            reply = self._chat(next_prompt)

            if self.verbose:
                print(reply)

            # Did the model give a final Answer?
            if "Answer:" in reply:
                # Extract everything after the last "Answer:"
                answer = reply.split("Answer:")[-1].strip()
                if self.verbose:
                    print(f"\n{'='*60}")
                    print("FINAL RESEARCH REPORT")
                    print(f"{'='*60}\n")
                    print(answer)
                    print(f"\n{'='*60}\n")
                return answer

            # Look for an Action
            match = ACTION_RE.search(reply)
            if not match:
                # Model didn't follow the format – ask it to continue properly
                next_prompt = (
                    "Observation: You did not output a valid Action or Answer. "
                    "Please continue with either:\n"
                    "Thought: ...\nAction: tool_name: argument\n"
                    "or\n"
                    "Thought: ...\nAnswer: ..."
                )
                continue

            tool_name, tool_arg = match.groups()
            tool_name = tool_name.strip()
            tool_arg = tool_arg.strip()

            if self.verbose:
                print(f"\n→ Calling tool: {tool_name}({tool_arg!r})")

            observation = run_tool(tool_name, tool_arg)

            if self.verbose:
                preview = observation[:400] + ("…" if len(observation) > 400 else "")
                print(f"← Observation: {preview}")

            next_prompt = f"Observation: {observation}"

        return (
            "I reached the maximum number of turns without producing a final Answer. "
            "Try increasing max_turns or narrowing the research topic."
        )


# Convenience factory for common providers
def create_agent(
    provider: str = "openai",
    model: Optional[str] = None,
    **kwargs,
) -> ReActAgent:
    """
    Quick helper to create an agent for popular providers.

    provider: "openai" | "xai" | "groq" | "together" | "openrouter"
    """
    defaults = {
        "openai": {
            "base_url": None,
            "model": model or "gpt-4o-mini",
        },
        "xai": {
            "base_url": "https://api.x.ai/v1",
            "model": model or "grok-3",
            "api_key": os.getenv("XAI_API_KEY"),
        },
        "groq": {
            "base_url": "https://api.groq.com/openai/v1",
            "model": model or "llama-3.3-70b-versatile",
            "api_key": os.getenv("GROQ_API_KEY"),
        },
        "together": {
            "base_url": "https://api.together.xyz/v1",
            "model": model or "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
            "api_key": os.getenv("TOGETHER_API_KEY"),
        },
        "openrouter": {
            "base_url": "https://openrouter.ai/api/v1",
            "model": model or "openai/gpt-4o-mini",
            "api_key": os.getenv("OPENROUTER_API_KEY"),
        },
        "Gemini":{
            "base URL": "https://generativelanguage.googleapis.com/v1beta/openai/"
            "model": model or "gemini-2.5-flash"
            "api_key": os.getenv("GEMINI_API_KEY"),
        },
    }

    if provider not in defaults:
        raise ValueError(f"Unknown provider '{provider}'. Choose from {list(defaults)}")

    cfg = defaults[provider]
    return ReActAgent(
        model=cfg["model"],
        base_url=cfg.get("base_url"),
        api_key=cfg.get("api_key"),
        **kwargs,
    )
