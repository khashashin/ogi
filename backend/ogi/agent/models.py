from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field as PydanticField
from sqlmodel import Column, DateTime, Field, JSON, SQLModel


class AgentRunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentStepType(str, Enum):
    THINK = "think"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    APPROVAL_REQUEST = "approval_request"
    APPROVAL_RESPONSE = "approval_response"
    ERROR = "error"
    SUMMARY = "summary"


class AgentStepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    COMPLETED = "completed"
    FAILED = "failed"


class ScopeConfig(BaseModel):
    mode: Literal["all", "selected"]
    entity_ids: list[UUID] = PydanticField(default_factory=list)


class BudgetConfig(BaseModel):
    max_steps: int | None = None
    max_transforms: int | None = None
    max_runtime_sec: int | None = None


class UsageInfo(BaseModel):
    steps_used: int = 0
    transforms_run: int = 0
    llm_calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0


class StartAgentRunRequest(BaseModel):
    prompt: str
    scope: ScopeConfig
    budget: BudgetConfig | None = None


class StepApprovalRequest(BaseModel):
    note: str | None = None


class AgentEventMessage(BaseModel):
    type: str
    project_id: UUID
    run_id: UUID
    step_id: UUID | None = None
    status: str | None = None
    summary: str | None = None
    timestamp: datetime


class AgentRun(SQLModel, table=True):
    __tablename__ = "agent_runs"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    project_id: UUID = Field(foreign_key="projects.id", ondelete="CASCADE", index=True)
    user_id: UUID = Field(foreign_key="profiles.id", ondelete="CASCADE", index=True)
    status: AgentRunStatus = Field(default=AgentRunStatus.PENDING, index=True)
    scope: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    prompt: str
    provider: str = ""
    model: str = ""
    config: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    budget: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    usage: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    summary: str | None = None
    error: str | None = None
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True)),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True)),
    )
    completed_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )


class AgentStep(SQLModel, table=True):
    __tablename__ = "agent_steps"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    run_id: UUID = Field(foreign_key="agent_runs.id", ondelete="CASCADE", index=True)
    step_number: int = Field(index=True)
    type: AgentStepType = Field(index=True)
    tool_name: str | None = None
    tool_input: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    tool_output: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    llm_output: str | None = None
    token_usage: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    status: AgentStepStatus = Field(default=AgentStepStatus.PENDING, index=True)
    worker_id: str | None = None
    claimed_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True)),
    )
    completed_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
