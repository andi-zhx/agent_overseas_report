"""Minimal DeepSeek smoke-test script.

Usage:
    python scripts/verify_deepseek_call.py --mode text
    python scripts/verify_deepseek_call.py --mode json
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agent_overseas_report.services.llm_service import DeepSeekLLMService, LLMServiceError


def load_dotenv_file(path: str = ".env") -> None:
    """Load simple KEY=VALUE pairs from a local .env file if present."""
    env_path = Path(path)
    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify the DeepSeek LLM service can call the provider.")
    parser.add_argument("--mode", choices=("text", "json"), default="text", help="Smoke-test response mode.")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s - %(message)s")
    load_dotenv_file()

    try:
        service = DeepSeekLLMService()
        if args.mode == "json":
            result = service.generate_json(
                "Return a compact health-check object for the LLM service.",
                schema_hint={"status": "ok", "provider": "deepseek"},
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return

        result = service.generate_text("Reply with exactly: DeepSeek service is reachable.")
        print(result)
    except LLMServiceError as exc:
        print(f"DeepSeek smoke test failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
