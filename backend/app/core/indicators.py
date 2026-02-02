# 技术指标计算模块
# 提供常用技术指标的计算功能

from typing import List, Optional, Tuple, Dict, Any
from dataclasses import dataclass
import math


@dataclass
class IndicatorResult:
    """指标计算结果"""
    name: str               # 指标名称
    values: List[float]     # 指标值列表
    params: Dict[str, Any]  # 参数


def sma(prices: List[float], period: int) -> List[float]:
    """
    简单移动平均线 (Simple Moving Average)

    Args:
        prices: 价格序列
        period: 周期

    Returns:
        SMA值列表，前period-1个为None表示的float('nan')
    """
    if len(prices) < period:
        return [float('nan')] * len(prices)

    result = [float('nan')] * (period - 1)
    for i in range(period - 1, len(prices)):
        avg = sum(prices[i - period + 1:i + 1]) / period
        result.append(avg)
    return result


def ema(prices: List[float], period: int) -> List[float]:
    """
    指数移动平均线 (Exponential Moving Average)

    Args:
        prices: 价格序列
        period: 周期

    Returns:
        EMA值列表
    """
    if len(prices) < period:
        return [float('nan')] * len(prices)

    multiplier = 2 / (period + 1)
    result = [float('nan')] * (period - 1)

    # 第一个EMA使用SMA
    first_ema = sum(prices[:period]) / period
    result.append(first_ema)

    # 后续EMA递推计算
    for i in range(period, len(prices)):
        ema_val = (prices[i] - result[-1]) * multiplier + result[-1]
        result.append(ema_val)

    return result


def macd(
    prices: List[float],
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9
) -> Tuple[List[float], List[float], List[float]]:
    """
    MACD指标 (Moving Average Convergence Divergence)

    Args:
        prices: 价格序列
        fast_period: 快线周期，默认12
        slow_period: 慢线周期，默认26
        signal_period: 信号线周期，默认9

    Returns:
        (DIF, DEA, MACD柱) 三个列表
    """
    # 计算快慢EMA
    ema_fast = ema(prices, fast_period)
    ema_slow = ema(prices, slow_period)

    # DIF = 快线 - 慢线
    dif = []
    for i in range(len(prices)):
        if math.isnan(ema_fast[i]) or math.isnan(ema_slow[i]):
            dif.append(float('nan'))
        else:
            dif.append(ema_fast[i] - ema_slow[i])

    # DEA = DIF的EMA
    # 找到DIF第一个有效值的位置
    valid_dif = [d for d in dif if not math.isnan(d)]
    dea_values = ema(valid_dif, signal_period) if valid_dif else []

    # 重新对齐DEA
    dea = [float('nan')] * (len(dif) - len(dea_values)) + dea_values

    # MACD柱 = (DIF - DEA) * 2
    macd_hist = []
    for i in range(len(prices)):
        if math.isnan(dif[i]) or math.isnan(dea[i]):
            macd_hist.append(float('nan'))
        else:
            macd_hist.append((dif[i] - dea[i]) * 2)

    return dif, dea, macd_hist


def rsi(prices: List[float], period: int = 14) -> List[float]:
    """
    相对强弱指标 (Relative Strength Index)

    Args:
        prices: 价格序列
        period: 周期，默认14

    Returns:
        RSI值列表 (0-100)
    """
    if len(prices) < period + 1:
        return [float('nan')] * len(prices)

    # 计算价格变化
    changes = [prices[i] - prices[i-1] for i in range(1, len(prices))]

    result = [float('nan')] * period

    # 计算初始平均涨跌
    gains = [max(c, 0) for c in changes[:period]]
    losses = [abs(min(c, 0)) for c in changes[:period]]
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    # 第一个RSI
    if avg_loss == 0:
        result.append(100.0)
    else:
        rs = avg_gain / avg_loss
        result.append(100 - (100 / (1 + rs)))

    # 后续RSI使用平滑方法
    for i in range(period, len(changes)):
        change = changes[i]
        gain = max(change, 0)
        loss = abs(min(change, 0))

        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period

        if avg_loss == 0:
            result.append(100.0)
        else:
            rs = avg_gain / avg_loss
            result.append(100 - (100 / (1 + rs)))

    return result


