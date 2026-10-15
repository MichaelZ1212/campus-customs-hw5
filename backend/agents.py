"""The five Campus Customs agents and how they talk to each other.

* Every agent is a PydanticAI Agent on gpt-6-luna (via Portkey).
* Every agent reaches shop data only through the campus-customs MCP server; each
  gets a filtered view of the same MCP connection holding just its allowlisted tools.
* Every agent has `ask_agent`, so any agent can delegate to any other. Guards stop
  self-delegation, cycles (asking someone already in the chain), depth beyond
  MAX_DELEGATION_DEPTH, more than MAX_DELEGATIONS_PER_TICKET, and repeat questions
  (answered from a per-ticket cache instead).
* Every tool call and delegation is written to the audit trail.
"""

from __future__ import annotations

from typing import Any

from fastmcp.client.transports import StdioTransport
from pydantic_ai import Agent, RunContext
from pydantic_ai.exceptions import ToolFailed, UsageLimitExceeded
from pydantic_ai.mcp import MCPToolset

from . import audit
from .config import (
    MAX_DELEGATION_DEPTH, MAX_DELEGATIONS_PER_TICKET, MODEL_SETTINGS, PROMPTS_DIR, ROOT,
    TICKET_USAGE_LIMITS, get_model, mcp_server_command,
)
from .models import AGENT_NAMES, AgentDeps, AgentName, AgentReport

# Tools a person must trigger. They are in no agent's allowlist, and the audit hook
# refuses them as well in case a filter is ever misconfigured.
HUMAN_ONLY_TOOLS = frozenset({"execute_approved_payment", "reject_approval_request", "reset_working_database"})

# Only the Boss reads the ticket and the business date itself. Specialists get the ticket brief with
# every request, and each of their main tools already returns business_date, so giving them
# get_ticket/get_business_date only invited redundant calls (seen on ticket 102).
_COMMON: set[str] = set()
AGENT_TOOLS: dict[AgentName, frozenset[str]] = {
    "boss": frozenset({"get_business_date", "get_ticket", "list_open_tickets", "get_cash_position", "list_approval_requests", "update_ticket_status"}),
    "inventory": frozenset(_COMMON | {"check_stock_and_vendor_status", "get_vendor_status", "evaluate_bulk_discount"}),
    "accounting": frozenset(_COMMON | {
        "get_cash_position", "get_vendor_status", "get_lease_payment_status", "evaluate_bulk_discount",
        "list_approval_requests", "request_payment", "create_purchase_order", "request_discount_approval",
    }),
    "facilities": frozenset(_COMMON | {"get_lease_payment_status", "save_message_draft"}),
    "customer_service": frozenset(_COMMON | {"check_stock_and_vendor_status", "save_message_draft"}),
}
assert not any(tools & HUMAN_ONLY_TOOLS for tools in AGENT_TOOLS.values()), "an agent was given a human-only tool"

AGENT_DESCRIPTIONS: dict[AgentName, str] = {
    "boss": "final decisions, priorities across tickets, ticket status",
    "inventory": "stock by SKU and size, shortages, vendor choice, lead times and delivery dates",
    "accounting": "cash, vendor invoices, margins, discounts; queues payment requests and purchase orders for human approval",
    "facilities": "lease and rent verification, landlord drafts",
    "customer_service": "customer-facing reply drafts",
}


