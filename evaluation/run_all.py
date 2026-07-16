"""Run every evaluation suite and emit a consolidated report (CI gate).

Usage: python -m evaluation.run_all
"""

import asyncio
import json
import sys
from datetime import UTC, datetime

from evaluation import agent_eval, prompt_eval, rag_eval


async def main() -> int:
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "rag": await rag_eval.evaluate(),
        "prompts_guardrails": await prompt_eval.evaluate(),
        "agents": await agent_eval.evaluate(),
    }
    report["passed"] = all(section["passed"] for section in
                           (report["rag"], report["prompts_guardrails"], report["agents"]))
    print(json.dumps(report, indent=2))  # noqa: T201 — CLI entrypoint
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
