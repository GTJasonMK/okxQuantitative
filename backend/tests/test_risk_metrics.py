# 风险指标功能测试
# 覆盖 risk_metrics 计算、storage 快照、API 端点

import math

import pytest
from fastapi.testclient import TestClient

from app.core.data_storage import DataStorage
from app.core.risk_metrics import (
    calculate_historical_var,
    calculate_max_drawdown,
    calculate_max_drawdown_series,
    calculate_parametric_var,
    calculate_returns,
    calculate_rolling_metrics,
    calculate_sharpe_ratio,
    calculate_sortino_ratio,
)
from app.main import app


# ==================== 风险计算测试 ====================


class TestRiskMetrics:
    """纯计算函数测试"""

    def test_calculate_returns(self):
        """收益率序列计算"""
        equities = [100, 110, 105, 120]
        returns = calculate_returns(equities)
        assert len(returns) == 3
        assert abs(returns[0] - 0.1) < 1e-10  # 100 -> 110 = +10%
        assert returns[1] < 0  # 110 -> 105 = 负
        assert returns[2] > 0  # 105 -> 120 = 正

    def test_calculate_returns_empty(self):
        """空序列返回空列表"""
        assert calculate_returns([]) == []
        assert calculate_returns([100]) == []

    def test_sharpe_ratio_positive(self):
        """正收益序列的夏普比率为正"""
        returns = [0.01, 0.02, 0.015, 0.01, 0.025, 0.01, 0.02, 0.015, 0.01, 0.02]
        sharpe = calculate_sharpe_ratio(returns)
        assert sharpe > 0

    def test_sharpe_ratio_insufficient_data(self):
        """数据不足返回 0"""
        assert calculate_sharpe_ratio([0.01]) == 0.0

    def test_sortino_ratio(self):
        """索提诺比率对正收益为正"""
        returns = [0.01, -0.005, 0.02, -0.003, 0.015, 0.01, -0.002, 0.025, 0.01, 0.02]
        sortino = calculate_sortino_ratio(returns)
        assert sortino > 0

    def test_sortino_no_negative(self):
        """全正收益序列的索提诺应为极大值"""
        returns = [0.01, 0.02, 0.015, 0.01, 0.025]
        sortino = calculate_sortino_ratio(returns)
        assert sortino == 9999.99  # safe_float 处理后的 inf

    def test_max_drawdown(self):
        """最大回撤计算精度"""
        equities = [100, 120, 90, 110, 80, 100]
        dd, dur = calculate_max_drawdown(equities)
        # 最大回撤: 120 -> 80 = 33.33%
        assert abs(dd - 33.33) < 0.1

    def test_max_drawdown_empty(self):
        assert calculate_max_drawdown([]) == (0.0, 0)

    def test_max_drawdown_series(self):
        """回撤时序数据结构"""
        equities = [100, 110, 105, 115]
        result = calculate_max_drawdown_series(equities)
        assert "drawdown_series" in result
        assert len(result["drawdown_series"]) == 4
        assert result["drawdown_series"][0] == 0  # 第一期无回撤
        assert result["peak"] == 115

    def test_historical_var(self):
        """历史 VaR 非负"""
        returns = [0.01, -0.02, 0.005, -0.03, 0.015, -0.01, 0.02, -0.025, 0.01, -0.015]
        var = calculate_historical_var(returns, confidence=0.95)
        assert var >= 0

    def test_historical_var_insufficient(self):
        """数据不足返回 0"""
        assert calculate_historical_var([0.01, 0.02]) == 0.0

    def test_parametric_var(self):
        """参数法 VaR"""
        returns = [0.01, -0.02, 0.005, -0.03, 0.015, -0.01, 0.02, -0.025, 0.01, -0.015]
        var = calculate_parametric_var(returns, confidence=0.95)
        assert var >= 0

    def test_rolling_metrics(self):
        """滚动指标结构"""
        returns = [0.01 * ((-1) ** i) for i in range(30)]
        result = calculate_rolling_metrics(returns, window=10)
        assert "rolling_sharpe" in result
        assert "rolling_volatility" in result
        assert "rolling_var_95" in result
        assert len(result["rolling_sharpe"]) == 30
        # 前 9 期应为 None（窗口不足）
        assert result["rolling_sharpe"][0] is None
        assert result["rolling_sharpe"][9] is not None


