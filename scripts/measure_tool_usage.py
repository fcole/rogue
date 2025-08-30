#!/usr/bin/env python3
"""
Measure tool-calling effectiveness with the Ollama tool-based generator.

Runs a set of prompts through the OllamaToolBasedGenerator and reports:
- Success rate
- Average/min/max tool calls per successful run
- Tool usage frequency distribution

Usage examples:
  python scripts/measure_tool_usage.py
  python scripts/measure_tool_usage.py --model qwen2.5-coder:32b-instruct
  python scripts/measure_tool_usage.py --endpoint http://host.docker.internal:11434
  python scripts/measure_tool_usage.py --prompts tests/fixtures/prompts/test_suite.txt
"""

import argparse
import json
import os
import sys
from pathlib import Path
from collections import Counter

# Ensure we can import src modules when running as a script
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.generator.ollama_tool_generator import OllamaToolBasedGenerator  # type: ignore


DEFAULT_PROMPTS = [
    "a small room with one ogre",
    "a dense maze with three ogres guarding treasure",
    "an open field with two goblins",
    "a flooded cavern with islands and bridges",
    "a castle with shops and a chest",
    "a forest clearing with wolves and a hermit",
    "an abandoned mine with narrow tunnels",
    "a crypt with sarcophagi and lurking undead",
    "a marketplace with multiple shops and crowds",
    "a desert oasis with palm trees and water",
]


def load_prompts(path: Path | None) -> list[str]:
    if path and path.exists():
        return [line.strip() for line in path.read_text().splitlines() if line.strip()]
    # Fall back to test suite prompts if available
    ts = ROOT / "tests/fixtures/prompts/test_suite.txt"
    if ts.exists():
        return [line.strip() for line in ts.read_text().splitlines() if line.strip()]
    return DEFAULT_PROMPTS


def main():
    parser = argparse.ArgumentParser(description="Measure Ollama tool usage effectiveness")
    parser.add_argument("--prompts", type=str, help="Path to prompts file (one per line)")
    parser.add_argument("--limit", type=int, default=10, help="Max prompts to run")
    parser.add_argument("--model", type=str, help="Override OLLAMA model")
    parser.add_argument("--endpoint", type=str, help="Override OLLAMA endpoint")
    parser.add_argument("--json-out", type=str, help="Optional path to write JSON report")
    args = parser.parse_args()

    # Optional overrides via env for the generator
    if args.model:
        os.environ["OLLAMA_MODEL"] = args.model
    if args.endpoint:
        os.environ["OLLAMA_ENDPOINT"] = args.endpoint

    prompts = load_prompts(Path(args.prompts) if args.prompts else None)[: args.limit]

    gen = OllamaToolBasedGenerator()

    summary = {
        "total": len(prompts),
        "success": 0,
        "failed": 0,
        "avg_tool_calls": 0.0,
        "min_tool_calls": None,
        "max_tool_calls": None,
        "tool_frequency": {},
        "per_prompt": [],
    }

    tool_counts: list[int] = []
    tool_freq: Counter[str] = Counter()

    for idx, prompt in enumerate(prompts):
        print(f"[{idx+1}/{len(prompts)}] {prompt}")
        result = gen.generate_maps([prompt])
        r = result["results"][0]
        if r.status != "success" or not r.map_data:
            print("  - failed")
            summary["failed"] += 1
            summary["per_prompt"].append({"prompt": prompt, "status": r.status})
            continue

        md = r.map_data.metadata or {}
        count = int(md.get("tool_call_count", 0))
        calls = list(md.get("executed_tool_calls", []))
        print(f"  - tool calls: {count}")
        summary["success"] += 1
        tool_counts.append(count)
        tool_freq.update(calls)
        summary["per_prompt"].append(
            {
                "prompt": prompt,
                "status": r.status,
                "tool_call_count": count,
                "executed_tool_calls": calls,
                "connectivity_verified": bool(md.get("connectivity_verified", False)),
            }
        )

    if tool_counts:
        summary["avg_tool_calls"] = sum(tool_counts) / len(tool_counts)
        summary["min_tool_calls"] = min(tool_counts)
        summary["max_tool_calls"] = max(tool_counts)
    summary["tool_frequency"] = dict(tool_freq.most_common())

    # Print summary
    print("\n=== Tool Usage Summary ===")
    print(f"Prompts:   {summary['total']}")
    print(f"Success:   {summary['success']}")
    print(f"Failed:    {summary['failed']}")
    if tool_counts:
        print(f"Avg calls: {summary['avg_tool_calls']:.1f} (min {summary['min_tool_calls']}, max {summary['max_tool_calls']})")
    if summary["tool_frequency"]:
        print("Top tools:")
        for name, cnt in list(summary["tool_frequency"].items())[:10]:
            print(f"  - {name}: {cnt}")

    if args.json_out:
        Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json_out).write_text(json.dumps(summary, indent=2))
        print(f"\nJSON report saved to: {args.json_out}")


if __name__ == "__main__":
    main()
