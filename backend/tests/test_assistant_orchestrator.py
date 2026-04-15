import asyncio
import json
from pathlib import Path

import pytest
import httpx

from app.assistant_runtime.orchestrator import (
    AssistantOrchestrator,
    AssistantOrchestratorError,
    AssistantUpstreamConnectionError,
)
from app.core.data_storage import DataStorage


@pytest.fixture(autouse=True)
def _avoid_asyncio_default_executor_hang(monkeypatch):
    async def _to_thread(func, /, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setattr(asyncio, "to_thread", _to_thread, raising=True)


class FakeTicker:
    def __init__(self):
        self.inst_id = "BTC-USDT"
        self.last = 123.0
        self.last_sz = 1.0
        self.ask_px = 123.2
        self.bid_px = 122.8
        self.open_24h = 120.0
        self.high_24h = 125.0
        self.low_24h = 118.0
        self.vol_24h = 999.0
        self.timestamp = 1704067200000

    @property
    def change_24h(self):
        return (self.last - self.open_24h) / self.open_24h * 100

    def to_dict(self):
        return {
            "inst_id": self.inst_id,
            "last": self.last,
            "last_sz": self.last_sz,
            "ask_px": self.ask_px,
            "bid_px": self.bid_px,
            "open_24h": self.open_24h,
            "high_24h": self.high_24h,
            "low_24h": self.low_24h,
            "vol_24h": self.vol_24h,
            "change_24h": self.change_24h,
            "timestamp": self.timestamp,
        }


class FakeFetcher:
    def get_ticker_cached(self, inst_id, inst_type=None):
        return FakeTicker()


class FakeManager:
    def get_local_candles(self, *args, **kwargs):
        return []


class FakeAccount:
    is_available = True

    def get_balance(self):
        return {"details": []}


class FakeCtx:
    def __init__(self, storage):
        self._storage = storage

    def storage(self):
        return self._storage

    def fetcher(self):
        return FakeFetcher()

    def manager(self):
        return FakeManager()

    def account(self, mode):
        return FakeAccount()

    def default_mode(self):
        return "simulated"


class FakeCompletionClient:
    def __init__(self):
        self.calls = 0

    async def complete(self, *, messages, tools=None, temperature=None):
        self.calls += 1
        if self.calls == 1:
            return {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "",
                            "tool_calls": [
                                {
                                    "id": "tool-1",
                                    "type": "function",
                                    "function": {
                                        "name": "get_market_snapshot",
                                        "arguments": "{\"inst_id\":\"BTC-USDT\",\"inst_type\":\"SPOT\"}",
                                    },
                                }
                            ],
                        }
                    }
                ],
                "usage": {"total_tokens": 100},
            }
        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "当前 24h 涨幅约 2.5%，先观望，等待更明确突破。",
                    }
                }
            ],
            "usage": {"total_tokens": 140},
        }


class FailingConnectCompletionClient:
    async def complete(self, *, messages, tools=None, temperature=None):
        raise httpx.ConnectError("upstream connect failed")


class HistoryAwareCompletionClient:
    def __init__(self):
        self.calls = 0

    async def complete(self, *, messages, tools=None, temperature=None):
        self.calls += 1
        if self.calls == 1:
            return {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "",
                            "tool_calls": [
                                {
                                    "id": "tool-1",
                                    "type": "function",
                                    "function": {
                                        "name": "get_market_snapshot",
                                        "arguments": "{\"inst_id\":\"BTC-USDT\",\"inst_type\":\"SPOT\"}",
                                    },
                                }
                            ],
                        }
                    }
                ],
                "usage": {"total_tokens": 100},
            }
        if self.calls == 2:
            return {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "第一轮分析完成。",
                        }
                    }
                ],
                "usage": {"total_tokens": 120},
            }

        tool_message_index = next(
            (index for index, message in enumerate(messages) if message.get("role") == "tool"),
            -1,
        )
        assert tool_message_index > 0
        previous_assistant = messages[tool_message_index - 1]
        assert previous_assistant.get("role") == "assistant"
        assert isinstance(previous_assistant.get("tool_calls"), list)
        assert previous_assistant["tool_calls"][0]["id"] == "tool-1"

        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "第二轮分析完成。",
                    }
                }
            ],
            "usage": {"total_tokens": 90},
        }


