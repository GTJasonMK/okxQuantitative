# 蒙特卡洛模拟测试

import pytest

from app.backtest.monte_carlo import MonteCarloConfig, MonteCarloResult, MonteCarloSimulator


class TestMonteCarlo:
    """蒙特卡洛模拟器测试"""

    @pytest.fixture
    def simulator(self):
        return MonteCarloSimulator()

    def test_basic_simulation(self, simulator):
        """基本模拟输出结构正确"""
        pnls = [100, -50, 200, -30, 150, -80, 50, 120, -40, 60]
        config = MonteCarloConfig(num_simulations=500, seed=42)
        result = simulator.run(pnls, initial_capital=10000, config=config)

        assert isinstance(result, MonteCarloResult)
        assert result.num_simulations == 500
        assert result.original_final_equity > 0
        assert "50%" in result.equity_percentiles
        assert result.prob_profit >= 0
        assert result.prob_profit <= 1

    def test_all_positive_pnls(self, simulator):
        """全正盈亏序列的正收益概率接近 100%"""
        pnls = [100, 200, 150, 80, 120]
        config = MonteCarloConfig(num_simulations=200, seed=42)
        result = simulator.run(pnls, initial_capital=10000, config=config)

        assert result.prob_profit == 1.0
        assert result.mean_final_equity > 10000

    def test_all_negative_pnls(self, simulator):
        """全负盈亏序列的正收益概率为 0"""
        pnls = [-100, -200, -150, -80, -120]
        config = MonteCarloConfig(num_simulations=200, seed=42)
        result = simulator.run(pnls, initial_capital=10000, config=config)

        assert result.prob_profit == 0.0
        assert result.mean_final_equity < 10000

    def test_empty_pnls(self, simulator):
        """空序列返回初始资金"""
        config = MonteCarloConfig(num_simulations=100)
        result = simulator.run([], initial_capital=10000, config=config)

        assert result.num_simulations == 0
        assert result.original_final_equity == 10000

    def test_deterministic_with_seed(self, simulator):
        """相同 seed 产生相同结果"""
        pnls = [100, -50, 200, -30, 150]
        config = MonteCarloConfig(num_simulations=100, seed=123)

        result1 = simulator.run(pnls, initial_capital=10000, config=config)
        result2 = simulator.run(pnls, initial_capital=10000, config=config)

        assert result1.mean_final_equity == result2.mean_final_equity
        assert result1.equity_percentiles == result2.equity_percentiles

    def test_confidence_levels(self, simulator):
        """置信水平百分位数递增"""
        pnls = [100, -50, 200, -30, 150, -80, 50, 120, -40, 60]
        config = MonteCarloConfig(num_simulations=1000, seed=42)
        result = simulator.run(pnls, initial_capital=10000, config=config)

        pcts = result.equity_percentiles
        assert float(pcts["5%"]) <= float(pcts["50%"])
        assert float(pcts["50%"]) <= float(pcts["95%"])

    def test_max_drawdown_calculated(self, simulator):
        """最大回撤被正确计算"""
        pnls = [100, -300, 200]  # 权益: 10000, 10100, 9800, 10000
        config = MonteCarloConfig(num_simulations=100, seed=42)
        result = simulator.run(pnls, initial_capital=10000, config=config)

        assert result.original_max_drawdown > 0
        assert "50%" in result.drawdown_percentiles
