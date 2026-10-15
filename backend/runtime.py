"""Owns the agent team and its MCP connection for the FastAPI app's lifetime.

Why a separate thread: on Windows, `uvicorn --reload` runs the app on a
SelectorEventLoop, which cannot start subprocesses, and the MCP server is a
stdio subprocess. So the MCP connection and all agent runs live on a dedicated
thread with its own (Proactor on Windows) event loop; routes hand coroutines to
it with `await runtime.call(...)`.
"""

from __future__ import annotations

import asyncio
import sys
import threading
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from .agents import AgentTeam

T = TypeVar("T")


class AgentRuntime:
    def __init__(self) -> None:
        self.loop: asyncio.AbstractEventLoop | None = None
        self.team: AgentTeam | None = None
        self.startup_error: BaseException | None = None
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()

    def start(self, timeout: float = 60) -> None:
        self._thread = threading.Thread(target=self._run, name="agent-runtime", daemon=True)
        self._thread.start()
        if not self._ready.wait(timeout):
            raise TimeoutError("MCP server did not start in time")
        if self.startup_error:
            raise RuntimeError(f"Could not connect to the MCP server: {self.startup_error}") from self.startup_error

    def _run(self) -> None:
        loop = asyncio.ProactorEventLoop() if sys.platform == "win32" else asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self.loop = loop
        try:
            team = AgentTeam()
            loop.run_until_complete(team.__aenter__())
            self.team = team
        except BaseException as error:  # reported to start()
            self.startup_error = error
            self._ready.set()
            return
        self._ready.set()
        loop.run_forever()

    async def call(self, factory: Callable[[AgentTeam], Awaitable[T]]) -> T:
        """Run `factory(team)` on the runtime loop and await its result from the caller's loop."""
        if not self.loop or not self.team:
            raise RuntimeError("Agent runtime is not running")
        future = asyncio.run_coroutine_threadsafe(factory(self.team), self.loop)
        return await asyncio.wrap_future(future)

    async def mcp(self, tool: str, args: dict[str, Any] | None = None) -> Any:
        return await self.call(lambda team: team.mcp.direct_call_tool(tool, args or {}))

    def stop(self) -> None:
        if not self.loop or not self.team:
            return
        try:
            asyncio.run_coroutine_threadsafe(self.team.__aexit__(None, None, None), self.loop).result(timeout=10)
        except Exception:
            pass
        self.loop.call_soon_threadsafe(self.loop.stop)
        if self._thread:
            self._thread.join(timeout=10)
