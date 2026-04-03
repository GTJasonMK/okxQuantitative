# 市场扫描功能测试
# 覆盖扫描引擎条件评估、方案 CRUD、API 端点

from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient

from app.core.data_storage import DataStorage
from app.core.market_scanner import MarketScanner, ScanCondition
from app.main import app


# ==================== 辅助：构造假 K 线数据 ====================


@dataclass
class FakeCandle:
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    volume_ccy: float = 0.0


def _generate_candles(
    base_price: float = 100.0,
    count: int = 50,
    trend: float = 0.5,
    volatility: float = 2.0,
    base_volume: float = 1000.0,
) -> list:
    """生成模拟 K 线序列"""
    candles = []
    price = base_price
    for i in range(count):
        import math
        delta = trend + volatility * math.sin(i * 0.3)
        price = max(price + delta, 1.0)
        candles.append(FakeCandle(
            timestamp=1700000000000 + i * 3600000,
            open=price - abs(delta) * 0.3,
            high=price + abs(delta) * 0.5,
            low=price - abs(delta) * 0.5,
            close=price,
            volume=base_volume + (i % 5) * 200,
        ))
    return candles


# ==================== 扫描引擎测试 ====================


class FakeStorage:
    """模拟存储，返回预设 K 线"""

    def __init__(self):
        self.candle_data = {}

    def set_candles(self, symbol: str, candles: list):
        self.candle_data[symbol] = candles

    def get_latest_candles(self, inst_id, timeframe, count=100, inst_type="SPOT"):
        candles = self.candle_data.get(inst_id, [])
        return candles[-count:]


class TestMarketScanner:
    """扫描引擎条件评估测试"""

    @pytest.fixture
    def scanner(self):
        storage = FakeStorage()
        # 准备一个上涨趋势币种（RSI 偏高）
        storage.set_candles("BTC-USDT", _generate_candles(
            base_price=60000, count=50, trend=200, volatility=500,
        ))
        # 准备一个横盘币种
        storage.set_candles("ETH-USDT", _generate_candles(
            base_price=3000, count=50, trend=0, volatility=30,
        ))
        return MarketScanner(storage)

    def test_rsi_condition(self, scanner):
        """RSI 条件筛选"""
        # RSI < 100 应该匹配所有有数据的币种
        results = scanner.scan(
            symbols=["BTC-USDT", "ETH-USDT"],
            conditions=[ScanCondition(indicator="rsi", operator="lt", value=100, params={"period": 14})],
        )
        assert len(results) >= 1
        for r in results:
            assert "rsi(14)" in r.indicator_values

    def test_volume_breakout(self, scanner):
        """放量突破条件"""
        results = scanner.scan(
            symbols=["BTC-USDT"],
            conditions=[ScanCondition(indicator="volume_breakout", operator="gte", value=0.1)],
        )
        # 放量条件宽松（0.1 倍），应该匹配
        assert len(results) >= 1

    def test_bb_squeeze(self, scanner):
        """布林带收窄条件"""
        # 宽松阈值，应匹配
        results = scanner.scan(
            symbols=["ETH-USDT"],
            conditions=[ScanCondition(indicator="bb_squeeze", operator="lt", value=1.0)],
        )
        assert len(results) >= 1

    def test_and_logic(self, scanner):
        """AND 逻辑：所有条件都满足"""
        results = scanner.scan(
            symbols=["BTC-USDT"],
            conditions=[
                ScanCondition(indicator="rsi", operator="lt", value=100),
                ScanCondition(indicator="rsi", operator="gt", value=-1),
            ],
            logic="and",
        )
        assert len(results) == 1

    def test_or_logic(self, scanner):
        """OR 逻辑：任一条件满足"""
        results = scanner.scan(
            symbols=["BTC-USDT"],
            conditions=[
                ScanCondition(indicator="rsi", operator="lt", value=1),  # 不太可能满足
                ScanCondition(indicator="rsi", operator="gt", value=0),  # 一定满足
            ],
            logic="or",
        )
        assert len(results) == 1

    def test_insufficient_data(self, scanner):
        """数据不足的币种被跳过"""
        scanner._storage.set_candles("NEW-USDT", _generate_candles(count=5))
        results = scanner.scan(
            symbols=["NEW-USDT"],
            conditions=[ScanCondition(indicator="rsi", operator="lt", value=100)],
        )
        assert len(results) == 0

    def test_empty_symbols(self, scanner):
        """空币种列表"""
        results = scanner.scan(
            symbols=[],
            conditions=[ScanCondition(indicator="rsi", operator="lt", value=100)],
        )
        assert results == []


# ==================== 存储层测试 ====================


