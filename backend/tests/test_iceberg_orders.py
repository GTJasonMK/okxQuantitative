# 冰山委托测试

import asyncio

import pytest

from app.core.iceberg_order import IcebergConfig, IcebergOrderManager


class TestIcebergOrder:
    """冰山委托管理器测试"""

    @pytest.fixture
    def manager(self):
        return IcebergOrderManager()

    def test_create_order(self, manager):
        """创建冰山委托"""
        config = IcebergConfig(
            total_size=10.0,
            slice_size=2.0,
            side="buy",
            randomize=False,
        )
        order = manager.create_order("BTC-USDT", config)

        assert order.iceberg_id.startswith("ice_")
        assert order.total_size == 10.0
        assert order.total_slices == 5
        assert order.status == "active"
        assert all(s.status == "pending" for s in order.slices)
        # 每片应为 2.0
        assert all(s.size == 2.0 for s in order.slices)

    def test_create_order_with_remainder(self, manager):
        """总量不整除时最后一片为余量"""
        config = IcebergConfig(
            total_size=10.0,
            slice_size=3.0,
            side="buy",
            randomize=False,
        )
        order = manager.create_order("BTC-USDT", config)

        assert order.total_slices == 4  # 3 + 3 + 3 + 1
        sizes = [s.size for s in order.slices]
        assert sum(sizes) == pytest.approx(10.0, abs=0.01)

    def test_create_order_randomized(self, manager):
        """随机化切片大小"""
        config = IcebergConfig(
            total_size=100.0,
            slice_size=20.0,
            side="buy",
            randomize=True,
            randomize_ratio=0.2,
        )
        order = manager.create_order("BTC-USDT", config)

        # 切片数量可能不同于 5（因为随机化会改变每片大小）
        total = sum(s.size for s in order.slices)
        assert total == pytest.approx(100.0, abs=0.01)

    @pytest.mark.asyncio
    async def test_execute_all_success(self, manager):
        """成功执行所有切片"""
        config = IcebergConfig(
            total_size=6.0,
            slice_size=2.0,
            side="buy",
            randomize=False,
            interval_seconds=0,  # 无间隔以加快测试
        )
        order = manager.create_order("BTC-USDT", config)

        async def mock_place_order(inst_id, side, size, price=None):
            return {"order_id": "test_123", "fill_price": 65000}

        result = await manager.execute(order.iceberg_id, mock_place_order)

        assert result.status == "completed"
        assert result.filled_slices == 3
        assert result.filled_size == pytest.approx(6.0)
        assert result.progress == pytest.approx(100.0)

    @pytest.mark.asyncio
    async def test_execute_partial_failure(self, manager):
        """部分切片下单失败"""
        config = IcebergConfig(
            total_size=6.0,
            slice_size=2.0,
            side="buy",
            randomize=False,
            interval_seconds=0,
        )
        order = manager.create_order("BTC-USDT", config)
        call_count = 0

        async def mock_place_order(inst_id, side, size, price=None):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise Exception("网络超时")
            return {"order_id": f"order_{call_count}", "fill_price": 65000}

        result = await manager.execute(order.iceberg_id, mock_place_order)

        assert result.status == "failed"  # 有失败切片
        assert result.filled_slices == 2
        failed = [s for s in result.slices if s.status == "failed"]
        assert len(failed) == 1

    @pytest.mark.asyncio
    async def test_cancel_order(self, manager):
        """取消冰山委托"""
        config = IcebergConfig(
            total_size=6.0,
            slice_size=2.0,
            side="buy",
            randomize=False,
            interval_seconds=0,
        )
        order = manager.create_order("BTC-USDT", config)

        # 在执行前取消
        ok = manager.cancel(order.iceberg_id)
        assert ok is True

        async def mock_place_order(inst_id, side, size, price=None):
            return {"order_id": "test", "fill_price": 65000}

        result = await manager.execute(order.iceberg_id, mock_place_order)
        assert result.status == "cancelled"
        assert result.filled_slices == 0

    def test_cancel_nonexistent(self, manager):
        """取消不存在的委托"""
        assert manager.cancel("nonexistent") is False

    def test_get_order(self, manager):
        """查询冰山委托"""
        config = IcebergConfig(total_size=5.0, slice_size=1.0, randomize=False)
        order = manager.create_order("ETH-USDT", config)

        found = manager.get_order(order.iceberg_id)
        assert found is not None
        assert found.inst_id == "ETH-USDT"

        assert manager.get_order("nonexistent") is None

    def test_to_dict(self, manager):
        """序列化为字典"""
        config = IcebergConfig(total_size=5.0, slice_size=2.5, randomize=False)
        order = manager.create_order("SOL-USDT", config)

        d = manager.to_dict(order)
        assert d["iceberg_id"] == order.iceberg_id
        assert d["total_size"] == 5.0
        assert len(d["slices"]) == 2
        assert d["progress"] == 0
