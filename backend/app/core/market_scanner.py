# 市场扫描引擎
# 按技术指标条件批量筛选交易对

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from . import indicators


@dataclass(frozen=True)
class ScanCondition:
    """单个筛选条件"""
    indicator: str  # rsi, sma_cross, bb_squeeze, macd_signal, volume_breakout
    operator: str   # gt, lt, gte, lte, cross_above, cross_below
    value: float = 0.0
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ScanResult:
    """单个币种的扫描结果"""
    inst_id: str
    matched: bool
    matched_conditions: List[str]
    indicator_values: Dict[str, float]
    price: float


class MarketScanner:
    """
    市场扫描器。
    对给定币种列表逐一计算指标，检查是否满足筛选条件。
    """

    def __init__(self, storage):
        self._storage = storage

    def scan(
        self,
        symbols: List[str],
        conditions: List[ScanCondition],
        logic: str = "and",
        timeframe: str = "1H",
        inst_type: str = "SPOT",
        candle_count: int = 100,
    ) -> List[ScanResult]:
        """
        执行扫描。

        Args:
            symbols: 要扫描的交易对列表
            conditions: 筛选条件列表
            logic: 条件逻辑 "and" 或 "or"
            timeframe: K 线周期
            inst_type: 交易类型
            candle_count: 每个币种加载的 K 线数量

        Returns:
            匹配结果列表
        """
        results: List[ScanResult] = []
        for symbol in symbols:
            candles = self._storage.get_latest_candles(
                symbol, timeframe, count=candle_count, inst_type=inst_type
            )
            if len(candles) < 20:
                continue

            closes = [c.close for c in candles]
            volumes = [c.volume for c in candles]
            highs = [c.high for c in candles]
            lows = [c.low for c in candles]
            current_price = closes[-1]

            matched_names: List[str] = []
            indicator_values: Dict[str, float] = {"price": current_price}

            for cond in conditions:
                passed, name, val = self._evaluate_condition(
                    cond, closes, volumes, highs, lows
                )
                if val is not None:
                    indicator_values[name] = val
                if passed:
                    matched_names.append(name)

            if logic == "and":
                matched = len(matched_names) == len(conditions)
            else:
                matched = len(matched_names) > 0

            if matched:
                results.append(ScanResult(
                    inst_id=symbol,
                    matched=True,
                    matched_conditions=matched_names,
                    indicator_values=indicator_values,
                    price=current_price,
                ))

        return results

    def _evaluate_condition(
        self,
        cond: ScanCondition,
        closes: List[float],
        volumes: List[float],
        highs: List[float],
        lows: List[float],
    ) -> tuple:
        """
        评估单个条件。

        Returns:
            (是否满足, 条件名称, 指标值)
        """
        ind = cond.indicator
        op = cond.operator
        target = cond.value
        params = cond.params

        if ind == "rsi":
            period = params.get("period", 14)
            rsi_values = indicators.rsi(closes, period=period)
            val = rsi_values[-1] if rsi_values and not math.isnan(rsi_values[-1]) else None
            if val is None:
                return False, f"rsi({period})", None
            return self._compare(val, op, target), f"rsi({period})", round(val, 2)

        elif ind == "sma_cross":
            fast = params.get("fast_period", 5)
            slow = params.get("slow_period", 20)
            fast_ma = indicators.sma(closes, fast)
            slow_ma = indicators.sma(closes, slow)
            if len(fast_ma) < 2 or math.isnan(fast_ma[-1]) or math.isnan(slow_ma[-1]):
                return False, f"sma({fast}/{slow})", None

            name = f"sma({fast}/{slow})"
            diff_now = fast_ma[-1] - slow_ma[-1]
            diff_prev = fast_ma[-2] - slow_ma[-2]

            if op == "cross_above":
                passed = diff_prev <= 0 and diff_now > 0
            elif op == "cross_below":
                passed = diff_prev >= 0 and diff_now < 0
            else:
                passed = self._compare(diff_now, op, target)
            return passed, name, round(diff_now, 4)

        elif ind == "bb_squeeze":
            period = params.get("period", 20)
            num_std = params.get("num_std", 2.0)
            bb = indicators.bollinger_bands(closes, period=period, num_std=num_std)
            upper, middle, lower = bb
            if math.isnan(upper[-1]) or middle[-1] == 0:
                return False, "bb_squeeze", None
            width = (upper[-1] - lower[-1]) / middle[-1]
            return self._compare(width, op, target), "bb_squeeze", round(width, 4)

        elif ind == "macd_signal":
            macd_line, signal_line, histogram = indicators.macd(closes)
            if math.isnan(histogram[-1]):
                return False, "macd_hist", None
            name = "macd_hist"
            val = histogram[-1]

            if op == "cross_above" and len(histogram) >= 2:
                passed = histogram[-2] <= 0 and histogram[-1] > 0
            elif op == "cross_below" and len(histogram) >= 2:
                passed = histogram[-2] >= 0 and histogram[-1] < 0
            else:
                passed = self._compare(val, op, target)
            return passed, name, round(val, 6)

        elif ind == "volume_breakout":
            period = params.get("period", 20)
            multiplier = target if target > 0 else 2.0
            vol_ma = indicators.volume_ma(volumes, period=period)
            if math.isnan(vol_ma[-1]) or vol_ma[-1] == 0:
                return False, "volume_ratio", None
            ratio = volumes[-1] / vol_ma[-1]
            passed = ratio >= multiplier
            return passed, "volume_ratio", round(ratio, 2)

        elif ind == "price":
            val = closes[-1]
            return self._compare(val, op, target), "price", round(val, 6)

        return False, ind, None

    @staticmethod
    def _compare(value: float, op: str, target: float) -> bool:
        """通用比较操作"""
        if op == "gt":
            return value > target
        elif op == "lt":
            return value < target
        elif op == "gte":
            return value >= target
        elif op == "lte":
            return value <= target
        return False


# 可用条件类型及参数说明
AVAILABLE_CONDITIONS = [
    {
        "indicator": "rsi",
        "label": "RSI",
        "operators": ["gt", "lt", "gte", "lte"],
        "params": {"period": {"type": "int", "default": 14, "min": 2, "max": 50}},
        "value_hint": "如 30（超卖）或 70（超买）",
    },
    {
        "indicator": "sma_cross",
        "label": "均线交叉",
        "operators": ["cross_above", "cross_below"],
        "params": {
            "fast_period": {"type": "int", "default": 5, "min": 2, "max": 100},
            "slow_period": {"type": "int", "default": 20, "min": 5, "max": 200},
        },
        "value_hint": "交叉信号无需设定值",
    },
    {
        "indicator": "bb_squeeze",
        "label": "布林带收窄",
        "operators": ["lt", "lte"],
        "params": {
            "period": {"type": "int", "default": 20},
            "num_std": {"type": "float", "default": 2.0},
        },
        "value_hint": "宽度比率阈值，如 0.05",
    },
    {
        "indicator": "macd_signal",
        "label": "MACD 信号",
        "operators": ["cross_above", "cross_below", "gt", "lt"],
        "params": {},
        "value_hint": "柱状图值或交叉信号",
    },
    {
        "indicator": "volume_breakout",
        "label": "放量突破",
        "operators": ["gte"],
        "params": {"period": {"type": "int", "default": 20}},
        "value_hint": "均量倍数，如 2.0 表示当前成交量 ≥ 均量的 2 倍",
    },
]
