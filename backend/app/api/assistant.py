"""AI 助手接口。"""

import asyncio
import json
from typing import Any, AsyncIterator, Dict, List

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..agent import AgentQueryService
from ..agent.schemas import (
    AgentLevelSnapshotListRequest,
    AgentLevelSnapshotRequest,
    AgentOrderDraftConfirmRequest,
    AgentOrderDraftListRequest,
    AgentOrderDraftRequest,
    AgentPatrolRunListRequest,
)
from ..assistant_runtime.orchestrator import AssistantOrchestrator, AssistantOrchestratorError
from ..assistant_runtime.schemas import (
    AssistantAgentSessionCreateRequest,
    AssistantAgentTurnRequest,
)
from ..core.app_context import get_app_context
from ..core.assistant_patrol import (
    get_assistant_patrol,
    normalize_assistant_patrol_settings,
)
from ..config import config


router = APIRouter(prefix="/assistant", tags=["AI助手"])


class AssistantMessage(BaseModel):
    """对话消息。"""

    role: str = Field(..., description="消息角色：user/assistant/system")
    content: str = Field(default="", description="消息内容")


class AssistantChatRequest(BaseModel):
    """AI 对话请求。"""

    messages: List[AssistantMessage] = Field(default_factory=list, description="前端当前会话消息")
    market_context: Dict[str, Any] = Field(default_factory=dict, description="当前行情上下文")


class AssistantPatrolConfigRequest(BaseModel):
    """主动巡检配置。"""

    enabled: bool = Field(default=False, description="是否启用后台主动巡检")
    interval_seconds: int = Field(default=300, ge=60, le=3600, description="巡检间隔秒数")
    scan_limit: int = Field(default=24, ge=1, le=200, description="扫描关注币种数量")
    candidate_limit: int = Field(default=3, ge=1, le=20, description="保留候选机会数量")
    inst_type: str = Field(default="SWAP", description="巡检市场类型 SPOT/SWAP")
    timeframes: List[str] = Field(default_factory=lambda: ["1H", "4H"], description="巡检周期列表")
    candles_limit: int = Field(default=240, ge=60, le=2000, description="每周期读取 K 线数量")
    recent_trade_limit: int = Field(default=40, ge=1, le=100, description="逐笔成交读取数量")
    orderbook_depth: int = Field(default=30, ge=1, le=200, description="盘口档位")
    mode: str = Field(default="simulated", description="模拟盘/实盘上下文")
    min_priority_score: float = Field(default=55.0, ge=0.0, le=100.0, description="最低候选分数")
    notification_cooldown_seconds: int = Field(default=900, ge=60, le=86400, description="同一机会重复推送冷却时间")


def _build_sse_payload(payload: Dict[str, Any]) -> str:
    """构造 SSE 数据块。"""

    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _normalize_message_role(role: str) -> str:
    """规范化消息角色。"""

    normalized = (role or "").strip().lower()
    if normalized in {"system", "user", "assistant"}:
        return normalized
    return "user"


def _extract_stream_delta(event: Dict[str, Any]) -> str:
    """从 OpenAI 兼容流式事件中提取文本增量。"""

    chunks: List[str] = []
    for choice in event.get("choices") or []:
        delta = choice.get("delta") or choice.get("message") or {}
        content = delta.get("content")
        if isinstance(content, str) and content:
            chunks.append(content)
            continue
        if isinstance(content, list):
            for item in content:
                if not isinstance(item, dict):
                    continue
                if isinstance(item.get("text"), str) and item["text"]:
                    chunks.append(item["text"])
                    continue
                if isinstance(item.get("value"), str) and item["value"]:
                    chunks.append(item["value"])
    return "".join(chunks)


