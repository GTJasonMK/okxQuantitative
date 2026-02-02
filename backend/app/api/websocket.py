# WebSocket API 路由
# 提供实时行情和账户数据推送

import asyncio
import json
from typing import Set, Dict, Any, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from .deps import get_ctx
from ..core.websocket_manager import TickerData
from ..utils.mode import coerce_mode, mode_from_bool


# 保持现有代码习惯：仍使用 config 变量名
config = get_ctx().cfg

router = APIRouter(prefix="/ws", tags=["WebSocket"])


class ConnectionManager:
    """
    WebSocket 连接管理器

    管理所有前端 WebSocket 客户端连接，并转发 OKX 数据
    支持: ticker(行情), account(账户), order(订单), fill(成交)
    """

    def __init__(self):
        # 活跃连接: websocket -> 订阅配置
        self._connections: Dict[WebSocket, Dict[str, Any]] = {}
        # 回调注册状态
        self._callback_registered = False
        # 私有 WS 回调注册状态（按 mode 维护，防止重复注册）
        self._private_callback_registered: Dict[str, bool] = {"simulated": False, "live": False}
        # asyncio.Lock 会绑定事件循环；ConnectionManager 是模块级单例，可能跨 loop 复用。
        # 这里按当前运行 loop 延迟创建，避免 "is bound to a different event loop" 异常。
        self._private_setup_lock: Optional[asyncio.Lock] = None
        self._private_setup_lock_loop = None
        # 全局交易对订阅引用计数: inst_id -> 订阅客户端数量
        self._ticker_ref_count: Dict[str, int] = {}

    def _get_private_setup_lock(self) -> asyncio.Lock:
        """获取与当前事件循环绑定的私有 WS 初始化锁"""
        loop = asyncio.get_running_loop()
        if self._private_setup_lock is None or self._private_setup_lock_loop is not loop:
            self._private_setup_lock_loop = loop
            self._private_setup_lock = asyncio.Lock()
        return self._private_setup_lock

    async def connect(self, websocket: WebSocket):
        """接受新的 WebSocket 连接"""
        await websocket.accept()
        self._connections[websocket] = {
            "tickers": set(),       # 订阅的交易对
            "account": False,       # 是否订阅账户
            "orders": False,        # 是否订阅订单
            "fills": False,         # 是否订阅成交
            "mode": None,           # 私有数据期望模式(simulated/live)，用于路由到对应 OKX 私有 WS
        }
        print(f"[WS] 新客户端连接，当前连接数: {len(self._connections)}")

        # 确保回调已注册
        if not self._callback_registered:
            await self._setup_callbacks()

    def disconnect(self, websocket: WebSocket):
        """断开 WebSocket 连接"""
        if websocket in self._connections:
            # 清理该客户端的订阅引用计数
            subs = self._connections[websocket]
            to_unsubscribe = []
            for inst_id in subs["tickers"]:
                # 引用计数归零时同步取消 OKX 订阅，避免“断线后订阅泄漏”
                if self._decrement_ticker_ref(inst_id) == 0:
                    to_unsubscribe.append(inst_id)
            del self._connections[websocket]

            # disconnect 是同步方法：用 create_task 在事件循环中异步取消订阅
            if to_unsubscribe:
                okx_manager = get_ctx().ws_manager()
                if okx_manager.is_running:
                    asyncio.create_task(okx_manager.unsubscribe(to_unsubscribe))
        print(f"[WS] 客户端断开，当前连接数: {len(self._connections)}")

    def _increment_ticker_ref(self, inst_id: str):
        """增加交易对订阅引用计数"""
        self._ticker_ref_count[inst_id] = self._ticker_ref_count.get(inst_id, 0) + 1

    def _decrement_ticker_ref(self, inst_id: str):
        """减少交易对订阅引用计数，返回剩余计数"""
        if inst_id in self._ticker_ref_count:
            self._ticker_ref_count[inst_id] -= 1
            if self._ticker_ref_count[inst_id] <= 0:
                del self._ticker_ref_count[inst_id]
                return 0
            return self._ticker_ref_count[inst_id]
        return 0

    async def _setup_callbacks(self):
        """设置 OKX 公共 WS 回调（ticker）"""
        try:
            manager = await get_ctx().start_ws()
            manager.add_ticker_callback(self._on_ticker_update)
            self._callback_registered = True
            print("[WS] 已注册 OKX 行情回调（ticker）")
        except Exception as e:
            print(f"[WS] 注册 OKX 回调失败: {e}")

    def _normalize_mode(self, mode: Any) -> str:
        """规范化 mode：None/非法值回退到当前配置"""
        return coerce_mode(mode, mode_from_bool(config.okx.is_simulated))

    async def _ensure_private_ws(self, mode: str):
        """
        确保指定 mode 的私有 WS 已启动且已注册回调

        目标：支持同一后端同时为“模拟盘/实盘”页面推送私有数据，
        避免模式不匹配导致前端页面“WS 显示已连接但数据静默不更新”。
        """
        mode = self._normalize_mode(mode)
        async with self._get_private_setup_lock():
            manager = await get_ctx().start_private_ws(mode)

            # 每个 mode 的回调只注册一次，防止重复广播
            if not self._private_callback_registered.get(mode, False):
                manager.add_account_callback(lambda event_type, data, m=mode: self._on_account_update(event_type, data, m))
                manager.add_orders_callback(lambda event_type, data, m=mode: self._on_orders_update(event_type, data, m))
                manager.add_fills_callback(lambda event_type, data, m=mode: self._on_fills_update(event_type, data, m))
                self._private_callback_registered[mode] = True
                print(f"[WS] 已注册 OKX 私有回调（account/orders/fills），mode={mode}")

    async def on_ws_manager_restart(self):
        """
        OKX WS 重启后的恢复动作

        - 重新注册回调（新 manager 实例不会继承旧回调）
        - 重新订阅所有仍被客户端引用的 ticker（避免推送静默中断）
        """
        try:
            # 新 manager 实例不带回调：重置注册状态
            self._callback_registered = False
            self._private_callback_registered = {"simulated": False, "live": False}

            await self._setup_callbacks()

            # 恢复 ticker 订阅（公共 WS）
            okx_manager = get_ctx().ws_manager()
            inst_ids = list(self._ticker_ref_count.keys())
            if inst_ids and okx_manager.is_running:
                await okx_manager.subscribe(inst_ids)
                print(f"[WS] OKX WS 重启后已恢复行情订阅: {len(inst_ids)} 个交易对")

            # 恢复私有 WS（按连接实际订阅的 mode）
            modes = set()
            for subs in self._connections.values():
                if subs.get("account") or subs.get("orders") or subs.get("fills"):
                    modes.add(self._normalize_mode(subs.get("mode")))
            for mode in modes:
                await self._ensure_private_ws(mode)
        except Exception as e:
            print(f"[WS] OKX WS 重启恢复失败: {e}")

    # ==================== 回调处理 ====================

    def _on_ticker_update(self, inst_id: str, ticker: TickerData):
        """行情更新回调"""
        asyncio.create_task(self._broadcast_ticker(inst_id, ticker))

    def _on_account_update(self, event_type: str, account_data: Dict, mode: str):
        """账户更新回调"""
        asyncio.create_task(self._broadcast_account(account_data, mode))

    def _on_orders_update(self, event_type: str, order_data: Dict, mode: str):
        """订单更新回调"""
        asyncio.create_task(self._broadcast_order(order_data, mode))

    def _on_fills_update(self, event_type: str, fill_data: Dict, mode: str):
        """成交更新回调"""
        asyncio.create_task(self._broadcast_fill(fill_data, mode))

    # ==================== 广播 ====================

    async def _broadcast_ticker(self, inst_id: str, ticker: TickerData):
        """广播行情数据"""
        message = json.dumps({
            "type": "ticker",
            "data": ticker.to_dict(),
        })
        await self._send_to_subscribers(
            message,
            filter_fn=lambda subs: inst_id in subs["tickers"]
        )

    async def _broadcast_account(self, account_data: Dict, mode: str):
        """广播账户数据（含 WS 连接模式）"""
        message = json.dumps({
            "type": "account",
            "mode": mode,  # 标记数据来源模式
            "data": account_data,
        })
        await self._send_to_subscribers(
            message,
            filter_fn=lambda subs: subs["account"] and self._normalize_mode(subs.get("mode")) == mode
        )

    async def _broadcast_order(self, order_data: Dict, mode: str):
        """广播订单数据（含 WS 连接模式）"""
        message = json.dumps({
            "type": "order",
            "mode": mode,  # 标记数据来源模式
            "data": order_data,
        })
        await self._send_to_subscribers(
            message,
            filter_fn=lambda subs: subs["orders"] and self._normalize_mode(subs.get("mode")) == mode
        )

    async def _broadcast_fill(self, fill_data: Dict, mode: str):
        """广播成交数据（含 WS 连接模式）"""
        message = json.dumps({
            "type": "fill",
            "mode": mode,  # 标记数据来源模式
            "data": fill_data,
        })
        await self._send_to_subscribers(
            message,
            filter_fn=lambda subs: subs["fills"] and self._normalize_mode(subs.get("mode")) == mode
        )

    async def _send_to_subscribers(self, message: str, filter_fn):
        """发送消息给符合条件的客户端"""
        disconnected = []
        # 遍历前拷贝，避免 RuntimeError: dictionary changed size during iteration
        connections_snapshot = list(self._connections.items())
        for websocket, subs in connections_snapshot:
            if filter_fn(subs):
                try:
                    if websocket.client_state == WebSocketState.CONNECTED:
                        await websocket.send_text(message)
                except Exception:
                    disconnected.append(websocket)

        for ws in disconnected:
            self.disconnect(ws)

    # ==================== 订阅管理 ====================

    async def handle_subscribe(self, websocket: WebSocket, message: Dict):
        """处理订阅请求"""
        if websocket not in self._connections:
            return

        subs = self._connections[websocket]
        channels = message.get("channels", [])
        instruments = message.get("instruments", [])
        okx_manager = get_ctx().ws_manager()
        requested_mode = message.get("mode")

        # 私有通道订阅：需要按 mode 启动对应的 OKX 私有 WS
        if any(ch in ("account", "orders", "fills") for ch in channels):
            subs["mode"] = self._normalize_mode(requested_mode)
            await self._ensure_private_ws(subs["mode"])

        for channel in channels:
            if channel == "ticker" and instruments:
                # 只对新增的交易对增加引用计数
                new_instruments = []
                for inst_id in instruments:
                    if inst_id not in subs["tickers"]:
                        subs["tickers"].add(inst_id)
                        self._increment_ticker_ref(inst_id)
                        new_instruments.append(inst_id)
                # 同步到 OKX WebSocket（只订阅新增的）
                if new_instruments and okx_manager.is_running:
                    await okx_manager.subscribe(new_instruments)

            elif channel == "account":
                subs["account"] = True

            elif channel == "orders":
                subs["orders"] = True

            elif channel == "fills":
                subs["fills"] = True

        # 兼容旧格式: {"action": "subscribe", "instruments": [...]}
        if not channels and instruments:
            new_instruments = []
            for inst_id in instruments:
                if inst_id not in subs["tickers"]:
                    subs["tickers"].add(inst_id)
                    self._increment_ticker_ref(inst_id)
                    new_instruments.append(inst_id)
            if new_instruments and okx_manager.is_running:
                await okx_manager.subscribe(new_instruments)

    async def handle_unsubscribe(self, websocket: WebSocket, message: Dict):
        """处理取消订阅请求"""
        if websocket not in self._connections:
            return

        subs = self._connections[websocket]
        channels = message.get("channels", [])
        instruments = message.get("instruments", [])
        okx_manager = get_ctx().ws_manager()

        # 需要从 OKX 取消订阅的交易对
        to_unsubscribe = []

        for channel in channels:
            if channel == "ticker" and instruments:
                for inst_id in instruments:
                    if inst_id in subs["tickers"]:
                        subs["tickers"].discard(inst_id)
                        # 减少引用计数，如果为0则需要取消 OKX 订阅
                        if self._decrement_ticker_ref(inst_id) == 0:
                            to_unsubscribe.append(inst_id)
            elif channel == "account":
                subs["account"] = False
            elif channel == "orders":
                subs["orders"] = False
            elif channel == "fills":
                subs["fills"] = False

        # 兼容旧格式
        if not channels and instruments:
            for inst_id in instruments:
                if inst_id in subs["tickers"]:
                    subs["tickers"].discard(inst_id)
                    if self._decrement_ticker_ref(inst_id) == 0:
                        to_unsubscribe.append(inst_id)

        # 同步取消订阅到 OKX
        if to_unsubscribe and okx_manager.is_running:
            await okx_manager.unsubscribe(to_unsubscribe)

    def get_stats(self) -> Dict[str, Any]:
        """获取连接统计"""
        all_tickers = set()
        account_count = 0
        orders_count = 0
        fills_count = 0

        for subs in self._connections.values():
            all_tickers.update(subs["tickers"])
            if subs["account"]:
                account_count += 1
            if subs["orders"]:
                orders_count += 1
            if subs["fills"]:
                fills_count += 1

        return {
            "active_connections": len(self._connections),
            "ticker_subscriptions": len(all_tickers),
            "account_subscribers": account_count,
            "orders_subscribers": orders_count,
            "fills_subscribers": fills_count,
        }


