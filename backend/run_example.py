#!/usr/bin/env python3
"""
Demo script – run the Research Assistant Agent on a sample topic.

Usage:
  export OPENAI_API_KEY=sk-...          # or XAI_API_KEY / GROQ_API_KEY etc.
  python run_example.py

  # Or force a specific provider / topic:
  python run_example.py --provider xai
  python run_example.py --provider groq --model llama-3.3-70b-versatile
  python run_example.py --topic "Benefits and risks of nuclear fusion energy"
"""

from __future__ import annotations

import argparse
import os
import sys

from agent import ReActAgent, create_agent


DEMO_TOPIC = (
    "Recent advances in solid-state batteries for electric vehicles "
    "(focus on 2023–2025 developments, key companies, and remaining challenges)"
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the Research Assistant Agent on a topic"
    )
    parser.add_argument(
        "--provider",
        default="openai",
        choices=["openai", "xai", "groq", "together", "openrouter"],
        help="LLM provider (default: openai)",
    )
    parser.add_argument("--model", default=None, help="Override the model name")
    parser.add_argument(
        "--topic",
        default=DEMO_TOPIC,
        help="Research topic to investigate",
    )
    parser.add_argument(
        "--max-turns",
        type=int,
        default=12,
        help="Maximum Thought→Action cycles (default: 12)",
    )
    parser.add_argument("--quiet", action="store_true", help="Less verbose output")
    args = parser.parse_args()

    # Quick sanity check for keys
    key_map = {
        "openai": "OPENAI_API_KEY",
        "xai": "XAI_API_KEY",
        "groq": "GROQ_API_KEY",
        "together": "TOGETHER_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
    }
    required = key_map[args.provider]
    if not os.getenv(required) and not os.getenv("OPENAI_API_KEY"):
        print(
            f"Error: environment variable {required} is not set.\n"
            f"Example:\n  export {required}=your-key-here\n"
            f"Then re-run this script.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Provider : {args.provider}")
    print(f"Topic    : {args.topic}\n")

    agent = create_agent(
        provider=args.provider,
        model=args.model,
        verbose=not args.quiet,
        max_turns=args.max_turns,
    )

    report = agent.run(args.topic)

    if args.quiet:
        print(report)


if __name__ == "__main__":
    main()
