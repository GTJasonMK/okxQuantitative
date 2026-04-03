# WebSocket 实时数据管理器
# 封装 OKX WebSocket 连接，提供实时行情和账户数据推送

import asyncio
import json
from typing import Dict, Set, Optional, Callable, Any, List, Awaitable, Union, Tuple
from dataclasses import dataclass
from threading import Lock
import time
import types

# python-okx / okx-sdk 依赖在部分环境可能未安装；做可选导入以避免后端无法启动。
def _missing_okx_ws(*args, **kwargs):  # pragma: no cover
    raise ModuleNotFoundError("缺少依赖 okx（python-okx/okx-sdk），请先安装后再使用 WebSocket 功能")


try:  # pragma: no cover
    import okx.websocket.WsPublicAsync as WsPublicAsync
except Exception:
    WsPublicAsync = types.SimpleNamespace(WsPublicAsync=_missing_okx_ws)

try:  # pragma: no cover
    import okx.websocket.WsPrivateAsync as WsPrivateAsync
except Exception:
    WsPrivateAsync = types.SimpleNamespace(WsPrivateAsync=_missing_okx_ws)

from ..config import config
from ..utils.mode import coerce_mode, mode_from_bool


# OKX WebSocket 地址
WS_PUBLIC_URL_LIVE = "wss://ws.okx.com:8443/ws/v5/public"
WS_PUBLIC_URL_SIMULATED = "wss://wspap.okx.com:8443/ws/v5/public?brokerId=9999"
WS_BUSINESS_URL_LIVE = "wss://ws.okx.com:8443/ws/v5/business"
WS_BUSINESS_URL_SIMULATED = "wss://wspap.okx.com:8443/ws/v5/business?brokerId=9999"
WS_PRIVATE_URL_LIVE = "wss://ws.okx.com:8443/ws/v5/private"
WS_PRIVATE_URL_SIMULATED = "wss://wspap.okx.com:8443/ws/v5/private?brokerId=9999"


@dataclass
class TickerData:
    """实时行情数据"""
    inst_id: str
    inst_type: str
    last: float
    last_sz: float
    ask_px: float
    ask_sz: float
    bid_px: float
    bid_sz: float
    open_24h: float
    high_24h: float
    low_24h: float
    vol_24h: float
    vol_ccy_24h: float
    timestamp: int

    @property
    def change_24h(self) -> float:
        """计算24小时涨跌幅"""
        if self.open_24h > 0:
            return round((self.last - self.open_24h) / self.open_24h * 100, 2)
        return 0.0

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "instId": self.inst_id,
            "instType": self.inst_type,
            "last": str(self.last),
            "lastSz": str(self.last_sz),
            "askPx": str(self.ask_px),
            "askSz": str(self.ask_sz),
            "bidPx": str(self.bid_px),
            "bidSz": str(self.bid_sz),
            "open24h": str(self.open_24h),
            "high24h": str(self.high_24h),
            "low24h": str(self.low_24h),
            "vol24h": str(self.vol_24h),
            "volCcy24h": str(self.vol_ccy_24h),
            "change24h": str(self.change_24h),
            "ts": str(self.timestamp),
        }


@dataclass
class CandleData:
    """实时 K 线数据"""
    inst_id: str
    inst_type: str
    timeframe: str
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    volume_ccy: float
    volume_quote: float
    confirm: int

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "instId": self.inst_id,
            "instType": self.inst_type,
            "timeframe": self.timeframe,
            "ts": str(self.timestamp),
            "open": str(self.open),
            "high": str(self.high),
            "low": str(self.low),
            "close": str(self.close),
            "vol": str(self.volume),
            "volCcy": str(self.volume_ccy),
            "volCcyQuote": str(self.volume_quote),
            "confirm": str(self.confirm),
        }


def _parse_ticker(data: Dict[str, Any]) -> Optional[TickerData]:
    """解析 OKX 推送的 Ticker 数据"""
    try:
        return TickerData(
            inst_id=data.get("instId", ""),
            inst_type=data.get("instType", ""),
            last=float(data.get("last", 0)),
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
            timestamp=int(data.get("ts", 0)),
        )
    except (ValueError, TypeError) as e:
        print(f"[WebSocketManager] 解析 Ticker 数据失败: {e}")
        return None