# ==================== 存储层测试 ====================


class TestStorageRisk:
    """风险快照存储测试"""

    @pytest.fixture
    def storage(self, tmp_path):
        db_path = tmp_path / "test_risk.db"
        return DataStorage(db_path)

    def test_save_and_get_snapshot(self, storage):
        """保存和读取权益快照"""
        storage.save_portfolio_snapshot(
            mode="simulated",
            date="2026-03-01",
            total_equity=10000,
            spot_value=6000,
            contract_value=3000,
            cash_value=1000,
        )
        snapshots = storage.get_portfolio_snapshots("simulated", days=30)
        assert len(snapshots) == 1
        assert snapshots[0]["total_equity"] == 10000
        assert snapshots[0]["date"] == "2026-03-01"

    def test_upsert_snapshot(self, storage):
        """同一日期更新快照"""
        storage.save_portfolio_snapshot(
            mode="simulated", date="2026-03-01", total_equity=10000
        )
        storage.save_portfolio_snapshot(
            mode="simulated", date="2026-03-01", total_equity=10500
        )
        snapshots = storage.get_portfolio_snapshots("simulated", days=30)
        assert len(snapshots) == 1
        assert snapshots[0]["total_equity"] == 10500

    def test_get_equities(self, storage):
        """获取权益序列"""
        for i, equity in enumerate([10000, 10100, 9900, 10200]):
            storage.save_portfolio_snapshot(
                mode="simulated",
                date=f"2026-03-{i+1:02d}",
                total_equity=equity,
            )
        equities = storage.get_portfolio_equities("simulated", days=30)
        assert equities == [10000, 10100, 9900, 10200]

    def test_mode_isolation(self, storage):
        """不同模式的快照隔离"""
        storage.save_portfolio_snapshot(
            mode="simulated", date="2026-03-01", total_equity=10000
        )
        storage.save_portfolio_snapshot(
            mode="live", date="2026-03-01", total_equity=50000
        )
        sim = storage.get_portfolio_equities("simulated")
        live = storage.get_portfolio_equities("live")
        assert sim == [10000]
        assert live == [50000]


# ==================== API 端点测试 ====================


class TestRiskAPI:
    """风险指标 API 测试"""

    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path, monkeypatch):
        db_path = tmp_path / "test_risk_api.db"
        test_storage = DataStorage(db_path)

        # 写入测试快照数据
        base_equity = 10000
        for i in range(30):
            delta = 50 * ((-1) ** i) + i * 10
            test_storage.save_portfolio_snapshot(
                mode="simulated",
                date=f"2026-03-{i+1:02d}",
                total_equity=base_equity + delta,
            )

        class FakeCtx:
            storage = test_storage

        monkeypatch.setattr("app.api.risk.get_app_context", lambda: FakeCtx())
        self.client = TestClient(app)

    def test_metrics_endpoint(self):
        """GET /api/risk/metrics 返回综合指标"""
        resp = self.client.get("/api/risk/metrics?mode=simulated&days=90")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["has_data"] is True
        assert "var_95" in data
        assert "sharpe_ratio" in data
        assert "max_drawdown" in data

    def test_var_endpoint(self):
        """GET /api/risk/var"""
        resp = self.client.get("/api/risk/var?mode=simulated&confidence=0.95")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "historical_var" in data
        assert "parametric_var" in data

    def test_drawdown_endpoint(self):
        """GET /api/risk/drawdown"""
        resp = self.client.get("/api/risk/drawdown?mode=simulated")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "drawdown_series" in data
        assert "equities" in data
        assert len(data["equities"]) == 30

    def test_rolling_endpoint(self):
        """GET /api/risk/rolling"""
        resp = self.client.get("/api/risk/rolling?mode=simulated&window=10")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "rolling_sharpe" in data
        assert "rolling_volatility" in data

    def test_snapshots_endpoint(self):
        """GET /api/risk/snapshots"""
        resp = self.client.get("/api/risk/snapshots?mode=simulated&days=30")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 30
