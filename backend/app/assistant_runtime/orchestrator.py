from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List, Optional, Sequence

import httpx

from ..agent import (
    AgentQueryService,
    MarketAnalysisError,
    MarketAnalysisSecurityError,
    MarketAnalysisTimeoutError,
    run_market_analysis,
)
from ..agent.schemas import (
    AgentAlignmentQueryRequest,
    AgentCandleQueryRequest,
    AgentCorrelationQueryRequest,
    AgentDataHealthQueryRequest,
    AgentIndicatorQueryRequest,
    AgentLevelSnapshotListRequest,
    AgentLevelSnapshotRequest,
    AgentMarketStructureRequest,
    AgentMarketQueryRequest,
    AgentOpportunityPatrolRequest,
    AgentOrderBookQueryRequest,
    AgentOrderDraftConfirmRequest,
    AgentOrderDraftListRequest,
    AgentOrderDraftRequest,
    AgentPatrolRunListRequest,
    AgentPositionQueryRequest,
    AgentPriceProjectionRequest,
    AgentPythonAnalysisRequest,
    AgentRiskBudgetRequest,
    AgentRecentTradesQueryRequest,
    AgentSupportResistanceRequest,
    AgentTradeSetupRequest,
    AgentTradingContextRequest,
    AgentWatchlistScanRequest,
)
from ..config import config
from ..core.app_context import AppContext
from .stream_helpers import (
    _append_stream_tool_call_buffer,
    _extract_text_content,
    _finalize_stream_tool_calls,
    _maybe_emit_stream_delta,
    _sanitize_completion_history,
    _should_fallback_streaming,
)


class AssistantOrchestratorError(RuntimeError):
    """AI 助手编排失败。"""

    status_code = 400

    def __init__(self, message: str, *, status_code: Optional[int] = None):
        super().__init__(message)
        if status_code is not None:
            self.status_code = int(status_code)


class AssistantUpstreamError(AssistantOrchestratorError):
    """AI 上游服务失败。"""

    status_code = 502


class AssistantUpstreamConnectionError(AssistantUpstreamError):
    """AI 上游连接失败。"""

    status_code = 503


class AssistantUpstreamTimeoutError(AssistantUpstreamError):
    """AI 上游超时。"""

    status_code = 504


class AssistantUpstreamResponseError(AssistantUpstreamError):
    """AI 上游返回异常 HTTP 状态。"""

    status_code = 502


