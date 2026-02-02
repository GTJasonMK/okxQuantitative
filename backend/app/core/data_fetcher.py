# 数据获取模块
# 负责从OKX交易所获取行情数据

import time
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

try:
    import okx.MarketData as MarketData
    import okx.PublicData as PublicData
    OKX_AVAILABLE = True
except ImportError:
    OKX_AVAILABLE = False
    print("警告: python-okx 未安装，部分功能不可用。请运行: pip install python-okx")

from ..config import config, TIMEFRAMES, INST_TYPES


class InstType(str, Enum):
    """交易品种类型"""
    SPOT = "SPOT"         # 现货
    SWAP = "SWAP"         # 永续合约
    FUTURES = "FUTURES"   # 交割合约
    OPTION = "OPTION"     # 期权


@dataclass
class Candle:
    """K线数据结构"""
    timestamp: int      # 时间戳（毫秒）
    open: float         # 开盘价
    high: float         # 最高价
    low: float          # 最低价
    close: float        # 收盘价
    volume: float       # 成交量（币）
    volume_ccy: float   # 成交额（计价货币）

    @property
    def datetime(self) -> datetime:
        """转换为datetime对象"""
        return datetime.fromtimestamp(self.timestamp / 1000)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "timestamp": self.timestamp,
            "datetime": self.datetime.isoformat(),
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "volume_ccy": self.volume_ccy,
        }


@dataclass
class Ticker:
    """实时行情数据结构"""
    inst_id: str        # 交易对
    last: float         # 最新价
    last_sz: float      # 最新成交量
    ask_px: float       # 卖一价
    ask_sz: float       # 卖一量
    bid_px: float       # 买一价
    bid_sz: float       # 买一量
    open_24h: float     # 24小时开盘价
    high_24h: float     # 24小时最高价
    low_24h: float      # 24小时最低价
    vol_24h: float      # 24小时成交量
    vol_ccy_24h: float  # 24小时成交额
    timestamp: int      # 时间戳

    @property
    def change_24h(self) -> float:
        """24小时涨跌幅"""
        if self.open_24h == 0:
            return 0
        return (self.last - self.open_24h) / self.open_24h * 100

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "inst_id": self.inst_id,
            "last": self.last,
            "ask_px": self.ask_px,
            "bid_px": self.bid_px,
            "open_24h": self.open_24h,
            "high_24h": self.high_24h,
            "low_24h": self.low_24h,
            "vol_24h": self.vol_24h,
            "change_24h": self.change_24h,
            "timestamp": self.timestamp,
        }


