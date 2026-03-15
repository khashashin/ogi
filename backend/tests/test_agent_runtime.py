import os
from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

os.environ["OGI_DB_PATH"] = ":memory:"
os.environ["OGI_USE_SQLITE"] = "true"
os.environ["OGI_SUPABASE_URL"] = ""
os.environ["OGI_SUPABASE_ANON_KEY"] = ""
os.environ["OGI_SUPABASE_SERVICE_ROLE_KEY"] = ""
os.environ["OGI_SUPABASE_JWT_SECRET"] = ""
os.environ["OGI_API_KEY_ENCRYPTION_KEY"] = "k0f97udxEhQ4duzTQESsQNmjUG74U7SMiFd7LrD0WBE="

from ogi.agent.context import AgentContextBuilder
from ogi.agent.llm_provider import LlmDecision, ScriptedLLMProvider, TokenUsage
from ogi.agent.models import AgentRun, AgentRunStatus, AgentStep, AgentStepStatus, AgentStepType
from ogi.agent.orchestrator import AgentOrchestrator
from ogi.agent.store import AgentStepStore
from ogi.agent.tool_implementations import build_default_tool_registry
from ogi.config import settings
from ogi.db import database as db_module
from ogi.engine.transform_execution_service import TransformExecutionService
from ogi.engine.transform_engine import TransformEngine
from ogi.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        async with app.router.lifespan_context(app):
            yield c


async def _create_project(client: AsyncClient, name: str) -> UUID:
    response = await client.post("/api/v1/projects", json={"name": name})
    assert response.status_code == 201
    return UUID(response.json()["id"])


async def _start_agent_run(client: AsyncClient, project_id: UUID, prompt: str = "Investigate") -> UUID:
    response = await client.post(
        f"/api/v1/projects/{project_id}/agent/start",
        json={"prompt": prompt, "scope": {"mode": "all", "entity_ids": []}},
    )
    assert response.status_code == 201
    return UUID(response.json()["id"])


def _build_orchestrator(*, decisions: list[LlmDecision], worker_id: str) -> AgentOrchestrator:
    assert db_module.async_session_maker is not None
    transform_engine = TransformEngine()
    transform_engine.auto_discover()
    plugin_engine = transform_engine.load_plugins(settings.plugin_dirs)
    execution_service = TransformExecutionService(
        transform_engine_getter=lambda: transform_engine,
        plugin_engine_getter=lambda: plugin_engine,
    )
    registry = build_default_tool_registry(
        transform_engine=transform_engine,
        plugin_engine=plugin_engine,
        transform_execution_service=execution_service,
    )
    return AgentOrchestrator(
        session_factory=db_module.async_session_maker,
        worker_id=worker_id,
        llm_provider=ScriptedLLMProvider(decisions),
        tool_registry=registry,
        context_builder=AgentContextBuilder(),
    )


@pytest.mark.asyncio
async def test_agent_claim_next_step_is_exclusive(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "agent_enabled", True)

    project_id = await _create_project(client, "AgentClaimProject")
    run_id = await _start_agent_run(client, project_id)

    assert db_module.async_session_maker is not None
    async with db_module.async_session_maker() as session:
        existing_steps = await AgentStepStore(session).list_for_run(run_id)
        for item in existing_steps:
            item.status = AgentStepStatus.COMPLETED
            item.completed_at = datetime.now(timezone.utc)
            session.add(item)
        step = AgentStep(
            run_id=run_id,
            step_number=2,
            type=AgentStepType.TOOL_CALL,
            tool_name="list_entities",
            status=AgentStepStatus.PENDING,
        )
        session.add(step)
        await session.commit()
        await session.refresh(step)
        step_id = step.id

    async with db_module.async_session_maker() as session:
        first_claim = await AgentStepStore(session).claim_next_runnable_step("worker-a", stale_after_seconds=60)

    async with db_module.async_session_maker() as session:
        second_claim = await AgentStepStore(session).claim_next_runnable_step("worker-b", stale_after_seconds=60)
        claimed_step = await session.get(AgentStep, step_id)

    assert first_claim is not None
    assert first_claim.id == step_id
    assert second_claim is None
    assert claimed_step is not None
    assert claimed_step.status == AgentStepStatus.RUNNING
    assert claimed_step.worker_id == "worker-a"


