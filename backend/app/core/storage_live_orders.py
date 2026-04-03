from typing import Any, Dict, List


class StorageLiveOrderMixin:
    def save_live_order(
        self,
        *,
        order_id: str,
        inst_id: str,
        side: str,
        size: str,
        price: str,
        signal_type: str,
        success: bool,
        ts: str,
        client_order_id: str = "",
        mode: str = "simulated",
        strategy_id: str = "",
        strategy_name: str = "",
        error_message: str = ""
    ) -> bool:
        """
        保存实时交易订单记录

        Args:
            order_id: 订单ID
            inst_id: 交易对
            side: 方向
            size: 数量
            price: 价格
            signal_type: 信号类型
            success: 是否成功
            ts: 时间戳
            strategy_id: 策略ID
            strategy_name: 策略名称
            error_message: 错误信息

        Returns:
            是否成功保存
        """
        query = """
            INSERT INTO live_order_records
            (order_id, client_order_id, inst_id, side, size, price, signal_type, success,
             error_message, mode, strategy_id, strategy_name, ts)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        with self._get_cursor() as cursor:
            cursor.execute(query, (
                order_id, client_order_id, inst_id, side, size, price, signal_type,
                1 if success else 0, error_message,
                mode, strategy_id, strategy_name, ts
            ))
            return cursor.rowcount > 0

    def get_live_orders(
        self,
        limit: int = 50,
        mode: str = "",
        strategy_id: str = ""
    ) -> List[Dict[str, Any]]:
        """
        获取实时交易订单记录

        Args:
            limit: 返回数量限制
            strategy_id: 按策略ID过滤

        Returns:
            订单记录列表
        """
        conditions = []
        params: List[Any] = []

        if strategy_id:
            conditions.append("strategy_id = ?")
            params.append(strategy_id)
        if mode:
            conditions.append("mode = ?")
            params.append(mode)

        query = "SELECT * FROM live_order_records"
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY ts DESC LIMIT ?"
        params.append(limit)

        orders = []
        with self._get_cursor() as cursor:
            cursor.execute(query, params)
            for row in cursor.fetchall():
                orders.append({
                    "id": row["id"],
                    "order_id": row["order_id"],
                    "client_order_id": row["client_order_id"] if "client_order_id" in row.keys() else "",
                    "inst_id": row["inst_id"],
                    "side": row["side"],
                    "size": row["size"],
                    "price": row["price"],
                    "signal_type": row["signal_type"],
                    "success": bool(row["success"]),
                    "error_message": row["error_message"],
                    "mode": row["mode"] if "mode" in row.keys() else "",
                    "strategy_id": row["strategy_id"],
                    "strategy_name": row["strategy_name"],
                    "timestamp": row["ts"],
                })
        return orders

    def get_unreconciled_live_orders(
        self,
        mode: str,
        inst_id: str = "",
        strategy_id: str = "",
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        """
        获取待补偿同步的实时订单记录。

        判定规则：success=1 且 error_message 含“补偿同步”但不含“完成”。
        """
        query = """
            SELECT * FROM live_order_records
            WHERE success = 1
              AND mode = ?
              AND error_message LIKE '%补偿同步%'
              AND error_message NOT LIKE '%补偿同步完成%'
        """
        params: List[Any] = [mode]

        if inst_id:
            query += " AND inst_id = ?"
            params.append(inst_id)
        if strategy_id:
            query += " AND strategy_id = ?"
            params.append(strategy_id)

        query += " ORDER BY ts DESC LIMIT ?"
        params.append(limit)

        rows: List[Dict[str, Any]] = []
        with self._get_cursor() as cursor:
            cursor.execute(query, tuple(params))
            for row in cursor.fetchall():
                rows.append({
                    "id": row["id"],
                    "order_id": row["order_id"],
                    "client_order_id": row["client_order_id"] if "client_order_id" in row.keys() else "",
                    "inst_id": row["inst_id"],
                    "side": row["side"],
                    "size": row["size"],
                    "price": row["price"],
                    "signal_type": row["signal_type"],
                    "success": bool(row["success"]),
                    "error_message": row["error_message"],
                    "mode": row["mode"] if "mode" in row.keys() else "",
                    "strategy_id": row["strategy_id"],
                    "strategy_name": row["strategy_name"],
                    "timestamp": row["ts"],
                })
        return rows

    def update_live_order_execution(
        self,
        *,
        size: str,
        price: str,
        order_id: str = "",
        client_order_id: str = "",
        mode: str = "",
        error_message: str = "",
    ) -> bool:
        """
        更新实时订单的执行结果（补偿同步场景）。

        Args:
            order_id: 订单ID（与 client_order_id 至少传一个）
            client_order_id: 客户端订单ID
            mode: simulated/live
            size: 累计成交数量
            price: 最新成交均价
            error_message: 补充说明

        Returns:
            是否成功更新
        """
        if not order_id and not client_order_id:
            return False

        query = "UPDATE live_order_records SET size = ?, price = ?, error_message = ? WHERE "
        params: List[Any] = [size, price, error_message]

        if order_id:
            query += "order_id = ?"
            params.append(order_id)
        else:
            query += "client_order_id = ?"
            params.append(client_order_id)

        if mode:
            query += " AND mode = ?"
            params.append(mode)

        with self._get_cursor() as cursor:
            cursor.execute(query, tuple(params))
            return cursor.rowcount > 0

    def close(self):
        """关闭数据库连接"""
        if hasattr(self._local, "connection") and self._local.connection:
            self._local.connection.close()
            self._local.connection = None
