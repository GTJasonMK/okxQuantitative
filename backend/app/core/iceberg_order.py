# 冰山委托模块
# 将大额订单拆分为多个小额子订单分批执行

import asyncio
import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class IcebergConfig:
    """冰山委托配置"""
    total_size: float               # 总数量
    slice_size: float               # 每笔子订单数量
    side: str = "buy"               # buy / sell
    price_limit: Optional[float] = None  # 限价（None=市价）
    interval_seconds: float = 5.0   # 子订单间隔（秒）
    randomize: bool = True          # 是否随机化切片大小（±20%）
    randomize_ratio: float = 0.2    # 随机化幅度


@dataclass
class IcebergSlice:
    """子订单"""
    slice_index: int
    size: float
    status: str = "pending"  # pending / filled / failed / cancelled
    order_id: str = ""
    fill_price: float = 0.0
    error: str = ""
    executed_at: Optional[str] = None


@dataclass
class IcebergOrder:
    """冰山委托"""
    iceberg_id: str
    inst_id: str
    side: str
    total_size: float
    slice_size: float
    config: IcebergConfig
    status: str = "active"  # active / completed / cancelled / failed
    slices: List[IcebergSlice] = field(default_factory=list)
    filled_size: float = 0.0
    filled_slices: int = 0
    total_slices: int = 0
    created_at: str = ""
    updated_at: str = ""

    @property
    def progress(self) -> float:
        if self.total_size <= 0:
            return 0
        return round(self.filled_size / self.total_size * 100, 2)


class IcebergOrderManager:
    """
    冰山委托管理器。

    将大单拆分为多个子单，按间隔依次下达。
    支持随机化切片大小和取消。
    """

    def __init__(self):
        self._active_orders: Dict[str, IcebergOrder] = {}
        self._cancelled: set = set()

    def create_order(
        self,
        inst_id: str,
        config: IcebergConfig,
    ) -> IcebergOrder:
        """
        创建冰山委托（仅创建计划，不立即执行）。

        Args:
            inst_id: 交易对
            config: 冰山配置

        Returns:
            IcebergOrder
        """
        iceberg_id = f"ice_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()

        # 计算切片
        slices: List[IcebergSlice] = []
        remaining = config.total_size
        idx = 0

        while remaining > 0:
            size = min(config.slice_size, remaining)
            if config.randomize and size == config.slice_size:
                factor = 1 + random.uniform(-config.randomize_ratio, config.randomize_ratio)
                size = min(size * factor, remaining)
            size = round(size, 8)
            if size <= 0:
                break

            slices.append(IcebergSlice(slice_index=idx, size=size))
            remaining -= size
            idx += 1

        order = IcebergOrder(
            iceberg_id=iceberg_id,
            inst_id=inst_id,
            side=config.side,
            total_size=config.total_size,
            slice_size=config.slice_size,
            config=config,
            slices=slices,
            total_slices=len(slices),
            created_at=now,
            updated_at=now,
        )

        self._active_orders[iceberg_id] = order
        return order

    async def execute(
        self,
        iceberg_id: str,
        place_order_fn,
    ) -> IcebergOrder:
        """
        执行冰山委托。

        Args:
            iceberg_id: 冰山 ID
            place_order_fn: 下单回调函数，签名:
                async def place_order(inst_id, side, size, price=None) -> dict

        Returns:
            更新后的 IcebergOrder
        """
        order = self._active_orders.get(iceberg_id)
        if not order:
            raise ValueError(f"冰山委托 {iceberg_id} 不存在")

        for sl in order.slices:
            if iceberg_id in self._cancelled:
                order.status = "cancelled"
                sl.status = "cancelled"
                break

            if sl.status != "pending":
                continue

            try:
                result = await place_order_fn(
                    inst_id=order.inst_id,
                    side=order.side,
                    size=sl.size,
                    price=order.config.price_limit,
                )
                sl.status = "filled"
                sl.order_id = result.get("order_id", "")
                sl.fill_price = float(result.get("fill_price", 0))
                sl.executed_at = datetime.now(timezone.utc).isoformat()
                order.filled_size += sl.size
                order.filled_slices += 1
            except Exception as e:
                sl.status = "failed"
                sl.error = str(e)

            order.updated_at = datetime.now(timezone.utc).isoformat()

            # 等待间隔
            if order.config.interval_seconds > 0:
                await asyncio.sleep(order.config.interval_seconds)

        # 更新最终状态
        if order.status != "cancelled":
            all_filled = all(s.status == "filled" for s in order.slices)
            order.status = "completed" if all_filled else "failed"
        order.updated_at = datetime.now(timezone.utc).isoformat()

        return order

    def cancel(self, iceberg_id: str) -> bool:
        """取消冰山委托（标记取消，等待当前切片完成后停止）"""
        if iceberg_id not in self._active_orders:
            return False
        self._cancelled.add(iceberg_id)
        order = self._active_orders[iceberg_id]
        for sl in order.slices:
            if sl.status == "pending":
                sl.status = "cancelled"
        order.status = "cancelled"
        order.updated_at = datetime.now(timezone.utc).isoformat()
        return True

    def get_order(self, iceberg_id: str) -> Optional[IcebergOrder]:
        return self._active_orders.get(iceberg_id)

    def get_active_orders(self) -> List[IcebergOrder]:
        return [o for o in self._active_orders.values() if o.status == "active"]

    def get_all_orders(self) -> List[IcebergOrder]:
        return list(self._active_orders.values())

    def to_dict(self, order: IcebergOrder) -> Dict[str, Any]:
        """序列化冰山委托为字典"""
        return {
            "iceberg_id": order.iceberg_id,
            "inst_id": order.inst_id,
            "side": order.side,
            "total_size": order.total_size,
            "slice_size": order.slice_size,
            "status": order.status,
            "filled_size": order.filled_size,
            "filled_slices": order.filled_slices,
            "total_slices": order.total_slices,
            "progress": order.progress,
            "slices": [
                {
                    "slice_index": s.slice_index,
                    "size": s.size,
                    "status": s.status,
                    "order_id": s.order_id,
                    "fill_price": s.fill_price,
                    "error": s.error,
                    "executed_at": s.executed_at,
                }
                for s in order.slices
            ],
            "created_at": order.created_at,
            "updated_at": order.updated_at,
        }