class LevelsCompletionClient:
    def __init__(self):
        self.calls = 0

    async def complete(self, *, messages, tools=None, temperature=None):
        self.calls += 1
        if self.calls == 1:
            return {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "",
                            "tool_calls": [
                                {
                                    "id": "tool-levels",
                                    "type": "function",
                                    "function": {
                                        "name": "detect_support_resistance",
                                        "arguments": "{\"inst_id\":\"BTC-USDT\",\"inst_type\":\"SPOT\",\"timeframes\":[\"1H\",\"4H\"]}",
                                    },
                                }
                            ],
                        }
                    }
                ],
                "usage": {"total_tokens": 88},
            }
        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "已识别关键位。",
                    }
                }
            ],
            "usage": {"total_tokens": 116},
        }


class SanitizingHistoryCompletionClient:
    def __init__(self, orphan_call_id: str):
        self.orphan_call_id = orphan_call_id

    async def complete(self, *, messages, tools=None, temperature=None):
        for message in messages:
            if message.get("role") != "assistant":
                continue
            tool_calls = message.get("tool_calls") or []
            assert all(
                str((tool_call or {}).get("id") or "").strip() != self.orphan_call_id
                for tool_call in tool_calls
            )
        for message in messages:
            if message.get("role") != "tool":
                continue
            assert str(message.get("tool_call_id") or "").strip() != self.orphan_call_id
        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "坏历史已被忽略，继续分析。",
                    }
                }
            ],
            "usage": {"total_tokens": 64},
        }


class FailingToolCompletionClient:
    def __init__(self):
        self.calls = 0

    async def complete(self, *, messages, tools=None, temperature=None):
        self.calls += 1
        if self.calls > 1:
            raise AssertionError("工具失败后不应继续请求上游")
        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "id": "call-fail",
                                "type": "function",
                                "function": {
                                    "name": "build_risk_budget",
                                    "arguments": "{\"inst_id\":\"BTC-USDT\"}",
                                },
                            }
                        ],
                    }
                }
            ],
            "usage": {"total_tokens": 73},
        }


def test_data_storage_assistant_session_roundtrip(tmp_path: Path):
    storage = DataStorage(tmp_path / "market.db")
    session_id = storage.create_assistant_session(
        title="BTC 观察",
        kind="agent",
        mode="simulated",
        inst_id="BTC-USDT",
        inst_type="SPOT",
        metadata={"source": "test"},
    )
    storage.append_assistant_message(session_id, role="user", content="看看 BTC")
    storage.append_assistant_step(
        session_id,
        step_index=1,
        step_type="tool",
        title="调用 get_market_snapshot",
        tool_name="get_market_snapshot",
        input_payload={"inst_id": "BTC-USDT"},
        output_payload={"last": 123.0},
    )

    detail = storage.get_assistant_session_detail(session_id)

    assert detail is not None
    assert detail["session"]["title"] == "BTC 观察"
    assert detail["messages"][0]["content"] == "看看 BTC"
    assert detail["steps"][0]["tool_name"] == "get_market_snapshot"
    assert storage.list_assistant_sessions(kind="agent", limit=10)[0]["session_id"] == session_id


def test_data_storage_can_update_assistant_step_status(tmp_path: Path):
    storage = DataStorage(tmp_path / "market.db")
    session_id = storage.create_assistant_session(title="step update")
    step_id = storage.append_assistant_step(
        session_id,
        step_index=1,
        step_type="tool",
        title="调用工具 get_market_snapshot",
        status="running",
        tool_name="get_market_snapshot",
        input_payload={"inst_id": "BTC-USDT"},
        output_payload={},
    )

    updated = storage.update_assistant_step(
        step_id,
        status="completed",
        output_payload={"summary": {"last": 123.0}},
        error_text="",
    )
    detail = storage.get_assistant_session_detail(session_id)

    assert updated is True
    assert detail is not None
    assert detail["steps"][0]["status"] == "completed"
    assert detail["steps"][0]["output"]["summary"]["last"] == 123.0