def bollinger_bands(
    prices: List[float],
    period: int = 20,
    num_std: float = 2.0
) -> Tuple[List[float], List[float], List[float]]:
    """
    布林带 (Bollinger Bands)

    Args:
        prices: 价格序列
        period: 周期，默认20
        num_std: 标准差倍数，默认2

    Returns:
        (上轨, 中轨, 下轨) 三个列表
    """
    middle = sma(prices, period)
    upper = []
    lower = []

    for i in range(len(prices)):
        if math.isnan(middle[i]):
            upper.append(float('nan'))
            lower.append(float('nan'))
        else:
            # 计算标准差
            window = prices[i - period + 1:i + 1]
            std = (sum((p - middle[i]) ** 2 for p in window) / period) ** 0.5
            upper.append(middle[i] + num_std * std)
            lower.append(middle[i] - num_std * std)

    return upper, middle, lower


def kdj(
    high: List[float],
    low: List[float],
    close: List[float],
    n: int = 9,
    m1: int = 3,
    m2: int = 3
) -> Tuple[List[float], List[float], List[float]]:
    """
    KDJ随机指标

    Args:
        high: 最高价序列
        low: 最低价序列
        close: 收盘价序列
        n: RSV周期，默认9
        m1: K值平滑周期，默认3
        m2: D值平滑周期，默认3

    Returns:
        (K, D, J) 三个列表
    """
    length = len(close)
    if length < n:
        return [float('nan')] * length, [float('nan')] * length, [float('nan')] * length

    rsv = []
    for i in range(length):
        if i < n - 1:
            rsv.append(float('nan'))
        else:
            highest = max(high[i - n + 1:i + 1])
            lowest = min(low[i - n + 1:i + 1])
            if highest == lowest:
                rsv.append(50.0)
            else:
                rsv.append((close[i] - lowest) / (highest - lowest) * 100)

    # 计算K值 (RSV的M1日移动平均)
    k_values = [float('nan')] * (n - 1)
    k_prev = 50.0  # 初始值

    for i in range(n - 1, length):
        if math.isnan(rsv[i]):
            k_values.append(float('nan'))
        else:
            k = (m1 - 1) / m1 * k_prev + 1 / m1 * rsv[i]
            k_values.append(k)
            k_prev = k

    # 计算D值 (K的M2日移动平均)
    d_values = [float('nan')] * (n - 1)
    d_prev = 50.0

    for i in range(n - 1, length):
        if math.isnan(k_values[i]):
            d_values.append(float('nan'))
        else:
            d = (m2 - 1) / m2 * d_prev + 1 / m2 * k_values[i]
            d_values.append(d)
            d_prev = d

    # 计算J值
    j_values = []
    for i in range(length):
        if math.isnan(k_values[i]) or math.isnan(d_values[i]):
            j_values.append(float('nan'))
        else:
            j_values.append(3 * k_values[i] - 2 * d_values[i])

    return k_values, d_values, j_values


def atr(
    high: List[float],
    low: List[float],
    close: List[float],
    period: int = 14
) -> List[float]:
    """
    平均真实波幅 (Average True Range)

    Args:
        high: 最高价序列
        low: 最低价序列
        close: 收盘价序列
        period: 周期，默认14

    Returns:
        ATR值列表，长度与输入相同
    """
    length = len(close)
    if length < 2:
        return [float('nan')] * length

    # 样本数不足时，返回全 NaN（保证输出长度与输入一致）
    if length < period:
        return [float('nan')] * length

    # 计算真实波幅
    tr = [high[0] - low[0]]  # 第一个TR
    for i in range(1, length):
        tr1 = high[i] - low[i]
        tr2 = abs(high[i] - close[i - 1])
        tr3 = abs(low[i] - close[i - 1])
        tr.append(max(tr1, tr2, tr3))

    # 计算ATR (TR的移动平均)
    result = [float('nan')] * (period - 1)

    # 第一个ATR使用简单平均
    first_atr = sum(tr[:period]) / period
    result.append(first_atr)

    # 后续使用平滑方法
    for i in range(period, length):
        atr_val = (result[-1] * (period - 1) + tr[i]) / period
        result.append(atr_val)

    return result


