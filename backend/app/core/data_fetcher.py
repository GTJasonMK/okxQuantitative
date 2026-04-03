# 数据获取模块
# 负责从OKX交易所获取行情数据

import time
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import httpx

try:
    import okx.MarketData as MarketData
    import okx.PublicData as PublicData
    OKX_AVAILABLE = True
except ImportError:
    OKX_AVAILABLE = False
    print("警告: python-okx 未安装，部分功能不可用。请运行: pip install python-okx")

from ..config import config
from ..utils.timeframes import TIMEFRAME_TO_MS


OKX_CANDLE_PAGE_LIMIT = 300
OKX_ORDERBOOK_STANDARD_MAX = 400
OKX_ORDERBOOK_FULL_MAX = 5000
OKX_PUBLIC_REST_BASE_URL = "https://www.okx.com"
OKX_PUBLIC_HTTP_TIMEOUT = 15.0
OKX_PUBLIC_HTTP_RETRY_COUNT = 2


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


@dataclass
class MarketTrade:
    """公共逐笔成交数据结构"""
    inst_id: str       # 交易对
    trade_id: str      # 成交ID
    price: float       # 成交价
    size: float        # 成交量
    side: str          # buy/sell
    timestamp: int     # 时间戳（毫秒）

    def to_dict(self) -> Dict[str, Any]:
        return {
            "inst_id": self.inst_id,
            "trade_id": self.trade_id,
            "price": self.price,
            "size": self.size,
            "side": self.side,
            "timestamp": self.timestamp,
        }


def _safe_float(value: Any, default: float = 0.0) -> float:
    """安全转换浮点数，异常时返回默认值。"""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    """安全转换整数，异常时返回默认值。"""
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _build_okx_candle_params(
    inst_id: str,
    timeframe: str,
    limit: int,
    after: Optional[int] = None,
    before: Optional[int] = None,
) -> Dict[str, str]:
    params = {
        "instId": inst_id,
        "bar": timeframe,
        "limit": str(min(limit, OKX_CANDLE_PAGE_LIMIT)),
    }
    if after is not None:
        params["after"] = str(after)
    if before is not None:
        params["before"] = str(before)
    return params