def _build_upstream_messages(request: AssistantChatRequest) -> List[Dict[str, str]]:
    """构造发给模型的消息列表。"""

    max_messages = max(2, config.ai_assistant.max_context_messages)
    trimmed_messages = [
        {
            "role": _normalize_message_role(message.role),
            "content": (message.content or "").strip(),
        }
        for message in request.messages[-max_messages:]
        if (message.content or "").strip()
    ]

    market_context = request.market_context or {}
    market_context_text = json.dumps(market_context, ensure_ascii=False, separators=(",", ":"))

    return [
        {"role": "system", "content": config.ai_assistant.system_prompt},
        {
            "role": "system",
            "content": (
                "以下是当前行情上下文 JSON。"
                "如果用户询问买卖建议，请严格基于这些数据分析："
                f"{market_context_text}"
            ),
        },
        *trimmed_messages,
    ]


async def _stream_upstream_response(request: AssistantChatRequest) -> AsyncIterator[str]:
    """向上游模型发起流式请求，并转为 SSE 下发给前端。"""

    if not config.ai_assistant.enabled:
        yield _build_sse_payload({
            "type": "error",
            "message": "AI 助手当前未启用。",
        })
        return

    if not config.ai_assistant.is_configured():
        yield _build_sse_payload({
            "type": "error",
            "message": "AI 助手未完成配置，请先在设置页填写 AI Key 和模型参数，或手动更新 config/.env。",
        })
        return

    timeout = httpx.Timeout(
        timeout=float(config.ai_assistant.timeout_seconds),
        connect=15.0,
        read=float(config.ai_assistant.timeout_seconds),
    )
    endpoint = f"{config.ai_assistant.base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {config.ai_assistant.api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": config.ai_assistant.model,
        "messages": _build_upstream_messages(request),
        "stream": True,
        "temperature": config.ai_assistant.temperature,
    }

    yielded_any_delta = False
    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            trust_env=config.ai_assistant.use_env_proxy,
        ) as client:
            async with client.stream("POST", endpoint, headers=headers, json=payload) as response:
                if response.status_code >= 400:
                    error_text = (await response.aread()).decode("utf-8", errors="ignore").strip()
                    yield _build_sse_payload({
                        "type": "error",
                        "message": error_text or f"AI 上游请求失败（HTTP {response.status_code}）",
                    })
                    return

                yield _build_sse_payload({
                    "type": "meta",
                    "provider": config.ai_assistant.provider_name,
                    "model": config.ai_assistant.model,
                })

                async for raw_line in response.aiter_lines():
                    line = (raw_line or "").strip()
                    if not line or not line.startswith("data:"):
                        continue

                    data = line[5:].strip()
                    if not data:
                        continue
                    if data == "[DONE]":
                        break

                    try:
                        event = json.loads(data)
                    except json.JSONDecodeError:
                        continue

                    delta = _extract_stream_delta(event)
                    if not delta:
                        continue

                    yielded_any_delta = True
                    yield _build_sse_payload({
                        "type": "delta",
                        "delta": delta,
                    })

        yield _build_sse_payload({
            "type": "done",
            "has_content": yielded_any_delta,
        })
    except httpx.ConnectError:
        yield _build_sse_payload({
            "type": "error",
            "message": "AI 上游连接失败，请检查网络、Base URL 或代理设置。",
        })
    except httpx.TimeoutException:
        yield _build_sse_payload({
            "type": "error",
            "message": "AI 请求超时，请稍后重试。",
        })
    except httpx.RequestError as exc:
        yield _build_sse_payload({
            "type": "error",
            "message": f"AI 上游请求失败，请检查网络链路：{exc.__class__.__name__}",
        })
    except Exception as exc:
        yield _build_sse_payload({
            "type": "error",
            "message": f"AI 助手请求失败: {exc}",
        })


@router.get("/status")
async def get_assistant_status() -> Dict[str, Any]:
    """获取 AI 助手状态。"""

    return {
        "enabled": config.ai_assistant.enabled,
        "configured": config.ai_assistant.is_configured(),
        "provider": config.ai_assistant.provider_name,
        "model": config.ai_assistant.model,
    }