def _normalize_candle_timeframe(timeframe: str) -> str:
    """规范化 K 线周期字符串"""
    if not isinstance(timeframe, str):
        return ""

    normalized = timeframe.strip()
    if not normalized:
        return ""

    if normalized.startswith("candle"):
        normalized = normalized[6:]

    if normalized.endswith("utc"):
        suffix = "utc"
        normalized = normalized[:-3]
    else:
        suffix = ""

    return f"{normalized}{suffix}"


def _build_candle_channel(timeframe: str) -> str:
    """根据周期生成 OKX K 线频道名"""
    normalized = _normalize_candle_timeframe(timeframe)
    return f"candle{normalized}" if normalized else ""


def _parse_candle_channel(channel: str) -> str:
    """从频道名反推周期"""
    return _normalize_candle_timeframe(channel)


def _build_candle_subscription_key(inst_id: str, timeframe: str) -> str:
    """构造 K 线订阅键"""
    return f"{inst_id}|{_normalize_candle_timeframe(timeframe)}"


def _parse_candle_subscription_key(key: str) -> Optional[Tuple[str, str]]:
    """解析 K 线订阅键"""
    if "|" not in key:
        return None
    inst_id, timeframe = key.split("|", 1)
    normalized_timeframe = _normalize_candle_timeframe(timeframe)
    if not inst_id or not normalized_timeframe:
        return None
    return inst_id, normalized_timeframe


def _parse_candle(
    item: Any,
    *,
    channel: str,
    inst_id: str,
    inst_type: str = "",
) -> Optional[CandleData]:
    """解析 OKX 推送的 K 线数据"""
    try:
        if not isinstance(item, (list, tuple)) or len(item) < 6:
            return None

        timeframe = _parse_candle_channel(channel)
        timestamp = int(item[0])
        return CandleData(
            inst_id=inst_id,
            inst_type=inst_type,
            timeframe=timeframe,
            timestamp=timestamp,
            open=float(item[1]),
            high=float(item[2]),
            low=float(item[3]),
            close=float(item[4]),
            volume=float(item[5]),
            volume_ccy=float(item[6]) if len(item) > 6 else 0.0,
            volume_quote=float(item[7]) if len(item) > 7 else 0.0,
            confirm=int(item[8]) if len(item) > 8 else 0,
        )
    except (ValueError, TypeError) as e:
        print(f"[WebSocketManager] 解析 Candle 数据失败: {e}")
        return None