def _parse_okx_candle_result(result: Dict[str, Any], error_prefix: str) -> List[Candle]:
    if result.get("code") != "0":
        print(f"{error_prefix}: {result.get('msg', '未知错误')}")
        return []

    candles = []
    for item in result.get("data", []):
        # OKX返回格式: [ts, o, h, l, c, vol, volCcy, volCcyQuote, confirm]
        # 实盘策略仅应使用已收盘K线，避免未收盘数据抖动导致误触发信号。
        if len(item) > 8 and str(item[8]) != "1":
            continue

        candles.append(Candle(
            timestamp=int(item[0]),
            open=float(item[1]),
            high=float(item[2]),
            low=float(item[3]),
            close=float(item[4]),
            volume=float(item[5]),
            volume_ccy=float(item[6]) if len(item) > 6 else 0,
        ))

    candles.reverse()
    return candles


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
        if timeframe not in TIMEFRAME_TO_MS:
            print(f"不支持的时间周期: {timeframe}，支持: {list(TIMEFRAME_TO_MS.keys())}")
            return []

        try:
            params = _build_okx_candle_params(inst_id, timeframe, limit, after=after, before=before)
            result = self.market_api.get_candlesticks(**params)
            return _parse_okx_candle_result(result, "获取K线失败")

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
        if timeframe not in TIMEFRAME_TO_MS:
            print(f"不支持的时间周期: {timeframe}，支持: {list(TIMEFRAME_TO_MS.keys())}")
            return []

        all_candles = []
        seen_timestamps = set()
        after = int(end_time.timestamp() * 1000) if end_time else None
        start_ts = int(start_time.timestamp() * 1000) if start_time else None
        history_api = getattr(getattr(self, "market_api", None), "get_history_candlesticks", None)

        while len(all_candles) < max_candles:
            prev_after = after
            page_limit = min(OKX_CANDLE_PAGE_LIMIT, max_candles - len(all_candles))
            if page_limit <= 0:
                break

            if callable(history_api):
                try:
                    params = _build_okx_candle_params(
                        inst_id,
                        timeframe,
                        page_limit,
                        after=after,
                    )
                    result = history_api(**params)
                    batch = _parse_okx_candle_result(result, "获取历史K线失败")
                except Exception as e:
                    print(f"获取历史K线异常: {e}")
                    break
            else:
                batch = self.get_candles(
                    inst_id=inst_id,
                    timeframe=timeframe,
                    limit=page_limit,
                    after=after,
                )

            if not batch:
                break

            # 防御性：若分页参数 after 不推进（例如接口忽略 after 或包含边界导致重复返回同一页），
            # 会造成大量重复请求直到 max_candles 才停止，触发限流并显著拖慢同步。
            # 这里检测“最老K线时间戳未向过去推进”则停止分页。
            oldest_timestamp = batch[0].timestamp
            if prev_after is not None and oldest_timestamp >= prev_after:
                print(f"[DataFetcher] 历史K线分页未推进（after={prev_after}），停止分页以避免重复拉取")
                break

            # 检查是否已达到开始时间
            if start_ts is not None:
                batch = [c for c in batch if c.timestamp >= start_ts]
                if not batch:
                    break

            fresh_batch = [c for c in batch if c.timestamp not in seen_timestamps]
            if not fresh_batch:
                break

            for candle in fresh_batch:
                seen_timestamps.add(candle.timestamp)

            all_candles = fresh_batch + all_candles
            after = oldest_timestamp - 1

            # 避免请求过于频繁
            time.sleep(0.1)

            if start_ts is not None and oldest_timestamp <= start_ts:
                break

        return all_candles[-max_candles:]

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

    def get_recent_trades(self, inst_id: str, limit: int = 50) -> List[MarketTrade]:
        """
        获取公共逐笔成交

        Args:
            inst_id: 交易对，如 BTC-USDT / BTC-USDT-SWAP
            limit: 返回数量，最大 100

        Returns:
            MarketTrade 列表，按时间倒序（最新在前）
        """
        try:
            result = self.market_api.get_trades(
                instId=inst_id,
                limit=str(min(max(limit, 1), 100)),
            )
            if result["code"] != "0":
                print(f"[DataFetcher] 获取 {inst_id} 最新成交失败: {result.get('msg', '未知错误')}")
                return []

            trades = []
            for item in result.get("data", []):
                try:
                    trades.append(MarketTrade(
                        inst_id=item.get("instId", inst_id),
                        trade_id=item.get("tradeId", ""),
                        price=float(item.get("px", 0)),
                        size=float(item.get("sz", 0)),
                        side=item.get("side", ""),
                        timestamp=int(item.get("ts", 0)),
                    ))
                except (TypeError, ValueError):
                    continue

            return trades
        except Exception as e:
            print(f"[DataFetcher] 获取 {inst_id} 最新成交异常: {e}")
            return []

    def get_orderbook(self, inst_id: str, size: int = 20) -> Optional[Dict[str, Any]]:
        """
        获取订单簿深度。

        Args:
            inst_id: 交易对，如 BTC-USDT / BTC-USDT-SWAP
            size: 返回档位数量

        Returns:
            规范化后的盘口深度字典，失败返回 None
        """
        normalized_size = min(max(int(size or 20), 1), OKX_ORDERBOOK_FULL_MAX)

        try:
            source = "books"
            payload: Optional[Dict[str, Any]] = None

            if normalized_size > OKX_ORDERBOOK_STANDARD_MAX:
                payload = self._get_full_orderbook_payload(inst_id, normalized_size)
                source = "books-full"
                if not payload:
                    print(
                        f"[DataFetcher] 获取 {inst_id} {normalized_size} 档全量盘口失败，"
                        f"回退到 {OKX_ORDERBOOK_STANDARD_MAX} 档标准盘口"
                    )

            if not payload:
                standard_size = min(normalized_size, OKX_ORDERBOOK_STANDARD_MAX)
                payload = self._get_standard_orderbook_payload(inst_id, standard_size)
                if not payload:
                    return None
                if normalized_size > OKX_ORDERBOOK_STANDARD_MAX:
                    source = "books-fallback"

            def normalize_levels(raw_levels: Any) -> List[Dict[str, Any]]:
                levels: List[Dict[str, Any]] = []
                cumulative_size = 0.0

                for item in raw_levels or []:
                    if not isinstance(item, (list, tuple)) or len(item) < 2:
                        continue

                    price = _safe_float(item[0])
                    size_value = _safe_float(item[1])
                    order_count = _safe_int(item[3]) if len(item) > 3 else 0

                    if price <= 0 or size_value < 0:
                        continue

                    cumulative_size += size_value
                    levels.append({
                        "price": price,
                        "size": size_value,
                        "total": cumulative_size,
                        "order_count": order_count,
                    })

                return levels[:normalized_size]

            asks = normalize_levels(payload.get("asks"))
            bids = normalize_levels(payload.get("bids"))

            best_ask = asks[0]["price"] if asks else 0.0
            best_bid = bids[0]["price"] if bids else 0.0
            spread = best_ask - best_bid if best_ask > 0 and best_bid > 0 else 0.0
            mid_price = ((best_ask + best_bid) / 2.0) if best_ask > 0 and best_bid > 0 else 0.0
            spread_rate = (spread / mid_price) if mid_price > 0 else 0.0
            actual_size = min(len(asks), len(bids)) if asks and bids else max(len(asks), len(bids))

            return {
                "inst_id": inst_id,
                "asks": asks,
                "bids": bids,
                "best_ask": best_ask,
                "best_bid": best_bid,
                "mid_price": mid_price,
                "spread": spread,
                "spread_rate": spread_rate,
                "ask_depth_total": asks[-1]["total"] if asks else 0.0,
                "bid_depth_total": bids[-1]["total"] if bids else 0.0,
                "timestamp": _safe_int(payload.get("ts")),
                "requested_size": normalized_size,
                "actual_size": actual_size,
                "source": source,
                "is_truncated": actual_size < normalized_size,
            }
        except Exception as e:
            print(f"[DataFetcher] 获取 {inst_id} 盘口异常: {e}")
            return None

    def _get_standard_orderbook_payload(self, inst_id: str, size: int) -> Optional[Dict[str, Any]]:
        """获取普通盘口，最大支持 400 档。"""
        try:
            result = self.market_api.get_orderbook(
                instId=inst_id,
                sz=str(min(max(int(size or 20), 1), OKX_ORDERBOOK_STANDARD_MAX)),
            )
        except Exception as exc:
            print(f"[DataFetcher] 获取 {inst_id} 标准盘口异常: {exc}")
            return None

        if result.get("code") != "0" or not result.get("data"):
            print(f"[DataFetcher] 获取 {inst_id} 标准盘口失败: {result.get('msg', '未知错误')}")
            return None

        payload = result["data"][0]
        return payload if isinstance(payload, dict) else None

    def _get_full_orderbook_payload(self, inst_id: str, size: int) -> Optional[Dict[str, Any]]:
        """当请求档位超过普通 books 上限时，回退到 books-full。"""
        normalized_size = min(max(int(size or 20), 1), OKX_ORDERBOOK_FULL_MAX)

        for attempt in range(1, OKX_PUBLIC_HTTP_RETRY_COUNT + 1):
            try:
                response = httpx.get(
                    f"{OKX_PUBLIC_REST_BASE_URL}/api/v5/market/books-full",
                    params={
                        "instId": inst_id,
                        "sz": str(normalized_size),
                    },
                    headers={
                        "Accept": "application/json",
                        "User-Agent": "okxQuantitative/1.0",
                    },
                    timeout=OKX_PUBLIC_HTTP_TIMEOUT,
                    follow_redirects=True,
                )
                response.raise_for_status()
                result = response.json()
            except httpx.TimeoutException as exc:
                print(f"[DataFetcher] 获取 {inst_id} 全量盘口超时(第{attempt}次): {exc}")
                if attempt < OKX_PUBLIC_HTTP_RETRY_COUNT:
                    time.sleep(0.3 * attempt)
                    continue
                return None
            except Exception as exc:
                print(f"[DataFetcher] 获取 {inst_id} 全量盘口异常: {exc}")
                return None

            if result.get("code") != "0" or not result.get("data"):
                print(f"[DataFetcher] 获取 {inst_id} 全量盘口失败: {result.get('msg', '未知错误')}")
                return None

            payload = result["data"][0]
            return payload if isinstance(payload, dict) else None

        return None


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