class DataFetcher:
    """
    数据获取器
    负责从OKX交易所获取各类行情数据
    """

    def __init__(self, is_simulated: bool = True):
        """
        初始化数据获取器

        Args:
            is_simulated: 是否使用模拟盘环境
        """
        if not OKX_AVAILABLE:
            raise ImportError("python-okx 未安装")

        flag = "1" if is_simulated else "0"
        self.market_api = MarketData.MarketAPI(flag=flag)
        self.public_api = PublicData.PublicAPI(flag=flag)
        self.is_simulated = is_simulated

    def get_ticker(self, inst_id: str) -> Optional[Ticker]:
        """
        获取单个交易对的实时行情

        Args:
            inst_id: 交易对，如 "BTC-USDT"

        Returns:
            Ticker对象，获取失败返回None
        """
        try:
            result = self.market_api.get_ticker(instId=inst_id)
            if result["code"] != "0" or not result["data"]:
                print(f"[DataFetcher] 获取 {inst_id} 行情失败: code={result.get('code')}, msg={result.get('msg', '未知错误')}")
                return None

            data = result["data"][0]
            return Ticker(
                inst_id=data["instId"],
                last=float(data["last"]),
                last_sz=float(data.get("lastSz", 0)),
                ask_px=float(data.get("askPx", 0)),
                ask_sz=float(data.get("askSz", 0)),
                bid_px=float(data.get("bidPx", 0)),
                bid_sz=float(data.get("bidSz", 0)),
                open_24h=float(data.get("open24h", 0)),
                high_24h=float(data.get("high24h", 0)),
                low_24h=float(data.get("low24h", 0)),
                vol_24h=float(data.get("vol24h", 0)),
                vol_ccy_24h=float(data.get("volCcy24h", 0)),
                timestamp=int(data["ts"]),
            )
        except Exception as e:
            print(f"[DataFetcher] 获取 {inst_id} 行情异常: {e}")
            return None

    def get_tickers(self, inst_type: InstType = InstType.SPOT) -> List[Ticker]:
        """
        获取某类型所有交易对的行情

        Args:
            inst_type: 交易类型

        Returns:
            Ticker列表
        """
        try:
            result = self.market_api.get_tickers(instType=inst_type.value)
            if result["code"] != "0":
                print(f"获取行情列表失败: {result.get('msg', '未知错误')}")
                return []

            tickers = []
            for data in result["data"]:
                try:
                    ticker = Ticker(
                        inst_id=data["instId"],
                        last=float(data["last"]),
                        last_sz=float(data.get("lastSz", 0)),
                        ask_px=float(data.get("askPx", 0)),
                        ask_sz=float(data.get("askSz", 0)),
                        bid_px=float(data.get("bidPx", 0)),
                        bid_sz=float(data.get("bidSz", 0)),
                        open_24h=float(data.get("open24h", 0)),
                        high_24h=float(data.get("high24h", 0)),
                        low_24h=float(data.get("low24h", 0)),
                        vol_24h=float(data.get("vol24h", 0)),
                        vol_ccy_24h=float(data.get("volCcy24h", 0)),
                        timestamp=int(data["ts"]),
                    )
                    tickers.append(ticker)
                except (KeyError, ValueError) as e:
                    continue
            return tickers
        except Exception as e:
            print(f"获取行情列表异常: {e}")
            return []

    def get_candles(
        self,
        inst_id: str,
        timeframe: str = "1H",
        limit: int = 100,
        after: Optional[int] = None,
        before: Optional[int] = None,
    ) -> List[Candle]:
        """
        获取K线数据

        Args:
            inst_id: 交易对，如 "BTC-USDT"
            timeframe: 时间周期，如 "1m", "5m", "1H", "1D"
            limit: 返回数量，最大300
            after: 请求此时间戳之前的数据（用于分页）
            before: 请求此时间戳之后的数据

        Returns:
            Candle列表，按时间正序排列
        """
        if timeframe not in TIMEFRAMES:
            print(f"不支持的时间周期: {timeframe}，支持: {list(TIMEFRAMES.keys())}")
            return []

        try:
            params = {
                "instId": inst_id,
                "bar": timeframe,
                "limit": str(min(limit, 300)),
            }
            if after:
                params["after"] = str(after)
            if before:
                params["before"] = str(before)

            result = self.market_api.get_candlesticks(**params)
            if result["code"] != "0":
                print(f"获取K线失败: {result.get('msg', '未知错误')}")
                return []

            candles = []
            for item in result["data"]:
                # OKX返回格式: [ts, o, h, l, c, vol, volCcy, volCcyQuote, confirm]
                candle = Candle(
                    timestamp=int(item[0]),
                    open=float(item[1]),
                    high=float(item[2]),
                    low=float(item[3]),
                    close=float(item[4]),
                    volume=float(item[5]),
                    volume_ccy=float(item[6]) if len(item) > 6 else 0,
                )
                candles.append(candle)

            # OKX返回的是倒序（最新在前），转为正序
            candles.reverse()
            return candles

        except Exception as e:
            print(f"获取K线异常: {e}")
            return []

    def get_history_candles(
        self,
        inst_id: str,
        timeframe: str = "1H",
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        max_candles: int = 1000,
    ) -> List[Candle]:
        """
        获取历史K线数据（自动分页）

        Args:
            inst_id: 交易对
            timeframe: 时间周期
            start_time: 开始时间
            end_time: 结束时间，默认为当前时间
            max_candles: 最大获取数量

        Returns:
            Candle列表
        """
        all_candles = []
        after = None

        if end_time:
            after = int(end_time.timestamp() * 1000)

        while len(all_candles) < max_candles:
            prev_after = after
            batch = self.get_candles(
                inst_id=inst_id,
                timeframe=timeframe,
                limit=300,
                after=after,
            )

            if not batch:
                break

            # 防御性：若分页参数 after 不推进（例如接口忽略 after 或包含边界导致重复返回同一页），
            # 会造成大量重复请求直到 max_candles 才停止，触发限流并显著拖慢同步。
            # 这里检测“最老K线时间戳未向过去推进”则停止分页。
            if prev_after is not None and batch[0].timestamp == prev_after:
                print(f"[DataFetcher] 历史K线分页未推进（after={prev_after}），停止分页以避免重复拉取")
                break

            # 检查是否已达到开始时间
            if start_time:
                start_ts = int(start_time.timestamp() * 1000)
                batch = [c for c in batch if c.timestamp >= start_ts]
                if not batch:
                    break

            all_candles = batch + all_candles
            after = batch[0].timestamp

            # 避免请求过于频繁
            time.sleep(0.1)

            # 如果返回数量少于请求数量，说明已经没有更多数据
            if len(batch) < 300:
                break

        return all_candles[:max_candles]

    def get_instruments(self, inst_type: InstType = InstType.SPOT) -> List[Dict[str, Any]]:
        """
        获取交易产品列表

        Args:
            inst_type: 交易类型

        Returns:
            交易产品信息列表
        """
        try:
            result = self.public_api.get_instruments(instType=inst_type.value)
            if result["code"] != "0":
                print(f"获取产品列表失败: {result.get('msg', '未知错误')}")
                return []

            instruments = []
            for item in result["data"]:
                instruments.append({
                    "inst_id": item["instId"],
                    "base_ccy": item.get("baseCcy", ""),      # 基础货币，如BTC
                    "quote_ccy": item.get("quoteCcy", ""),    # 计价货币，如USDT
                    "tick_sz": item.get("tickSz", ""),        # 最小价格单位
                    "lot_sz": item.get("lotSz", ""),          # 最小交易数量
                    "min_sz": item.get("minSz", ""),          # 最小下单数量
                    "state": item.get("state", ""),           # 状态
                })
            return instruments

        except Exception as e:
            print(f"获取产品列表异常: {e}")
            return []


# 便捷函数
def create_fetcher(is_simulated: bool = True) -> Optional[DataFetcher]:
    """
    创建数据获取器实例

    Args:
        is_simulated: 是否使用模拟盘

    Returns:
        DataFetcher实例，创建失败返回None
    """
    try:
        return DataFetcher(is_simulated=is_simulated)
    except ImportError as e:
        print(f"创建数据获取器失败 (依赖未安装): {e}")
        return None
    except Exception as e:
        print(f"创建数据获取器失败: {e}")
        return None