@router.post("/chat/stream")
async def stream_chat(request: AssistantChatRequest):
    """流式对话接口。"""

    if not request.messages:
        raise HTTPException(status_code=400, detail="消息列表不能为空")

    return StreamingResponse(
        _stream_upstream_response(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _get_orchestrator() -> AssistantOrchestrator:
    return AssistantOrchestrator(get_app_context())


def _get_query_service() -> AgentQueryService:
    return AgentQueryService(get_app_context())


def _get_patrol_service():
    return get_assistant_patrol(get_app_context())


def _map_query_error(exc: Exception) -> HTTPException:
    detail = str(exc)
    if "未找到" in detail:
        return HTTPException(status_code=404, detail=detail)
    return HTTPException(status_code=400, detail=detail)


@router.get("/agent/tools")
async def list_agent_tools() -> Dict[str, Any]:
    """返回 AI 编排器可调用工具。"""

    orchestrator = _get_orchestrator()
    return {
        "tools": orchestrator.list_tools(),
        "enabled": config.ai_assistant.enabled,
        "configured": config.ai_assistant.is_configured(),
    }


@router.get("/agent/order-drafts")
async def list_agent_order_drafts(
    session_id: str = "",
    inst_id: str = "",
    status: str = "",
    limit: int = 30,
) -> Dict[str, Any]:
    """查询订单草案列表。"""

    service = _get_query_service()
    request = AgentOrderDraftListRequest(
        session_id=session_id,
        inst_id=inst_id,
        status=status,
        limit=limit,
    )
    try:
        result = await asyncio.to_thread(service.list_order_drafts, request)
    except Exception as exc:
        raise _map_query_error(exc)
    return {"data": result}


@router.post("/agent/order-drafts")
async def create_agent_order_draft(request: AgentOrderDraftRequest) -> Dict[str, Any]:
    """生成待确认订单草案。"""

    service = _get_query_service()
    try:
        result = await asyncio.to_thread(service.create_order_draft, request)
    except Exception as exc:
        raise _map_query_error(exc)
    return {"data": result}


@router.get("/agent/order-drafts/{draft_id}")
async def get_agent_order_draft(draft_id: str) -> Dict[str, Any]:
    """读取单个订单草案。"""

    service = _get_query_service()
    try:
        result = await asyncio.to_thread(service.get_order_draft, draft_id)
    except Exception as exc:
        raise _map_query_error(exc)
    return {"data": result}


@router.post("/agent/order-drafts/{draft_id}/confirm")
async def confirm_agent_order_draft(draft_id: str) -> Dict[str, Any]:
    """确认订单草案。仅更新草案状态，不会自动下单。"""

    service = _get_query_service()
    try:
        result = await asyncio.to_thread(
            service.confirm_order_draft,
            AgentOrderDraftConfirmRequest(draft_id=draft_id),
        )
    except Exception as exc:
        raise _map_query_error(exc)
    return {"data": result}


@router.get("/agent/level-snapshots")
async def list_agent_level_snapshots(
    session_id: str = "",
    inst_id: str = "",
    source: str = "",
    limit: int = 30,
) -> Dict[str, Any]:
    """查询关键位快照列表。"""

    service = _get_query_service()
    request = AgentLevelSnapshotListRequest(
        session_id=session_id,
        inst_id=inst_id,
        source=source,
        limit=limit,
    )
    try:
        result = await asyncio.to_thread(service.list_level_snapshots, request)
    except Exception as exc:
        raise _map_query_error(exc)
    return {"data": result}


@router.post("/agent/level-snapshots")
async def create_agent_level_snapshot(request: AgentLevelSnapshotRequest) -> Dict[str, Any]:
    """保存当前关键位分析快照。"""

    service = _get_query_service()
    try:
        result = await asyncio.to_thread(service.save_support_resistance_snapshot, request)
    except Exception as exc:
        raise _map_query_error(exc)
    return {"data": result}


@router.get("/agent/level-snapshots/{snapshot_id}")
async def get_agent_level_snapshot(snapshot_id: str) -> Dict[str, Any]:
    """读取单个关键位快照。"""

    service = _get_query_service()
    try:
        result = await asyncio.to_thread(service.get_level_snapshot, snapshot_id)
    except Exception as exc:
        raise _map_query_error(exc)
    return {"data": result}


@router.get("/agent/patrol/status")
async def get_agent_patrol_status() -> Dict[str, Any]:
    """获取后台主动巡检状态。"""

    service = _get_patrol_service()
    return {"data": service.get_status()}


@router.get("/agent/patrol/config")
async def get_agent_patrol_config() -> Dict[str, Any]:
    """获取后台主动巡检配置。"""

    service = _get_patrol_service()
    return {"data": service.get_settings()}


@router.put("/agent/patrol/config")
async def update_agent_patrol_config(request: AssistantPatrolConfigRequest) -> Dict[str, Any]:
    """更新后台主动巡检配置。"""

    service = _get_patrol_service()
    settings = normalize_assistant_patrol_settings(request.model_dump())
    applied = service.apply_settings(settings, persist=True)
    return {
        "data": applied,
        "status": service.get_status(),
    }


@router.post("/agent/patrol/run-now")
async def run_agent_patrol_now() -> Dict[str, Any]:
    """立即执行一轮主动巡检。"""

    service = _get_patrol_service()
    result = await service.run_now()
    return {"data": result}


@router.get("/agent/patrol/runs")
async def list_agent_patrol_runs(
    inst_type: str = "",
    mode: str = "",
    trigger: str = "",
    limit: int = 30,
) -> Dict[str, Any]:
    """查询巡检运行记录列表。"""

    service = _get_query_service()
    request = AgentPatrolRunListRequest(
        inst_type=inst_type,
        mode=mode,
        trigger=trigger,
        limit=limit,
    )
    try:
        result = await asyncio.to_thread(service.list_patrol_runs, request)
    except Exception as exc:
        raise _map_query_error(exc)
    return {"data": result}


@router.get("/agent/patrol/runs/{run_id}")
async def get_agent_patrol_run(run_id: str) -> Dict[str, Any]:
    """读取单个巡检运行记录。"""

    service = _get_query_service()
    try:
        result = await asyncio.to_thread(service.get_patrol_run, run_id)
    except Exception as exc:
        raise _map_query_error(exc)
    return {"data": result}


@router.get("/agent/sessions")
async def list_agent_sessions(limit: int = 30) -> Dict[str, Any]:
    """列出 AI 分析会话。"""

    storage = get_app_context().storage()
    return {
        "data": storage.list_assistant_sessions(kind="agent", limit=max(int(limit), 1)),
    }


@router.post("/agent/sessions")
async def create_agent_session(request: AssistantAgentSessionCreateRequest) -> Dict[str, Any]:
    """创建新的 AI 分析会话。"""

    storage = get_app_context().storage()
    session_id = storage.create_assistant_session(
        title=request.title,
        kind="agent",
        mode=request.mode.value,
        inst_id=request.inst_id,
        inst_type=request.inst_type.value,
        metadata=request.metadata,
    )
    return {
        "data": storage.get_assistant_session(session_id),
    }


@router.get("/agent/sessions/{session_id}")
async def get_agent_session_detail(session_id: str) -> Dict[str, Any]:
    """获取单个 AI 分析会话详情。"""

    storage = get_app_context().storage()
    detail = storage.get_assistant_session_detail(session_id)
    if not detail:
        raise HTTPException(status_code=404, detail=f"未找到会话 {session_id}")
    return {"data": detail}


async def _stream_agent_chat_response(
    request: AssistantAgentTurnRequest,
) -> AsyncIterator[str]:
    storage = get_app_context().storage()
    session_id = (request.session_id or "").strip()
    session = storage.get_assistant_session(session_id) if session_id else None

    if session_id and not session:
        yield _build_sse_payload({
            "type": "error",
            "message": f"未找到会话 {session_id}",
        })
        return

    if not session:
        title = (request.title or "").strip() or (request.message.strip()[:24])
        session_id = storage.create_assistant_session(
            title=title,
            kind="agent",
            mode=request.mode.value,
            inst_id=request.inst_id,
            inst_type=request.inst_type.value,
            metadata={
                "market_context": request.market_context,
            },
        )
        session = storage.get_assistant_session(session_id)

    storage.append_assistant_message(
        session_id,
        role="user",
        content=request.message,
        metadata={
            "market_context": request.market_context,
        },
    )

    orchestrator = _get_orchestrator()
    queue: asyncio.Queue[Dict[str, Any] | None] = asyncio.Queue()

    async def _push_delta(delta: str) -> None:
        await queue.put({
            "type": "delta",
            "delta": delta,
        })

    async def _runner() -> None:
        try:
            result = await orchestrator.run_turn_stream(
                session_id=session_id,
                user_message=request.message,
                inst_id=request.inst_id or (session or {}).get("inst_id", ""),
                inst_type=request.inst_type.value or (session or {}).get("inst_type", "SPOT"),
                mode=request.mode.value or (session or {}).get("mode", "simulated"),
                market_context=request.market_context,
                max_tool_rounds=request.max_tool_rounds,
                on_delta=_push_delta,
            )
            await queue.put({
                "type": "done",
                "session_id": session_id,
                "assistant_message": result["assistant_message"],
            })
        except AssistantOrchestratorError as exc:
            await queue.put({
                "type": "error",
                "message": str(exc),
                "status_code": getattr(exc, "status_code", 400),
                "session_id": session_id,
            })
        finally:
            await queue.put(None)

    task = asyncio.create_task(_runner())
    try:
        yield _build_sse_payload({
            "type": "meta",
            "session_id": session_id,
            "provider": config.ai_assistant.provider_name,
            "model": config.ai_assistant.model,
        })
        while True:
            event = await queue.get()
            if event is None:
                break
            yield _build_sse_payload(event)
    except asyncio.CancelledError:
        task.cancel()
        raise
    finally:
        if not task.done():
            task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        except Exception:
            pass


@router.post("/agent/chat")
async def run_agent_chat(request: AssistantAgentTurnRequest) -> Dict[str, Any]:
    """执行一轮可调用工具的 AI 分析对话。"""

    storage = get_app_context().storage()
    session_id = (request.session_id or "").strip()
    session = storage.get_assistant_session(session_id) if session_id else None

    if session_id and not session:
        raise HTTPException(status_code=404, detail=f"未找到会话 {session_id}")

    if not session:
        title = (request.title or "").strip() or (request.message.strip()[:24])
        session_id = storage.create_assistant_session(
            title=title,
            kind="agent",
            mode=request.mode.value,
            inst_id=request.inst_id,
            inst_type=request.inst_type.value,
            metadata={
                "market_context": request.market_context,
            },
        )
        session = storage.get_assistant_session(session_id)

    storage.append_assistant_message(
        session_id,
        role="user",
        content=request.message,
        metadata={
            "market_context": request.market_context,
        },
    )

    orchestrator = _get_orchestrator()
    try:
        result = await orchestrator.run_turn(
            session_id=session_id,
            user_message=request.message,
            inst_id=request.inst_id or (session or {}).get("inst_id", ""),
            inst_type=request.inst_type.value or (session or {}).get("inst_type", "SPOT"),
            mode=request.mode.value or (session or {}).get("mode", "simulated"),
            market_context=request.market_context,
            max_tool_rounds=request.max_tool_rounds,
        )
    except AssistantOrchestratorError as exc:
        raise HTTPException(status_code=getattr(exc, "status_code", 400), detail=str(exc))

    detail = storage.get_assistant_session_detail(session_id)
    return {
        "data": {
            "session_id": session_id,
            "assistant_message": result["assistant_message"],
            "tool_steps": result["tool_steps"],
            "session": result["session"],
            "detail": detail,
        }
    }


@router.post("/agent/chat/stream")
async def run_agent_chat_stream(request: AssistantAgentTurnRequest):
    """执行一轮带流式输出的 AI 分析对话。"""

    return StreamingResponse(
        _stream_agent_chat_response(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
