# 风险数据存储混入
# 持久化每日权益快照，用于 VaR 和滚动指标计算

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class StorageRiskMixin:
    """风险数据存储，管理投资组合每日快照。"""

    def save_portfolio_snapshot(
        self,
        mode: str,
        date: str,
        total_equity: float,
        spot_value: float = 0.0,
        contract_value: float = 0.0,
        cash_value: float = 0.0,
        positions: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        保存或更新某日的投资组合快照。

        Args:
            mode: 交易模式
            date: 日期 YYYY-MM-DD
            total_equity: 总权益
            spot_value: 现货持仓价值
            contract_value: 合约持仓价值
            cash_value: 现金价值
            positions: 各币种持仓明细
            metadata: 扩展数据
        """
        with self._get_cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO portfolio_snapshots
                    (mode, date, total_equity, spot_value, contract_value,
                     cash_value, positions_json, metadata_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(mode, date) DO UPDATE SET
                    total_equity = excluded.total_equity,
                    spot_value = excluded.spot_value,
                    contract_value = excluded.contract_value,
                    cash_value = excluded.cash_value,
                    positions_json = excluded.positions_json,
                    metadata_json = excluded.metadata_json
                """,
                (
                    mode,
                    date,
                    total_equity,
                    spot_value,
                    contract_value,
                    cash_value,
                    json.dumps(positions or {}, ensure_ascii=False),
                    json.dumps(metadata or {}, ensure_ascii=False),
                ),
            )
            return True

    def get_portfolio_snapshots(
        self,
        mode: str,
        days: int = 90,
    ) -> List[Dict[str, Any]]:
        """获取最近 N 天的权益快照。"""
        query = """
            SELECT * FROM portfolio_snapshots
            WHERE mode = ?
            ORDER BY date DESC
            LIMIT ?
        """
        rows: List[Dict[str, Any]] = []
        with self._get_cursor() as cursor:
            cursor.execute(query, (mode, days))
            for row in cursor.fetchall():
                rows.append({
                    "mode": row["mode"],
                    "date": row["date"],
                    "total_equity": row["total_equity"],
                    "spot_value": row["spot_value"],
                    "contract_value": row["contract_value"],
                    "cash_value": row["cash_value"],
                    "positions": json.loads(row["positions_json"] or "{}"),
                    "metadata": json.loads(row["metadata_json"] or "{}"),
                    "created_at": row["created_at"],
                })
        # 返回正序（从旧到新）
        rows.reverse()
        return rows

    def get_portfolio_equities(self, mode: str, days: int = 90) -> List[float]:
        """获取权益序列（浮点数列表），用于风险计算。"""
        snapshots = self.get_portfolio_snapshots(mode, days)
        return [s["total_equity"] for s in snapshots if s["total_equity"] > 0]