class OKXWebSocketManager:
    """
    OKX WebSocket 管理器

    管理与 OKX 的公共和私有 WebSocket 连接
    - 公共通道: 实时行情 (tickers)
    - Business 通道: 原生 K 线 (candles)
    - 私有通道: 账户余额 (account), 订单 (orders), 成交 (fills)
    """

    def __init__(self, is_simulated: bool = True):
        """
        初始化 WebSocket 管理器

        Args:
            is_simulated: True=模拟盘, False=实盘
        """
        self._is_simulated = is_simulated
        self._public_url = WS_PUBLIC_URL_SIMULATED if is_simulated else WS_PUBLIC_URL_LIVE
        self._business_url = WS_BUSINESS_URL_SIMULATED if is_simulated else WS_BUSINESS_URL_LIVE
        self._private_url = WS_PRIVATE_URL_SIMULATED if is_simulated else WS_PRIVATE_URL_LIVE

        # 公共 WebSocket
        self._public_ws: Optional[WsPublicAsync.WsPublicAsync] = None
        self._public_running = False

        # Business WebSocket（K 线等业务频道）
        self._business_ws: Optional[WsPublicAsync.WsPublicAsync] = None
        self._business_running = False

        # 私有 WebSocket
        self._private_ws: Optional[WsPrivateAsync.WsPrivateAsync] = None
        self._private_running = False

        self._lock = Lock()

        # 订阅的交易对集合
        self._subscribed_ticker_instruments: Set[str] = set()
        self._subscribed_candle_keys: Set[str] = set()

        # 数据缓存
        self._ticker_cache: Dict[str, TickerData] = {}
        self._candle_cache: Dict[str, CandleData] = {}
        self._account_cache: Dict[str, Any] = {}  # ccy -> balance info
        self._orders_cache: List[Dict[str, Any]] = []
        self._fills_cache: List[Dict[str, Any]] = []

        # 回调函数
        self._ticker_callbacks: List[Callable] = []
        self._candle_callbacks: List[Callable] = []
        self._account_callbacks: List[Callable] = []
        self._orders_callbacks: List[Callable] = []
        self._fills_callbacks: List[Callable] = []

        # 统计信息
        self._public_message_count = 0
        self._business_message_count = 0
        self._private_message_count = 0
        self._start_time: Optional[float] = None

    @property
    def is_running(self) -> bool:
        """检查公共行情连接是否运行中"""
        return self._public_running

    @property
    def is_business_running(self) -> bool:
        """检查 business 连接是否运行中"""
        return self._business_running

    @property
    def is_private_running(self) -> bool:
        """检查私有连接是否运行中"""
        return self._private_running

    @property
    def mode(self) -> str:
        """获取当前模式"""
        return "simulated" if self._is_simulated else "live"

    # ==================== 回调注册 ====================

    def add_ticker_callback(self, callback: Callable):
        """添加行情回调"""
        with self._lock:
            if callback not in self._ticker_callbacks:
                self._ticker_callbacks.append(callback)

    def remove_ticker_callback(self, callback: Callable):
        """移除行情回调"""
        with self._lock:
            if callback in self._ticker_callbacks:
                self._ticker_callbacks.remove(callback)

    def add_candle_callback(self, callback: Callable):
        """添加 K 线回调"""
        with self._lock:
            if callback not in self._candle_callbacks:
                self._candle_callbacks.append(callback)

    def remove_candle_callback(self, callback: Callable):
        """移除 K 线回调"""
        with self._lock:
            if callback in self._candle_callbacks:
                self._candle_callbacks.remove(callback)

    def add_account_callback(self, callback: Callable):
        """添加账户回调"""
        with self._lock:
            if callback not in self._account_callbacks:
                self._account_callbacks.append(callback)

    def remove_account_callback(self, callback: Callable):
        """移除账户回调"""
        with self._lock:
            if callback in self._account_callbacks:
                self._account_callbacks.remove(callback)

    def add_orders_callback(self, callback: Callable):
        """添加订单回调"""
        with self._lock:
            if callback not in self._orders_callbacks:
                self._orders_callbacks.append(callback)

    def remove_orders_callback(self, callback: Callable):
        """移除订单回调"""
        with self._lock:
            if callback in self._orders_callbacks:
                self._orders_callbacks.remove(callback)

    def add_fills_callback(self, callback: Callable):
        """添加成交回调"""
        with self._lock:
            if callback not in self._fills_callbacks:
                self._fills_callbacks.append(callback)

    def remove_fills_callback(self, callback: Callable):
        """移除成交回调"""
        with self._lock:
            if callback in self._fills_callbacks:
                self._fills_callbacks.remove(callback)

    # 兼容旧接口
    def add_callback(self, callback: Callable):
        """添加行情回调（兼容旧接口）"""
        self.add_ticker_callback(callback)

    def remove_callback(self, callback: Callable):
        """移除行情回调（兼容旧接口）"""
        self.remove_ticker_callback(callback)

    # ==================== 数据获取 ====================

    def get_ticker(self, inst_id: str) -> Optional[TickerData]:
        """获取指定交易对的最新行情"""
        return self._ticker_cache.get(inst_id)

    def get_all_tickers(self) -> Dict[str, TickerData]:
        """获取所有已订阅交易对的最新行情"""
        return self._ticker_cache.copy()

    def get_latest_candle(self, inst_id: str, timeframe: str) -> Optional[CandleData]:
        """获取指定交易对和周期的最新 K 线"""
        return self._candle_cache.get(_build_candle_subscription_key(inst_id, timeframe))

    def get_account_balance(self) -> Dict[str, Any]:
        """获取账户余额缓存"""
        return self._account_cache.copy()

    def get_recent_orders(self) -> List[Dict[str, Any]]:
        """获取最近的订单推送"""
        return self._orders_cache.copy()

    def get_recent_fills(self) -> List[Dict[str, Any]]:
        """获取最近的成交推送"""
        return self._fills_cache.copy()

    # ==================== 消息处理 ====================

    def _on_public_message(self, message: str):
        """处理公共 WebSocket 消息"""
        try:
            data = json.loads(message)

            # 处理订阅确认
            if data.get("event") == "subscribe":
                channel = data.get("arg", {}).get("channel", "")
                inst_id = data.get("arg", {}).get("instId", "")
                print(f"[WS-Public] 订阅成功: {channel} - {inst_id}")
                return

            # 处理 Ticker 数据
            if "data" in data and data.get("arg", {}).get("channel") == "tickers":
                for item in data["data"]:
                    ticker = _parse_ticker(item)
                    if ticker:
                        self._ticker_cache[ticker.inst_id] = ticker
                        self._public_message_count += 1

                        # 在锁内拷贝回调列表，锁外执行，避免死锁
                        with self._lock:
                            callbacks = self._ticker_callbacks.copy()
                        for callback in callbacks:
                            try:
                                callback(ticker.inst_id, ticker)
                            except Exception as e:
                                print(f"[WS-Public] 回调执行失败: {e}")

        except json.JSONDecodeError:
            pass
        except Exception as e:
            print(f"[WS-Public] 消息处理异常: {e}")

    def _on_business_message(self, message: str):
        """处理 business WebSocket 消息（K 线等）"""
        try:
            data = json.loads(message)

            # 处理订阅确认
            if data.get("event") == "subscribe":
                channel = data.get("arg", {}).get("channel", "")
                inst_id = data.get("arg", {}).get("instId", "")
                print(f"[WS-Business] 订阅成功: {channel} - {inst_id}")
                return

            channel = data.get("arg", {}).get("channel", "")
            inst_id = data.get("arg", {}).get("instId", "")
            inst_type = data.get("arg", {}).get("instType", "")

            if "data" in data and channel.startswith("candle"):
                for item in data["data"]:
                    candle = _parse_candle(item, channel=channel, inst_id=inst_id, inst_type=inst_type)
                    if not candle:
                        continue

                    cache_key = _build_candle_subscription_key(candle.inst_id, candle.timeframe)
                    self._candle_cache[cache_key] = candle
                    self._business_message_count += 1

                    with self._lock:
                        callbacks = self._candle_callbacks.copy()
                    for callback in callbacks:
                        try:
                            callback(candle.inst_id, candle.timeframe, candle)
                        except Exception as e:
                            print(f"[WS-Business] 回调执行失败: {e}")
        except json.JSONDecodeError:
            pass
        except Exception as e:
            print(f"[WS-Business] 消息处理异常: {e}")

    def _on_private_message(self, message: str):
        """处理私有 WebSocket 消息"""
        try:
            data = json.loads(message)
            self._private_message_count += 1

            # 处理登录确认
            if data.get("event") == "login":
                if data.get("code") == "0":
                    print("[WS-Private] 登录成功")
                else:
                    print(f"[WS-Private] 登录失败: {data.get('msg')}")
                return

            # 处理订阅确认
            if data.get("event") == "subscribe":
                channel = data.get("arg", {}).get("channel", "")
                print(f"[WS-Private] 订阅成功: {channel}")
                return

            # 处理数据推送
            arg = data.get("arg", {})
            channel = arg.get("channel", "")
            items = data.get("data", [])

            if channel == "account":
                self._handle_account_update(items)
            elif channel == "orders":
                self._handle_orders_update(items)
            elif channel == "fills":
                self._handle_fills_update(items)

        except json.JSONDecodeError:
            pass
        except Exception as e:
            print(f"[WS-Private] 消息处理异常: {e}")

    def _handle_account_update(self, items: List[Dict]):
        """处理账户余额更新"""
        for item in items:
            # 更新缓存
            details = item.get("details", [])
            for detail in details:
                ccy = detail.get("ccy", "")
                if ccy:
                    self._account_cache[ccy] = {
                        "ccy": ccy,
                        "cashBal": detail.get("cashBal", "0"),
                        "availBal": detail.get("availBal", "0"),
                        "frozenBal": detail.get("frozenBal", "0"),
                        "eqUsd": detail.get("eqUsd", "0"),
                        "uTime": item.get("uTime", ""),
                    }

            # 在锁内拷贝回调列表，锁外执行，避免死锁
            with self._lock:
                callbacks = self._account_callbacks.copy()
            # 重要：给回调传递快照，避免异步广播期间账户字典被继续更新，
            # 导致 json.dumps 迭代时出现 "dictionary changed size during iteration"。
            snapshot = self._account_cache.copy()
            for callback in callbacks:
                try:
                    callback("account", snapshot)
                except Exception as e:
                    print(f"[WS-Private] 账户回调执行失败: {e}")

    def _handle_orders_update(self, items: List[Dict]):
        """处理订单更新"""
        for item in items:
            # 保留最近50条
            self._orders_cache.insert(0, item)
            if len(self._orders_cache) > 50:
                self._orders_cache = self._orders_cache[:50]

            # 在锁内拷贝回调列表，锁外执行，避免死锁
            with self._lock:
                callbacks = self._orders_callbacks.copy()
            for callback in callbacks:
                try:
                    callback("order", item)
                except Exception as e:
                    print(f"[WS-Private] 订单回调执行失败: {e}")

    def _handle_fills_update(self, items: List[Dict]):
        """处理成交更新"""
        for item in items:
            # 保留最近50条
            self._fills_cache.insert(0, item)
            if len(self._fills_cache) > 50:
                self._fills_cache = self._fills_cache[:50]

            # 在锁内拷贝回调列表，锁外执行，避免死锁
            with self._lock:
                callbacks = self._fills_callbacks.copy()
            for callback in callbacks:
                try:
                    callback("fill", item)
                except Exception as e:
                    print(f"[WS-Private] 成交回调执行失败: {e}")

    # ==================== 连接管理 ====================

    async def start(self):
        """启动公共/Business WebSocket 连接"""
        if self._public_running and self._business_running:
            print("[WS-Public] 公共/Business 连接已经在运行中")
            return

        try:
            if not self._public_running:
                self._public_ws = WsPublicAsync.WsPublicAsync(url=self._public_url)
                await self._public_ws.start()
                self._public_running = True
                print(f"[WS-Public] 连接成功，模式: {self.mode}")

            if not self._business_running:
                self._business_ws = WsPublicAsync.WsPublicAsync(url=self._business_url)
                await self._business_ws.start()
                self._business_running = True
                print(f"[WS-Business] 连接成功，模式: {self.mode}")

            self._start_time = time.time()
        except Exception as e:
            print(f"[WS-Public] 启动公共/Business 连接失败: {e}")
            try:
                if self._public_ws:
                    await self._public_ws.stop()
            except Exception:
                pass
            try:
                if self._business_ws:
                    await self._business_ws.stop()
            except Exception:
                pass
            self._public_ws = None
            self._business_ws = None
            self._public_running = False
            self._business_running = False
            raise

    async def start_private(self):
        """启动私有 WebSocket 连接（需要 API 密钥）"""
        if self._private_running:
            print("[WS-Private] 已经在运行中")
            return

        # 按 WS 实例模式选择对应密钥，避免 simulated/live 串用“当前模式”的密钥
        creds = config.okx.demo if self._is_simulated else config.okx.live
        if not creds.is_valid():
            print("[WS-Private] API 密钥未配置，无法启动私有连接")
            return

        try:
            self._private_ws = WsPrivateAsync.WsPrivateAsync(
                apiKey=creds.api_key,
                passphrase=creds.passphrase,
                secretKey=creds.secret_key,
                url=self._private_url,
            )
            await self._private_ws.start()

            # 短暂等待登录响应（通常 500ms 内完成）
            await asyncio.sleep(0.5)

            # 检查连接是否仍然存活（登录失败时连接会被 OKX 关闭）
            ws = getattr(self._private_ws, 'websocket', None)
            if ws and getattr(ws, 'closed', False):
                print("[WS-Private] 连接已被服务端关闭，登录可能失败")
                print("[WS-Private] 请检查 API 密钥配置是否正确")
                self._private_running = False
                return

            self._private_running = True
            print(f"[WS-Private] 连接成功，模式: {self.mode}")

            # 订阅账户、订单、成交
            await self._subscribe_private_channels()
        except Exception as e:
            error_msg = str(e)
            print(f"[WS-Private] 连接失败: {error_msg}")
            self._private_running = False
            # 登录失败通常是 API 密钥问题，打印更详细的提示
            if "Login failed" in error_msg or "4001" in error_msg:
                print("[WS-Private] API 密钥认证失败，请检查:")
                print("  1. API Key 是否正确")
                print("  2. Secret Key 是否正确")
                print("  3. Passphrase 是否正确")
                print("  4. API 权限是否包含读取账户信息")
                print("  5. 是否使用了正确的模式（模拟盘/实盘）")

    async def _subscribe_private_channels(self):
        """订阅私有通道"""
        if not self._private_running:
            return

        try:
            # 订阅所有私有通道，支持多种交易类型（SPOT/SWAP/FUTURES/MARGIN）
            # account 通道不需要 instType 参数
            # orders 和 fills 需要分别为每种交易类型订阅
            channels = [
                {"channel": "account"},
                # SPOT 现货
                {"channel": "orders", "instType": "SPOT"},
                {"channel": "fills", "instType": "SPOT"},
                # SWAP 永续合约
                {"channel": "orders", "instType": "SWAP"},
                {"channel": "fills", "instType": "SWAP"},
                # FUTURES 交割合约
                {"channel": "orders", "instType": "FUTURES"},
                {"channel": "fills", "instType": "FUTURES"},
                # MARGIN 杠杆交易
                {"channel": "orders", "instType": "MARGIN"},
                {"channel": "fills", "instType": "MARGIN"},
            ]
            await self._private_ws.subscribe(channels, self._on_private_message)

            print("[WS-Private] 已订阅: account, orders(SPOT/SWAP/FUTURES/MARGIN), fills(SPOT/SWAP/FUTURES/MARGIN)")
        except Exception as e:
            print(f"[WS-Private] 订阅私有通道失败: {e}")

    async def stop(self):
        """停止所有 WebSocket 连接"""
        # 停止公共连接
        if self._public_running:
            try:
                if self._public_ws:
                    await self._public_ws.stop()
                self._public_running = False
                self._subscribed_ticker_instruments.clear()
                self._ticker_cache.clear()
                self._public_ws = None
                print("[WS-Public] 连接已关闭")
            except Exception as e:
                print(f"[WS-Public] 关闭连接失败: {e}")

        if self._business_running:
            try:
                if self._business_ws:
                    await self._business_ws.stop()
                self._business_running = False
                self._subscribed_candle_keys.clear()
                self._candle_cache.clear()
                self._business_ws = None
                print("[WS-Business] 连接已关闭")
            except Exception as e:
                print(f"[WS-Business] 关闭连接失败: {e}")

        # 停止私有连接
        if self._private_running:
            try:
                if self._private_ws:
                    await self._private_ws.stop()
                self._private_running = False
                print("[WS-Private] 连接已关闭")
            except Exception as e:
                print(f"[WS-Private] 关闭连接失败: {e}")

    # ==================== 订阅管理 ====================

    async def subscribe_tickers(self, inst_ids: List[str]):
        """
        订阅交易对的实时行情

        Args:
            inst_ids: 交易对列表，如 ["BTC-USDT", "ETH-USDT"]
        """
        if not self._public_running:
            print("[WS-Public] 未连接，无法订阅")
            return

        # 过滤已订阅的
        new_instruments = [i for i in inst_ids if i not in self._subscribed_ticker_instruments]
        if not new_instruments:
            return

        try:
            params = [{"channel": "tickers", "instId": inst_id} for inst_id in new_instruments]
            await self._public_ws.subscribe(params, self._on_public_message)

            for inst_id in new_instruments:
                self._subscribed_ticker_instruments.add(inst_id)

            print(f"[WS-Public] 已订阅 {len(new_instruments)} 个交易对")
        except Exception as e:
            print(f"[WS-Public] 订阅失败: {e}")

    async def unsubscribe_tickers(self, inst_ids: List[str]):
        """取消订阅实时行情"""
        if not self._public_running:
            return

        subscribed = [i for i in inst_ids if i in self._subscribed_ticker_instruments]
        if not subscribed:
            return

        try:
            params = [{"channel": "tickers", "instId": inst_id} for inst_id in subscribed]
            await self._public_ws.unsubscribe(params, self._on_public_message)

            for inst_id in subscribed:
                self._subscribed_ticker_instruments.discard(inst_id)
                self._ticker_cache.pop(inst_id, None)

            print(f"[WS-Public] 已取消订阅 {len(subscribed)} 个交易对")
        except Exception as e:
            print(f"[WS-Public] 取消订阅失败: {e}")

    async def subscribe_candles(self, subscriptions: List[Tuple[str, str]]):
        """订阅交易对的实时 K 线"""
        if not self._business_running:
            print("[WS-Business] 未连接，无法订阅 K 线")
            return

        pending: List[Tuple[str, str]] = []
        for inst_id, timeframe in subscriptions:
            normalized_timeframe = _normalize_candle_timeframe(timeframe)
            if not inst_id or not normalized_timeframe:
                continue
            key = _build_candle_subscription_key(inst_id, normalized_timeframe)
            if key in self._subscribed_candle_keys:
                continue
            pending.append((inst_id, normalized_timeframe))

        if not pending:
            return

        try:
            params = [
                {
                    "channel": _build_candle_channel(timeframe),
                    "instId": inst_id,
                }
                for inst_id, timeframe in pending
            ]
            await self._business_ws.subscribe(params, self._on_business_message)

            for inst_id, timeframe in pending:
                self._subscribed_candle_keys.add(_build_candle_subscription_key(inst_id, timeframe))

            print(f"[WS-Business] 已订阅 {len(pending)} 个 K 线频道")
        except Exception as e:
            print(f"[WS-Business] 订阅 K 线失败: {e}")

    async def unsubscribe_candles(self, subscriptions: List[Tuple[str, str]]):
        """取消订阅交易对的实时 K 线"""
        if not self._business_running:
            return

        pending: List[Tuple[str, str]] = []
        for inst_id, timeframe in subscriptions:
            normalized_timeframe = _normalize_candle_timeframe(timeframe)
            if not inst_id or not normalized_timeframe:
                continue
            key = _build_candle_subscription_key(inst_id, normalized_timeframe)
            if key not in self._subscribed_candle_keys:
                continue
            pending.append((inst_id, normalized_timeframe))

        if not pending:
            return

        try:
            params = [
                {
                    "channel": _build_candle_channel(timeframe),
                    "instId": inst_id,
                }
                for inst_id, timeframe in pending
            ]
            await self._business_ws.unsubscribe(params, self._on_business_message)

            for inst_id, timeframe in pending:
                key = _build_candle_subscription_key(inst_id, timeframe)
                self._subscribed_candle_keys.discard(key)
                self._candle_cache.pop(key, None)

            print(f"[WS-Business] 已取消订阅 {len(pending)} 个 K 线频道")
        except Exception as e:
            print(f"[WS-Business] 取消订阅 K 线失败: {e}")

    async def subscribe(self, inst_ids: List[str]):
        """兼容旧接口：订阅实时行情"""
        await self.subscribe_tickers(inst_ids)

    async def unsubscribe(self, inst_ids: List[str]):
        """兼容旧接口：取消订阅实时行情"""
        await self.unsubscribe_tickers(inst_ids)

    # ==================== 统计信息 ====================

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        uptime = time.time() - self._start_time if self._start_time else 0
        return {
            "public": {
                "running": self._public_running,
                "subscribed_count": len(self._subscribed_ticker_instruments),
                "subscribed_instruments": list(self._subscribed_ticker_instruments),
                "cached_tickers": len(self._ticker_cache),
                "message_count": self._public_message_count,
            },
            "business": {
                "running": self._business_running,
                "subscribed_count": len(self._subscribed_candle_keys),
                "subscribed_candles": list(self._subscribed_candle_keys),
                "cached_candles": len(self._candle_cache),
                "message_count": self._business_message_count,
            },
            "private": {
                "running": self._private_running,
                "cached_accounts": len(self._account_cache),
                "cached_orders": len(self._orders_cache),
                "cached_fills": len(self._fills_cache),
                "message_count": self._private_message_count,
            },
            "mode": self.mode,
            "uptime_seconds": round(uptime, 1),
        }