def _usage_snapshot(usage) -> dict[str, int]:
    """The shared per-ticket usage counter at this moment (sub-runs add to the same object)."""
    return {"requests": usage.requests, "tool_calls": usage.tool_calls,
            "input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens}


def _instructions(name: AgentName) -> str:
    policies = (PROMPTS_DIR / "shop_policies.md").read_text(encoding="utf-8")
    role = (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")
    team = "\n".join(f"- `{n}`: {d}" for n, d in AGENT_DESCRIPTIONS.items() if n != name)
    return f"{role}\n\n## Teammates you can ask with `ask_agent`\n{team}\n\n{policies}"


class AgentTeam:
    """One MCP connection shared by five agents. Use as `async with AgentTeam() as team:`.

    The run ID lives in each run's AgentDeps, so one team (and one MCP connection)
    can serve many runs, e.g. for the lifetime of the FastAPI app. Agents are built
    on first use, so MCP-only callers work even without PORTKEY_API_KEY.
    """

    def __init__(self):
        command, args, env = mcp_server_command()
        self.mcp = MCPToolset(
            StdioTransport(command, args, env=env, cwd=str(ROOT)),
            id="campus-customs",
            process_tool_call=self._audited_tool_call,
            tool_error_behavior="failed",  # business-rule refusals go back to the model without retry loops
        )
        self._agents: dict[AgentName, Agent[AgentDeps, Any]] | None = None

    @property
    def agents(self) -> dict[AgentName, Agent[AgentDeps, Any]]:
        if self._agents is None:
            self._agents = {name: self._build(name) for name in AGENT_NAMES}
        return self._agents

    async def __aenter__(self) -> "AgentTeam":
        await self.mcp.__aenter__()
        return self

    async def __aexit__(self, *exc) -> None:
        await self.mcp.__aexit__(*exc)

    # ----------------------------------------------------------- building

    def _build(self, name: AgentName) -> Agent[AgentDeps, Any]:
        allowed = AGENT_TOOLS[name]
        toolset = self.mcp.filtered(lambda ctx, tool_def: tool_def.name in allowed)
        agent: Agent[AgentDeps, Any] = Agent(
            get_model(),
            name=name,
            deps_type=AgentDeps,
            output_type=AgentReport,
            instructions=_instructions(name),
            toolsets=[toolset],
            tools=[self._ask_agent_tool()],
            model_settings=MODEL_SETTINGS,
            retries=2,
        )
        return agent

    async def _audited_tool_call(self, ctx: RunContext[AgentDeps], call_tool, name: str, args: dict[str, Any]):
        deps = ctx.deps
        base = dict(run_id=deps.run_id, agent=deps.agent, ticket_id=deps.ticket_id, action="mcp_tool_call", tool=name, inputs=args)
        if name in HUMAN_ONLY_TOOLS or name not in AGENT_TOOLS[deps.agent]:
            audit.record(**base, status="refused", error="tool not permitted for this agent")
            raise ToolFailed(f"{deps.agent} is not permitted to call {name}.")
        try:
            result = await call_tool(name, args)
        except ToolFailed as error:
            audit.record(**base, status="tool_error", error=error.message)
            raise
        except Exception as error:
            audit.record(**base, status="error", error=f"{type(error).__name__}: {error}")
            raise
        audit.record(**base, outputs=result)
        return result

    def _ask_agent_tool(self):
        team = self

        async def ask_agent(ctx: RunContext[AgentDeps], agent: AgentName, task: str, context: str = "") -> AgentReport | str:
            """Ask another Campus Customs agent to do work outside your own tools and return its structured report.

            Args:
                agent: Who to ask: boss, inventory, accounting, facilities or customer_service.
                task: One precise request, e.g. "Queue payment of invoice 501 then a PO for 1 x CC-TEE-WHITE S from vendor 1".
                context: Facts you already have (IDs, quantities, amounts, dates) so they don't re-fetch them.
            """
            deps = ctx.deps
            state = deps.state
            log = dict(run_id=deps.run_id, agent=deps.agent, ticket_id=deps.ticket_id, action="delegation",
                       tool="ask_agent", delegation_target=agent, inputs={"task": task, "context": context})

            refusal = None
            if agent == deps.agent:
                refusal = "You cannot delegate to yourself. Use your own tools."
            elif agent in deps.chain:
                refusal = f"{agent} is already waiting on this chain ({' -> '.join(deps.chain)}). Answer with what you have."
            elif len(deps.chain) >= MAX_DELEGATION_DEPTH:
                refusal = f"Delegation depth limit ({MAX_DELEGATION_DEPTH}) reached. Answer with what you have."
            elif state.delegations >= MAX_DELEGATIONS_PER_TICKET:
                refusal = f"Delegation limit for this ticket ({MAX_DELEGATIONS_PER_TICKET}) reached. Decide with what you have."
            if refusal:
                audit.record(**log, status="refused", error=refusal)
                return refusal

            key = (agent, " ".join(task.lower().split()))
            if key in state.cache:
                cached = state.cache[key]
                audit.record(**log, outputs=cached.model_dump(), status="cached")
                return cached

            state.delegations += 1
            audit.record(**log, status="started")
            prompt = f"{state.brief or f'Ticket {deps.ticket_id}.'}\nRequest from {deps.agent}: {task}"
            if context:
                prompt += f"\n\nContext already gathered:\n{context}"
            sub_deps = AgentDeps(deps.run_id, deps.ticket_id, agent, deps.chain + (agent,), state)
            before = _usage_snapshot(ctx.usage)
            try:
                result = await team.agents[agent].run(
                    prompt, deps=sub_deps, output_type=AgentReport, usage=ctx.usage, usage_limits=TICKET_USAGE_LIMITS
                )
            except UsageLimitExceeded as error:
                audit.record(**log, status="usage_limit", error=str(error))
                return f"{agent} stopped: the ticket's usage budget is exhausted ({error}). Decide with what you have."
            except Exception as error:
                audit.record(**log, status="error", error=f"{type(error).__name__}: {error}")
                return f"{agent} failed ({type(error).__name__}). Decide with what you have."

            report = result.output
            state.cache[key] = report
            spent = {k: v - before[k] for k, v in _usage_snapshot(ctx.usage).items()}
            audit.record(**log, outputs=report.model_dump(), status="completed", usage=spent)
            return report

        return ask_agent