class TestStorageScanner:
    """扫描方案存储测试"""

    @pytest.fixture
    def storage(self, tmp_path):
        return DataStorage(tmp_path / "test_scanner.db")

    def test_profile_crud(self, storage):
        """方案增删改查"""
        pid = storage.save_scanner_profile({
            "name": "RSI 超卖",
            "conditions": [{"indicator": "rsi", "operator": "lt", "value": 30}],
            "timeframe": "4H",
        })
        assert pid.startswith("sp_")

        profiles = storage.get_scanner_profiles()
        assert len(profiles) == 1
        assert profiles[0]["name"] == "RSI 超卖"

        profile = storage.get_scanner_profile(pid)
        assert profile is not None
        assert profile["timeframe"] == "4H"

        ok = storage.delete_scanner_profile(pid)
        assert ok is True
        assert storage.get_scanner_profile(pid) is None

    def test_results_save_and_query(self, storage):
        """扫描结果保存与查询"""
        pid = storage.save_scanner_profile({
            "name": "测试方案",
            "conditions": [],
        })
        storage.save_scanner_results(pid, [
            {"inst_id": "BTC-USDT", "price": 65000, "matched_conditions": ["rsi(14)"]},
            {"inst_id": "ETH-USDT", "price": 3200, "matched_conditions": ["rsi(14)"]},
        ])

        results = storage.get_scanner_results(profile_id=pid)
        assert len(results) == 2
        assert results[0]["inst_id"] in ("BTC-USDT", "ETH-USDT")


# ==================== API 端点测试 ====================


class TestScannerAPI:
    """扫描器 API 测试"""

    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path, monkeypatch):
        db_path = tmp_path / "test_scanner_api.db"
        test_storage = DataStorage(db_path)

        # 写入测试 K 线数据
        from app.core.data_fetcher import Candle
        candles = []
        price = 100.0
        for i in range(50):
            import math as _m
            price = 100 + 10 * _m.sin(i * 0.2)
            candles.append(Candle(
                timestamp=1700000000000 + i * 3600000,
                open=price - 0.5,
                high=price + 1,
                low=price - 1,
                close=price,
                volume=1000 + i * 10,
                volume_ccy=0,
            ))
        test_storage.save_candles("TEST-USDT", "1H", candles, inst_type="SPOT")

        class FakeCtx:
            storage = test_storage

        monkeypatch.setattr("app.api.scanner.get_app_context", lambda: FakeCtx())
        self.client = TestClient(app)

    def test_get_conditions(self):
        """GET /api/scanner/conditions"""
        resp = self.client.get("/api/scanner/conditions")
        assert resp.status_code == 200
        data = resp.json()["data"]
        indicators = [c["indicator"] for c in data]
        assert "rsi" in indicators
        assert "sma_cross" in indicators

    def test_create_profile(self):
        """POST /api/scanner/profiles"""
        resp = self.client.post("/api/scanner/profiles", json={
            "name": "测试方案",
            "conditions": [
                {"indicator": "rsi", "operator": "lt", "value": 80},
            ],
            "timeframe": "1H",
        })
        assert resp.status_code == 200
        assert resp.json()["data"]["name"] == "测试方案"

    def test_list_profiles(self):
        """GET /api/scanner/profiles"""
        self.client.post("/api/scanner/profiles", json={
            "name": "方案A",
            "conditions": [{"indicator": "rsi", "operator": "lt", "value": 30}],
        })
        resp = self.client.get("/api/scanner/profiles")
        assert resp.status_code == 200
        assert len(resp.json()["data"]) >= 1

    def test_run_inline_scan(self):
        """POST /api/scanner/scan 即时扫描"""
        resp = self.client.post("/api/scanner/scan", json={
            "symbols": ["TEST-USDT"],
            "conditions": [
                {"indicator": "rsi", "operator": "lt", "value": 100},
            ],
            "timeframe": "1H",
            "inst_type": "SPOT",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["scanned"] == 1
        assert data["matched"] >= 0

    def test_run_profile_scan(self):
        """POST /api/scanner/scan/{id}"""
        create_resp = self.client.post("/api/scanner/profiles", json={
            "name": "执行测试",
            "conditions": [{"indicator": "rsi", "operator": "lt", "value": 100}],
            "symbols": ["TEST-USDT"],
        })
        pid = create_resp.json()["data"]["profile_id"]

        resp = self.client.post(f"/api/scanner/scan/{pid}")
        assert resp.status_code == 200
        assert resp.json()["scanned"] == 1

    def test_delete_profile(self):
        """DELETE /api/scanner/profiles/{id}"""
        create_resp = self.client.post("/api/scanner/profiles", json={
            "name": "待删除",
            "conditions": [],
        })
        pid = create_resp.json()["data"]["profile_id"]

        resp = self.client.delete(f"/api/scanner/profiles/{pid}")
        assert resp.status_code == 200
