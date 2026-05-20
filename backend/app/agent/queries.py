from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from ..core.app_context import AppContext
from ..core.holdings import build_holdings_base
from ..core.indicators import IndicatorCalculator
from ..core.data_guardian import get_data_guardian
from ..core.risk_control import build_risk_summary, evaluate_order_risk, get_risk_control_store
from ..utils.mode import normalize_mode
from ..utils.numbers import safe_float_convert as _safe_float
from ..utils.watched_symbols_store import load_watched_symbols
from .query_utils import (
    _age_ms_from_iso,
    _average,
    _build_horizontal_annotation,
    _build_trendline_annotation,
    _dedupe_timeframes,
    _format_order_number,
    _health_status_from_score,
    _latest_valid,
    _normalize_inst_type,
    _normalize_timeframe,
    _pearson_correlation,
    _resolve_analysis_inst_id,
    _resolve_query_inst_id,
    _safe_json_value,
    _serialize_candle,
    _serialize_health_row,
    _serialize_indicator_payload,
    _serialize_optional_health_row,
    _summarize_position_snapshot,
    _trend_label,
    _utc_now_iso,
)
from .schemas import (
    AgentAlignmentQueryRequest,
    AgentCapabilityDescriptor,
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

class AgentQueryService:
    """给 AI/Agent 提供稳定的只读查询能力。"""

    def __init__(self, ctx: AppContext):
        self.ctx = ctx

    def list_capabilities(self) -> List[Dict[str, Any]]:
        capabilities = [
            AgentCapabilityDescriptor(
                name="query.market_snapshot",
                kind="query",
                goal="读取单个交易对的最新行情快照",
                input_example={"inst_id": "BTC-USDT-SWAP", "inst_type": "SWAP"},
                output_summary={"fields": ["ticker", "price_summary", "inst_id", "inst_type"]},
            ),
            AgentCapabilityDescriptor(
                name="query.candles",
                kind="query",
                goal="读取一个或多个周期的本地优先 K 线数据",
                input_example={"inst_id": "BTC-USDT", "inst_type": "SPOT", "timeframes": ["1m", "1H"], "limit": 300},
                output_summary={"fields": ["timeframes", "candles", "count", "start_time", "end_time"]},
            ),
            AgentCapabilityDescriptor(
                name="query.indicators",
                kind="query",
                goal="基于本地优先 K 线计算结构化指标快照",
                input_example={"inst_id": "BTC-USDT", "inst_type": "SPOT", "timeframe": "1H", "indicators": ["ma5", "macd"]},
                output_summary={"fields": ["indicator_snapshots", "candles", "timeframe"]},
            ),
            AgentCapabilityDescriptor(
                name="query.orderbook",
                kind="query",
                goal="读取当前盘口深度和价差摘要",
                input_example={"inst_id": "BTC-USDT-SWAP", "inst_type": "SWAP", "depth": 50},
                output_summary={"fields": ["bids", "asks", "best_bid", "best_ask", "spread"]},
            ),
            AgentCapabilityDescriptor(
                name="query.trading_context",
                kind="query",
                goal="聚合单个交易对的行情、K线、指标、盘口、逐笔、持仓与数据健康度",
                input_example={"inst_id": "BTC-USDT", "inst_type": "SPOT", "timeframes": ["5m", "1H", "4H"]},
                output_summary={"fields": ["market_snapshot", "timeframes", "alignment", "data_health", "position"]},
            ),
            AgentCapabilityDescriptor(
                name="query.watchlist_scan",
                kind="query",
                goal="批量扫描关注币种并返回趋势、异动与数据健康概览",
                input_example={"inst_type": "SPOT", "timeframes": ["1H", "4H"], "limit": 20},
                output_summary={"fields": ["rows", "summary", "scan_context"]},
            ),
            AgentCapabilityDescriptor(
                name="query.data_health",
                kind="query",
                goal="读取本地数据库库存覆盖、同步新鲜度与缺失周期情况",
                input_example={"symbol": "BTC-USDT"},
                output_summary={"fields": ["rows", "summary", "guardian"]},
            ),
            AgentCapabilityDescriptor(
                name="query.position",
                kind="query",
                goal="读取账户持仓基础快照",
                input_example={"mode": "simulated"},
                output_summary={"fields": ["available", "holdings", "cost_data", "summary"]},
            ),
            AgentCapabilityDescriptor(
                name="analysis.multi_timeframe_alignment",
                kind="analysis",
                goal="分析多个周期的趋势一致性、冲突周期与置信度",
                input_example={"inst_id": "BTC-USDT", "inst_type": "SPOT", "timeframes": ["1m", "5m", "1H", "4H", "1D"]},
                output_summary={"fields": ["alignment", "confidence", "timeframe_signals", "conflict_timeframes"]},
            ),
            AgentCapabilityDescriptor(
                name="analysis.market_structure",
                kind="analysis",
                goal="输出结构化市场分析，包括趋势、波动、量能、盘口、风险与结论",
                input_example={"inst_id": "BTC-USDT", "inst_type": "SPOT", "timeframes": ["5m", "1H", "4H"]},
                output_summary={"fields": ["trend", "volatility", "volume", "orderbook", "risk", "conclusion"]},
            ),
            AgentCapabilityDescriptor(
                name="analysis.support_resistance",
                kind="analysis",
                goal="识别当前支撑位、压力位和最近失效位，并返回可直接叠加到图表的水平位标记",
                input_example={"inst_id": "BTC-USDT", "inst_type": "SPOT", "timeframes": ["1H", "4H", "1D"]},
                output_summary={"fields": ["supports", "resistances", "invalidation_levels", "chart_annotations"]},
            ),
            AgentCapabilityDescriptor(
                name="action.level_snapshot",
                kind="action",
                goal="把当前关键位分析保存为可追溯快照，便于回看、复盘和后续复用",
                side_effect_free=False,
                risk_level="low",
                input_example={"inst_id": "BTC-USDT", "inst_type": "SPOT", "timeframes": ["1H", "4H", "1D"]},
                output_summary={"fields": ["snapshot_id", "inst_id", "supports", "resistances", "chart_annotations"]},
            ),
            AgentCapabilityDescriptor(
                name="query.level_snapshots",
                kind="query",
                goal="读取已保存的关键位快照列表或单个标的的历史快照",
                input_example={"inst_id": "BTC-USDT", "source": "assistant", "limit": 20},
                output_summary={"fields": ["snapshots", "count"]},
            ),
            AgentCapabilityDescriptor(
                name="analysis.price_projection",
                kind="analysis",
                goal="基于最近趋势和波动给出未来路径的启发式推演，并返回可叠加到图表的预测线",
                input_example={"inst_id": "BTC-USDT", "inst_type": "SPOT", "timeframe": "1H", "horizon_bars": 24},
                output_summary={"fields": ["selected_scenario", "scenarios", "projection_summary", "chart_annotations"]},
            ),
            AgentCapabilityDescriptor(
                name="analysis.opportunity_patrol",
                kind="analysis",
                goal="主动巡检关注币种并给出候选机会列表、理由、风险和优先级",
                input_example={"inst_type": "SPOT", "candidate_limit": 5, "timeframes": ["1H", "4H"]},
                output_summary={"fields": ["candidates", "summary", "scan_context"]},
            ),
            AgentCapabilityDescriptor(
                name="query.patrol_runs",
                kind="query",
                goal="读取已持久化的巡检运行记录，查看历史候选机会和运行摘要",
                input_example={"inst_type": "SWAP", "mode": "simulated", "trigger": "scheduled", "limit": 20},
                output_summary={"fields": ["runs", "count"]},
            ),
            AgentCapabilityDescriptor(
                name="analysis.risk_budget",
                kind="analysis",
                goal="结合当前账户风险敞口，计算某个标的可承受的建议仓位预算",
                input_example={"inst_id": "BTC-USDT", "inst_type": "SPOT", "mode": "simulated", "stop_loss_ratio": 0.03},
                output_summary={"fields": ["summary", "budget", "config", "proposed_order_evaluation"]},
            ),
            AgentCapabilityDescriptor(
                name="analysis.trade_setup",
                kind="analysis",
                goal="将结构、关键位、路径推演和风控预算整合成单标的交易计划",
                input_example={"inst_id": "BTC-USDT", "inst_type": "SPOT", "mode": "simulated"},
                output_summary={"fields": ["setup_status", "bias", "trade_plan", "chart_annotations", "checklist"]},
            ),
            AgentCapabilityDescriptor(
                name="analysis.watchlist_correlation",
                kind="analysis",
                goal="计算关注币种或指定币种列表之间的收益率相关性，辅助分散风险",
                input_example={"symbols": ["BTC-USDT", "ETH-USDT", "SOL-USDT"], "inst_type": "SPOT", "timeframe": "4H"},
                output_summary={"fields": ["symbols", "matrix", "top_positive", "top_negative", "portfolio_hint"]},
            ),
            AgentCapabilityDescriptor(
                name="action.order_draft",
                kind="action",
                goal="基于交易计划和风险预算生成一份待确认订单草案，不会直接下单",
                side_effect_free=False,
                risk_level="medium",
                input_example={"inst_id": "BTC-USDT", "inst_type": "SPOT", "mode": "simulated", "side_preference": "buy"},
                output_summary={"fields": ["draft_id", "status", "inst_id", "side", "size", "price", "plan", "risk"]},
            ),
            AgentCapabilityDescriptor(
                name="query.order_drafts",
                kind="query",
                goal="读取已生成的订单草案列表",
                input_example={"session_id": "", "inst_id": "BTC-USDT", "status": "draft"},
                output_summary={"fields": ["drafts", "count"]},
            ),
            AgentCapabilityDescriptor(
                name="action.order_draft_confirm",
                kind="action",
                goal="确认一份订单草案，状态变为 confirmed，但不会自动下单",
                side_effect_free=False,
                risk_level="medium",
                input_example={"draft_id": "draft_xxx"},
                output_summary={"fields": ["draft_id", "status", "executed", "message"]},
            ),
            AgentCapabilityDescriptor(
                name="analysis.python_market",
                kind="analysis",
                goal="在受限沙箱中基于市场数据执行自定义 Python 分析",
                input_example={"inst_id": "BTC-USDT", "timeframes": ["1H"], "indicators": ["ma20", "rsi"], "timeout_seconds": 12},
                output_summary={"fields": ["summary", "metrics", "tables", "artifacts", "warnings"]},
            ),
        ]
        return [item.model_dump() for item in capabilities]

    def get_market_snapshot(self, request: AgentMarketQueryRequest) -> Dict[str, Any]:
        resolved_inst_id, inst_type = _resolve_query_inst_id(request.inst_id, request.inst_type.value)
        fetcher = self.ctx.fetcher()
        storage = self.ctx.storage()

        ticker = None
        if fetcher:
            ticker = fetcher.get_ticker_cached(resolved_inst_id, inst_type)
        if ticker is None:
            ticker = storage.get_latest_ticker(resolved_inst_id, inst_type=inst_type)
        if ticker is None:
            raise ValueError(f"未找到 {resolved_inst_id or request.inst_id} 的行情快照")

        spread = float(getattr(ticker, "ask_px", 0) or 0) - float(getattr(ticker, "bid_px", 0) or 0)
        mid_price = (
            (float(getattr(ticker, "ask_px", 0) or 0) + float(getattr(ticker, "bid_px", 0) or 0)) / 2.0
            if float(getattr(ticker, "ask_px", 0) or 0) > 0 and float(getattr(ticker, "bid_px", 0) or 0) > 0
            else 0.0
        )
        spread_bps = (spread / mid_price * 10000.0) if mid_price > 0 else 0.0

        ticker_payload = _safe_json_value(ticker.to_dict() if hasattr(ticker, "to_dict") else ticker)
        return {
            "inst_id": resolved_inst_id,
            "inst_type": inst_type,
            "ticker": ticker_payload,
            "price_summary": {
                "last": ticker_payload.get("last"),
                "bid_px": ticker_payload.get("bid_px"),
                "ask_px": ticker_payload.get("ask_px"),
                "change_24h": ticker_payload.get("change_24h"),
                "spread": _safe_json_value(spread),
                "spread_bps": _safe_json_value(spread_bps),
                "mid_price": _safe_json_value(mid_price),
            },
            "fetched_at": datetime.utcnow().isoformat(),
        }

    def _load_candles(
        self,
        *,
        inst_id: str,
        inst_type: str,
        timeframe: str,
        limit: int,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        auto_sync: bool = True,
    ) -> List[Any]:
        start_dt = parse_iso_datetime(start_time) if start_time else None
        end_dt = parse_iso_datetime(end_time) if end_time else None
        manager = self.ctx.manager()
        return manager.get_local_candles(
            inst_id,
            timeframe,
            limit=limit,
            start_time=start_dt,
            end_time=end_dt,
            auto_sync=auto_sync,
            inst_type=inst_type,
        )

    def _build_timeframe_signal(self, candles: List[Any], timeframe: str) -> Dict[str, Any]:
        if not candles:
            return {
                "timeframe": timeframe,
                "trend": "missing",
                "score": 0,
                "confidence": 0.0,
                "close": None,
                "change_pct": None,
                "volume_ratio": None,
                "atr_ratio": None,
                "indicators": {},
                "votes": {},
            }

        calculator = IndicatorCalculator(candles)
        last_candle = candles[-1]
        previous_candle = candles[-2] if len(candles) >= 2 else candles[-1]
        last_close = _safe_float(getattr(last_candle, "close", 0))
        previous_close = _safe_float(getattr(previous_candle, "close", 0), last_close)
        last_volume = _safe_float(getattr(last_candle, "volume", 0))
        change_pct = ((last_close - previous_close) / previous_close * 100.0) if previous_close > 0 else 0.0

        ma20 = _safe_float(_latest_valid(calculator.sma(20)), last_close)
        rsi14 = _safe_float(_latest_valid(calculator.rsi(14)))
        atr14 = _safe_float(_latest_valid(calculator.atr(14)))
        vma20 = _safe_float(_latest_valid(calculator.volume_ma(20)))
        macd_latest = _latest_valid(_safe_json_value(calculator.macd()))
        macd_hist = _safe_float((macd_latest or {}).get("histogram"))
        macd_dif = _safe_float((macd_latest or {}).get("dif"))
        macd_dea = _safe_float((macd_latest or {}).get("dea"))

        score = 0.0
        votes: Dict[str, Any] = {}

        price_vs_ma = 0
        if ma20 > 0:
            if last_close > ma20:
                price_vs_ma = 1
            elif last_close < ma20:
                price_vs_ma = -1
        score += price_vs_ma
        votes["price_vs_ma20"] = price_vs_ma

        macd_vote = 0
        if macd_hist > 0 or macd_dif > macd_dea:
            macd_vote = 1
        elif macd_hist < 0 or macd_dif < macd_dea:
            macd_vote = -1
        score += macd_vote
        votes["macd"] = macd_vote

        rsi_vote = 0
        if rsi14 >= 60:
            rsi_vote = 1
        elif rsi14 <= 40:
            rsi_vote = -1
        score += rsi_vote
        votes["rsi"] = rsi_vote

        momentum_vote = 0
        if change_pct >= 0.4:
            momentum_vote = 1
        elif change_pct <= -0.4:
            momentum_vote = -1
        score += momentum_vote * 0.5
        votes["price_change"] = momentum_vote

        volume_ratio = (last_volume / vma20) if vma20 > 0 else 1.0
        atr_ratio = (atr14 / last_close) if last_close > 0 else 0.0
        confidence = min(1.0, abs(score) / 3.5)

        return {
            "timeframe": timeframe,
            "trend": _trend_label(score),
            "score": round(score, 4),
            "confidence": round(confidence, 4),
            "close": _safe_json_value(last_close),
            "change_pct": _safe_json_value(change_pct),
            "volume_ratio": _safe_json_value(volume_ratio),
            "atr_ratio": _safe_json_value(atr_ratio),
            "latest_candle": _serialize_candle(last_candle),
            "indicators": {
                "ma20": _safe_json_value(ma20),
                "rsi14": _safe_json_value(rsi14),
                "atr14": _safe_json_value(atr14),
                "volume_ma20": _safe_json_value(vma20),
                "macd": _safe_json_value(macd_latest or {}),
            },
            "votes": votes,
        }

    def _build_data_health_payload(self, *, symbol: str = "", include_orphans: bool = True) -> Dict[str, Any]:
        storage = self.ctx.storage()
        inventory_rows = storage.get_symbol_data_inventory() if storage else []
        watched_records = load_watched_symbols()
        watched_symbols = {item["symbol"] for item in watched_records}

        try:
            guardian = get_data_guardian(self.ctx)
            guardian_status = guardian.get_status()
        except Exception:
            guardian_status = {}

        enabled_timeframes = _dedupe_timeframes(guardian_status.get("timeframes") or ["1m", "5m", "1H", "4H", "1D"])
        normalized_symbol = normalize_watched_symbol(symbol) if symbol else ""

        def build_row(entry: Optional[Dict[str, Any]]) -> Dict[str, Any]:
            base_symbol = normalize_watched_symbol((entry or {}).get("symbol") or normalized_symbol)
            watched = base_symbol in watched_symbols
            markets_payload: Dict[str, Any] = {}
            scores: List[float] = []
            present_timeframes: set[str] = set()

            for inst_type, market in ((entry or {}).get("markets") or {}).items():
                timeframe_rows: List[Dict[str, Any]] = []
                for timeframe_item in market.get("timeframes") or []:
                    timeframe = _normalize_timeframe(timeframe_item.get("timeframe") or "1H")
                    present_timeframes.add(timeframe)
                    age_ms = _age_ms_from_iso(timeframe_item.get("last_sync_time") or timeframe_item.get("newest_time"))
                    timeframe_ms = TIMEFRAME_TO_MS.get(timeframe)
                    freshness_score = 100.0
                    if age_ms is None:
                        freshness_score = 20.0
                    elif timeframe_ms and age_ms > timeframe_ms * 12:
                        freshness_score = 25.0
                    elif timeframe_ms and age_ms > timeframe_ms * 4:
                        freshness_score = 55.0
                    elif timeframe_ms and age_ms > timeframe_ms * 2:
                        freshness_score = 75.0
                    if not timeframe_item.get("history_complete"):
                        freshness_score -= 10.0
                    freshness_score = max(0.0, freshness_score)
                    scores.append(freshness_score)

                    timeframe_rows.append({
                        "timeframe": timeframe,
                        "candle_count": int(timeframe_item.get("candle_count", 0) or 0),
                        "history_complete": bool(timeframe_item.get("history_complete", False)),
                        "last_sync_mode": timeframe_item.get("last_sync_mode") or "window",
                        "last_sync_time": timeframe_item.get("last_sync_time"),
                        "oldest_time": timeframe_item.get("oldest_time"),
                        "newest_time": timeframe_item.get("newest_time"),
                        "freshness_ms": age_ms,
                        "status": _health_status_from_score(freshness_score),
                        "health_score": round(freshness_score, 2),
                    })

                timeframe_rows.sort(key=lambda item: _timeframe_sort_key(item["timeframe"]))
                market_score = _average(item["health_score"] for item in timeframe_rows) if timeframe_rows else 0.0
                markets_payload[inst_type] = {
                    "inst_id": market.get("inst_id") or "",
                    "inst_type": inst_type,
                    "candle_count": int(market.get("candle_count", 0) or 0),
                    "timeframe_count": int(market.get("timeframe_count", 0) or 0),
                    "history_complete_count": int(market.get("history_complete_count", 0) or 0),
                    "oldest_time": market.get("oldest_time"),
                    "newest_time": market.get("newest_time"),
                    "last_sync_time": market.get("last_sync_time"),
                    "health_score": round(market_score, 2),
                    "timeframes": timeframe_rows,
                }

            missing_timeframes = [item for item in enabled_timeframes if item not in present_timeframes]
            coverage_ratio = (
                (len(present_timeframes) / len(enabled_timeframes))
                if enabled_timeframes else
                (1.0 if present_timeframes else 0.0)
            )
            health_score = _average(scores) if scores else 0.0
            if missing_timeframes:
                health_score = max(0.0, health_score - min(40.0, len(missing_timeframes) * 8.0))

            return {
                "symbol": base_symbol,
                "watched": watched,
                "orphan": bool(entry) and not watched,
                "has_local_data": bool(entry),
                "coverage_ratio": round(coverage_ratio, 4),
                "health_score": round(health_score, 2),
                "status": _health_status_from_score(health_score),
                "missing_timeframes": missing_timeframes,
                "markets": markets_payload,
                "storage_counts": _safe_json_value((entry or {}).get("storage_counts") or {}),
                "candle_count": int((entry or {}).get("candle_count", 0) or 0),
                "timeframe_record_count": int((entry or {}).get("timeframe_record_count", 0) or 0),
            }

        if normalized_symbol:
            matched = next(
                (item for item in inventory_rows if normalize_watched_symbol(item.get("symbol")) == normalized_symbol),
                None,
            )
            rows = [build_row(matched)]
        else:
            rows = [build_row(item) for item in inventory_rows]

        if not normalized_symbol and not include_orphans:
            rows = [item for item in rows if not item.get("orphan")]

        if normalized_symbol and rows and not rows[0].get("symbol"):
            rows[0]["symbol"] = normalized_symbol
            rows[0]["watched"] = normalized_symbol in watched_symbols

        summary = {
            "symbol_count": len(rows),
            "watched_symbol_count": sum(1 for item in rows if item.get("watched")),
            "orphan_symbol_count": sum(1 for item in rows if item.get("orphan")),
            "healthy_count": sum(1 for item in rows if item.get("status") == "healthy"),
            "degraded_count": sum(1 for item in rows if item.get("status") == "degraded"),
            "stale_count": sum(1 for item in rows if item.get("status") == "stale"),
            "missing_count": sum(1 for item in rows if item.get("status") == "missing"),
            "watched_list_count": len(watched_symbols),
            "enabled_timeframes": enabled_timeframes,
        }

        return {
            "symbol": normalized_symbol,
            "rows": rows,
            "summary": summary,
            "guardian": {
                "enabled": bool(guardian_status.get("enabled", False)),
                "running": bool(guardian_status.get("running", False)),
                "current_phase": guardian_status.get("current_phase") or "idle",
                "watched_count": int(guardian_status.get("watched_count", 0) or 0),
                "timeframes": enabled_timeframes,
                "last_run_started_at": guardian_status.get("last_run_started_at"),
                "last_run_finished_at": guardian_status.get("last_run_finished_at"),
                "last_successful_run_at": guardian_status.get("last_successful_run_at"),
                "last_run_summary": _safe_json_value(guardian_status.get("last_run_summary") or {}),
                "last_errors": _safe_json_value(guardian_status.get("last_errors") or []),
            },
            "fetched_at": _utc_now_iso(),
        }

    def get_multi_timeframe_candles(self, request: AgentCandleQueryRequest) -> Dict[str, Any]:
        resolved_inst_id, inst_type = _resolve_query_inst_id(request.inst_id, request.inst_type.value)
        payload: Dict[str, Any] = {
            "inst_id": resolved_inst_id,
            "inst_type": inst_type,
            "timeframes": {},
        }

        for timeframe in [_normalize_timeframe(item) for item in request.timeframes]:
            candles = self._load_candles(
                inst_id=resolved_inst_id,
                inst_type=inst_type,
                timeframe=timeframe,
                limit=request.limit,
                start_time=request.start_time,
                end_time=request.end_time,
                auto_sync=request.auto_sync,
            )
            serialized = [_serialize_candle(item) for item in candles]
            payload["timeframes"][timeframe] = {
                "count": len(serialized),
                "candles": serialized,
                "start_time": serialized[0]["datetime"] if serialized else None,
                "end_time": serialized[-1]["datetime"] if serialized else None,
            }

        return payload

    def _resolve_indicator(self, calculator: IndicatorCalculator, indicator_name: str) -> Dict[str, Any]:
        lower = indicator_name.lower().replace(" ", "").replace("-", "_")
        alias_lower = lower

        if lower.startswith("vma"):
            alias_lower = f"volume_ma{lower[3:]}"
        elif lower in {"boll", "bbands", "bb"}:
            alias_lower = "bollinger"

        def extract_period(prefix: str, default: Optional[int] = None) -> Optional[int]:
            if alias_lower == prefix and default is not None:
                return default
            if alias_lower.startswith(f"{prefix}:"):
                value = alias_lower.split(":", 1)[1]
                return int(value) if value.isdigit() else default
            suffix = alias_lower[len(prefix):]
            return int(suffix) if suffix.isdigit() else default

        if alias_lower == "macd":
            return _serialize_indicator_payload(indicator_name, calculator.macd(), {"fast": 12, "slow": 26, "signal": 9})
        if alias_lower == "bollinger":
            return _serialize_indicator_payload(indicator_name, calculator.bollinger(), {"period": 20, "num_std": 2.0})
        if alias_lower == "kdj":
            return _serialize_indicator_payload(indicator_name, calculator.kdj(), {"n": 9, "m1": 3, "m2": 3})
        if alias_lower.startswith("ma"):
            period = extract_period("ma")
            if period is None:
                raise ValueError(f"无效的移动平均指标: {indicator_name}")
            return _serialize_indicator_payload(indicator_name, calculator.sma(period), {"period": period, "type": "sma"})
        if alias_lower.startswith("ema"):
            period = extract_period("ema")
            if period is None:
                raise ValueError(f"无效的 EMA 指标: {indicator_name}")
            return _serialize_indicator_payload(indicator_name, calculator.ema(period), {"period": period, "type": "ema"})
        if alias_lower.startswith("rsi"):
            period = extract_period("rsi", default=14)
            return _serialize_indicator_payload(indicator_name, calculator.rsi(period), {"period": period})
        if alias_lower.startswith("atr"):
            period = extract_period("atr", default=14)
            return _serialize_indicator_payload(indicator_name, calculator.atr(period), {"period": period})
        if alias_lower.startswith("volume_ma"):
            period = extract_period("volume_ma", default=20)
            return _serialize_indicator_payload(indicator_name, calculator.volume_ma(period), {"period": period})
        if alias_lower.startswith("vwap"):
            period = extract_period("vwap")
            return _serialize_indicator_payload(
                indicator_name,
                calculator.vwap(period),
                {
                    "period": period,
                    "mode": "rolling" if period is not None else "cumulative",
                    "source": "hlc3",
                },
            )

        raise ValueError(f"不支持的指标: {indicator_name}")

    def get_indicator_snapshot(self, request: AgentIndicatorQueryRequest) -> Dict[str, Any]:
        resolved_inst_id, inst_type = _resolve_query_inst_id(request.inst_id, request.inst_type.value)
        timeframe = _normalize_timeframe(request.timeframe)
        candles = self._load_candles(
            inst_id=resolved_inst_id,
            inst_type=inst_type,
            timeframe=timeframe,
            limit=request.limit,
            auto_sync=request.auto_sync,
        )
        if not candles:
            raise ValueError(f"未找到 {resolved_inst_id or request.inst_id} {timeframe} 的 K 线数据")

        calculator = IndicatorCalculator(candles)
        indicator_payload = {
            name: self._resolve_indicator(calculator, name)
            for name in request.indicators
        }
        serialized_candles = [_serialize_candle(item) for item in candles]
        return {
            "inst_id": resolved_inst_id,
            "inst_type": inst_type,
            "timeframe": timeframe,
            "candles": serialized_candles,
            "indicator_snapshots": indicator_payload,
        }

    def get_orderbook_snapshot(self, request: AgentOrderBookQueryRequest) -> Dict[str, Any]:
        resolved_inst_id, inst_type = _resolve_query_inst_id(request.inst_id, request.inst_type.value)
        fetcher = self.ctx.fetcher()
        if not fetcher:
            return {
                "inst_id": resolved_inst_id,
                "inst_type": inst_type,
                "available": False,
                "message": "数据获取器不可用",
                "bids": [],
                "asks": [],
            }

        try:
            orderbook = fetcher.get_orderbook(resolved_inst_id, request.depth)
        except Exception as exc:
            return {
                "inst_id": resolved_inst_id,
                "inst_type": inst_type,
                "available": False,
                "message": f"获取盘口深度失败: {exc}",
                "bids": [],
                "asks": [],
            }

        if not orderbook:
            return {
                "inst_id": resolved_inst_id,
                "inst_type": inst_type,
                "available": False,
                "message": "未获取到盘口深度",
                "bids": [],
                "asks": [],
            }

        payload = _safe_json_value(orderbook)
        payload["available"] = True
        return payload

    def get_recent_trades_snapshot(self, request: AgentRecentTradesQueryRequest) -> Dict[str, Any]:
        resolved_inst_id, inst_type = _resolve_query_inst_id(request.inst_id, request.inst_type.value)
        fetcher = self.ctx.fetcher()
        storage = self.ctx.storage()

        trades = []
        if fetcher:
            trades = fetcher.get_recent_trades_local_first(resolved_inst_id, request.limit, inst_type=inst_type)
        if not trades:
            trades = storage.get_recent_trades(resolved_inst_id, limit=request.limit, inst_type=inst_type)

        serialized = [_safe_json_value(item.to_dict() if hasattr(item, "to_dict") else item) for item in trades]
        buy_volume = sum(float(item.get("size", 0) or 0) for item in serialized if item.get("side") == "buy")
        sell_volume = sum(float(item.get("size", 0) or 0) for item in serialized if item.get("side") == "sell")
        return {
            "inst_id": resolved_inst_id,
            "inst_type": inst_type,
            "limit": request.limit,
            "trades": serialized,
            "summary": {
                "trade_count": len(serialized),
                "buy_volume": _safe_json_value(buy_volume),
                "sell_volume": _safe_json_value(sell_volume),
                "latest_trade": serialized[-1] if serialized else None,
            },
        }

    def get_position_snapshot(self, request: AgentPositionQueryRequest) -> Dict[str, Any]:
        mode = normalize_mode(request.mode.value) or self.ctx.default_mode()
        account = self.ctx.account(mode)
        if not account.is_available:
            return {
                "mode": mode,
                "available": False,
                "holdings": [],
                "cost_data": {},
                "summary": {"holding_count": 0},
                "message": "账户 API 未初始化",
            }

        balance = account.get_balance()
        if "error" in balance:
            return {
                "mode": mode,
                "available": False,
                "holdings": [],
                "cost_data": {},
                "summary": {"holding_count": 0},
                "message": str(balance["error"]),
            }

        details = balance.get("details", [])
        storage = self.ctx.storage()
        cost_data = storage.get_cost_basis(mode)
        holdings = build_holdings_base(balance_details=details, cost_data=cost_data)
        return {
            "mode": mode,
            "available": True,
            "holdings": holdings,
            "cost_data": {
                key: {
                    "avg_cost": _safe_json_value(value.get("avg_cost")),
                    "total_cost": _safe_json_value(value.get("total_cost")),
                    "total_fee": _safe_json_value(value.get("total_fee", 0)),
                }
                for key, value in cost_data.items()
            },
            "summary": {
                "holding_count": len(holdings),
                "assets": [item.get("ccy") for item in holdings],
            },
        }

    def build_analysis_dataset(self, request: AgentPythonAnalysisRequest) -> Dict[str, Any]:
        resolved_inst_id, inst_type = _resolve_query_inst_id(request.inst_id, request.inst_type.value)
        timeframes = [_normalize_timeframe(item) for item in request.timeframes]
        candles_payload = self.get_multi_timeframe_candles(
            AgentCandleQueryRequest(
                inst_id=resolved_inst_id,
                inst_type=inst_type,
                timeframes=timeframes,
                limit=request.candles_limit,
                auto_sync=True,
            )
        )

        dataset: Dict[str, Any] = {
            "context": {
                "goal": request.goal,
                "inst_id": resolved_inst_id,
                "inst_type": inst_type,
                "timeframes": timeframes,
                "generated_at": datetime.utcnow().isoformat(),
            },
            "candles": candles_payload["timeframes"],
        }

        if request.indicators:
            dataset["indicators"] = {}
            for timeframe in timeframes:
                indicator_payload = self.get_indicator_snapshot(
                    AgentIndicatorQueryRequest(
                        inst_id=resolved_inst_id,
                        inst_type=inst_type,
                        timeframe=timeframe,
                        indicators=request.indicators,
                        limit=request.candles_limit,
                        auto_sync=True,
                    )
                )
                dataset["indicators"][timeframe] = {
                    "timeframe": timeframe,
                    "indicator_snapshots": indicator_payload["indicator_snapshots"],
                }

        if request.include_market_snapshot:
            dataset["market_snapshot"] = self.get_market_snapshot(
                AgentMarketQueryRequest(inst_id=resolved_inst_id, inst_type=inst_type)
            )
        if request.include_orderbook:
            dataset["orderbook"] = self.get_orderbook_snapshot(
                AgentOrderBookQueryRequest(inst_id=resolved_inst_id, inst_type=inst_type, depth=request.orderbook_depth)
            )
        if request.include_recent_trades:
            dataset["recent_trades"] = self.get_recent_trades_snapshot(
                AgentRecentTradesQueryRequest(inst_id=resolved_inst_id, inst_type=inst_type, limit=request.recent_trade_limit)
            )
        if request.include_position:
            dataset["position"] = self.get_position_snapshot(AgentPositionQueryRequest(mode=request.mode))

        return dataset

    def get_trading_context(self, request: AgentTradingContextRequest) -> Dict[str, Any]:
        resolved_inst_id, inst_type = _resolve_query_inst_id(request.inst_id, request.inst_type.value)
        timeframes = _dedupe_timeframes(request.timeframes)
        market_snapshot = self.get_market_snapshot(
            AgentMarketQueryRequest(inst_id=resolved_inst_id, inst_type=inst_type)
        )

        timeframe_payload: Dict[str, Any] = {}
        for timeframe in timeframes:
            candles = self._load_candles(
                inst_id=resolved_inst_id,
                inst_type=inst_type,
                timeframe=timeframe,
                limit=request.candles_limit,
                auto_sync=request.auto_sync,
            )
            serialized_candles = [_serialize_candle(item) for item in candles]
            indicator_snapshot = self.get_indicator_snapshot(
                AgentIndicatorQueryRequest(
                    inst_id=resolved_inst_id,
                    inst_type=inst_type,
                    timeframe=timeframe,
                    indicators=request.indicators,
                    limit=request.candles_limit,
                    auto_sync=request.auto_sync,
                )
            ) if candles else {
                "indicator_snapshots": {},
            }
            signal = self._build_timeframe_signal(candles, timeframe)
            timeframe_payload[timeframe] = {
                "count": len(serialized_candles),
                "candles": serialized_candles,
                "start_time": serialized_candles[0]["datetime"] if serialized_candles else None,
                "end_time": serialized_candles[-1]["datetime"] if serialized_candles else None,
                "latest_candle": serialized_candles[-1] if serialized_candles else None,
                "indicator_snapshots": indicator_snapshot["indicator_snapshots"],
                "signal": signal,
            }

        data_health_payload = self._build_data_health_payload(symbol=resolved_inst_id, include_orphans=True)
        orderbook_payload = self.get_orderbook_snapshot(
            AgentOrderBookQueryRequest(inst_id=resolved_inst_id, inst_type=inst_type, depth=request.orderbook_depth)
        ) if request.include_orderbook else None
        trades_payload = self.get_recent_trades_snapshot(
            AgentRecentTradesQueryRequest(inst_id=resolved_inst_id, inst_type=inst_type, limit=request.recent_trade_limit)
        ) if request.include_recent_trades else None
        position_payload = self.get_position_snapshot(
            AgentPositionQueryRequest(mode=request.mode)
        ) if request.include_position else None
        alignment = self.analyze_multi_timeframe_alignment(
            AgentAlignmentQueryRequest(
                inst_id=resolved_inst_id,
                inst_type=inst_type,
                timeframes=timeframes,
                limit=request.candles_limit,
                auto_sync=request.auto_sync,
            )
        )

        return {
            "inst_id": resolved_inst_id,
            "inst_type": inst_type,
            "mode": normalize_mode(request.mode.value) or self.ctx.default_mode(),
            "market_snapshot": market_snapshot,
            "timeframes": timeframe_payload,
            "alignment": alignment,
            "data_health": data_health_payload["rows"][0] if data_health_payload["rows"] else _serialize_health_row(None),
            "orderbook": orderbook_payload,
            "recent_trades": trades_payload,
            "position": position_payload,
            "fetched_at": _utc_now_iso(),
        }

    def scan_watchlist_context(self, request: AgentWatchlistScanRequest) -> Dict[str, Any]:
        inst_type = str(request.inst_type.value).upper()
        watched_records = load_watched_symbols()
        if not watched_records:
            return {
                "inst_type": inst_type,
                "rows": [],
                "summary": {
                    "scan_count": 0,
                    "watched_count": 0,
                    "available_count": 0,
                },
                "scan_context": {
                    "timeframes": _dedupe_timeframes(request.timeframes),
                    "sort_by": request.sort_by,
                },
                "fetched_at": _utc_now_iso(),
            }

        fetcher = self.ctx.fetcher()
        ticker_map: Dict[str, Any] = {}
        if fetcher and hasattr(fetcher, "get_tickers_cached"):
            try:
                ticker_map = fetcher.get_tickers_cached(inst_type)
            except Exception:
                ticker_map = {}

        data_health = self._build_data_health_payload(include_orphans=True)
        health_by_symbol = {
            item.get("symbol"): item
            for item in data_health["rows"]
            if isinstance(item, dict) and item.get("symbol")
        }

        rows: List[Dict[str, Any]] = []
        timeframes = _dedupe_timeframes(request.timeframes)
        for watched in watched_records:
            enabled = bool(watched.get("sync_spot", True)) if inst_type == "SPOT" else bool(watched.get("sync_swap", True))
            if not enabled:
                continue
            inst_id = watched.get("spot_inst_id") if inst_type == "SPOT" else watched.get("swap_inst_id")
            if not inst_id:
                continue
            try:
                market_snapshot = self.get_market_snapshot(
                    AgentMarketQueryRequest(inst_id=inst_id, inst_type=inst_type)
                )
                ticker = ticker_map.get(inst_id)
                ticker_payload = _safe_json_value(
                    ticker.to_dict() if hasattr(ticker, "to_dict") else ticker
                ) if ticker else market_snapshot["ticker"]
                if isinstance(ticker_payload, dict) and "volume_24h" not in ticker_payload:
                    ticker_payload["volume_24h"] = ticker_payload.get("vol_24h")

                alignment = self.analyze_multi_timeframe_alignment(
                    AgentAlignmentQueryRequest(
                        inst_id=inst_id,
                        inst_type=inst_type,
                        timeframes=timeframes,
                        limit=request.candles_limit,
                        auto_sync=True,
                    )
                )
                orderbook = self.get_orderbook_snapshot(
                    AgentOrderBookQueryRequest(inst_id=inst_id, inst_type=inst_type, depth=request.orderbook_depth)
                ) if request.include_orderbook else None
                health_row = health_by_symbol.get(watched["symbol"])
                spread_bps = _safe_float((market_snapshot.get("price_summary") or {}).get("spread_bps"))
                change_24h = _safe_float(ticker_payload.get("change_24h"))
                volatility_signal = max(
                    (
                        abs(_safe_float((signal or {}).get("atr_ratio")))
                        for signal in alignment.get("timeframe_signals", {}).values()
                    ),
                    default=0.0,
                )
                orderbook_imbalance = None
                if orderbook and orderbook.get("available"):
                    bid_total = sum(_safe_float(item.get("size")) for item in orderbook.get("bids") or [])
                    ask_total = sum(_safe_float(item.get("size")) for item in orderbook.get("asks") or [])
                    total_depth = bid_total + ask_total
                    orderbook_imbalance = (bid_total / total_depth) if total_depth > 0 else None

                signal_score = (
                    _safe_float(alignment.get("confidence")) * 70.0
                    + min(abs(change_24h), 20.0) * 1.5
                    + max(0.0, 10.0 - min(spread_bps, 10.0))
                    - min(volatility_signal * 100.0, 15.0)
                    + (
                        (abs((orderbook_imbalance or 0.5) - 0.5) * 20.0)
                        if orderbook_imbalance is not None else
                        0.0
                    )
                )

                rows.append({
                    "symbol": watched["symbol"],
                    "inst_id": inst_id,
                    "inst_type": inst_type,
                    "available": True,
                    "price_summary": market_snapshot.get("price_summary") or {},
                    "ticker": ticker_payload,
                    "alignment": {
                        "alignment": alignment.get("alignment"),
                        "confidence": alignment.get("confidence"),
                        "bullish_count": alignment.get("bullish_count"),
                        "bearish_count": alignment.get("bearish_count"),
                        "conflict_timeframes": alignment.get("conflict_timeframes") or [],
                    },
                    "orderbook": {
                        "available": bool(orderbook and orderbook.get("available")),
                        "imbalance": _safe_json_value(orderbook_imbalance),
                    } if request.include_orderbook else None,
                    "data_health": _serialize_optional_health_row(health_row),
                    "signal_score": round(signal_score, 4),
                })
            except Exception as exc:
                rows.append({
                    "symbol": watched["symbol"],
                    "inst_id": inst_id,
                    "inst_type": inst_type,
                    "available": False,
                    "data_health": _serialize_optional_health_row(health_by_symbol.get(watched["symbol"])),
                    "error": str(exc),
                })

        sort_key = request.sort_by
        rows.sort(
            key=lambda item: float(
                item.get("signal_score", 0) if sort_key == "signal_score"
                else ((item.get("ticker") or {}).get(sort_key, 0) if isinstance(item.get("ticker"), dict) else 0) or 0
            ),
            reverse=True,
        )
        rows = rows[:request.limit]

        return {
            "inst_type": inst_type,
            "rows": rows,
            "summary": {
                "scan_count": len(rows),
                "watched_count": len(watched_records),
                "available_count": sum(1 for item in rows if bool(item.get("available"))),
                "bullish_count": sum(1 for item in rows if (item.get("alignment") or {}).get("alignment") == "bullish"),
                "bearish_count": sum(1 for item in rows if (item.get("alignment") or {}).get("alignment") == "bearish"),
                "top_symbol": rows[0]["symbol"] if rows else "",
                "sort_by": sort_key,
            },
            "scan_context": {
                "timeframes": timeframes,
                "indicators": request.indicators,
                "include_orderbook": request.include_orderbook,
            },
            "fetched_at": _utc_now_iso(),
        }

    def get_data_health(self, request: AgentDataHealthQueryRequest) -> Dict[str, Any]:
        return self._build_data_health_payload(
            symbol=request.symbol,
            include_orphans=request.include_orphans,
        )

    def analyze_multi_timeframe_alignment(self, request: AgentAlignmentQueryRequest) -> Dict[str, Any]:
        resolved_inst_id, inst_type = _resolve_query_inst_id(request.inst_id, request.inst_type.value)
        timeframe_signals: Dict[str, Any] = {}
        bullish_count = 0
        bearish_count = 0
        neutral_count = 0

        for timeframe in _dedupe_timeframes(request.timeframes):
            candles = self._load_candles(
                inst_id=resolved_inst_id,
                inst_type=inst_type,
                timeframe=timeframe,
                limit=request.limit,
                auto_sync=request.auto_sync,
            )
            signal = self._build_timeframe_signal(candles, timeframe)
            timeframe_signals[timeframe] = signal
            if signal["trend"] == "bullish":
                bullish_count += 1
            elif signal["trend"] == "bearish":
                bearish_count += 1
            elif signal["trend"] == "neutral":
                neutral_count += 1

        total = max(len(timeframe_signals), 1)
        if bullish_count > bearish_count and bullish_count >= max(2, bearish_count + 1):
            alignment = "bullish"
        elif bearish_count > bullish_count and bearish_count >= max(2, bullish_count + 1):
            alignment = "bearish"
        elif bullish_count == 0 and bearish_count == 0:
            alignment = "neutral"
        else:
            alignment = "mixed"

        majority_trend = "bullish" if bullish_count >= bearish_count else "bearish"
        conflict_timeframes = [
            timeframe
            for timeframe, signal in timeframe_signals.items()
            if alignment in {"bullish", "bearish"} and signal.get("trend") not in {alignment, "missing"}
        ]
        aligned_timeframes = [
            timeframe
            for timeframe, signal in timeframe_signals.items()
            if signal.get("trend") == (alignment if alignment in {"bullish", "bearish"} else majority_trend)
        ]
        confidence = (
            max(bullish_count, bearish_count) / total
            if alignment in {"bullish", "bearish"} else
            (0.35 if alignment == "mixed" else 0.2)
        )

        return {
            "inst_id": resolved_inst_id,
            "inst_type": inst_type,
            "alignment": alignment,
            "confidence": round(confidence, 4),
            "bullish_count": bullish_count,
            "bearish_count": bearish_count,
            "neutral_count": neutral_count,
            "aligned_timeframes": aligned_timeframes,
            "conflict_timeframes": conflict_timeframes,
            "timeframe_signals": timeframe_signals,
            "summary": {
                "message": (
                    "多周期趋势同向。"
                    if alignment in {"bullish", "bearish"} else
                    ("周期之间存在明显冲突。" if alignment == "mixed" else "当前缺少明确共振。")
                ),
            },
            "fetched_at": _utc_now_iso(),
        }

    def analyze_market_structure(self, request: AgentMarketStructureRequest) -> Dict[str, Any]:
        inst_type = _normalize_inst_type(request.inst_id, request.inst_type.value)
        timeframes = _dedupe_timeframes(request.timeframes)
        trading_context = self.get_trading_context(
            AgentTradingContextRequest(
                inst_id=request.inst_id,
                inst_type=inst_type,
                timeframes=timeframes,
                candles_limit=request.limit,
                indicators=["ma20", "rsi", "macd", "atr14", "volume_ma20"],
                include_orderbook=True,
                orderbook_depth=request.orderbook_depth,
                include_recent_trades=True,
                recent_trade_limit=request.recent_trade_limit,
                include_position=False,
                mode=request.mode,
                auto_sync=request.auto_sync,
            )
        )
        alignment = trading_context.get("alignment") or {}
        price_summary = (trading_context.get("market_snapshot") or {}).get("price_summary") or {}
        signals = alignment.get("timeframe_signals") or {}
        reference_timeframe = timeframes[min(len(timeframes) - 1, max(0, len(timeframes) // 2))]
        reference_signal = signals.get(reference_timeframe) or next(iter(signals.values()), {})

        orderbook = trading_context.get("orderbook") or {}
        bid_total = sum(_safe_float(item.get("size")) for item in orderbook.get("bids") or [])
        ask_total = sum(_safe_float(item.get("size")) for item in orderbook.get("asks") or [])
        orderbook_total = bid_total + ask_total
        orderbook_imbalance = (bid_total / orderbook_total) if orderbook_total > 0 else 0.5
        trades = trading_context.get("recent_trades") or {}
        trades_summary = trades.get("summary") or {}
        trade_buy = _safe_float(trades_summary.get("buy_volume"))
        trade_sell = _safe_float(trades_summary.get("sell_volume"))
        trade_imbalance = (trade_buy / (trade_buy + trade_sell)) if (trade_buy + trade_sell) > 0 else 0.5
        health_row = trading_context.get("data_health") or _serialize_health_row(None)
        atr_ratio = _safe_float(reference_signal.get("atr_ratio"))
        volume_ratio = _safe_float(reference_signal.get("volume_ratio"), 1.0)
        spread_bps = _safe_float(price_summary.get("spread_bps"))

        volatility_state = "high" if atr_ratio >= 0.03 else ("moderate" if atr_ratio >= 0.015 else "low")
        volume_state = "expanded" if volume_ratio >= 1.25 else ("soft" if volume_ratio <= 0.8 else "normal")
        orderbook_state = "bid_support" if orderbook_imbalance >= 0.56 else ("ask_pressure" if orderbook_imbalance <= 0.44 else "balanced")

        risk_flags: List[str] = []
        if _safe_float(health_row.get("health_score")) < 60:
            risk_flags.append("data_stale")
        if spread_bps >= 8:
            risk_flags.append("wide_spread")
        if volatility_state == "high":
            risk_flags.append("high_volatility")
        if alignment.get("alignment") == "mixed":
            risk_flags.append("timeframe_conflict")

        bias = alignment.get("alignment")
        if bias not in {"bullish", "bearish"}:
            if orderbook_state == "bid_support" and trade_imbalance > 0.55:
                bias = "bullish"
            elif orderbook_state == "ask_pressure" and trade_imbalance < 0.45:
                bias = "bearish"
            else:
                bias = "neutral"

        confidence = min(
            1.0,
            _safe_float(alignment.get("confidence")) * 0.6
            + abs(orderbook_imbalance - 0.5) * 0.5
            + abs(trade_imbalance - 0.5) * 0.35,
        )

        key_levels = {
            "current_price": _safe_json_value(price_summary.get("last")),
            "ma20": _safe_json_value((reference_signal.get("indicators") or {}).get("ma20")),
            "best_bid": _safe_json_value(orderbook.get("best_bid")),
            "best_ask": _safe_json_value(orderbook.get("best_ask")),
        }
        invalidation = (
            f"若价格重新跌破 {key_levels['ma20']} 且买盘失衡消失，则看多逻辑失效。"
            if bias == "bullish" and key_levels["ma20"] is not None else
            (
                f"若价格重新站回 {key_levels['ma20']} 且卖压无法延续，则看空逻辑失效。"
                if bias == "bearish" and key_levels["ma20"] is not None else
                "等待多周期方向重新一致后再评估。"
            )
        )

        return {
            "inst_id": request.inst_id,
            "inst_type": inst_type,
            "mode": normalize_mode(request.mode.value) or self.ctx.default_mode(),
            "trend": {
                "bias": bias,
                "alignment": alignment.get("alignment"),
                "confidence": round(confidence, 4),
                "timeframe_reference": reference_timeframe,
                "aligned_timeframes": alignment.get("aligned_timeframes") or [],
                "conflict_timeframes": alignment.get("conflict_timeframes") or [],
            },
            "volatility": {
                "atr_ratio": _safe_json_value(atr_ratio),
                "state": volatility_state,
                "spread_bps": _safe_json_value(spread_bps),
            },
            "volume": {
                "volume_ratio": _safe_json_value(volume_ratio),
                "state": volume_state,
                "trade_buy_volume": _safe_json_value(trade_buy),
                "trade_sell_volume": _safe_json_value(trade_sell),
                "trade_imbalance": _safe_json_value(trade_imbalance),
            },
            "orderbook": {
                "state": orderbook_state,
                "imbalance": _safe_json_value(orderbook_imbalance),
                "bid_total": _safe_json_value(bid_total),
                "ask_total": _safe_json_value(ask_total),
                "best_bid": orderbook.get("best_bid"),
                "best_ask": orderbook.get("best_ask"),
            },
            "risk": {
                "health_score": _safe_json_value(health_row.get("health_score")),
                "status": health_row.get("status"),
                "flags": risk_flags,
            },
            "conclusion": {
                "bias": bias,
                "confidence": round(confidence, 4),
                "suggested_action": (
                    "顺势跟踪，但等待回踩确认。"
                    if bias == "bullish" else
                    ("优先防守，等待反弹失败后再考虑空头延续。" if bias == "bearish" else "暂时观望。")
                ),
                "key_levels": key_levels,
                "invalidation": invalidation,
            },
            "fetched_at": _utc_now_iso(),
        }

    def detect_support_resistance(self, request: AgentSupportResistanceRequest) -> Dict[str, Any]:
        inst_type = _normalize_inst_type(request.inst_id, request.inst_type.value)
        market_snapshot = self.get_market_snapshot(
            AgentMarketQueryRequest(inst_id=request.inst_id, inst_type=inst_type)
        )
        current_price = _safe_float((market_snapshot.get("price_summary") or {}).get("last"))
        if current_price <= 0:
            raise ValueError(f"未找到 {request.inst_id} 的有效最新价")

        raw_levels: List[Dict[str, Any]] = []
        timeframe_weights = {
            timeframe: index + 1
            for index, timeframe in enumerate(_dedupe_timeframes(request.timeframes))
        }

        for timeframe in _dedupe_timeframes(request.timeframes):
            candles = self._load_candles(
                inst_id=request.inst_id,
                inst_type=inst_type,
                timeframe=timeframe,
                limit=request.limit,
                auto_sync=request.auto_sync,
            )
            if len(candles) < 7:
                continue
            window = 2
            weight = float(timeframe_weights.get(timeframe, 1))
            for index in range(window, len(candles) - window):
                current = candles[index]
                low = _safe_float(getattr(current, "low", 0))
                high = _safe_float(getattr(current, "high", 0))
                volume = _safe_float(getattr(current, "volume", 0))
                timestamp = _safe_float(getattr(current, "timestamp", 0))
                previous_slice = candles[index - window:index]
                next_slice = candles[index + 1:index + window + 1]
                if previous_slice and next_slice:
                    is_support = all(
                        low <= _safe_float(getattr(item, "low", 0))
                        for item in [*previous_slice, *next_slice]
                    )
                    is_resistance = all(
                        high >= _safe_float(getattr(item, "high", 0))
                        for item in [*previous_slice, *next_slice]
                    )
                    recency_weight = 1.0 + (index / max(len(candles), 1))
                    volume_weight = 1.0 + min(volume / 100.0, 2.0)
                    if is_support:
                        raw_levels.append({
                            "side": "support",
                            "price": low,
                            "timeframe": timeframe,
                            "timestamp": timestamp,
                            "strength": round(weight * recency_weight * volume_weight, 4),
                        })
                    if is_resistance:
                        raw_levels.append({
                            "side": "resistance",
                            "price": high,
                            "timeframe": timeframe,
                            "timestamp": timestamp,
                            "strength": round(weight * recency_weight * volume_weight, 4),
                        })

        tolerance = current_price * (request.cluster_tolerance_bps / 10000.0)

        def cluster_levels(levels: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
            clusters: List[Dict[str, Any]] = []
            for item in sorted(levels, key=lambda entry: entry["price"]):
                if not clusters:
                    clusters.append({
                        "prices": [item["price"]],
                        "timeframes": {item["timeframe"]},
                        "timestamps": [item["timestamp"]],
                        "strength_total": item["strength"],
                        "touch_count": 1,
                    })
                    continue
                previous = clusters[-1]
                center_price = sum(previous["prices"]) / len(previous["prices"])
                if abs(item["price"] - center_price) <= tolerance:
                    previous["prices"].append(item["price"])
                    previous["timeframes"].add(item["timeframe"])
                    previous["timestamps"].append(item["timestamp"])
                    previous["strength_total"] += item["strength"]
                    previous["touch_count"] += 1
                else:
                    clusters.append({
                        "prices": [item["price"]],
                        "timeframes": {item["timeframe"]},
                        "timestamps": [item["timestamp"]],
                        "strength_total": item["strength"],
                        "touch_count": 1,
                    })

            normalized: List[Dict[str, Any]] = []
            for cluster in clusters:
                prices = cluster["prices"]
                strength = cluster["strength_total"]
                avg_price = sum(prices) / len(prices)
                normalized.append({
                    "price": round(avg_price, 8),
                    "strength": round(strength, 4),
                    "touch_count": int(cluster["touch_count"]),
                    "timeframes": sorted(cluster["timeframes"], key=_timeframe_sort_key),
                    "latest_timestamp": max(cluster["timestamps"]) if cluster["timestamps"] else None,
                    "distance_pct": round(((avg_price - current_price) / current_price) * 100.0, 4),
                })
            normalized.sort(key=lambda item: (-item["strength"], abs(item["distance_pct"])))
            return normalized

        supports = cluster_levels([item for item in raw_levels if item["side"] == "support" and item["price"] < current_price])[:request.max_levels_per_side]
        resistances = cluster_levels([item for item in raw_levels if item["side"] == "resistance" and item["price"] > current_price])[:request.max_levels_per_side]

        invalidation_levels: List[Dict[str, Any]] = []
        if supports:
            invalidation_levels.append({
                "kind": "bullish_invalidation",
                "price": supports[0]["price"],
                "reason": "若价格有效跌破最近支撑，则当前偏多结构失效",
            })
        if resistances:
            invalidation_levels.append({
                "kind": "bearish_invalidation",
                "price": resistances[0]["price"],
                "reason": "若价格有效突破最近压力，则当前偏空结构失效",
            })

        chart_annotations = [
            *[
                _build_horizontal_annotation(
                    level["price"],
                    role="support",
                    timeframe="/".join(level["timeframes"]),
                    strength=level["strength"],
                )
                for level in supports
            ],
            *[
                _build_horizontal_annotation(
                    level["price"],
                    role="resistance",
                    timeframe="/".join(level["timeframes"]),
                    strength=level["strength"],
                )
                for level in resistances
            ],
        ]

        return {
            "inst_id": request.inst_id,
            "inst_type": inst_type,
            "current_price": _safe_json_value(current_price),
            "supports": supports,
            "resistances": resistances,
            "invalidation_levels": invalidation_levels,
            "chart_annotations": chart_annotations,
            "summary": {
                "nearest_support": supports[0]["price"] if supports else None,
                "nearest_resistance": resistances[0]["price"] if resistances else None,
                "support_count": len(supports),
                "resistance_count": len(resistances),
            },
            "fetched_at": _utc_now_iso(),
        }

    def get_level_snapshot(self, snapshot_id: str) -> Dict[str, Any]:
        storage = self.ctx.storage()
        snapshot = storage.get_assistant_level_snapshot((snapshot_id or "").strip())
        if not snapshot:
            raise ValueError(f"未找到关键位快照 {snapshot_id}")
        return {
            "snapshot": snapshot,
            "fetched_at": _utc_now_iso(),
        }

    def save_support_resistance_snapshot(self, request: AgentLevelSnapshotRequest) -> Dict[str, Any]:
        storage = self.ctx.storage()
        session_id = (request.session_id or "").strip()
        if session_id and not storage.get_assistant_session(session_id):
            raise ValueError(f"未找到会话 {session_id}")

        analysis = self.detect_support_resistance(
            AgentSupportResistanceRequest(
                inst_id=request.inst_id,
                inst_type=request.inst_type.value,
                timeframes=request.timeframes,
                limit=request.limit,
                max_levels_per_side=request.max_levels_per_side,
                cluster_tolerance_bps=request.cluster_tolerance_bps,
                auto_sync=request.auto_sync,
            )
        )
        title = (request.title or "").strip() or f"{request.inst_id} 关键位快照"
        summary = {
            **(analysis.get("summary") or {}),
            "message": (
                f"已保存 {request.inst_id} 关键位快照，"
                f"支撑 {len(analysis.get('supports') or [])} 个，"
                f"压力 {len(analysis.get('resistances') or [])} 个。"
            ),
        }
        metadata = {
            "note": (request.note or "").strip(),
            "source": (request.source or "assistant").strip() or "assistant",
        }
        snapshot_id = storage.create_assistant_level_snapshot(
            session_id=session_id,
            source=metadata["source"],
            title=title,
            inst_id=request.inst_id,
            inst_type=analysis.get("inst_type") or _normalize_inst_type(request.inst_id, request.inst_type.value),
            timeframes=_dedupe_timeframes(request.timeframes),
            current_price=_safe_float(analysis.get("current_price")),
            supports=analysis.get("supports") or [],
            resistances=analysis.get("resistances") or [],
            invalidation_levels=analysis.get("invalidation_levels") or [],
            chart_annotations=analysis.get("chart_annotations") or [],
            summary=summary,
            metadata=metadata,
        )
        snapshot = storage.get_assistant_level_snapshot(snapshot_id)
        return {
            "snapshot_id": snapshot_id,
            "inst_id": request.inst_id,
            "inst_type": analysis.get("inst_type") or request.inst_type.value,
            "supports": analysis.get("supports") or [],
            "resistances": analysis.get("resistances") or [],
            "invalidation_levels": analysis.get("invalidation_levels") or [],
            "chart_annotations": analysis.get("chart_annotations") or [],
            "summary": summary,
            "snapshot": snapshot,
            "message": "关键位快照已保存，可供后续复盘或再次调取。",
            "fetched_at": _utc_now_iso(),
        }

    def list_level_snapshots(self, request: AgentLevelSnapshotListRequest) -> Dict[str, Any]:
        storage = self.ctx.storage()
        snapshots = storage.list_assistant_level_snapshots(
            session_id=(request.session_id or "").strip(),
            inst_id=(request.inst_id or "").strip(),
            source=(request.source or "").strip(),
            limit=request.limit,
        )
        return {
            "snapshots": snapshots,
            "count": len(snapshots),
            "filters": {
                "session_id": (request.session_id or "").strip(),
                "inst_id": (request.inst_id or "").strip(),
                "source": (request.source or "").strip(),
                "limit": request.limit,
            },
            "fetched_at": _utc_now_iso(),
        }

    def generate_price_projection(self, request: AgentPriceProjectionRequest) -> Dict[str, Any]:
        inst_type = _normalize_inst_type(request.inst_id, request.inst_type.value)
        timeframe = _normalize_timeframe(request.timeframe)
        candles = self._load_candles(
            inst_id=request.inst_id,
            inst_type=inst_type,
            timeframe=timeframe,
            limit=request.limit,
            auto_sync=request.auto_sync,
        )
        if len(candles) < 30:
            raise ValueError(f"未找到足够的 {request.inst_id} {timeframe} K 线数据")

        signal = self._build_timeframe_signal(candles, timeframe)
        alignment = self.analyze_multi_timeframe_alignment(
            AgentAlignmentQueryRequest(
                inst_id=request.inst_id,
                inst_type=inst_type,
                timeframes=[timeframe, "4H" if timeframe != "4H" else "1D"],
                limit=request.limit,
                auto_sync=request.auto_sync,
            )
        )
        recent = candles[-min(20, len(candles)):]
        closes = [_safe_float(getattr(item, "close", 0)) for item in recent]
        last_candle = candles[-1]
        last_ts = _safe_float(getattr(last_candle, "timestamp", 0))
        last_close = _safe_float(getattr(last_candle, "close", 0))
        timeframe_ms = TIMEFRAME_TO_MS.get(timeframe, 60 * 60 * 1000)

        if len(closes) >= 2:
            slope = (closes[-1] - closes[0]) / max(len(closes) - 1, 1)
        else:
            slope = 0.0
        atr_ratio = _safe_float(signal.get("atr_ratio"))
        atr_value = atr_ratio * last_close if last_close > 0 else 0.0
        volatility_band = atr_value * max(math.sqrt(max(request.horizon_bars, 1)), 1.0)
        projected_drift = slope * request.horizon_bars

        scenarios = {
            "bullish": {
                "end_price": round(last_close + projected_drift + volatility_band * 0.9, 8),
                "confidence": round(min(0.85, 0.35 + _safe_float(alignment.get("confidence")) * 0.5), 4),
            },
            "base": {
                "end_price": round(last_close + projected_drift, 8),
                "confidence": round(0.55, 4),
            },
            "bearish": {
                "end_price": round(last_close + projected_drift - volatility_band * 0.9, 8),
                "confidence": round(min(0.8, 0.3 + (1.0 - _safe_float(alignment.get("confidence"))) * 0.4), 4),
            },
        }
        for scenario_name, payload in scenarios.items():
            mid_price = round((last_close + payload["end_price"]) / 2.0, 8)
            payload["path"] = [
                {"timestamp": int(last_ts), "price": round(last_close, 8)},
                {"timestamp": int(last_ts + timeframe_ms * max(request.horizon_bars // 2, 1)), "price": mid_price},
                {"timestamp": int(last_ts + timeframe_ms * request.horizon_bars), "price": payload["end_price"]},
            ]

        if alignment.get("alignment") == "bullish":
            selected = "bullish"
        elif alignment.get("alignment") == "bearish":
            selected = "bearish"
        else:
            selected = "base"

        selected_path = scenarios[selected]["path"]
        chart_annotations = [
            _build_trendline_annotation(
                start_ts=selected_path[0]["timestamp"],
                end_ts=selected_path[-1]["timestamp"],
                start_price=selected_path[0]["price"],
                end_price=selected_path[-1]["price"],
                scenario=selected,
            ),
        ]

        return {
            "inst_id": request.inst_id,
            "inst_type": inst_type,
            "timeframe": timeframe,
            "horizon_bars": request.horizon_bars,
            "selected_scenario": selected,
            "scenarios": scenarios,
            "projection_summary": {
                "start_price": round(last_close, 8),
                "selected_end_price": scenarios[selected]["end_price"],
                "drift": round(projected_drift, 8),
                "volatility_band": round(volatility_band, 8),
                "alignment": alignment.get("alignment"),
                "note": "这是基于最近趋势与波动的启发式路径推演，不是确定性预测。",
            },
            "chart_annotations": chart_annotations,
            "fetched_at": _utc_now_iso(),
        }

    def patrol_market_opportunities(self, request: AgentOpportunityPatrolRequest) -> Dict[str, Any]:
        inst_type = str(request.inst_type.value).upper()
        watchlist_scan = self.scan_watchlist_context(
            AgentWatchlistScanRequest(
                inst_type=inst_type,
                limit=request.scan_limit,
                timeframes=request.timeframes,
                candles_limit=request.candles_limit,
                include_orderbook=True,
                orderbook_depth=request.orderbook_depth,
                sort_by="signal_score",
            )
        )

        candidates: List[Dict[str, Any]] = []
        for row in watchlist_scan.get("rows", [])[: max(request.candidate_limit * 2, request.candidate_limit)]:
            inst_id = row.get("inst_id") or row.get("symbol")
            if not inst_id:
                continue
            structure = self.analyze_market_structure(
                AgentMarketStructureRequest(
                    inst_id=inst_id,
                    inst_type=inst_type,
                    timeframes=request.timeframes,
                    limit=request.candles_limit,
                    orderbook_depth=request.orderbook_depth,
                    recent_trade_limit=request.recent_trade_limit,
                    mode=request.mode,
                )
            )
            levels = self.detect_support_resistance(
                AgentSupportResistanceRequest(
                    inst_id=inst_id,
                    inst_type=inst_type,
                    timeframes=[*request.timeframes, "1D"],
                    limit=max(180, request.candles_limit),
                    max_levels_per_side=2,
                )
            )
            bias = (structure.get("trend") or {}).get("bias") or "neutral"
            confidence = _safe_float((structure.get("trend") or {}).get("confidence"))
            health_score = _safe_float(((structure.get("risk") or {}).get("health_score")))
            spread_bps = _safe_float(((row.get("price_summary") or {}).get("spread_bps")))
            if bias == "neutral" or confidence < 0.42 or health_score < 45 or spread_bps > 15:
                continue

            nearest_support = ((levels.get("supports") or [{}])[0]).get("price")
            nearest_resistance = ((levels.get("resistances") or [{}])[0]).get("price")
            action = "关注回踩低吸" if bias == "bullish" else "关注反弹承压"
            priority = round(
                confidence * 60.0
                + _safe_float(row.get("signal_score")) * 0.3
                + min(health_score / 5.0, 20.0),
                4,
            )

            candidates.append({
                "symbol": row.get("symbol") or inst_id,
                "inst_id": inst_id,
                "inst_type": inst_type,
                "priority_score": priority,
                "bias": bias,
                "confidence": round(confidence, 4),
                "action": action,
                "entry_reference": nearest_support if bias == "bullish" else nearest_resistance,
                "invalidation_reference": nearest_support if bias == "bearish" else nearest_resistance,
                "reasoning": {
                    "signal_score": row.get("signal_score"),
                    "alignment": (row.get("alignment") or {}).get("alignment"),
                    "health_score": health_score,
                    "spread_bps": spread_bps,
                },
                "data_health": _serialize_health_row(row.get("data_health")),
                "key_levels": {
                    "supports": levels.get("supports") or [],
                    "resistances": levels.get("resistances") or [],
                },
                "chart_annotations": [
                    {
                        **item,
                        "meta": {
                            **(item.get("meta") or {}),
                            "origin": "patrol",
                        },
                    }
                    for item in (levels.get("chart_annotations") or [])
                ],
                "structure": {
                    "trend": structure.get("trend") or {},
                    "conclusion": structure.get("conclusion") or {},
                },
            })

        candidates.sort(key=lambda item: item["priority_score"], reverse=True)
        candidates = candidates[:request.candidate_limit]

        for candidate in candidates:
            try:
                setup = self.build_trade_setup(
                    AgentTradeSetupRequest(
                        inst_id=candidate.get("inst_id") or candidate.get("symbol") or "",
                        inst_type=inst_type,
                        mode=request.mode,
                        side_preference="buy" if candidate.get("bias") == "bullish" else (
                            "sell" if candidate.get("bias") == "bearish" else "auto"
                        ),
                        structure_timeframes=request.timeframes,
                        level_timeframes=[*request.timeframes, "1D"],
                        projection_timeframe=request.timeframes[0] if request.timeframes else "1H",
                        candles_limit=max(request.candles_limit, 180),
                        orderbook_depth=request.orderbook_depth,
                        recent_trade_limit=request.recent_trade_limit,
                    )
                )
            except Exception:
                setup = {}

            candidate["setup_status"] = setup.get("setup_status") or "watch"
            candidate["setup_confidence"] = setup.get("confidence")
            candidate["trade_plan"] = setup.get("trade_plan") or {}
            candidate["checklist"] = setup.get("checklist") or []
            candidate["setup_summary"] = setup.get("summary") or {}
            candidate["chart_annotations"] = (
                list(candidate.get("chart_annotations") or [])
                + list(setup.get("chart_annotations") or [])
            )
            if setup.get("structure"):
                candidate["structure"] = setup.get("structure")
            if setup.get("projection"):
                candidate["projection"] = setup.get("projection")

        return {
            "inst_type": inst_type,
            "candidates": candidates,
            "summary": {
                "candidate_count": len(candidates),
                "scan_count": len(watchlist_scan.get("rows") or []),
                "top_candidate": candidates[0]["symbol"] if candidates else "",
                "ready_count": sum(1 for item in candidates if item.get("setup_status") == "ready"),
                "watch_count": sum(1 for item in candidates if item.get("setup_status") == "watch"),
                "message": (
                    f"发现 {len(candidates)} 个可继续跟踪的候选机会。"
                    if candidates else
                    "本轮未发现满足条件的高质量候选机会。"
                ),
            },
            "scan_context": {
                "timeframes": _dedupe_timeframes(request.timeframes),
                "mode": normalize_mode(request.mode.value) or self.ctx.default_mode(),
                "orderbook_depth": request.orderbook_depth,
            },
            "fetched_at": _utc_now_iso(),
        }

    def get_patrol_run(self, run_id: str) -> Dict[str, Any]:
        storage = self.ctx.storage()
        run = storage.get_assistant_patrol_run((run_id or "").strip())
        if not run:
            raise ValueError(f"未找到巡检记录 {run_id}")
        return {
            "run": run,
            "fetched_at": _utc_now_iso(),
        }

    def list_patrol_runs(self, request: AgentPatrolRunListRequest) -> Dict[str, Any]:
        storage = self.ctx.storage()
        runs = storage.list_assistant_patrol_runs(
            inst_type=(request.inst_type or "").strip().upper(),
            mode=(request.mode or "").strip(),
            trigger=(request.trigger or "").strip(),
            limit=request.limit,
        )
        return {
            "runs": runs,
            "count": len(runs),
            "filters": {
                "inst_type": (request.inst_type or "").strip().upper(),
                "mode": (request.mode or "").strip(),
                "trigger": (request.trigger or "").strip(),
                "limit": request.limit,
            },
            "fetched_at": _utc_now_iso(),
        }

    def build_risk_budget(self, request: AgentRiskBudgetRequest) -> Dict[str, Any]:
        mode = normalize_mode(request.mode.value) or self.ctx.default_mode()
        inst_type = _normalize_inst_type(request.inst_id, request.inst_type.value)
        account = self.ctx.account(mode)
        fetcher = self.ctx.fetcher()
        storage = self.ctx.storage()
        cost_data = storage.get_cost_basis(mode)
        summary = build_risk_summary(
            account=account,
            fetcher=fetcher,
            cost_data=cost_data,
        )
        config = get_risk_control_store().get_config_dict()

        market_snapshot = self.get_market_snapshot(
            AgentMarketQueryRequest(inst_id=request.inst_id, inst_type=inst_type)
        )
        reference_price = _safe_float(request.entry_price, _safe_float((market_snapshot.get("price_summary") or {}).get("last")))
        stop_loss_ratio = (
            request.stop_loss_ratio
            if request.stop_loss_ratio is not None else
            _safe_float(config.get("default_stop_loss_ratio"), 0.03)
        )
        max_single_loss_ratio = (
            request.max_single_loss_ratio
            if request.max_single_loss_ratio is not None else
            _safe_float(config.get("max_single_loss_ratio"), 0.02)
        )
        max_total_position_ratio = (
            request.max_total_position_ratio
            if request.max_total_position_ratio is not None else
            _safe_float(config.get("max_total_position_ratio"), 1.0)
        )

        total_equity = _safe_float(summary.get("total_equity"))
        current_exposure = _safe_float(summary.get("total_exposure"))
        remaining_exposure = max(0.0, total_equity * max_total_position_ratio - current_exposure)
        risk_limited_notional = (
            (total_equity * max_single_loss_ratio / stop_loss_ratio)
            if total_equity > 0 and stop_loss_ratio > 0 else
            remaining_exposure
        )
        recommended_max_notional = max(
            0.0,
            min(
                remaining_exposure if remaining_exposure > 0 else 0.0,
                risk_limited_notional if risk_limited_notional > 0 else remaining_exposure,
            ),
        )
        suggested_max_size = (recommended_max_notional / reference_price) if reference_price > 0 else 0.0
        stop_price = (
            reference_price * (1 - stop_loss_ratio if request.side == "buy" else 1 + stop_loss_ratio)
            if reference_price > 0 else
            0.0
        )

        proposed_order_evaluation = None
        if request.proposed_size is not None:
            proposed_order_evaluation = evaluate_order_risk(
                account=account,
                fetcher=fetcher,
                inst_id=request.inst_id,
                inst_type=inst_type,
                side=request.side,
                size=request.proposed_size,
                price=reference_price,
                stop_loss_ratio=stop_loss_ratio,
            )

        return {
            "inst_id": request.inst_id,
            "inst_type": inst_type,
            "mode": mode,
            "config": {
                **config,
                "applied_stop_loss_ratio": round(stop_loss_ratio, 8),
                "applied_max_single_loss_ratio": round(max_single_loss_ratio, 8),
                "applied_max_total_position_ratio": round(max_total_position_ratio, 8),
            },
            "summary": summary,
            "reference_price": _safe_json_value(reference_price),
            "budget": {
                "remaining_exposure": round(remaining_exposure, 8),
                "risk_limited_notional": round(risk_limited_notional, 8),
                "recommended_max_notional": round(recommended_max_notional, 8),
                "suggested_max_size": round(suggested_max_size, 8),
                "stop_price": round(stop_price, 8) if stop_price > 0 else 0.0,
                "status": "blocked" if recommended_max_notional <= 0 else "available",
            },
            "proposed_order_evaluation": proposed_order_evaluation,
            "fetched_at": _utc_now_iso(),
        }

    def build_trade_setup(self, request: AgentTradeSetupRequest) -> Dict[str, Any]:
        mode = normalize_mode(request.mode.value) or self.ctx.default_mode()
        inst_type = _normalize_inst_type(request.inst_id, request.inst_type.value)
        structure_timeframes = _dedupe_timeframes(request.structure_timeframes)
        level_timeframes = _dedupe_timeframes(request.level_timeframes)
        projection_timeframe = _normalize_timeframe(request.projection_timeframe)

        structure = self.analyze_market_structure(
            AgentMarketStructureRequest(
                inst_id=request.inst_id,
                inst_type=inst_type,
                timeframes=structure_timeframes,
                limit=request.candles_limit,
                orderbook_depth=request.orderbook_depth,
                recent_trade_limit=request.recent_trade_limit,
                mode=mode,
                auto_sync=request.auto_sync,
            )
        )
        levels = self.detect_support_resistance(
            AgentSupportResistanceRequest(
                inst_id=request.inst_id,
                inst_type=inst_type,
                timeframes=level_timeframes,
                limit=max(request.candles_limit, 180),
                max_levels_per_side=3,
                auto_sync=request.auto_sync,
            )
        )
        projection = self.generate_price_projection(
            AgentPriceProjectionRequest(
                inst_id=request.inst_id,
                inst_type=inst_type,
                timeframe=projection_timeframe,
                limit=request.candles_limit,
                horizon_bars=max(12, min(48, request.candles_limit // 8)),
                auto_sync=request.auto_sync,
            )
        )

        current_price = _safe_float(levels.get("current_price"))
        structure_bias = str(((structure.get("trend") or {}).get("bias") or "neutral")).lower()
        projection_bias = str(projection.get("selected_scenario") or "base").lower()

        if request.side_preference == "buy":
            bias = "bullish"
            side = "buy"
        elif request.side_preference == "sell":
            bias = "bearish"
            side = "sell"
        elif structure_bias == "bullish":
            bias = "bullish"
            side = "buy"
        elif structure_bias == "bearish":
            bias = "bearish"
            side = "sell"
        else:
            bias = "neutral"
            side = "flat"

        supports = levels.get("supports") or []
        resistances = levels.get("resistances") or []
        nearest_support = _safe_float((supports[0] or {}).get("price")) if supports else 0.0
        nearest_resistance = _safe_float((resistances[0] or {}).get("price")) if resistances else 0.0

        if side == "buy":
            entry_reference = nearest_support if nearest_support > 0 else current_price
            entry_zone_low = min(entry_reference, current_price) if current_price > 0 else entry_reference
            entry_zone_high = max(entry_reference, current_price) if current_price > 0 else entry_reference
        elif side == "sell":
            entry_reference = nearest_resistance if nearest_resistance > 0 else current_price
            entry_zone_low = min(entry_reference, current_price) if current_price > 0 else entry_reference
            entry_zone_high = max(entry_reference, current_price) if current_price > 0 else entry_reference
        else:
            entry_reference = current_price
            entry_zone_low = current_price
            entry_zone_high = current_price

        risk_budget = None
        if side in {"buy", "sell"} and entry_reference > 0:
            try:
                risk_budget = self.build_risk_budget(
                    AgentRiskBudgetRequest(
                        inst_id=request.inst_id,
                        inst_type=inst_type,
                        mode=mode,
                        side=side,
                        entry_price=entry_reference,
                        stop_loss_ratio=request.stop_loss_ratio,
                    )
                )
            except Exception:
                risk_budget = {
                    "reference_price": _safe_json_value(entry_reference),
                    "budget": {
                        "status": "unavailable",
                    },
                }

        stop_loss_price = _safe_float((((risk_budget or {}).get("budget") or {}).get("stop_price")))
        stop_distance = abs(entry_reference - stop_loss_price) if entry_reference > 0 and stop_loss_price > 0 else 0.0

        target_prices: List[float] = []
        if side == "buy":
            target_prices.extend(
                _safe_float(item.get("price"))
                for item in resistances
                if _safe_float(item.get("price")) > entry_reference > 0
            )
            projected_price = _safe_float((projection.get("projection_summary") or {}).get("selected_end_price"))
            if projected_price > entry_reference > 0:
                target_prices.append(projected_price)
        elif side == "sell":
            target_prices.extend(
                _safe_float(item.get("price"))
                for item in supports
                if 0 < _safe_float(item.get("price")) < entry_reference
            )
            projected_price = _safe_float((projection.get("projection_summary") or {}).get("selected_end_price"))
            if 0 < projected_price < entry_reference:
                target_prices.append(projected_price)

        normalized_targets: List[Dict[str, Any]] = []
        seen_target_prices: set[float] = set()
        for index, price in enumerate(target_prices):
            if price <= 0:
                continue
            rounded_price = round(price, 8)
            if rounded_price in seen_target_prices:
                continue
            seen_target_prices.add(rounded_price)
            reward = abs(rounded_price - entry_reference) if entry_reference > 0 else 0.0
            reward_risk = (reward / stop_distance) if stop_distance > 0 else 0.0
            normalized_targets.append({
                "label": f"T{len(normalized_targets) + 1}",
                "price": rounded_price,
                "distance_pct": round(((rounded_price - entry_reference) / entry_reference) * 100.0, 4)
                if entry_reference > 0 else 0.0,
                "reward_risk": round(reward_risk, 4),
            })
            if len(normalized_targets) >= 3:
                break

        structure_confidence = _safe_float((structure.get("trend") or {}).get("confidence"))
        health_score = _safe_float(((structure.get("risk") or {}).get("health_score")))
        spread_bps = _safe_float(((structure.get("volatility") or {}).get("spread_bps")))
        execution_score = max(0.0, min(100.0, 100.0 - spread_bps * 5.0))
        projection_score = 50.0
        if side == "buy":
            projection_score = 80.0 if projection_bias == "bullish" else (56.0 if projection_bias == "base" else 24.0)
        elif side == "sell":
            projection_score = 80.0 if projection_bias == "bearish" else (56.0 if projection_bias == "base" else 24.0)
        total_confidence = min(
            1.0,
            (
                structure_confidence * 0.45
                + min(max(health_score, 0.0), 100.0) / 100.0 * 0.2
                + projection_score / 100.0 * 0.2
                + execution_score / 100.0 * 0.15
            ),
        )

        budget_status = str((((risk_budget or {}).get("budget") or {}).get("status") or "available")).lower()
        best_reward_risk = max((item["reward_risk"] for item in normalized_targets), default=0.0)
        if side == "flat" or current_price <= 0 or health_score < 35:
            setup_status = "avoid"
        elif budget_status == "blocked":
            setup_status = "avoid"
        elif structure_confidence >= 0.58 and best_reward_risk >= 1.6 and health_score >= 55 and spread_bps <= 12:
            setup_status = "ready"
        else:
            setup_status = "watch"

        checklist: List[str] = []
        if side == "buy":
            checklist.append("等待价格回踩入场区并确认买盘未明显减弱。")
            checklist.append("若最新一档压力被放量突破，可上调后续目标位。")
        elif side == "sell":
            checklist.append("等待价格反弹至入场区附近并确认卖压重新占优。")
            checklist.append("若最近支撑被快速击穿，可跟踪空头延续。")
        else:
            checklist.append("当前方向不清晰，等待多周期趋势重新一致。")

        if health_score < 60:
            checklist.append("本地数据健康度一般，执行前先确认数据已同步到最新。")
        if spread_bps > 8:
            checklist.append("当前价差偏宽，注意滑点和成交成本。")
        if best_reward_risk > 0:
            checklist.append(f"当前最优目标的收益风险比约为 {best_reward_risk:.2f}。")

        chart_annotations = list(levels.get("chart_annotations") or []) + list(projection.get("chart_annotations") or [])
        if entry_reference > 0:
            chart_annotations.append(
                _build_horizontal_annotation(
                    entry_reference,
                    role="entry",
                    timeframe="/".join(structure_timeframes),
                    strength=total_confidence * 10.0,
                )
            )
        if stop_loss_price > 0:
            chart_annotations.append(
                _build_horizontal_annotation(
                    stop_loss_price,
                    role="stop",
                    timeframe=projection_timeframe,
                    strength=6.0,
                )
            )
        for item in normalized_targets[:2]:
            chart_annotations.append(
                _build_horizontal_annotation(
                    item["price"],
                    role="target",
                    timeframe=projection_timeframe,
                    strength=6.0 + item["reward_risk"],
                )
            )

        summary_message = (
            "当前结构、关键位和预算匹配，已形成可执行交易计划。"
            if setup_status == "ready" else
            ("已有方向但还需要等待更好的触发条件。" if setup_status == "watch" else "当前不建议直接形成交易计划。")
        )

        return {
            "inst_id": request.inst_id,
            "inst_type": inst_type,
            "mode": mode,
            "setup_status": setup_status,
            "bias": bias,
            "confidence": round(total_confidence, 4),
            "component_scores": {
                "structure_confidence": round(structure_confidence, 4),
                "health_score": round(health_score, 2),
                "projection_score": round(projection_score, 2),
                "execution_score": round(execution_score, 2),
            },
            "trade_plan": {
                "side": side,
                "entry_reference": _safe_json_value(round(entry_reference, 8) if entry_reference > 0 else 0.0),
                "entry_zone": {
                    "low": _safe_json_value(round(entry_zone_low, 8) if entry_zone_low > 0 else 0.0),
                    "high": _safe_json_value(round(entry_zone_high, 8) if entry_zone_high > 0 else 0.0),
                    "width_pct": round(((entry_zone_high - entry_zone_low) / entry_reference) * 100.0, 4)
                    if entry_reference > 0 else 0.0,
                },
                "stop_loss": {
                    "price": _safe_json_value(round(stop_loss_price, 8) if stop_loss_price > 0 else 0.0),
                    "distance_pct": round(((stop_loss_price - entry_reference) / entry_reference) * 100.0, 4)
                    if entry_reference > 0 and stop_loss_price > 0 else 0.0,
                },
                "targets": normalized_targets,
                "invalidation": (structure.get("conclusion") or {}).get("invalidation") or "",
                "risk_budget": {
                    "reference_price": (risk_budget or {}).get("reference_price"),
                    "budget": ((risk_budget or {}).get("budget") or {}),
                },
            },
            "key_levels": {
                "supports": supports,
                "resistances": resistances,
            },
            "structure": {
                "trend": structure.get("trend") or {},
                "risk": structure.get("risk") or {},
                "conclusion": structure.get("conclusion") or {},
            },
            "projection": {
                "selected_scenario": projection.get("selected_scenario"),
                "projection_summary": projection.get("projection_summary") or {},
            },
            "checklist": checklist,
            "chart_annotations": chart_annotations,
            "summary": {
                "message": summary_message,
                "best_reward_risk": round(best_reward_risk, 4),
                "budget_status": budget_status,
            },
            "fetched_at": _utc_now_iso(),
        }

    def analyze_watchlist_correlation(self, request: AgentCorrelationQueryRequest) -> Dict[str, Any]:
        inst_type = _normalize_inst_type("", request.inst_type.value)
        timeframe = _normalize_timeframe(request.timeframe)

        symbols: List[str] = []
        seen_symbols: set[str] = set()

        for item in request.symbols:
            inst_id = _resolve_analysis_inst_id(item, inst_type)
            if not inst_id or inst_id in seen_symbols:
                continue
            seen_symbols.add(inst_id)
            symbols.append(inst_id)

        if not symbols and request.use_watchlist_if_empty:
            for row in load_watched_symbols():
                raw_symbol = (
                    row.get("swap_inst_id")
                    if inst_type == "SWAP" else
                    row.get("spot_inst_id")
                ) or row.get("symbol") or ""
                inst_id = _resolve_analysis_inst_id(str(raw_symbol), inst_type)
                if not inst_id or inst_id in seen_symbols:
                    continue
                if inst_type == "SWAP" and row.get("sync_swap") is False and not row.get("swap_inst_id"):
                    continue
                if inst_type == "SPOT" and row.get("sync_spot") is False and not row.get("spot_inst_id"):
                    continue
                seen_symbols.add(inst_id)
                symbols.append(inst_id)

        if len(symbols) < 2:
            raise ValueError("至少需要 2 个交易对才能计算相关性")

        candle_map: Dict[str, List[Any]] = {}
        for symbol in symbols:
            candles = self._load_candles(
                inst_id=symbol,
                inst_type=inst_type,
                timeframe=timeframe,
                limit=request.limit,
                auto_sync=request.auto_sync,
            )
            if len(candles) < 20:
                raise ValueError(f"{symbol} 可用K线不足，至少需要 20 根")
            candle_map[symbol] = candles

        series_by_symbol: Dict[str, Dict[int, float]] = {
            symbol: {
                int(getattr(candle, "timestamp", 0) or 0): _safe_float(getattr(candle, "close", 0))
                for candle in candles
            }
            for symbol, candles in candle_map.items()
        }

        common_timestamps: Optional[set[int]] = None
        for series in series_by_symbol.values():
            timestamps = {timestamp for timestamp, close in series.items() if timestamp > 0 and close > 0}
            common_timestamps = timestamps if common_timestamps is None else (common_timestamps & timestamps)
        aligned_timestamps = sorted(common_timestamps or [])
        if len(aligned_timestamps) < 20:
            raise ValueError("交易对之间公共时间轴不足，无法计算稳定相关性")

        returns_by_symbol: Dict[str, List[float]] = {}
        for symbol in symbols:
            aligned_prices = [series_by_symbol[symbol][ts] for ts in aligned_timestamps]
            returns: List[float] = []
            for left, right in zip(aligned_prices[:-1], aligned_prices[1:]):
                if left <= 0:
                    continue
                returns.append((right - left) / left)
            if len(returns) < 5:
                raise ValueError(f"{symbol} 收益率样本不足")
            returns_by_symbol[symbol] = returns

        matrix: List[List[float]] = []
        heatmap: List[List[float]] = []
        pairs: List[Dict[str, Any]] = []

        for row_index, symbol_a in enumerate(symbols):
            row: List[float] = []
            for col_index, symbol_b in enumerate(symbols):
                if row_index == col_index:
                    correlation = 1.0
                else:
                    correlation = _pearson_correlation(returns_by_symbol[symbol_a], returns_by_symbol[symbol_b])
                correlation = round(max(-1.0, min(1.0, correlation)), 4)
                row.append(correlation)
                heatmap.append([col_index, row_index, correlation])
                if row_index < col_index:
                    pairs.append({
                        "pair": f"{symbol_a} / {symbol_b}",
                        "symbol_a": symbol_a,
                        "symbol_b": symbol_b,
                        "correlation": correlation,
                    })
            matrix.append(row)

        avg_abs_corr = _average(abs(item["correlation"]) for item in pairs)
        diversification_score = max(0.0, min(100.0, (1.0 - min(avg_abs_corr, 1.0)) * 100.0))
        if avg_abs_corr >= 0.75:
            portfolio_hint = "组合高度同向，分散效果较弱。"
        elif avg_abs_corr >= 0.55:
            portfolio_hint = "组合存在一定同向性，建议搭配低相关标的。"
        else:
            portfolio_hint = "当前组合相关性不高，具备一定分散效果。"

        symbol_profiles: List[Dict[str, Any]] = []
        for symbol in symbols:
            related = [
                item["correlation"]
                for item in pairs
                if item["symbol_a"] == symbol or item["symbol_b"] == symbol
            ]
            symbol_profiles.append({
                "symbol": symbol,
                "average_correlation": round(_average(related), 4) if related else 0.0,
                "average_abs_correlation": round(_average(abs(item) for item in related), 4) if related else 0.0,
            })
        symbol_profiles.sort(key=lambda item: item["average_abs_correlation"])

        pairs_sorted = sorted(pairs, key=lambda item: item["correlation"], reverse=True)
        lowest_pairs = sorted(pairs, key=lambda item: item["correlation"])

        return {
            "symbols": symbols,
            "inst_type": inst_type,
            "timeframe": timeframe,
            "limit": request.limit,
            "aligned_points": len(aligned_timestamps),
            "matrix": matrix,
            "heatmap": heatmap,
            "pairs": pairs,
            "top_positive": pairs_sorted[:5],
            "top_negative": lowest_pairs[:5],
            "symbol_profiles": symbol_profiles,
            "portfolio_hint": {
                "average_abs_correlation": round(avg_abs_corr, 4),
                "diversification_score": round(diversification_score, 2),
                "message": portfolio_hint,
                "least_crowded_symbol": symbol_profiles[0]["symbol"] if symbol_profiles else "",
            },
            "summary": {
                "symbol_count": len(symbols),
                "pair_count": len(pairs),
                "message": portfolio_hint,
            },
            "fetched_at": _utc_now_iso(),
        }

    def get_order_draft(self, draft_id: str) -> Dict[str, Any]:
        storage = self.ctx.storage()
        draft = storage.get_assistant_order_draft((draft_id or "").strip())
        if not draft:
            raise ValueError(f"未找到订单草案 {draft_id}")
        return {
            "draft": draft,
            "fetched_at": _utc_now_iso(),
        }

    def create_order_draft(self, request: AgentOrderDraftRequest) -> Dict[str, Any]:
        storage = self.ctx.storage()
        session_id = (request.session_id or "").strip()
        if session_id and not storage.get_assistant_session(session_id):
            raise ValueError(f"未找到会话 {session_id}")

        inst_type = _normalize_inst_type(request.inst_id, request.inst_type.value)
        mode = normalize_mode(request.mode.value) or self.ctx.default_mode()
        trade_setup = self.build_trade_setup(
            AgentTradeSetupRequest(
                inst_id=request.inst_id,
                inst_type=inst_type,
                mode=mode,
                side_preference=request.side_preference,
                stop_loss_ratio=request.stop_loss_ratio,
                auto_sync=request.auto_sync,
            )
        )

        trade_plan = dict(trade_setup.get("trade_plan") or {})
        setup_status = str(trade_setup.get("setup_status") or "watch").lower()
        side = str(trade_plan.get("side") or request.side_preference or "").lower()
        if request.side_preference in {"buy", "sell"}:
            side = request.side_preference
        if side not in {"buy", "sell"}:
            raise ValueError("当前交易计划没有明确方向，无法生成订单草案")

        entry_reference = _safe_float(
            request.price if request.price is not None else trade_plan.get("entry_reference")
        )
        if entry_reference <= 0:
            entry_reference = _safe_float(
                ((trade_plan.get("risk_budget") or {}).get("reference_price"))
            )
        if request.order_type == "limit" and entry_reference <= 0:
            raise ValueError("当前交易计划缺少有效入场价格，无法生成限价草案")

        budget = ((trade_plan.get("risk_budget") or {}).get("budget") or {})
        suggested_size = _safe_float(budget.get("suggested_max_size"))
        draft_size = _safe_float(request.size if request.size is not None else suggested_size)
        if draft_size <= 0:
            raise ValueError("当前风险预算不可用，请手动提供有效的草案数量")

        stop_loss_price = _safe_float((trade_plan.get("stop_loss") or {}).get("price"))
        stop_loss_ratio = (
            abs(entry_reference - stop_loss_price) / entry_reference
            if entry_reference > 0 and stop_loss_price > 0 else
            _safe_float(request.stop_loss_ratio, 0.03)
        )

        take_profit_prices = [
            _safe_float(item.get("price"))
            for item in (trade_plan.get("targets") or [])
            if _safe_float(item.get("price")) > 0
        ]
        take_profit_prices = [round(price, 8) for price in take_profit_prices[:3]]

        risk_evaluation = None
        try:
            risk_evaluation = evaluate_order_risk(
                account=self.ctx.account(mode),
                fetcher=self.ctx.fetcher(),
                inst_id=request.inst_id,
                inst_type=inst_type,
                side=side,
                size=draft_size,
                price=entry_reference if entry_reference > 0 else None,
                stop_loss_ratio=stop_loss_ratio,
                pos_side=request.pos_side,
                reduce_only=request.reduce_only,
            )
        except Exception as exc:
            risk_evaluation = {
                "status": "unavailable",
                "message": str(exc),
            }

        price_value = entry_reference if request.order_type == "limit" else 0.0
        direction_label = "买入" if side == "buy" else "卖出"
        price_label = _format_order_number(price_value) if price_value > 0 else "市价"
        size_label = _format_order_number(draft_size)
        stop_label = _format_order_number(stop_loss_price)
        title = (request.title or "").strip() or f"{direction_label}{request.inst_id}草案"

        summary_parts = [
            f"{direction_label} {request.inst_id}",
            f"数量 {size_label}",
            f"价格 {price_label}",
        ]
        if stop_label:
            summary_parts.append(f"止损 {stop_label}")
        if take_profit_prices:
            summary_parts.append(
                "目标 "
                + " / ".join(_format_order_number(price) for price in take_profit_prices[:3])
            )
        summary_parts.append(f"计划状态 {setup_status}")
        summary_text = "，".join(summary_parts) + "。"
        if (request.note or "").strip():
            summary_text += f"备注：{request.note.strip()}"

        plan_payload = {
            "setup_status": trade_setup.get("setup_status"),
            "bias": trade_setup.get("bias"),
            "confidence": trade_setup.get("confidence"),
            "component_scores": trade_setup.get("component_scores") or {},
            "trade_plan": trade_plan,
            "key_levels": trade_setup.get("key_levels") or {},
            "projection": trade_setup.get("projection") or {},
            "checklist": trade_setup.get("checklist") or [],
            "summary": trade_setup.get("summary") or {},
        }
        risk_payload = {
            "budget_status": (trade_setup.get("summary") or {}).get("budget_status") or budget.get("status") or "",
            "budget": budget,
            "risk_evaluation": risk_evaluation,
        }
        annotations = list(trade_setup.get("chart_annotations") or [])
        metadata = {
            "note": (request.note or "").strip(),
            "requested_side_preference": request.side_preference,
            "requires_confirmation": True,
            "requires_manual_execution": True,
            "setup_status": setup_status,
        }

        draft_id = storage.create_assistant_order_draft(
            session_id=session_id,
            source="assistant",
            title=title,
            status="draft",
            mode=mode,
            inst_id=request.inst_id,
            inst_type=inst_type,
            side=side,
            order_type=request.order_type,
            td_mode=request.td_mode,
            pos_side=request.pos_side,
            reduce_only=request.reduce_only,
            size=size_label,
            price=_format_order_number(price_value),
            stop_loss_price=stop_label,
            take_profit_prices=take_profit_prices,
            risk_payload=risk_payload,
            plan_payload=plan_payload,
            annotations=annotations,
            summary=summary_text,
            metadata=metadata,
        )
        draft = storage.get_assistant_order_draft(draft_id)

        return {
            "draft_id": draft_id,
            "status": "draft",
            "session_id": session_id,
            "inst_id": request.inst_id,
            "inst_type": inst_type,
            "mode": mode,
            "side": side,
            "size": size_label,
            "price": _format_order_number(price_value),
            "stop_loss_price": stop_label,
            "take_profit_prices": take_profit_prices,
            "plan": plan_payload,
            "risk": risk_payload,
            "annotations": annotations,
            "summary": summary_text,
            "requires_confirmation": True,
            "requires_manual_execution": True,
            "message": "订单草案已生成，仅保存待确认信息，不会自动下单。",
            "draft": draft,
            "fetched_at": _utc_now_iso(),
        }

    def list_order_drafts(self, request: AgentOrderDraftListRequest) -> Dict[str, Any]:
        status = (request.status or "").strip().lower()
        if status and status not in {"draft", "confirmed", "cancelled"}:
            raise ValueError("status 仅支持 draft/confirmed/cancelled")

        storage = self.ctx.storage()
        drafts = storage.list_assistant_order_drafts(
            session_id=(request.session_id or "").strip(),
            inst_id=(request.inst_id or "").strip(),
            status=status,
            limit=request.limit,
        )

        status_counts: Dict[str, int] = {}
        for item in drafts:
            current_status = str(item.get("status") or "draft")
            status_counts[current_status] = status_counts.get(current_status, 0) + 1

        return {
            "drafts": drafts,
            "count": len(drafts),
            "status_counts": status_counts,
            "filters": {
                "session_id": (request.session_id or "").strip(),
                "inst_id": (request.inst_id or "").strip(),
                "status": status,
                "limit": request.limit,
            },
            "fetched_at": _utc_now_iso(),
        }

    def confirm_order_draft(self, request: AgentOrderDraftConfirmRequest) -> Dict[str, Any]:
        storage = self.ctx.storage()
        draft = storage.get_assistant_order_draft((request.draft_id or "").strip())
        if not draft:
            raise ValueError(f"未找到订单草案 {request.draft_id}")
        if str(draft.get("status") or "").lower() == "cancelled":
            raise ValueError("已取消的订单草案不能再次确认")
        if str(draft.get("status") or "").lower() == "confirmed":
            return {
                "draft_id": draft["draft_id"],
                "status": "confirmed",
                "changed": False,
                "executed": False,
                "draft": draft,
                "message": "订单草案已经确认过，但仍不会自动下单。",
                "fetched_at": _utc_now_iso(),
            }

        metadata = dict(draft.get("metadata") or {})
        metadata.update({
            "confirmed_via": "assistant",
            "requires_manual_execution": True,
        })
        storage.update_assistant_order_draft(
            draft["draft_id"],
            metadata=metadata,
            confirmed=True,
        )
        updated = storage.get_assistant_order_draft(draft["draft_id"])
        return {
            "draft_id": draft["draft_id"],
            "status": "confirmed",
            "changed": True,
            "executed": False,
            "draft": updated,
            "message": "订单草案已确认，仍需你在交易链路中手动执行，不会自动下单。",
            "fetched_at": _utc_now_iso(),
        }