def volume_ma(volumes: List[float], period: int = 20) -> List[float]:
    """
    成交量移动平均

    Args:
        volumes: 成交量序列
        period: 周期

    Returns:
        成交量MA值列表
    """
    return sma(volumes, period)


class IndicatorCalculator:
    """
    指标计算器
    封装所有指标计算功能，支持从K线数据直接计算
    """

    def __init__(self, candles: List):
        """
        初始化指标计算器

        Args:
            candles: K线数据列表，需要有open/high/low/close/volume属性
        """
        self.candles = candles
        self._extract_prices()

    def _extract_prices(self):
        """从K线提取价格序列"""
        self.opens = [c.open for c in self.candles]
        self.highs = [c.high for c in self.candles]
        self.lows = [c.low for c in self.candles]
        self.closes = [c.close for c in self.candles]
        self.volumes = [c.volume for c in self.candles]
        self.timestamps = [c.timestamp for c in self.candles]

    def sma(self, period: int, source: str = "close") -> List[float]:
        """计算SMA"""
        prices = self._get_source(source)
        return sma(prices, period)

    def ema(self, period: int, source: str = "close") -> List[float]:
        """计算EMA"""
        prices = self._get_source(source)
        return ema(prices, period)

    def macd(
        self,
        fast: int = 12,
        slow: int = 26,
        signal: int = 9
    ) -> Dict[str, List[float]]:
        """计算MACD"""
        dif, dea, hist = macd(self.closes, fast, slow, signal)
        return {"dif": dif, "dea": dea, "histogram": hist}

    def rsi(self, period: int = 14) -> List[float]:
        """计算RSI"""
        return rsi(self.closes, period)

    def bollinger(
        self,
        period: int = 20,
        num_std: float = 2.0
    ) -> Dict[str, List[float]]:
        """计算布林带"""
        upper, middle, lower = bollinger_bands(self.closes, period, num_std)
        return {"upper": upper, "middle": middle, "lower": lower}

    def kdj(
        self,
        n: int = 9,
        m1: int = 3,
        m2: int = 3
    ) -> Dict[str, List[float]]:
        """计算KDJ"""
        k, d, j = kdj(self.highs, self.lows, self.closes, n, m1, m2)
        return {"k": k, "d": d, "j": j}

    def atr(self, period: int = 14) -> List[float]:
        """计算ATR"""
        return atr(self.highs, self.lows, self.closes, period)

    def volume_ma(self, period: int = 20) -> List[float]:
        """计算成交量MA"""
        return volume_ma(self.volumes, period)

    def _get_source(self, source: str) -> List[float]:
        """获取价格源"""
        source_map = {
            "open": self.opens,
            "high": self.highs,
            "low": self.lows,
            "close": self.closes,
            "volume": self.volumes,
        }
        return source_map.get(source, self.closes)

    def calculate_all(self) -> Dict[str, Any]:
        """计算所有常用指标"""
        return {
            "ma5": self.sma(5),
            "ma10": self.sma(10),
            "ma20": self.sma(20),
            "ma60": self.sma(60),
            "ema12": self.ema(12),
            "ema26": self.ema(26),
            "macd": self.macd(),
            "rsi": self.rsi(),
            "bollinger": self.bollinger(),
            "kdj": self.kdj(),
            "atr": self.atr(),
            "volume_ma": self.volume_ma(),
        }