# 全局连接管理器
connection_manager = ConnectionManager()


# 注册“OKX WS 重启监听器”：保存配置/切换模式后无需前端重连，也能恢复回调与订阅
async def _on_okx_ws_restart():
    await connection_manager.on_ws_manager_restart()


get_ctx().add_ws_restart_listener(_on_okx_ws_restart)


@router.websocket("/market")
async def websocket_market(websocket: WebSocket):
    """
    实时数据 WebSocket 端点

    订阅格式:
    - 行情:   {"action": "subscribe", "channels": ["ticker"], "instruments": ["BTC-USDT"]}
    - 账户:   {"action": "subscribe", "channels": ["account"]}
    - 订单:   {"action": "subscribe", "channels": ["orders"]}
    - 成交:   {"action": "subscribe", "channels": ["fills"]}
    - 全部:   {"action": "subscribe", "channels": ["ticker", "account", "orders", "fills"], "instruments": ["BTC-USDT"]}

    推送格式:
    - {"type": "ticker",  "data": {...}}
    - {"type": "account", "data": {...}}
    - {"type": "order",   "data": {...}}
    - {"type": "fill",    "data": {...}}
    """
    await connection_manager.connect(websocket)

    try:
        while True:
            data = await websocket.receive_text()

            try:
                message = json.loads(data)
                action = message.get("action")

                if action == "subscribe":
                    await connection_manager.handle_subscribe(websocket, message)
                    await websocket.send_text(json.dumps({
                        "type": "subscribed",
                        "channels": message.get("channels", []),
                        "instruments": message.get("instruments", []),
                    }))

                elif action == "unsubscribe":
                    await connection_manager.handle_unsubscribe(websocket, message)
                    await websocket.send_text(json.dumps({
                        "type": "unsubscribed",
                        "channels": message.get("channels", []),
                        "instruments": message.get("instruments", []),
                    }))

                elif action == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))

            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "Invalid JSON",
                }))

    except WebSocketDisconnect:
        pass
    except Exception as e:
        # 避免异常导致连接未清理，从而造成订阅引用计数泄漏/内存泄漏
        print(f"[WS] 客户端处理异常: {e}")
    finally:
        connection_manager.disconnect(websocket)


@router.get("/stats")
async def get_websocket_stats():
    """获取 WebSocket 统计信息"""
    client_stats = connection_manager.get_stats()
    okx_stats = get_ctx().ws_manager().get_stats()

    return {
        "clients": client_stats,
        "okx_websocket": okx_stats,
    }


@router.post("/start")
async def start_websocket_service():
    """手动启动 OKX WebSocket 服务"""
    try:
        await get_ctx().start_ws()
        return {"success": True, "message": "WebSocket 服务已启动"}
    except Exception as e:
        return {"success": False, "message": str(e)}