@pytest.mark.asyncio
async def test_assistant_orchestrator_runs_tool_call_and_persists_trace(tmp_path: Path):
    storage = DataStorage(tmp_path / "market.db")
    ctx = FakeCtx(storage)
    orchestrator = AssistantOrchestrator(ctx, completion_client=FakeCompletionClient())
    session_id = storage.create_assistant_session(
        title="BTC 分析",
        kind="agent",
        mode="simulated",
        inst_id="BTC-USDT",
        inst_type="SPOT",
    )
    storage.append_assistant_message(session_id, role="user", content="帮我看下 BTC 现在适不适合买")

    result = await orchestrator.run_turn(
        session_id=session_id,
        user_message="帮我看下 BTC 现在适不适合买",
        inst_id="BTC-USDT",
        inst_type="SPOT",
        mode="simulated",
        market_context={"source": "unit-test"},
        max_tool_rounds=3,
    )

    detail = storage.get_assistant_session_detail(session_id)

    assert "先观望" in result["assistant_message"]["content"]
    assert len(result["tool_steps"]) == 1
    assert result["tool_steps"][0]["tool_name"] == "get_market_snapshot"
    assert detail is not None
    assert detail["session"]["status"] == "completed"
    assert any(item["role"] == "tool" for item in detail["messages"])
    assert detail["steps"][0]["status"] == "completed"


@pytest.mark.asyncio
async def test_assistant_orchestrator_marks_session_failed_on_upstream_connect_error(tmp_path: Path):
    storage = DataStorage(tmp_path / "market.db")
    ctx = FakeCtx(storage)
    orchestrator = AssistantOrchestrator(ctx, completion_client=FailingConnectCompletionClient())
    session_id = storage.create_assistant_session(
        title="BTC 分析",
        kind="agent",
        mode="simulated",
        inst_id="BTC-USDT",
        inst_type="SPOT",
    )
    storage.append_assistant_message(session_id, role="user", content="帮我看下 BTC")

    with pytest.raises(AssistantUpstreamConnectionError):
        await orchestrator.run_turn(
            session_id=session_id,
            user_message="帮我看下 BTC",
            inst_id="BTC-USDT",
            inst_type="SPOT",
            mode="simulated",
            market_context={"source": "unit-test"},
            max_tool_rounds=3,
        )

    detail = storage.get_assistant_session_detail(session_id)

    assert detail is not None
    assert detail["session"]["status"] == "failed"
    assert "连接失败" in (detail["session"]["last_error"] or "")


@pytest.mark.asyncio
async def test_assistant_orchestrator_preserves_tool_calls_in_history_for_next_turn(tmp_path: Path):
    storage = DataStorage(tmp_path / "market.db")
    ctx = FakeCtx(storage)
    orchestrator = AssistantOrchestrator(ctx, completion_client=HistoryAwareCompletionClient())
    session_id = storage.create_assistant_session(
        title="BTC 多轮分析",
        kind="agent",
        mode="simulated",
        inst_id="BTC-USDT",
        inst_type="SPOT",
    )
    storage.append_assistant_message(session_id, role="user", content="先做第一轮分析")

    first_result = await orchestrator.run_turn(
        session_id=session_id,
        user_message="先做第一轮分析",
        inst_id="BTC-USDT",
        inst_type="SPOT",
        mode="simulated",
        market_context={"source": "unit-test"},
        max_tool_rounds=3,
    )

    second_result = await orchestrator.run_turn(
        session_id=session_id,
        user_message="再按同样思路复核一次",
        inst_id="BTC-USDT",
        inst_type="SPOT",
        mode="simulated",
        market_context={"source": "unit-test"},
        max_tool_rounds=3,
    )

    detail = storage.get_assistant_session_detail(session_id)

    assert "第一轮分析完成" in first_result["assistant_message"]["content"]
    assert "第二轮分析完成" in second_result["assistant_message"]["content"]
    assert detail is not None
    assistant_messages = [item for item in detail["messages"] if item["role"] == "assistant"]
    assert any((item.get("metadata") or {}).get("tool_calls") for item in assistant_messages)


