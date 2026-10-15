"""Campus Customs MCP server (FastMCP, stdio transport).

Start with:  python -m mcp_server.server
Tools live in three modules; add a function to one of them and list it in that
module's TOOLS to expose it:
  tools.py           the original three read-only ticket tools (Problem 3)
  workflow_tools.py  ticket context, cash, vendor checks and approval requests
  human_tools.py     HUMAN-ONLY payment execution, rejection and reset
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from . import human_tools, tools, workflow_tools

mcp = FastMCP(
    "campus-customs",
    instructions=(
        "Operational data for the Campus Customs shop, read from data/campus_customs_new.db. "
        "desk.date_today is the business date for all due and overdue calculations. "
        "Tools marked HUMAN-ONLY must only be called on a person's explicit instruction."
    ),
    log_level="WARNING",
)

for tool in tools.TOOLS + workflow_tools.TOOLS + human_tools.TOOLS:
    mcp.add_tool(tool)


if __name__ == "__main__":
    mcp.run()