@pytest.mark.asyncio
async def test_agent_runtime_recovers_stale_claims_and_runs(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(settings, "agent_enabled", True)
    monkeypatch.setattr(settings, "agent_claim_timeout_sec", 30)

    project_id = await _create_project(client, "AgentRecoveryProject")
    first_run_id = await _start_agent_run(client, project_id, prompt="Recover step")
    second_run_id = await _start_agent_run(client, await _create_project(client, "AgentRecoveryProjectTwo"), prompt="Recover run")
    third_run_id = await _start_agent_run(client, await _create_project(client, "AgentRecoveryProjectThree"), prompt="Paused run")

    stale_time = datetime.now(timezone.utc) - timedelta(seconds=120)

    assert db_module.async_session_maker is not None
    async with db_module.async_session_maker() as session:
        first_existing = await AgentStepStore(session).list_for_run(first_run_id)
        second_existing = await AgentStepStore(session).list_for_run(second_run_id)
        third_existing = await AgentStepStore(session).list_for_run(third_run_id)
        for item in [*first_existing, *second_existing, *third_existing]:
            item.status = AgentStepStatus.COMPLETED
            item.completed_at = datetime.now(timezone.utc)
            session.add(item)

        first_run = await session.get(AgentRun, first_run_id)
        second_run = await session.get(AgentRun, second_run_id)
        third_run = await session.get(AgentRun, third_run_id)
        assert first_run is not None and second_run is not None and third_run is not None

        first_run.status = AgentRunStatus.RUNNING
        first_run.updated_at = stale_time
        second_run.status = AgentRunStatus.RUNNING
        second_run.updated_at = stale_time
        third_run.status = AgentRunStatus.PAUSED
        third_run.updated_at = stale_time

        session.add(
            AgentStep(
                run_id=first_run_id,
                step_number=2,
                type=AgentStepType.TOOL_CALL,
                tool_name="list_entities",
                status=AgentStepStatus.RUNNING,
                worker_id="stale-worker",
                claimed_at=stale_time,
            )
        )
        session.add(
            AgentStep(
                run_id=second_run_id,
                step_number=2,
                type=AgentStepType.THINK,
                status=AgentStepStatus.COMPLETED,
                completed_at=datetime.now(timezone.utc),
            )
        )
        session.add(first_run)
        session.add(second_run)
        session.add(third_run)
        await session.commit()

    orchestrator = _build_orchestrator(decisions=[], worker_id="worker-recover")
    recovered_steps, recovered_runs = await orchestrator.recover_stale_state()

    assert recovered_steps == 1
    assert recovered_runs == 1

    async with db_module.async_session_maker() as session:
        recovered_step = (
            await session.execute(
                AgentStep.__table__.select()
                .where(AgentStep.run_id == first_run_id)
                .where(AgentStep.step_number == 2)
            )
        ).mappings().first()
        first_run = await session.get(AgentRun, first_run_id)
        second_run = await session.get(AgentRun, second_run_id)
        third_run = await session.get(AgentRun, third_run_id)

    assert recovered_step is not None
    assert recovered_step["status"] == AgentStepStatus.PENDING.value
    assert recovered_step["worker_id"] is None
    assert first_run is not None
    assert first_run.status == AgentRunStatus.RUNNING
    assert second_run is not None
    assert second_run.status == AgentRunStatus.FAILED
    assert third_run is not None
    assert third_run.status == AgentRunStatus.PAUSED


@pytest.mark.asyncio
async def test_agent_approval_step_pauses_and_resumes(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(settings, "agent_enabled", True)

    project_id = await _create_project(client, "AgentApprovalRuntime")
    run_id = await _start_agent_run(client, project_id, prompt="Approval runtime")

    assert db_module.async_session_maker is not None
    async with db_module.async_session_maker() as session:
        existing_steps = await AgentStepStore(session).list_for_run(run_id)
        for item in existing_steps:
            item.status = AgentStepStatus.COMPLETED
            item.completed_at = datetime.now(timezone.utc)
            session.add(item)
        step = AgentStep(
            run_id=run_id,
            step_number=2,
            type=AgentStepType.APPROVAL_REQUEST,
            tool_name="run_transform",
            tool_input={"transform_name": "domain_to_ip"},
            status=AgentStepStatus.PENDING,
        )
        session.add(step)
        await session.commit()
        await session.refresh(step)
        step_id = step.id

    orchestrator = _build_orchestrator(decisions=[], worker_id="worker-approve")
    result = await orchestrator.run_once()
    assert result.processed is True

    async with db_module.async_session_maker() as session:
        paused_run = await session.get(AgentRun, run_id)
        approval_step = await session.get(AgentStep, step_id)

    assert paused_run is not None
    assert paused_run.status == AgentRunStatus.PAUSED
    assert approval_step is not None
    assert approval_step.status == AgentStepStatus.WAITING_APPROVAL

    approve_response = await client.post(
        f"/api/v1/projects/{project_id}/agent/runs/{run_id}/steps/{step_id}/approve",
        json={"note": "Looks safe"},
    )
    assert approve_response.status_code == 200

    resumed = await orchestrator.run_once()
    assert resumed.processed is True

    async with db_module.async_session_maker() as session:
        resumed_run = await session.get(AgentRun, run_id)
        resolved_step = await session.get(AgentStep, step_id)

    assert resumed_run is not None
    assert resumed_run.status == AgentRunStatus.RUNNING
    assert resolved_step is not None
    assert resolved_step.status == AgentStepStatus.COMPLETED
    assert resolved_step.approval_payload == {
        "tool_name": "run_transform",
        "tool_input": {"transform_name": "domain_to_ip"},
        "decision": "approved",
        "note": "Looks safe",
    }


@pytest.mark.asyncio
async def test_agent_budget_exceeded_fails_run(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "agent_enabled", True)

    project_id = await _create_project(client, "AgentBudgetProject")
    run_id = await _start_agent_run(client, project_id, prompt="Budget failure")

    assert db_module.async_session_maker is not None
    async with db_module.async_session_maker() as session:
        run = await session.get(AgentRun, run_id)
        assert run is not None
        run.budget = {"max_steps": 1, "max_transforms": 10, "max_runtime_sec": 600}
        run.usage = {"steps_used": 1, "transforms_run": 0, "llm_calls": 0, "prompt_tokens": 0, "completion_tokens": 0}
        session.add(run)
        await session.commit()

    orchestrator = _build_orchestrator(decisions=[], worker_id="worker-budget")
    result = await orchestrator.run_once()
    assert result.processed is True

    async with db_module.async_session_maker() as session:
        run = await session.get(AgentRun, run_id)
        step = (
            await session.execute(
                AgentStep.__table__.select().where(AgentStep.run_id == run_id)
            )
        ).mappings().first()

    assert run is not None
    assert run.status == AgentRunStatus.FAILED
    assert "max_steps" in (run.error or "")
    assert step is not None
    assert step["status"] == AgentStepStatus.FAILED.value


@pytest.mark.asyncio
async def test_agent_valid_tool_flow_completes_run(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "agent_enabled", True)

    project_id = await _create_project(client, "AgentToolFlow")
    create_entity = await client.post(
        f"/api/v1/projects/{project_id}/entities",
        json={"type": "Domain", "value": "flow.example"},
    )
    assert create_entity.status_code == 201
    run_id = await _start_agent_run(client, project_id, prompt="List current entities and finish.")

    orchestrator = _build_orchestrator(
        worker_id="worker-tool-flow",
        decisions=[
            LlmDecision(
                reasoning="I should inspect the current entities first.",
                action_type="tool_call",
                tool_name="list_entities",
                tool_params={"limit": 10},
                token_usage=TokenUsage(prompt_tokens=11, completion_tokens=7),
            ),
            LlmDecision(
                reasoning="I have enough information to finish.",
                action_type="finish",
                final_summary="The investigation found the initial domain and no additional relationships yet.",
                token_usage=TokenUsage(prompt_tokens=13, completion_tokens=5),
            ),
        ],
    )

    for _ in range(4):
        await orchestrator.run_once()

    async with db_module.async_session_maker() as session:
        run = await session.get(AgentRun, run_id)
        steps = await AgentStepStore(session).list_for_run(run_id)

    assert run is not None
    assert run.status == AgentRunStatus.COMPLETED
    assert run.summary == "The investigation found the initial domain and no additional relationships yet."
    assert run.usage["llm_calls"] == 2
    assert run.usage["prompt_tokens"] == 24
    assert run.usage["completion_tokens"] == 12
    assert [step.type for step in steps] == [
        AgentStepType.THINK,
        AgentStepType.TOOL_CALL,
        AgentStepType.TOOL_RESULT,
        AgentStepType.THINK,
        AgentStepType.SUMMARY,
    ]
    assert steps[2].tool_output is not None
    assert steps[2].tool_output["summary"].startswith("Listed")


@pytest.mark.asyncio
async def test_agent_invalid_tool_call_fails_run(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "agent_enabled", True)

    project_id = await _create_project(client, "AgentInvalidTool")
    run_id = await _start_agent_run(client, project_id, prompt="Call an invalid tool.")

    orchestrator = _build_orchestrator(
        worker_id="worker-invalid-tool",
        decisions=[
            LlmDecision(
                reasoning="I will use a nonexistent tool.",
                action_type="tool_call",
                tool_name="missing_tool",
                tool_params={},
                token_usage=TokenUsage(prompt_tokens=3, completion_tokens=2),
            )
        ],
    )

    await orchestrator.run_once()

    async with db_module.async_session_maker() as session:
        run = await session.get(AgentRun, run_id)

    assert run is not None
    assert run.status == AgentRunStatus.FAILED
    assert "unknown tool" in (run.error or "").lower()


@pytest.mark.asyncio
async def test_agent_run_transform_tool_executes_via_shared_service(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(settings, "agent_enabled", True)

    project_id = await _create_project(client, "AgentRunTransformTool")
    created_entity = await client.post(
        f"/api/v1/projects/{project_id}/entities",
        json={"type": "EmailAddress", "value": "analyst@example.com"},
    )
    assert created_entity.status_code == 201
    entity_id = created_entity.json()["id"]
    run_id = await _start_agent_run(client, project_id, prompt="Extract the domain from the email and finish.")

    orchestrator = _build_orchestrator(
        worker_id="worker-run-transform",
        decisions=[
            LlmDecision(
                reasoning="I should run the email_to_domain transform.",
                action_type="tool_call",
                tool_name="run_transform",
                tool_params={"entity_id": entity_id, "transform_name": "email_to_domain"},
                token_usage=TokenUsage(prompt_tokens=10, completion_tokens=6),
            ),
            LlmDecision(
                reasoning="The transform produced the related domain.",
                action_type="finish",
                final_summary="The email address resolved to the domain example.com.",
                token_usage=TokenUsage(prompt_tokens=9, completion_tokens=4),
            ),
        ],
    )

    await orchestrator.run_once()
    await orchestrator.run_once()

    async with db_module.async_session_maker() as session:
        steps = await AgentStepStore(session).list_for_run(run_id)
        tool_step = next(step for step in steps if step.type == AgentStepType.TOOL_CALL)

    assert tool_step.status == AgentStepStatus.WAITING_APPROVAL

    approve_response = await client.post(
        f"/api/v1/projects/{project_id}/agent/runs/{run_id}/steps/{tool_step.id}/approve",
        json={"note": "Execute it"},
    )
    assert approve_response.status_code == 200

    for _ in range(3):
        await orchestrator.run_once()

    async with db_module.async_session_maker() as session:
        run = await session.get(AgentRun, run_id)
        steps = await AgentStepStore(session).list_for_run(run_id)
        entities = await client.get(f"/api/v1/projects/{project_id}/entities")

    assert run is not None
    assert run.status == AgentRunStatus.COMPLETED
    result_step = next(step for step in steps if step.type == AgentStepType.TOOL_RESULT)
    assert result_step.tool_output is not None
    assert result_step.tool_output["data"]["transform_run"]["transform_name"] == "email_to_domain"
    values = {entity["value"] for entity in entities.json()}
    assert "example.com" in values


@pytest.mark.asyncio
async def test_agent_context_builder_summarizes_older_steps(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "agent_enabled", True)

    project_id = await _create_project(client, "AgentContextProject")
    run_id = await _start_agent_run(client, project_id, prompt="Summarize old steps.")

    assert db_module.async_session_maker is not None
    async with db_module.async_session_maker() as session:
        run = await session.get(AgentRun, run_id)
        assert run is not None
        step_store = AgentStepStore(session)
        next_number = await step_store.next_step_number(run_id)
        for offset in range(5):
            session.add(
                AgentStep(
                    run_id=run_id,
                    step_number=next_number + offset,
                    type=AgentStepType.TOOL_RESULT,
                    tool_name="list_entities",
                    tool_output={"summary": f"result {offset}"},
                    status=AgentStepStatus.COMPLETED,
                    completed_at=datetime.now(timezone.utc),
                )
            )
        await session.commit()
        steps = await step_store.list_for_run(run_id)

        transform_engine = TransformEngine()
        transform_engine.auto_discover()
        plugin_engine = transform_engine.load_plugins(settings.plugin_dirs)
        registry = build_default_tool_registry(
            transform_engine=transform_engine,
            plugin_engine=plugin_engine,
            transform_execution_service=TransformExecutionService(
                transform_engine_getter=lambda: transform_engine,
                plugin_engine_getter=lambda: plugin_engine,
            ),
        )
        builder = AgentContextBuilder(max_recent_steps=2)
        messages = await builder.build_messages(
            run=run,
            recent_steps=steps,
            tools=registry.list_tools(),
            session=session,
        )

    combined = "\n".join(message["content"] for message in messages)
    assert "Earlier completed steps summary" in combined
    assert "Recent step history" in combined
