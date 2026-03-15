from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Literal
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ogi.agent.models import ScopeConfig


class ToolDefinition(BaseModel):
    name: str
    description: str
    parameters: dict[str, Any]
    risk_level: Literal["low", "medium", "high"]
    requires_approval: bool = False


class ToolResult(BaseModel):
    success: bool = True
    data: dict[str, Any] = Field(default_factory=dict)
    summary: str


@dataclass
class ToolContext:
    project_id: UUID
    user_id: UUID
    run_id: UUID
    scope: ScopeConfig
    session: AsyncSession


ToolHandler = Callable[[dict[str, Any], ToolContext], Awaitable[ToolResult]]


@dataclass
class RegisteredTool:
    definition: ToolDefinition
    handler: ToolHandler


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, RegisteredTool] = {}

    def register(self, definition: ToolDefinition, handler: ToolHandler) -> None:
        self._tools[definition.name] = RegisteredTool(definition=definition, handler=handler)

    def list_tools(self) -> list[ToolDefinition]:
        return [tool.definition for tool in self._tools.values()]

    def get_tool(self, name: str) -> RegisteredTool | None:
        return self._tools.get(name)

    async def execute(self, name: str, params: dict[str, Any], ctx: ToolContext) -> ToolResult:
        tool = self.get_tool(name)
        if tool is None:
            raise ValueError(f"Unknown tool '{name}'")
        return await tool.handler(params, ctx)