# ==================== 全局实例（按 mode 维护多实例） ====================

# 说明：
# - 前端同时存在“模拟盘/实盘”两个交易页，REST 接口已支持通过 mode 选择实例。
# - 为避免私有 WS 只能连一套环境导致另一页“连接正常但数据静默不更新”，这里按 mode 缓存 WS 管理器实例。
# - 默认 mode（None）仍使用当前配置 config.okx.is_simulated，对旧调用保持兼容。

_ws_managers: Dict[str, OKXWebSocketManager] = {}
_ws_manager_lock = Lock()

# WS 重启监听器：用于在 restart_ws_manager 后恢复回调/订阅等状态
WSRestartListener = Callable[[], Union[None, Awaitable[None]]]
_ws_restart_listeners: List[WSRestartListener] = []
_ws_restart_lock = Lock()


def add_ws_restart_listener(listener: WSRestartListener):
    """注册 WS 重启监听器（幂等）"""
    with _ws_restart_lock:
        if listener not in _ws_restart_listeners:
            _ws_restart_listeners.append(listener)


async def _notify_ws_restart_listeners():
    """通知所有已注册监听器"""
    with _ws_restart_lock:
        listeners = list(_ws_restart_listeners)

    for listener in listeners:
        try:
            result = listener()
            if asyncio.iscoroutine(result):
                await result
        except Exception as e:
            print(f"[WS-Restart] 重启监听器执行失败: {e}")


