"""Human approval desk (command line). The only way payments get executed.

    python -m backend.approvals list
    python -m backend.approvals approve 1 --by "Your Name"
    python -m backend.approvals reject 4 --by "Your Name" --note "too expensive"

Calls the HUMAN-ONLY MCP tools; no agent can reach this path.
"""

from __future__ import annotations

import argparse
import asyncio
import json

from fastmcp.client.transports import StdioTransport
from pydantic_ai.mcp import MCPToolset

from . import audit
from .config import ROOT, mcp_server_command


async def _call(name: str, args: dict) -> object:
    command, cmd_args, env = mcp_server_command()
    async with MCPToolset(StdioTransport(command, cmd_args, env=env, cwd=str(ROOT)), tool_error_behavior="error") as mcp:
        return await mcp.direct_call_tool(name, args)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    for cmd in ("approve", "reject"):
        p = sub.add_parser(cmd)
        p.add_argument("request_id", type=int)
        p.add_argument("--by", required=True, help="name of the human making the decision")
        if cmd == "reject":
            p.add_argument("--note", default="")
    args = parser.parse_args()

    if args.command == "list":
        result = asyncio.run(_call("list_approval_requests", {"status": "pending"}))
    else:
        tool, payload = (
            ("execute_approved_payment", {"approval_request_id": args.request_id, "approved_by": args.by})
            if args.command == "approve"
            else ("reject_approval_request", {"approval_request_id": args.request_id, "decided_by": args.by, "note": args.note})
        )
        try:
            result = asyncio.run(_call(tool, payload))
            status = "ok" if not (isinstance(result, dict) and result.get("error")) else "rejected"
            audit.record(run_id="human", agent=f"human:{args.by}", action=f"approval_{args.command}", tool=tool,
                         inputs=payload, outputs=result, status=status)
        except Exception as error:
            audit.record(run_id="human", agent=f"human:{args.by}", action=f"approval_{args.command}", tool=tool,
                         inputs=payload, status="error", error=str(error))
            raise SystemExit(f"Refused: {error}")
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