@dataclass
class AssistantUpstreamClient:
    """OpenAI 兼容上游客户端。"""

    def _build_request_payload(
        self,
        *,
        messages: Sequence[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: Optional[float] = None,
        stream: bool = False,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "model": config.ai_assistant.model,
            "messages": list(messages),
            "temperature": config.ai_assistant.temperature if temperature is None else temperature,
            "stream": stream,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        return payload

    def _build_http_context(self) -> tuple[httpx.Timeout, str, Dict[str, str]]:
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
        return timeout, endpoint, headers

    async def complete(
        self,
        *,
        messages: Sequence[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: Optional[float] = None,
    ) -> Dict[str, Any]:
        if not config.ai_assistant.enabled:
            raise AssistantOrchestratorError("AI 助手当前未启用")
        if not config.ai_assistant.is_configured():
            raise AssistantOrchestratorError("AI 助手未完成配置")

        timeout, endpoint, headers = self._build_http_context()
        payload = self._build_request_payload(
            messages=messages,
            tools=tools,
            temperature=temperature,
            stream=False,
        )
        try:
            async with httpx.AsyncClient(
                timeout=timeout,
                trust_env=config.ai_assistant.use_env_proxy,
            ) as client:
                response = await client.post(endpoint, headers=headers, json=payload)
                if response.status_code >= 400:
                    detail = response.text.strip() or f"HTTP {response.status_code}"
                    if len(detail) > 300:
                        detail = f"{detail[:300]}..."
                    raise AssistantUpstreamResponseError(
                        f"AI 上游请求失败（HTTP {response.status_code}）: {detail}",
                    )
                return response.json()
        except httpx.ConnectError as exc:
            raise AssistantUpstreamConnectionError(
                "AI 上游连接失败，请检查网络、Base URL 或代理设置。",
            ) from exc
        except httpx.TimeoutException as exc:
            raise AssistantUpstreamTimeoutError(
                "AI 上游请求超时，请稍后重试。",
            ) from exc
        except httpx.RequestError as exc:
            raise AssistantUpstreamConnectionError(
                f"AI 上游请求失败，请检查网络链路：{exc.__class__.__name__}",
            ) from exc

    async def stream_complete(
        self,
        *,
        messages: Sequence[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: Optional[float] = None,
        on_delta: Optional[Callable[[str], Awaitable[None] | None]] = None,
    ) -> Dict[str, Any]:
        if not config.ai_assistant.enabled:
            raise AssistantOrchestratorError("AI 助手当前未启用")
        if not config.ai_assistant.is_configured():
            raise AssistantOrchestratorError("AI 助手未完成配置")

        timeout, endpoint, headers = self._build_http_context()
        payload = self._build_request_payload(
            messages=messages,
            tools=tools,
            temperature=temperature,
            stream=True,
        )

        try:
            async with httpx.AsyncClient(
                timeout=timeout,
                trust_env=config.ai_assistant.use_env_proxy,
            ) as client:
                async with client.stream("POST", endpoint, headers=headers, json=payload) as response:
                    if response.status_code >= 400:
                        detail = (await response.aread()).decode("utf-8", errors="ignore").strip()
                        if _should_fallback_streaming(response.status_code, detail):
                            fallback_completion = await self.complete(
                                messages=messages,
                                tools=tools,
                                temperature=temperature,
                            )
                            fallback_message = (((fallback_completion.get("choices") or [{}])[0]) or {}).get("message") or {}
                            await _maybe_emit_stream_delta(on_delta, _extract_text_content(fallback_message.get("content")))
                            return fallback_completion
                        if len(detail) > 300:
                            detail = f"{detail[:300]}..."
                        raise AssistantUpstreamResponseError(
                            f"AI 上游请求失败（HTTP {response.status_code}）: {detail or f'HTTP {response.status_code}'}",
                        )

                    content_type = (response.headers.get("content-type") or "").lower()
                    if "text/event-stream" not in content_type:
                        raw_body = await response.aread()
                        try:
                            payload_json = json.loads(raw_body.decode("utf-8", errors="ignore") or "{}")
                        except Exception as exc:
                            raise AssistantUpstreamResponseError("AI 上游响应格式无法识别") from exc
                        full_message = (((payload_json.get("choices") or [{}])[0]) or {}).get("message") or {}
                        await _maybe_emit_stream_delta(on_delta, _extract_text_content(full_message.get("content")))
                        return payload_json

                    accumulated_content = ""
                    accumulated_tool_calls: List[Dict[str, Any]] = []
                    usage: Dict[str, Any] = {}
                    finish_reason = ""

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

                        if isinstance(event.get("usage"), dict):
                            usage = event["usage"]

                        for choice in event.get("choices") or []:
                            delta = choice.get("delta") or choice.get("message") or {}
                            delta_text = _extract_text_content(delta.get("content"))
                            if delta_text:
                                accumulated_content = f"{accumulated_content}{delta_text}"
                                await _maybe_emit_stream_delta(on_delta, delta_text)
                            _append_stream_tool_call_buffer(
                                accumulated_tool_calls,
                                delta.get("tool_calls"),
                            )
                            if isinstance(choice.get("finish_reason"), str) and choice["finish_reason"]:
                                finish_reason = choice["finish_reason"]

                    message_payload: Dict[str, Any] = {
                        "role": "assistant",
                        "content": accumulated_content,
                    }
                    finalized_tool_calls = _finalize_stream_tool_calls(accumulated_tool_calls)
                    if finalized_tool_calls:
                        message_payload["tool_calls"] = finalized_tool_calls

                    return {
                        "choices": [
                            {
                                "message": message_payload,
                                "finish_reason": finish_reason or ("tool_calls" if finalized_tool_calls else "stop"),
                            }
                        ],
                        "usage": usage,
                    }
        except httpx.ConnectError as exc:
            raise AssistantUpstreamConnectionError(
                "AI 上游连接失败，请检查网络、Base URL 或代理设置。",
            ) from exc
        except httpx.TimeoutException as exc:
            raise AssistantUpstreamTimeoutError(
                "AI 上游请求超时，请稍后重试。",
            ) from exc
        except httpx.RequestError as exc:
            raise AssistantUpstreamConnectionError(
                f"AI 上游请求失败，请检查网络链路：{exc.__class__.__name__}",
            ) from exc


class AssistantOrchestrator:
    """把 LLM 对话和 agent 工具层编排到一起。"""

    def __init__(
        self,
        ctx: AppContext,
        *,
        completion_client: Optional[AssistantUpstreamClient] = None,
    ):
        self.ctx = ctx
        self.query_service = AgentQueryService(ctx)
        self.completion_client = completion_client or AssistantUpstreamClient()
        self.storage = ctx.storage()

    def list_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "get_market_snapshot",
                    "description": "读取单个交易对的最新行情快照",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "inst_id": {"type": "string"},
                            "inst_type": {"type": "string", "enum": ["SPOT", "SWAP", "FUTURES", "OPTION"]},
                        },
                        "required": ["inst_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_multi_timeframe_candles",
                    "description": "读取多周期 K 线数据",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "inst_id": {"type": "string"},
                            "inst_type": {"type": "string", "enum": ["SPOT", "SWAP", "FUTURES", "OPTION"]},
                            "timeframes": {"type": "array", "items": {"type": "string"}},
                            "limit": {"type": "integer", "minimum": 20, "maximum": 5000},
                        },
                        "required": ["inst_id", "timeframes"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_indicator_snapshot",
                    "description": "基于 K 线计算结构化指标快照",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "inst_id": {"type": "string"},
                            "inst_type": {"type": "string", "enum": ["SPOT", "SWAP", "FUTURES", "OPTION"]},
                            "timeframe": {"type": "string"},
                            "indicators": {"type": "array", "items": {"type": "string"}},
                            "limit": {"type": "integer", "minimum": 20, "maximum": 5000},
                        },
                        "required": ["inst_id", "timeframe", "indicators"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_trading_context",
                    "description": "聚合单个交易对的行情、K线、指标、盘口、逐笔、持仓与数据健康度",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "inst_id": {"type": "string"},
                            "inst_type": {"type": "string", "enum": ["SPOT", "SWAP", "FUTURES", "OPTION"]},
                            "timeframes": {"type": "array", "items": {"type": "string"}},
                            "candles_limit": {"type": "integer", "minimum": 20, "maximum": 5000},
                            "indicators": {"type": "array", "items": {"type": "string"}},
                            "include_orderbook": {"type": "boolean"},
                            "orderbook_depth": {"type": "integer", "minimum": 1, "maximum": 500},
                            "include_recent_trades": {"type": "boolean"},
                            "recent_trade_limit": {"type": "integer", "minimum": 1, "maximum": 100},
                            "include_position": {"type": "boolean"},
                            "mode": {"type": "string", "enum": ["simulated", "live"]},
                        },
                        "required": ["inst_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_orderbook_snapshot",
                    "description": "读取盘口深度快照",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "inst_id": {"type": "string"},
                            "inst_type": {"type": "string", "enum": ["SPOT", "SWAP", "FUTURES", "OPTION"]},
                            "depth": {"type": "integer", "minimum": 1, "maximum": 500},
                        },
                        "required": ["inst_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "scan_watchlist_context",
                    "description": "批量扫描关注币种并返回趋势、异动与数据健康概览",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "inst_type": {"type": "string", "enum": ["SPOT", "SWAP"]},
                            "limit": {"type": "integer", "minimum": 1, "maximum": 200},
                            "timeframes": {"type": "array", "items": {"type": "string"}},
                            "candles_limit": {"type": "integer", "minimum": 20, "maximum": 2000},
                            "include_orderbook": {"type": "boolean"},
                            "orderbook_depth": {"type": "integer", "minimum": 1, "maximum": 200},
                            "sort_by": {"type": "string", "enum": ["signal_score", "change_24h", "volume_24h"]},
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_data_health",
                    "description": "读取本地数据库库存覆盖、同步新鲜度、缺失周期和守护器状态",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "symbol": {"type": "string"},
                            "include_orphans": {"type": "boolean"},
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_recent_trades_snapshot",
                    "description": "读取最新逐笔成交快照",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "inst_id": {"type": "string"},
                            "inst_type": {"type": "string", "enum": ["SPOT", "SWAP", "FUTURES", "OPTION"]},
                            "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                        },
                        "required": ["inst_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_position_snapshot",
                    "description": "读取账户持仓基础快照",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "mode": {"type": "string", "enum": ["simulated", "live"]},
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "analyze_multi_timeframe_alignment",
                    "description": "分析多个周期的趋势一致性、冲突周期与置信度",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "inst_id": {"type": "string"},
                            "inst_type": {"type": "string", "enum": ["SPOT", "SWAP", "FUTURES", "OPTION"]},
                            "timeframes": {"type": "array", "items": {"type": "string"}},
                            "limit": {"type": "integer", "minimum": 20, "maximum": 5000},
                        },
                        "required": ["inst_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "analyze_market_structure",
                    "description": "输出结构化市场分析，覆盖趋势、波动、量能、盘口、风险与结论",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "inst_id": {"type": "string"},
                            "inst_type": {"type": "string", "enum": ["SPOT", "SWAP", "FUTURES", "OPTION"]},
                            "timeframes": {"type": "array", "items": {"type": "string"}},
                            "limit": {"type": "integer", "minimum": 20, "maximum": 5000},
                            "orderbook_depth": {"type": "integer", "minimum": 1, "maximum": 500},
                            "recent_trade_limit": {"type": "integer", "minimum": 1, "maximum": 100},
                            "mode": {"type": "string", "enum": ["simulated", "live"]},
                        },
                        "required": ["inst_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "detect_support_resistance",
                    "description": "识别当前支撑位、压力位和失效位，并返回可叠加到图表的关键位标记",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "inst_id": {"type": "string"},
                            "inst_type": {"type": "string", "enum": ["SPOT", "SWAP", "FUTURES", "OPTION"]},
                            "timeframes": {"type": "array", "items": {"type": "string"}},
                            "limit": {"type": "integer", "minimum": 60, "maximum": 5000},
                            "max_levels_per_side": {"type": "integer", "minimum": 1, "maximum": 8},
                            "cluster_tolerance_bps": {"type": "number", "minimum": 1, "maximum": 500},
                        },
                        "required": ["inst_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "save_support_resistance_snapshot",
                    "description": "把当前关键位分析保存为快照，便于后续复盘、对比或重新加载到图表",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "session_id": {"type": "string"},
                            "source": {"type": "string"},
                            "title": {"type": "string"},
                            "note": {"type": "string"},
                            "inst_id": {"type": "string"},
                            "inst_type": {"type": "string", "enum": ["SPOT", "SWAP", "FUTURES", "OPTION"]},
                            "timeframes": {"type": "array", "items": {"type": "string"}},
                            "limit": {"type": "integer", "minimum": 60, "maximum": 5000},
                            "max_levels_per_side": {"type": "integer", "minimum": 1, "maximum": 8},
                            "cluster_tolerance_bps": {"type": "number", "minimum": 1, "maximum": 500},
                            "auto_sync": {"type": "boolean"},
                        },
                        "required": ["inst_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "list_support_resistance_snapshots",
                    "description": "读取已保存的关键位快照列表",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "session_id": {"type": "string"},
                            "inst_id": {"type": "string"},
                            "source": {"type": "string"},
                            "limit": {"type": "integer", "minimum": 1, "maximum": 200},
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "generate_price_projection",
                    "description": "生成未来一段时间的启发式价格路径推演，并返回可叠加到图表的预测线",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "inst_id": {"type": "string"},
                            "inst_type": {"type": "string", "enum": ["SPOT", "SWAP", "FUTURES", "OPTION"]},
                            "timeframe": {"type": "string"},
                            "limit": {"type": "integer", "minimum": 60, "maximum": 5000},
                            "horizon_bars": {"type": "integer", "minimum": 3, "maximum": 240},
                        },
                        "required": ["inst_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "patrol_market_opportunities",
                    "description": "主动巡检关注币种并返回候选机会、理由、关键位和优先级",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "inst_type": {"type": "string", "enum": ["SPOT", "SWAP"]},
                            "scan_limit": {"type": "integer", "minimum": 1, "maximum": 200},
                            "candidate_limit": {"type": "integer", "minimum": 1, "maximum": 20},
                            "timeframes": {"type": "array", "items": {"type": "string"}},
                            "candles_limit": {"type": "integer", "minimum": 60, "maximum": 2000},
                            "recent_trade_limit": {"type": "integer", "minimum": 1, "maximum": 100},
                            "orderbook_depth": {"type": "integer", "minimum": 1, "maximum": 200},
                            "mode": {"type": "string", "enum": ["simulated", "live"]},
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "list_patrol_runs",
                    "description": "读取已保存的巡检运行记录，查看历史候选机会和巡检摘要",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "inst_type": {"type": "string"},
                            "mode": {"type": "string", "enum": ["simulated", "live"]},
                            "trigger": {"type": "string", "enum": ["scheduled", "manual"]},
                            "limit": {"type": "integer", "minimum": 1, "maximum": 200},
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "build_risk_budget",
                    "description": "结合账户权益和风控配置，计算可承受的建议仓位预算，并可选评估拟下单规模",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "inst_id": {"type": "string"},
                            "inst_type": {"type": "string", "enum": ["SPOT", "SWAP", "FUTURES", "OPTION"]},
                            "mode": {"type": "string", "enum": ["simulated", "live"]},
                            "side": {"type": "string", "enum": ["buy", "sell"]},
                            "entry_price": {"type": "number"},
                            "stop_loss_ratio": {"type": "number", "minimum": 0, "maximum": 1},
                            "max_single_loss_ratio": {"type": "number", "minimum": 0, "maximum": 1},
                            "max_total_position_ratio": {"type": "number", "minimum": 0, "maximum": 10},
                            "proposed_size": {"type": "number", "minimum": 0},
                        },
                        "required": ["inst_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "build_trade_setup",
                    "description": "把结构、关键位、未来路径推演和风险预算整合成单标的交易计划，并返回可叠加图表的标记",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "inst_id": {"type": "string"},
                            "inst_type": {"type": "string", "enum": ["SPOT", "SWAP", "FUTURES", "OPTION"]},
                            "mode": {"type": "string", "enum": ["simulated", "live"]},
                            "side_preference": {"type": "string", "enum": ["auto", "buy", "sell"]},
                            "structure_timeframes": {"type": "array", "items": {"type": "string"}},
                            "level_timeframes": {"type": "array", "items": {"type": "string"}},
                            "projection_timeframe": {"type": "string"},
                            "candles_limit": {"type": "integer", "minimum": 60, "maximum": 5000},
                            "orderbook_depth": {"type": "integer", "minimum": 1, "maximum": 500},
                            "recent_trade_limit": {"type": "integer", "minimum": 1, "maximum": 100},
                            "stop_loss_ratio": {"type": "number", "minimum": 0, "maximum": 1},
                        },
                        "required": ["inst_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "analyze_watchlist_correlation",
                    "description": "计算关注币种或指定币种列表之间的收益率相关性，辅助分散风险和组合配置",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "symbols": {"type": "array", "items": {"type": "string"}},
                            "inst_type": {"type": "string", "enum": ["SPOT", "SWAP", "FUTURES", "OPTION"]},
                            "timeframe": {"type": "string"},
                            "limit": {"type": "integer", "minimum": 20, "maximum": 5000},
                            "use_watchlist_if_empty": {"type": "boolean"},
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "create_order_draft",
                    "description": "基于当前标的交易计划和风险预算生成待确认订单草案，只保存草案，不会真实下单",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "session_id": {"type": "string"},
                            "inst_id": {"type": "string"},
                            "inst_type": {"type": "string", "enum": ["SPOT", "SWAP", "FUTURES", "OPTION"]},
                            "mode": {"type": "string", "enum": ["simulated", "live"]},
                            "side_preference": {"type": "string", "enum": ["auto", "buy", "sell"]},
                            "order_type": {"type": "string", "enum": ["limit", "market"]},
                            "td_mode": {"type": "string"},
                            "pos_side": {"type": "string"},
                            "reduce_only": {"type": "boolean"},
                            "size": {"type": "number", "minimum": 0},
                            "price": {"type": "number", "minimum": 0},
                            "stop_loss_ratio": {"type": "number", "minimum": 0, "maximum": 1},
                            "title": {"type": "string"},
                            "note": {"type": "string"},
                            "auto_sync": {"type": "boolean"},
                        },
                        "required": ["inst_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "list_order_drafts",
                    "description": "读取当前会话或指定标的的订单草案列表",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "session_id": {"type": "string"},
                            "inst_id": {"type": "string"},
                            "status": {"type": "string", "enum": ["draft", "confirmed", "cancelled"]},
                            "limit": {"type": "integer", "minimum": 1, "maximum": 200},
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "confirm_order_draft",
                    "description": "将订单草案标记为已确认，仍不会自动下单，只更新草案状态",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "draft_id": {"type": "string"},
                        },
                        "required": ["draft_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "run_python_market_analysis",
                    "description": "编写并执行受限 Python 分析代码，适合做数据筛选、统计和自定义逻辑验证",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "goal": {"type": "string"},
                            "inst_id": {"type": "string"},
                            "inst_type": {"type": "string", "enum": ["SPOT", "SWAP", "FUTURES", "OPTION"]},
                            "timeframes": {"type": "array", "items": {"type": "string"}},
                            "candles_limit": {"type": "integer", "minimum": 20, "maximum": 5000},
                            "indicators": {"type": "array", "items": {"type": "string"}},
                            "include_orderbook": {"type": "boolean"},
                            "include_recent_trades": {"type": "boolean"},
                            "include_position": {"type": "boolean"},
                            "mode": {"type": "string", "enum": ["simulated", "live"]},
                            "code": {"type": "string"},
                        },
                        "required": ["inst_id", "timeframes", "code"],
                    },
                },
            },
        ]

    def _build_system_prompt(self, *, inst_id: str, inst_type: str, mode: str, market_context: Dict[str, Any]) -> str:
        context_text = json.dumps(market_context or {}, ensure_ascii=False, separators=(",", ":"))
        return (
            f"{config.ai_assistant.system_prompt}\n"
            "你当前运行在交易分析编排模式。\n"
            "规则：\n"
            "1. 优先使用工具获取数据，再给结论。\n"
            "2. 不能调用任何交易执行能力，也不能假装已经下单。\n"
            "3. 如果数据不足，明确指出缺失项。\n"
            "4. 单标的优先使用 get_trading_context；关注列表筛选优先使用 scan_watchlist_context。\n"
            "5. 需要解释多周期趋势时优先使用 analyze_multi_timeframe_alignment 或 analyze_market_structure。\n"
            "6. 需要关键位时优先使用 detect_support_resistance；需要未来路径推演时优先使用 generate_price_projection。\n"
            "7. 需要主动找机会时优先使用 patrol_market_opportunities。\n"
            "8. 需要仓位建议时优先使用 build_risk_budget，不要自行臆造仓位数字。\n"
            "9. 需要把单标的结论落成可执行计划时，优先使用 build_trade_setup。\n"
            "10. 需要做组合/关注列表分散分析时，优先使用 analyze_watchlist_correlation。\n"
            "11. 只有当用户明确要求“保存关键位”时，才调用 save_support_resistance_snapshot。\n"
            "12. 当用户要求查看历史巡检结果或候选机会回顾时，优先使用 list_patrol_runs。\n"
            "13. 只有当用户明确要求“生成草案”“保存草案”“确认草案”时，才调用 create_order_draft / confirm_order_draft。\n"
            "14. 订单草案不是下单，任何情况下都不能声称已经成交或已执行交易。\n"
            "15. 当普通查询不够时，可以调用 run_python_market_analysis 编写简短分析代码。\n"
            "16. 最终回答默认使用这四段：结论、依据、风险、失效条件。\n"
            f"当前默认标的: {inst_id or '未指定'} / {inst_type} / {mode}\n"
            f"前端附带上下文 JSON: {context_text}"
        )

    def _summarize_tool_result(self, result: Any) -> Dict[str, Any]:
        if not isinstance(result, dict):
            return {"result": result}
        summary: Dict[str, Any] = {}
        for key in (
            "inst_id",
            "inst_type",
            "timeframe",
            "mode",
            "available",
            "setup_status",
            "bias",
            "summary",
            "dataset_overview",
            "price_summary",
            "alignment",
            "trend",
            "volatility",
            "volume",
            "risk",
            "conclusion",
            "budget",
            "reference_price",
            "current_price",
            "trade_plan",
            "draft_id",
            "drafts",
            "count",
            "plan",
            "risk",
            "executed",
            "message",
            "snapshot_id",
            "snapshots",
            "run_id",
            "runs",
            "portfolio_hint",
            "selected_scenario",
            "projection_summary",
        ):
            if key in result:
                summary[key] = result[key]
        if "timeframes" in result and isinstance(result["timeframes"], dict):
            summary["timeframes"] = {
                name: {
                    "count": payload.get("count", 0),
                    "start_time": payload.get("start_time"),
                    "end_time": payload.get("end_time"),
                }
                for name, payload in result["timeframes"].items()
            }
        if "indicator_snapshots" in result and isinstance(result["indicator_snapshots"], dict):
            summary["indicator_snapshots"] = {
                name: payload.get("latest")
                for name, payload in result["indicator_snapshots"].items()
            }
        if "trades" in result and isinstance(result["trades"], list):
            summary["trade_count"] = len(result["trades"])
        if "bids" in result and isinstance(result["bids"], list):
            summary["bid_levels"] = len(result["bids"])
        if "asks" in result and isinstance(result["asks"], list):
            summary["ask_levels"] = len(result["asks"])
        if "rows" in result and isinstance(result["rows"], list):
            summary["row_count"] = len(result["rows"])
            if result["rows"]:
                summary["first_row"] = result["rows"][0]
        if "candidates" in result and isinstance(result["candidates"], list):
            summary["candidate_count"] = len(result["candidates"])
            if result["candidates"]:
                summary["top_candidate"] = result["candidates"][0]
        if "supports" in result and isinstance(result["supports"], list):
            summary["supports"] = result["supports"][:3]
        if "resistances" in result and isinstance(result["resistances"], list):
            summary["resistances"] = result["resistances"][:3]
        if "chart_annotations" in result and isinstance(result["chart_annotations"], list):
            summary["chart_annotations"] = result["chart_annotations"][:8]
        if "scenarios" in result and isinstance(result["scenarios"], dict):
            summary["scenarios"] = {
                name: {
                    "end_price": payload.get("end_price"),
                    "confidence": payload.get("confidence"),
                    "path": payload.get("path"),
                }
                for name, payload in result["scenarios"].items()
            }
        if "timeframe_signals" in result and isinstance(result["timeframe_signals"], dict):
            summary["timeframe_signals"] = {
                name: {
                    "trend": payload.get("trend"),
                    "confidence": payload.get("confidence"),
                    "change_pct": payload.get("change_pct"),
                }
                for name, payload in result["timeframe_signals"].items()
            }
        if "matrix" in result and isinstance(result["matrix"], list):
            summary["matrix_size"] = [len(result["matrix"]), len(result["matrix"][0]) if result["matrix"] else 0]
        if "top_positive" in result and isinstance(result["top_positive"], list):
            summary["top_positive"] = result["top_positive"][:3]
        if "top_negative" in result and isinstance(result["top_negative"], list):
            summary["top_negative"] = result["top_negative"][:3]
        if "draft" in result and isinstance(result["draft"], dict):
            draft = result["draft"]
            summary["draft"] = {
                "draft_id": draft.get("draft_id"),
                "status": draft.get("status"),
                "inst_id": draft.get("inst_id"),
                "side": draft.get("side"),
                "size": draft.get("size"),
                "price": draft.get("price"),
            }
        if "drafts" in result and isinstance(result["drafts"], list):
            summary["drafts"] = result["drafts"][:5]
        if "snapshot" in result and isinstance(result["snapshot"], dict):
            snapshot = result["snapshot"]
            summary["snapshot"] = {
                "snapshot_id": snapshot.get("snapshot_id"),
                "inst_id": snapshot.get("inst_id"),
                "inst_type": snapshot.get("inst_type"),
                "source": snapshot.get("source"),
                "created_at": snapshot.get("created_at"),
            }
        if "snapshots" in result and isinstance(result["snapshots"], list):
            summary["snapshots"] = result["snapshots"][:5]
        if "run" in result and isinstance(result["run"], dict):
            run = result["run"]
            summary["run"] = {
                "run_id": run.get("run_id"),
                "trigger": run.get("trigger"),
                "inst_type": run.get("inst_type"),
                "mode": run.get("mode"),
                "created_at": run.get("created_at"),
            }
        if "runs" in result and isinstance(result["runs"], list):
            summary["runs"] = result["runs"][:5]
        if not summary:
            return result
        return summary

    def _normalize_tool_arguments(self, raw_arguments: Any) -> Dict[str, Any]:
        if isinstance(raw_arguments, dict):
            return raw_arguments
        if not raw_arguments:
            return {}
        try:
            return json.loads(raw_arguments)
        except Exception as exc:
            raise AssistantOrchestratorError(f"工具参数不是合法 JSON: {raw_arguments}") from exc

    def _execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        try:
            if tool_name == "get_market_snapshot":
                request = AgentMarketQueryRequest.model_validate(arguments)
                return self.query_service.get_market_snapshot(request)
            if tool_name == "get_multi_timeframe_candles":
                request = AgentCandleQueryRequest.model_validate(arguments)
                return self.query_service.get_multi_timeframe_candles(request)
            if tool_name == "get_indicator_snapshot":
                request = AgentIndicatorQueryRequest.model_validate(arguments)
                return self.query_service.get_indicator_snapshot(request)
            if tool_name == "get_trading_context":
                request = AgentTradingContextRequest.model_validate(arguments)
                return self.query_service.get_trading_context(request)
            if tool_name == "get_orderbook_snapshot":
                request = AgentOrderBookQueryRequest.model_validate(arguments)
                return self.query_service.get_orderbook_snapshot(request)
            if tool_name == "scan_watchlist_context":
                request = AgentWatchlistScanRequest.model_validate(arguments)
                return self.query_service.scan_watchlist_context(request)
            if tool_name == "get_data_health":
                request = AgentDataHealthQueryRequest.model_validate(arguments)
                return self.query_service.get_data_health(request)
            if tool_name == "get_recent_trades_snapshot":
                request = AgentRecentTradesQueryRequest.model_validate(arguments)
                return self.query_service.get_recent_trades_snapshot(request)
            if tool_name == "get_position_snapshot":
                request = AgentPositionQueryRequest.model_validate(arguments)
                return self.query_service.get_position_snapshot(request)
            if tool_name == "analyze_multi_timeframe_alignment":
                request = AgentAlignmentQueryRequest.model_validate(arguments)
                return self.query_service.analyze_multi_timeframe_alignment(request)
            if tool_name == "analyze_market_structure":
                request = AgentMarketStructureRequest.model_validate(arguments)
                return self.query_service.analyze_market_structure(request)
            if tool_name == "detect_support_resistance":
                request = AgentSupportResistanceRequest.model_validate(arguments)
                return self.query_service.detect_support_resistance(request)
            if tool_name == "save_support_resistance_snapshot":
                request = AgentLevelSnapshotRequest.model_validate(arguments)
                return self.query_service.save_support_resistance_snapshot(request)
            if tool_name == "list_support_resistance_snapshots":
                request = AgentLevelSnapshotListRequest.model_validate(arguments)
                return self.query_service.list_level_snapshots(request)
            if tool_name == "generate_price_projection":
                request = AgentPriceProjectionRequest.model_validate(arguments)
                return self.query_service.generate_price_projection(request)
            if tool_name == "patrol_market_opportunities":
                request = AgentOpportunityPatrolRequest.model_validate(arguments)
                return self.query_service.patrol_market_opportunities(request)
            if tool_name == "list_patrol_runs":
                request = AgentPatrolRunListRequest.model_validate(arguments)
                return self.query_service.list_patrol_runs(request)
            if tool_name == "build_risk_budget":
                request = AgentRiskBudgetRequest.model_validate(arguments)
                return self.query_service.build_risk_budget(request)
            if tool_name == "build_trade_setup":
                request = AgentTradeSetupRequest.model_validate(arguments)
                return self.query_service.build_trade_setup(request)
            if tool_name == "analyze_watchlist_correlation":
                request = AgentCorrelationQueryRequest.model_validate(arguments)
                return self.query_service.analyze_watchlist_correlation(request)
            if tool_name == "create_order_draft":
                request = AgentOrderDraftRequest.model_validate(arguments)
                return self.query_service.create_order_draft(request)
            if tool_name == "list_order_drafts":
                request = AgentOrderDraftListRequest.model_validate(arguments)
                return self.query_service.list_order_drafts(request)
            if tool_name == "confirm_order_draft":
                request = AgentOrderDraftConfirmRequest.model_validate(arguments)
                return self.query_service.confirm_order_draft(request)
            if tool_name == "run_python_market_analysis":
                request = AgentPythonAnalysisRequest.model_validate(arguments)
                dataset = self.query_service.build_analysis_dataset(request)
                return run_market_analysis(
                    code=request.code,
                    dataset=dataset,
                    timeout_seconds=request.timeout_seconds,
                )
        except (MarketAnalysisSecurityError, MarketAnalysisTimeoutError, MarketAnalysisError) as exc:
            raise AssistantOrchestratorError(str(exc)) from exc
        except Exception as exc:
            raise AssistantOrchestratorError(f"{tool_name} 执行失败: {exc}") from exc

        raise AssistantOrchestratorError(f"未知工具: {tool_name}")

    def _build_completion_messages(
        self,
        *,
        session_id: str,
        user_message: str,
        system_prompt: str,
    ) -> List[Dict[str, Any]]:
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
        ]
        messages.extend(
            _sanitize_completion_history(self.storage.get_assistant_messages(session_id))
        )
        if not messages or messages[-1].get("role") != "user" or messages[-1].get("content") != user_message:
            messages.append({"role": "user", "content": user_message})
        return messages

    def _mark_session_failed(self, session_id: str, error_text: str) -> None:
        self.storage.update_assistant_session(session_id, status="failed", last_error=error_text)

    def _append_final_assistant_message(
        self,
        *,
        session_id: str,
        completion: Dict[str, Any],
        assistant_content: str,
        tool_steps: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        self.storage.append_assistant_message(
            session_id,
            role="assistant",
            content=assistant_content,
            metadata={
                "usage": completion.get("usage") or {},
            },
        )
        self.storage.update_assistant_session(session_id, status="completed", last_error="")
        return {
            "assistant_message": {
                "role": "assistant",
                "content": assistant_content,
            },
            "tool_steps": tool_steps,
            "session": self.storage.get_assistant_session(session_id),
        }

    def _append_assistant_tool_request(
        self,
        *,
        session_id: str,
        assistant_content: str,
        tool_calls: List[Dict[str, Any]],
        completion: Dict[str, Any],
        messages: List[Dict[str, Any]],
    ) -> None:
        self.storage.append_assistant_message(
            session_id,
            role="assistant",
            content=assistant_content,
            metadata={
                "tool_calls": tool_calls,
                "usage": completion.get("usage") or {},
            },
        )
        messages.append({
            "role": "assistant",
            "content": assistant_content,
            "tool_calls": tool_calls,
        })

    def _append_tool_message(
        self,
        *,
        session_id: str,
        tool_name: str,
        call_id: str,
        serialized_content: str,
        messages: List[Dict[str, Any]],
        metadata: Dict[str, Any],
    ) -> None:
        self.storage.append_assistant_message(
            session_id,
            role="tool",
            content=serialized_content,
            tool_name=tool_name,
            tool_call_id=call_id,
            metadata=metadata,
        )
        messages.append({
            "role": "tool",
            "tool_call_id": call_id,
            "content": serialized_content,
        })

    def _execute_tool_calls(
        self,
        *,
        session_id: str,
        tool_calls: List[Dict[str, Any]],
        messages: List[Dict[str, Any]],
        tool_steps: List[Dict[str, Any]],
    ) -> None:
        for tool_call in tool_calls:
            function_payload = tool_call.get("function") or {}
            tool_name = str(function_payload.get("name") or "").strip()
            call_id = str(tool_call.get("id") or "").strip()
            arguments = self._normalize_tool_arguments(function_payload.get("arguments"))
            step_index = len(tool_steps) + 1
            step_title = f"调用工具 {tool_name or 'unknown'}"
            step_id = self.storage.append_assistant_step(
                session_id,
                step_index=step_index,
                step_type="tool",
                title=step_title,
                status="running",
                tool_name=tool_name,
                input_payload=arguments,
                output_payload={},
            )
            try:
                output = self._execute_tool(tool_name, arguments)
                serialized_output = json.dumps(output, ensure_ascii=False)
                step_record = {
                    "id": step_id,
                    "step_index": step_index,
                    "tool_name": tool_name,
                    "status": "completed",
                    "input": arguments,
                    "output": self._summarize_tool_result(output),
                }
                self.storage.update_assistant_step(
                    step_id,
                    title=step_title,
                    status="completed",
                    tool_name=tool_name,
                    output_payload=step_record["output"],
                    error_text="",
                )
                self._append_tool_message(
                    session_id=session_id,
                    tool_name=tool_name,
                    call_id=call_id,
                    serialized_content=serialized_output,
                    messages=messages,
                    metadata={"summary": step_record["output"]},
                )
                tool_steps.append(step_record)
            except AssistantOrchestratorError as exc:
                error_text = str(exc)
                self.storage.update_assistant_step(
                    step_id,
                    title=step_title,
                    status="failed",
                    tool_name=tool_name,
                    output_payload={},
                    error_text=error_text,
                )
                self._append_tool_message(
                    session_id=session_id,
                    tool_name=tool_name,
                    call_id=call_id,
                    serialized_content=json.dumps(
                        {
                            "error": error_text,
                            "tool_name": tool_name,
                        },
                        ensure_ascii=False,
                    ),
                    messages=messages,
                    metadata={"error": error_text},
                )
                self.storage.update_assistant_session(session_id, status="failed", last_error=error_text)
                raise

    async def run_turn(
        self,
        *,
        session_id: str,
        user_message: str,
        inst_id: str = "",
        inst_type: str = "SPOT",
        mode: str = "simulated",
        market_context: Optional[Dict[str, Any]] = None,
        max_tool_rounds: int = 4,
    ) -> Dict[str, Any]:
        system_prompt = self._build_system_prompt(
            inst_id=inst_id,
            inst_type=inst_type,
            mode=mode,
            market_context=market_context or {},
        )
        messages = self._build_completion_messages(
            session_id=session_id,
            user_message=user_message,
            system_prompt=system_prompt,
        )
        self.storage.update_assistant_session(session_id, status="active", last_error="")

        tool_steps: List[Dict[str, Any]] = []
        round_limit = max(int(max_tool_rounds), 1)
        for round_index in range(1, round_limit + 1):
            try:
                completion = await self.completion_client.complete(
                    messages=messages,
                    tools=self.list_tools(),
                    temperature=config.ai_assistant.temperature,
                )
            except httpx.TimeoutException as exc:
                error_text = "AI 上游请求超时，请稍后重试。"
                self._mark_session_failed(session_id, error_text)
                raise AssistantUpstreamTimeoutError(error_text) from exc
            except httpx.RequestError as exc:
                error_text = "AI 上游连接失败，请检查网络、Base URL 或代理设置。"
                self._mark_session_failed(session_id, error_text)
                raise AssistantUpstreamConnectionError(error_text) from exc
            except AssistantOrchestratorError as exc:
                self._mark_session_failed(session_id, str(exc))
                raise
            choice = ((completion.get("choices") or [{}])[0]) or {}
            message = choice.get("message") or {}
            assistant_content = _extract_text_content(message.get("content"))
            tool_calls = message.get("tool_calls") or []

            if not tool_calls:
                return self._append_final_assistant_message(
                    session_id=session_id,
                    completion=completion,
                    assistant_content=assistant_content,
                    tool_steps=tool_steps,
                )

            self._append_assistant_tool_request(
                session_id=session_id,
                assistant_content=assistant_content,
                tool_calls=tool_calls,
                completion=completion,
                messages=messages,
            )
            self._execute_tool_calls(
                session_id=session_id,
                tool_calls=tool_calls,
                messages=messages,
                tool_steps=tool_steps,
            )

        error_text = "工具调用轮次超过上限，未得到最终结论"
        self.storage.update_assistant_session(session_id, status="failed", last_error=error_text)
        raise AssistantOrchestratorError(error_text)

    async def run_turn_stream(
        self,
        *,
        session_id: str,
        user_message: str,
        inst_id: str = "",
        inst_type: str = "SPOT",
        mode: str = "simulated",
        market_context: Optional[Dict[str, Any]] = None,
        max_tool_rounds: int = 4,
        on_delta: Optional[Callable[[str], Awaitable[None] | None]] = None,
    ) -> Dict[str, Any]:
        system_prompt = self._build_system_prompt(
            inst_id=inst_id,
            inst_type=inst_type,
            mode=mode,
            market_context=market_context or {},
        )
        messages = self._build_completion_messages(
            session_id=session_id,
            user_message=user_message,
            system_prompt=system_prompt,
        )
        self.storage.update_assistant_session(session_id, status="active", last_error="")

        tool_steps: List[Dict[str, Any]] = []
        round_limit = max(int(max_tool_rounds), 1)
        for round_index in range(1, round_limit + 1):
            try:
                completion = await self.completion_client.stream_complete(
                    messages=messages,
                    tools=self.list_tools(),
                    temperature=config.ai_assistant.temperature,
                    on_delta=on_delta,
                )
            except httpx.TimeoutException as exc:
                error_text = "AI 上游请求超时，请稍后重试。"
                self._mark_session_failed(session_id, error_text)
                raise AssistantUpstreamTimeoutError(error_text) from exc
            except httpx.RequestError as exc:
                error_text = "AI 上游连接失败，请检查网络、Base URL 或代理设置。"
                self._mark_session_failed(session_id, error_text)
                raise AssistantUpstreamConnectionError(error_text) from exc
            except AssistantOrchestratorError as exc:
                self._mark_session_failed(session_id, str(exc))
                raise

            choice = ((completion.get("choices") or [{}])[0]) or {}
            message = choice.get("message") or {}
            assistant_content = _extract_text_content(message.get("content"))
            tool_calls = message.get("tool_calls") or []

            if not tool_calls:
                return self._append_final_assistant_message(
                    session_id=session_id,
                    completion=completion,
                    assistant_content=assistant_content,
                    tool_steps=tool_steps,
                )

            self._append_assistant_tool_request(
                session_id=session_id,
                assistant_content=assistant_content,
                tool_calls=tool_calls,
                completion=completion,
                messages=messages,
            )
            self._execute_tool_calls(
                session_id=session_id,
                tool_calls=tool_calls,
                messages=messages,
                tool_steps=tool_steps,
            )

        error_text = "工具调用轮次超过上限，未得到最终结论"
        self.storage.update_assistant_session(session_id, status="failed", last_error=error_text)
        raise AssistantOrchestratorError(error_text)
