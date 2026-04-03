from typing import Any, Dict, List, Optional


class StorageBacktestMixin:
    def save_backtest_result(self, result_dict: Dict[str, Any], strategy_id: str = "", params: Dict[str, Any] = None) -> int:
        """
        保存回测结果到数据库

        Args:
            result_dict: BacktestResult.to_dict() 的返回值
            strategy_id: 策略ID
            params: 策略参数

        Returns:
            新记录的ID
        """
        import json

        # 提取详细数据（equity_curve和trades）单独存储为JSON
        detail_data = {
            "equity_curve": result_dict.get("equity_curve", []),
            "trades": result_dict.get("trades", []),
            "candles": result_dict.get("candles", []),
            "indicators": result_dict.get("indicators", {}),
            "sample_step": result_dict.get("sample_step", 1),
            "inst_type": result_dict.get("inst_type", "SPOT"),
        }
        detail_json = json.dumps(detail_data, ensure_ascii=False)
        params_json = json.dumps(params or {}, ensure_ascii=False)

        # 计算回测天数
        days = result_dict.get("duration_days", 0)

        query = """
            INSERT INTO backtest_results (
                strategy_name, strategy_id, symbol, inst_type, timeframe, days,
                start_time, end_time,
                initial_capital, final_capital,
                total_return, annual_return, max_drawdown,
                sharpe_ratio, sortino_ratio, calmar_ratio,
                win_rate, profit_factor,
                total_trades, winning_trades, losing_trades,
                avg_profit, avg_loss, largest_profit, largest_loss,
                total_commission,
                params_json, detail_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        with self._get_cursor() as cursor:
            cursor.execute(query, (
                result_dict.get("strategy_name", ""),
                strategy_id,
                result_dict.get("symbol", ""),
                result_dict.get("inst_type", "SPOT"),
                result_dict.get("timeframe", ""),
                days,
                result_dict.get("start_time", ""),
                result_dict.get("end_time", ""),
                result_dict.get("initial_capital", 0),
                result_dict.get("final_capital", 0),
                result_dict.get("total_return", 0),
                result_dict.get("annual_return", 0),
                result_dict.get("max_drawdown", 0),
                result_dict.get("sharpe_ratio", 0),
                result_dict.get("sortino_ratio", 0),
                result_dict.get("calmar_ratio", 0),
                result_dict.get("win_rate", 0),
                result_dict.get("profit_factor", 0),
                result_dict.get("total_trades", 0),
                result_dict.get("winning_trades", 0),
                result_dict.get("losing_trades", 0),
                result_dict.get("avg_profit", 0),
                result_dict.get("avg_loss", 0),
                result_dict.get("largest_profit", 0),
                result_dict.get("largest_loss", 0),
                result_dict.get("total_commission", 0),
                params_json,
                detail_json,
            ))
            return cursor.lastrowid

    def get_backtest_results(
        self,
        limit: int = 50,
        strategy_id: str = "",
        symbol: str = ""
    ) -> List[Dict[str, Any]]:
        """
        获取回测历史记录列表（不含详细数据）

        Args:
            limit: 返回数量限制
            strategy_id: 按策略ID过滤
            symbol: 按交易对过滤

        Returns:
            回测记录列表
        """
        query = """
            SELECT id, strategy_name, strategy_id, symbol, timeframe, days,
                   inst_type,
                   start_time, end_time, initial_capital, final_capital,
                   total_return, annual_return, max_drawdown,
                   sharpe_ratio, sortino_ratio, calmar_ratio,
                   win_rate, profit_factor,
                   total_trades, winning_trades, losing_trades,
                   avg_profit, avg_loss, largest_profit, largest_loss,
                   total_commission, params_json, created_at
            FROM backtest_results
            WHERE 1=1
        """
        params: List[Any] = []

        if strategy_id:
            query += " AND strategy_id = ?"
            params.append(strategy_id)
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        results = []
        with self._get_cursor() as cursor:
            cursor.execute(query, params)
            for row in cursor.fetchall():
                results.append({
                    "id": row["id"],
                    "strategy_name": row["strategy_name"],
                    "strategy_id": row["strategy_id"],
                    "symbol": row["symbol"],
                    "inst_type": row["inst_type"],
                    "timeframe": row["timeframe"],
                    "days": row["days"],
                    "start_time": row["start_time"],
                    "end_time": row["end_time"],
                    "initial_capital": row["initial_capital"],
                    "final_capital": row["final_capital"],
                    "total_return": row["total_return"],
                    "annual_return": row["annual_return"],
                    "max_drawdown": row["max_drawdown"],
                    "sharpe_ratio": row["sharpe_ratio"],
                    "sortino_ratio": row["sortino_ratio"],
                    "calmar_ratio": row["calmar_ratio"],
                    "win_rate": row["win_rate"],
                    "profit_factor": row["profit_factor"],
                    "total_trades": row["total_trades"],
                    "winning_trades": row["winning_trades"],
                    "losing_trades": row["losing_trades"],
                    "avg_profit": row["avg_profit"],
                    "avg_loss": row["avg_loss"],
                    "largest_profit": row["largest_profit"],
                    "largest_loss": row["largest_loss"],
                    "total_commission": row["total_commission"],
                    "params_json": row["params_json"],
                    "created_at": row["created_at"],
                })
        return results

    def get_backtest_result_detail(self, result_id: int) -> Optional[Dict[str, Any]]:
        """
        获取单条回测结果的完整数据（含equity_curve和trades）

        Args:
            result_id: 记录ID

        Returns:
            完整回测结果，或None
        """
        import json

        query = """
            SELECT id, strategy_name, strategy_id, symbol, timeframe, days,
                   inst_type,
                   start_time, end_time, initial_capital, final_capital,
                   total_return, annual_return, max_drawdown,
                   sharpe_ratio, sortino_ratio, calmar_ratio,
                   win_rate, profit_factor,
                   total_trades, winning_trades, losing_trades,
                   avg_profit, avg_loss, largest_profit, largest_loss,
                   total_commission, params_json, detail_json, created_at
            FROM backtest_results
            WHERE id = ?
        """

        with self._get_cursor() as cursor:
            cursor.execute(query, (result_id,))
            row = cursor.fetchone()
            if not row:
                return None

            result = {
                "id": row["id"],
                "strategy_name": row["strategy_name"],
                "strategy_id": row["strategy_id"],
                "symbol": row["symbol"],
                "inst_type": row["inst_type"],
                "timeframe": row["timeframe"],
                "days": row["days"],
                "start_time": row["start_time"],
                "end_time": row["end_time"],
                "initial_capital": row["initial_capital"],
                "final_capital": row["final_capital"],
                "total_return": row["total_return"],
                "annual_return": row["annual_return"],
                "max_drawdown": row["max_drawdown"],
                "sharpe_ratio": row["sharpe_ratio"],
                "sortino_ratio": row["sortino_ratio"],
                "calmar_ratio": row["calmar_ratio"],
                "win_rate": row["win_rate"],
                "profit_factor": row["profit_factor"],
                "total_trades": row["total_trades"],
                "winning_trades": row["winning_trades"],
                "losing_trades": row["losing_trades"],
                "avg_profit": row["avg_profit"],
                "avg_loss": row["avg_loss"],
                "largest_profit": row["largest_profit"],
                "largest_loss": row["largest_loss"],
                "total_commission": row["total_commission"],
                "created_at": row["created_at"],
            }

            # 解析JSON详细数据
            if row["detail_json"]:
                detail = json.loads(row["detail_json"])
                result["equity_curve"] = detail.get("equity_curve", [])
                result["trades"] = detail.get("trades", [])
                result["candles"] = detail.get("candles", [])
                result["indicators"] = detail.get("indicators", {})
                result["sample_step"] = detail.get("sample_step", 1)
                result["inst_type"] = detail.get("inst_type", result["inst_type"])

            if row["params_json"]:
                result["params"] = json.loads(row["params_json"])

            return result

    def delete_backtest_result(self, result_id: int) -> bool:
        """
        删除回测记录

        Args:
            result_id: 记录ID

        Returns:
            是否成功删除
        """
        query = "DELETE FROM backtest_results WHERE id = ?"
        with self._get_cursor() as cursor:
            cursor.execute(query, (result_id,))
            return cursor.rowcount > 0