@pytest.mark.asyncio
async def test_assistant_orchestrator_supports_levels_tool_and_persists_chart_annotations(tmp_path: Path):
    storage = DataStorage(tmp_path / "market.db")
    ctx = FakeCtx(storage)
    orchestrator = AssistantOrchestrator(ctx, completion_client=LevelsCompletionClient())
    session_id = storage.create_assistant_session(
        title="BTC 关键位",
        kind="agent",
        mode="simulated",
        inst_id="BTC-USDT",
        inst_type="SPOT",
    )
    storage.append_assistant_message(session_id, role="user", content="帮我标出当前 BTC 的支撑位和压力位")

    result = await orchestrator.run_turn(
        session_id=session_id,
        user_message="帮我标出当前 BTC 的支撑位和压力位",
        inst_id="BTC-USDT",
        inst_type="SPOT",
        mode="simulated",
        market_context={"source": "unit-test"},
        max_tool_rounds=3,
    )

    assert "已识别关键位" in result["assistant_message"]["content"]
    assert result["tool_steps"][0]["tool_name"] == "detect_support_resistance"
    assert isinstance(result["tool_steps"][0]["output"].get("chart_annotations"), list)


@pytest.mark.asyncio
async def test_assistant_orchestrator_skips_orphan_tool_call_history_in_next_turn(tmp_path: Path):
    storage = DataStorage(tmp_path / "market.db")
    ctx = FakeCtx(storage)
    orphan_call_id = "call-orphan"
    orchestrator = AssistantOrchestrator(
        ctx,
        completion_client=SanitizingHistoryCompletionClient(orphan_call_id),
    )
    session_id = storage.create_assistant_session(
        title="BTC 坏历史",
        kind="agent",
        mode="simulated",
        inst_id="BTC-USDT",
        inst_type="SPOT",
    )
    storage.append_assistant_message(session_id, role="user", content="先做一次分析")
    storage.append_assistant_message(
        session_id,
        role="assistant",
        content="",
        metadata={
            "tool_calls": [
                {
                    "id": orphan_call_id,
                    "type": "function",
                    "function": {
                        "name": "build_risk_budget",
                        "arguments": "{\"inst_id\":\"BTC-USDT\"}",
                    },
                }
            ],
        },
    )

    result = await orchestrator.run_turn(
        session_id=session_id,
        user_message="继续分析",
        inst_id="BTC-USDT",
        inst_type="SPOT",
        mode="simulated",
        market_context={"source": "unit-test"},
        max_tool_rounds=3,
    )

    assert "坏历史已被忽略" in result["assistant_message"]["content"]


@pytest.mark.asyncio
async def test_assistant_orchestrator_persists_error_tool_output_when_tool_execution_fails(
    tmp_path: Path,
    monkeypatch,
):
    storage = DataStorage(tmp_path / "market.db")
    ctx = FakeCtx(storage)
    orchestrator = AssistantOrchestrator(
        ctx,
        completion_client=FailingToolCompletionClient(),
    )
    session_id = storage.create_assistant_session(
        title="BTC 工具失败",
        kind="agent",
        mode="simulated",
        inst_id="BTC-USDT",
        inst_type="SPOT",
    )
    storage.append_assistant_message(session_id, role="user", content="给我一份交易计划")

    def _raise_tool_error(tool_name, arguments):
        raise AssistantOrchestratorError("工具爆炸")

    monkeypatch.setattr(orchestrator, "_execute_tool", _raise_tool_error, raising=True)

    with pytest.raises(AssistantOrchestratorError, match="工具爆炸"):
        await orchestrator.run_turn(
            session_id=session_id,
            user_message="给我一份交易计划",
            inst_id="BTC-USDT",
            inst_type="SPOT",
            mode="simulated",
            market_context={"source": "unit-test"},
            max_tool_rounds=3,
        )

    detail = storage.get_assistant_session_detail(session_id)

    assert detail is not None
    assert detail["session"]["status"] == "failed"
    assert detail["steps"][0]["status"] == "failed"
    tool_messages = [item for item in detail["messages"] if item["role"] == "tool"]
    assert len(tool_messages) == 1
    assert tool_messages[0]["tool_call_id"] == "call-fail"
    payload = json.loads(tool_messages[0]["content"])
    assert payload["error"] == "工具爆炸"
    assert payload["tool_name"] == "build_risk_budget"