def _normalize_mode(mode: Optional[str]) -> str:
    """规范化 mode：None -> 当前配置；非法值也回退到当前配置"""
    return coerce_mode(mode, mode_from_bool(config.okx.is_simulated))


def get_ws_manager(mode: Optional[str] = None) -> OKXWebSocketManager:
    """获取指定 mode 的 WebSocket 管理器实例"""
    normalized = _normalize_mode(mode)
    with _ws_manager_lock:
        manager = _ws_managers.get(normalized)
        if manager is None:
            manager = OKXWebSocketManager(is_simulated=(normalized == "simulated"))
            _ws_managers[normalized] = manager
    return manager


async def start_ws_manager(mode: Optional[str] = None):
    """启动指定 mode 的 WebSocket 管理器（公共 + Business）"""
    manager = get_ws_manager(mode)
    if not manager.is_running or not manager.is_business_running:
        await manager.start()
    return manager


async def start_private_ws_manager(mode: str):
    """仅启动指定 mode 的私有 WS（账户/订单/成交）"""
    manager = get_ws_manager(mode)
    if not manager.is_private_running:
        await manager.start_private()
    return manager


async def stop_ws_manager(mode: Optional[str] = None):
    """停止指定 mode 的 WebSocket 管理器；mode=None 时停止全部"""
    global _ws_managers
    with _ws_manager_lock:
        if mode is None:
            managers = list(_ws_managers.items())
            _ws_managers = {}
        else:
            normalized = _normalize_mode(mode)
            managers = [(normalized, _ws_managers.pop(normalized, None))]

    for _, mgr in managers:
        if mgr:
            await mgr.stop()


async def restart_ws_manager():
    """
    重启全局 WebSocket 管理器（用于配置变更后）

    会停止旧连接，清空实例，然后用新配置创建新连接
    """
    # 1. 停止并清空所有实例（包含 simulated/live），避免配置变更后继续使用旧连接/旧密钥
    try:
        await stop_ws_manager(mode=None)
    except Exception as e:
        print(f"[WS-Restart] 停止旧连接失败: {e}")

    # 2. 用新配置创建“当前模式”实例并启动（公共 + Business）
    await start_ws_manager(mode=None)
    # 4. 通知监听器恢复回调/订阅（前端连接不需要重连）
    await _notify_ws_restart_listeners()
    print(f"[WS-Restart] 已重启，模式: {'simulated' if config.okx.is_simulated else 'live'}")
