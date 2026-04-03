from pathlib import Path

import pytest
from fastapi import HTTPException

from app.assistant_runtime.orchestrator import AssistantUpstreamConnectionError
from app.assistant_runtime.schemas import AssistantAgentTurnRequest
from app.core.data_storage import DataStorage


class FakeCtx:
    def __init__(self, storage):
        self._storage = storage

    def storage(self):
        return self._storage


class FailingOrchestrator:
    async def run_turn(self, **kwargs):
        raise AssistantUpstreamConnectionError(
            "AI 上游连接失败，请检查网络、Base URL 或代理设置。",
        )


class FakeQueryService:
    def save_support_resistance_snapshot(self, request):
        return {
            "snapshot_id": "snapshot-1",
            "snapshot": {"snapshot_id": "snapshot-1", "inst_id": request.inst_id},
        }

    def list_level_snapshots(self, request):
        return {
            "snapshots": [
                {"snapshot_id": "snapshot-1", "inst_id": request.inst_id or "BTC-USDT"},
            ],
            "count": 1,
        }

    def get_level_snapshot(self, snapshot_id):
        return {
            "snapshot": {"snapshot_id": snapshot_id, "inst_id": "BTC-USDT"},
        }

    def list_patrol_runs(self, request):
        return {
            "runs": [
                {"run_id": "run-1", "inst_type": request.inst_type or "SWAP"},
            ],
            "count": 1,
        }

    def get_patrol_run(self, run_id):
        return {
            "run": {"run_id": run_id, "inst_type": "SWAP"},
        }

    def create_order_draft(self, request):
        return {
            "draft_id": "draft-1",
            "status": "draft",
            "inst_id": request.inst_id,
        }

    def list_order_drafts(self, request):
        return {
            "drafts": [
                {"draft_id": "draft-1", "status": "draft", "inst_id": request.inst_id or "BTC-USDT"},
            ],
            "count": 1,
        }

    def get_order_draft(self, draft_id):
        return {
            "draft": {"draft_id": draft_id, "status": "draft", "inst_id": "BTC-USDT"},
        }

    def confirm_order_draft(self, request):
        return {
            "draft_id": request.draft_id,
            "status": "confirmed",
            "executed": False,
        }


@pytest.mark.asyncio
async def test_run_agent_chat_maps_upstream_connect_error_to_503(tmp_path: Path, monkeypatch):
    import app.api.assistant as assistant_api

    storage = DataStorage(tmp_path / "market.db")
    monkeypatch.setattr(assistant_api, "get_app_context", lambda: FakeCtx(storage), raising=True)
    monkeypatch.setattr(assistant_api, "_get_orchestrator", lambda: FailingOrchestrator(), raising=True)

    request = AssistantAgentTurnRequest(
        message="帮我看下 BTC",
        inst_id="BTC-USDT",
    )

    with pytest.raises(HTTPException) as exc_info:
        await assistant_api.run_agent_chat(request)

    assert exc_info.value.status_code == 503
    assert "连接失败" in exc_info.value.detail


@pytest.mark.asyncio
async def test_assistant_order_draft_endpoints_delegate_to_query_service(monkeypatch):
    import app.api.assistant as assistant_api

    monkeypatch.setattr(assistant_api, "_get_query_service", lambda: FakeQueryService(), raising=True)

    created = await assistant_api.create_agent_order_draft(
        assistant_api.AgentOrderDraftRequest(
            inst_id="BTC-USDT",
            inst_type="SPOT",
            mode="simulated",
            side_preference="buy",
        )
    )
    listed = await assistant_api.list_agent_order_drafts(inst_id="BTC-USDT", status="draft", limit=10)
    detail = await assistant_api.get_agent_order_draft("draft-1")
    confirmed = await assistant_api.confirm_agent_order_draft("draft-1")

    assert created["data"]["draft_id"] == "draft-1"
    assert listed["data"]["count"] == 1
    assert detail["data"]["draft"]["draft_id"] == "draft-1"
    assert confirmed["data"]["status"] == "confirmed"


@pytest.mark.asyncio
async def test_assistant_level_snapshot_and_patrol_run_endpoints_delegate_to_query_service(monkeypatch):
    import app.api.assistant as assistant_api

    monkeypatch.setattr(assistant_api, "_get_query_service", lambda: FakeQueryService(), raising=True)

    saved = await assistant_api.create_agent_level_snapshot(
        assistant_api.AgentLevelSnapshotRequest(
            inst_id="BTC-USDT",
            inst_type="SPOT",
        )
    )
    listed_snapshots = await assistant_api.list_agent_level_snapshots(inst_id="BTC-USDT", limit=10)
    snapshot_detail = await assistant_api.get_agent_level_snapshot("snapshot-1")
    listed_runs = await assistant_api.list_agent_patrol_runs(inst_type="SWAP", limit=10)
    run_detail = await assistant_api.get_agent_patrol_run("run-1")

    assert saved["data"]["snapshot_id"] == "snapshot-1"
    assert listed_snapshots["data"]["count"] == 1
    assert snapshot_detail["data"]["snapshot"]["snapshot_id"] == "snapshot-1"
    assert listed_runs["data"]["count"] == 1
    assert run_detail["data"]["run"]["run_id"] == "run-1"
