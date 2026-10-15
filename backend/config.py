"""Model, MCP and limit settings shared by every agent."""

from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path

from openai import AsyncOpenAI
from pydantic_ai.models.openai import OpenAIResponsesModel, OpenAIResponsesModelSettings
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.usage import UsageLimits

ROOT = Path(__file__).resolve().parent.parent
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
AUDIT_PATH = Path(os.getenv("CAMPUS_CUSTOMS_AUDIT", ROOT / "output" / "audit_trail.json"))
# Only passed to the MCP server process. The backend itself never opens the database.
# CAMPUS_CUSTOMS_DB can point a test run at a scratch copy.
WORKING_DB = Path(os.getenv("CAMPUS_CUSTOMS_DB", ROOT / "data" / "campus_customs_new.db"))

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

# Optional .env at the project root (copy .env.example). Real shell variables take precedence.
try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env", override=False)
except ImportError:
    pass

# The only model used anywhere in this project.
MODEL_NAME = "gpt-6-luna"
PORTKEY_BASE_URL = "https://api.portkey.ai/v1"

# gpt-6-luna rejects function tools with reasoning on /chat/completions, so agents
# use the Responses API. Low reasoning effort keeps token use down.
MODEL_SETTINGS = OpenAIResponsesModelSettings(openai_reasoning_effort="low", max_tokens=1500)

# Loop and spend limits. A ticket's agents share one usage counter, so these cap
# the whole ticket (Boss plus every delegated agent), not each agent separately.
MAX_DELEGATION_DEPTH = 3          # Boss -> A -> B -> C, no deeper
MAX_DELEGATIONS_PER_TICKET = 8
TICKET_USAGE_LIMITS = UsageLimits(request_limit=40, tool_calls_limit=45, total_tokens_limit=120_000)
TRIAGE_USAGE_LIMITS = UsageLimits(request_limit=6, tool_calls_limit=6, total_tokens_limit=20_000)


@lru_cache(maxsize=1)
def get_model() -> OpenAIResponsesModel:
    """gpt-6-luna through the Portkey gateway, authenticated with PORTKEY_API_KEY."""
    api_key = os.getenv("PORTKEY_API_KEY")
    if not api_key:
        raise RuntimeError("PORTKEY_API_KEY is not set. Export it before running the agents.")
    client = AsyncOpenAI(
        api_key=api_key,
        base_url=PORTKEY_BASE_URL,
        default_headers={"x-portkey-api-key": api_key, "x-portkey-provider": "openai"},
        timeout=120.0,
        max_retries=2,
    )
    return OpenAIResponsesModel(MODEL_NAME, provider=OpenAIProvider(openai_client=client))


def mcp_server_command() -> tuple[str, list[str], dict[str, str]]:
    """How the backend launches the MCP server: same Python, run as a module from the project root."""
    env = {**os.environ, "PYTHONPATH": str(ROOT), "CAMPUS_CUSTOMS_DB": str(WORKING_DB)}
    return sys.executable, ["-m", "mcp_server.server"], env