def test_assistant_orchestrator_lists_and_dispatches_new_analysis_tools(tmp_path: Path, monkeypatch):
    storage = DataStorage(tmp_path / "market.db")
    ctx = FakeCtx(storage)
    orchestrator = AssistantOrchestrator(ctx, completion_client=FakeCompletionClient())

    tool_names = {
        item["function"]["name"]
        for item in orchestrator.list_tools()
        if item.get("type") == "function"
    }
    assert "build_trade_setup" in tool_names
    assert "analyze_watchlist_correlation" in tool_names
    assert "save_support_resistance_snapshot" in tool_names
    assert "list_support_resistance_snapshots" in tool_names
    assert "list_patrol_runs" in tool_names
    assert "create_order_draft" in tool_names
    assert "list_order_drafts" in tool_names
    assert "confirm_order_draft" in tool_names

    monkeypatch.setattr(
        orchestrator.query_service,
        "build_trade_setup",
        lambda request: {"setup_status": "watch", "inst_id": request.inst_id},
        raising=True,
    )
    monkeypatch.setattr(
        orchestrator.query_service,
        "analyze_watchlist_correlation",
        lambda request: {"symbols": ["BTC-USDT", "ETH-USDT"], "matrix": [[1.0, 0.5], [0.5, 1.0]]},
        raising=True,
    )
    monkeypatch.setattr(
        orchestrator.query_service,
        "save_support_resistance_snapshot",
        lambda request: {"snapshot_id": "snapshot-1", "inst_id": request.inst_id},
        raising=True,
    )
    monkeypatch.setattr(
        orchestrator.query_service,
        "list_level_snapshots",
        lambda request: {"snapshots": [{"snapshot_id": "snapshot-1"}], "count": 1},
        raising=True,
    )
    monkeypatch.setattr(
        orchestrator.query_service,
        "list_patrol_runs",
        lambda request: {"runs": [{"run_id": "run-1"}], "count": 1},
        raising=True,
    )
    monkeypatch.setattr(
        orchestrator.query_service,
        "create_order_draft",
        lambda request: {"draft_id": "draft-1", "status": "draft", "inst_id": request.inst_id},
        raising=True,
    )
    monkeypatch.setattr(
        orchestrator.query_service,
        "list_order_drafts",
        lambda request: {"drafts": [{"draft_id": "draft-1", "status": "draft"}], "count": 1},
        raising=True,
    )
    monkeypatch.setattr(
        orchestrator.query_service,
        "confirm_order_draft",
        lambda request: {"draft_id": request.draft_id, "status": "confirmed", "executed": False},
        raising=True,
    )

    trade_setup = orchestrator._execute_tool("build_trade_setup", {"inst_id": "BTC-USDT"})
    correlation = orchestrator._execute_tool("analyze_watchlist_correlation", {})
    saved_snapshot = orchestrator._execute_tool("save_support_resistance_snapshot", {"inst_id": "BTC-USDT"})
    listed_snapshots = orchestrator._execute_tool("list_support_resistance_snapshots", {"inst_id": "BTC-USDT"})
    listed_runs = orchestrator._execute_tool("list_patrol_runs", {"inst_type": "SWAP"})
    created_draft = orchestrator._execute_tool("create_order_draft", {"inst_id": "BTC-USDT"})
    listed_drafts = orchestrator._execute_tool("list_order_drafts", {"inst_id": "BTC-USDT"})
    confirmed_draft = orchestrator._execute_tool("confirm_order_draft", {"draft_id": "draft-1"})

    assert trade_setup["setup_status"] == "watch"
    assert correlation["symbols"] == ["BTC-USDT", "ETH-USDT"]
    assert saved_snapshot["snapshot_id"] == "snapshot-1"
    assert listed_snapshots["count"] == 1
    assert listed_runs["count"] == 1
    assert created_draft["draft_id"] == "draft-1"
    assert listed_drafts["count"] == 1
    assert confirmed_draft["status"] == "confirmed"
