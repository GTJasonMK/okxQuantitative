from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List


class StorageFillMixin:
    def save_fill(
        self,
        trade_id: str,
        inst_id: str,
        side: str,
        fill_px,
        fill_sz,
        ts: int,
        mode: str,
        fee=0,
        fee_ccy: str = "",
        source: str = "api"
    ) -> bool:
        """
        保存单条成交记录

        Args:
            trade_id: 成交ID（用于去重）
            inst_id: 交易对，如 BTC-USDT
            side: buy/sell
            fill_px: 成交价格（字符串或数字，内部保留原始精度）
            fill_sz: 成交数量（字符串或数字，内部保留原始精度）
            ts: 成交时间戳（毫秒）
            mode: simulated/live
            fee: 手续费（字符串或数字）
            fee_ccy: 手续费币种
            source: 数据来源 api/manual

        Returns:
            是否成功保存（重复记录返回False）
        """
        # 从交易对中提取币种（如 BTC-USDT -> BTC）
        ccy = inst_id.split("-")[0] if "-" in inst_id else inst_id

        query = """
            INSERT OR IGNORE INTO local_fills
            (trade_id, inst_id, ccy, side, fill_px, fill_sz, fee, fee_ccy, ts, mode, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        with self._get_cursor() as cursor:
            cursor.execute(query, (
                trade_id, inst_id, ccy, side, str(fill_px), str(fill_sz),
                str(fee), fee_ccy, ts, mode, source
            ))
            return cursor.rowcount > 0

    def save_fills_batch(self, fills: List[Dict[str, Any]], mode: str) -> int:
        """
        批量保存成交记录

        Args:
            fills: 成交记录列表
            mode: simulated/live

        Returns:
            新增记录数量
        """
        query = """
            INSERT OR IGNORE INTO local_fills
            (trade_id, inst_id, ccy, side, fill_px, fill_sz, fee, fee_ccy, ts, mode, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        new_count = 0
        with self._get_cursor() as cursor:
            for fill in fills:
                inst_id = fill.get("instId", fill.get("inst_id", ""))
                ccy = inst_id.split("-")[0] if "-" in inst_id else inst_id

                # trade_id 去重键：优先使用 tradeId，若为空则使用 billId
                # 若都为空，使用 (inst_id, ts, side, fill_px, fill_sz) 生成合成 ID
                trade_id = fill.get("tradeId", fill.get("trade_id", ""))
                if not trade_id:
                    trade_id = fill.get("billId", fill.get("bill_id", ""))
                if not trade_id:
                    # 最后兜底：生成合成 ID
                    ts = fill.get("ts", 0)
                    side = fill.get("side", "")
                    fill_px = fill.get("fillPx", fill.get("fill_px", "0"))
                    fill_sz = fill.get("fillSz", fill.get("fill_sz", "0"))
                    trade_id = f"synth_{inst_id}_{ts}_{side}_{fill_px}_{fill_sz}"
                    print(f"[DataStorage] 成交记录缺少 tradeId/billId，使用合成 ID: {trade_id}")

                side = fill.get("side", "")

                # 保留原始字符串精度，不转成 float
                fill_px = fill.get("fillPx", fill.get("fill_px", "0"))
                fill_sz = fill.get("fillSz", fill.get("fill_sz", "0"))

                # 按交易所返回的原始数据保存手续费，不区分买卖方向
                # 让成本计算逻辑自己根据 fee_ccy 判断如何处理
                fee = fill.get("fee", "0") or "0"
                fee_ccy = fill.get("feeCcy", fill.get("fee_ccy", ""))

                cursor.execute(query, (
                    trade_id,
                    inst_id,
                    ccy,
                    side,
                    fill_px,  # 保留原始字符串
                    fill_sz,  # 保留原始字符串
                    fee,      # 保留原始字符串
                    fee_ccy,
                    int(fill.get("ts", 0)),
                    mode,
                    "api"
                ))
                if cursor.rowcount > 0:
                    new_count += 1

        return new_count

    def rebuild_fills_table(self) -> bool:
        """
        重建 local_fills 和 cost_basis 表（用于修复精度问题）

        会删除所有现有数据，需要重新同步

        Returns:
            是否成功
        """
        print("[DataStorage] 重建数据表...")
        with self._get_cursor() as cursor:
            # 删除旧表
            cursor.execute("DROP TABLE IF EXISTS local_fills")
            cursor.execute("DROP TABLE IF EXISTS cost_basis")

            # 重新创建 local_fills（使用 TEXT 类型保持精度）
            cursor.execute("""
                CREATE TABLE local_fills (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_id TEXT,
                    inst_id TEXT NOT NULL,
                    ccy TEXT NOT NULL,
                    side TEXT NOT NULL,
                    fill_px TEXT NOT NULL,
                    fill_sz TEXT NOT NULL,
                    fee TEXT DEFAULT '0',
                    fee_ccy TEXT,
                    ts INTEGER NOT NULL,
                    mode TEXT NOT NULL,
                    source TEXT DEFAULT 'api',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(trade_id, mode)
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_fills_ccy_mode
                ON local_fills(ccy, mode)
            """)

            # 重新创建 cost_basis（使用 TEXT 类型保持精度）
            cursor.execute("""
                CREATE TABLE cost_basis (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ccy TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    avg_cost TEXT NOT NULL,
                    total_qty TEXT NOT NULL,
                    total_cost TEXT NOT NULL,
                    total_fee TEXT NOT NULL DEFAULT '0',
                    total_buy_cost TEXT NOT NULL DEFAULT '0',
                    total_sell_revenue TEXT NOT NULL DEFAULT '0',
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(ccy, mode)
                )
            """)

        print("[DataStorage] 数据表重建完成，请重新同步成交记录")
        return True

    def get_fills(
        self,
        mode: str,
        ccy: str = "",
        inst_id: str = "",
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        获取本地成交记录

        Args:
            mode: simulated/live
            ccy: 币种过滤（可选）
            inst_id: 交易对过滤（可选，如 BTC-USDT）
            limit: 返回数量限制

        Returns:
            成交记录列表
        """
        # 构建动态查询条件
        conditions = ["mode = ?"]
        params = [mode]

        if inst_id:
            # inst_id 过滤优先级高于 ccy
            conditions.append("inst_id = ?")
            params.append(inst_id)
        elif ccy:
            conditions.append("ccy = ?")
            params.append(ccy)

        params.append(limit)

        query = f"""
            SELECT * FROM local_fills
            WHERE {" AND ".join(conditions)}
            ORDER BY ts DESC
            LIMIT ?
        """

        fills = []
        with self._get_cursor() as cursor:
            cursor.execute(query, params)
            for row in cursor.fetchall():
                fills.append({
                    "trade_id": row["trade_id"],
                    "inst_id": row["inst_id"],
                    "ccy": row["ccy"],
                    "side": row["side"],
                    "fill_px": row["fill_px"],
                    "fill_sz": row["fill_sz"],
                    "fee": row["fee"],
                    "fee_ccy": row["fee_ccy"],
                    "ts": row["ts"],
                    "source": row["source"],
                })
        return fills

    def get_fills_count(self, mode: str) -> int:
        """获取成交记录总数"""
        query = "SELECT COUNT(*) as cnt FROM local_fills WHERE mode = ?"
        with self._get_cursor() as cursor:
            cursor.execute(query, (mode,))
            row = cursor.fetchone()
            return row["cnt"] if row else 0

    def _build_realized_trade_records(
        self,
        mode: str,
        inst_id: str = "",
    ) -> List[Dict[str, Any]]:
        """
        基于本地成交记录构建“已平仓成交”的绩效序列。

        说明：
        - 采用移动平均成本法估算每笔卖出的已实现盈亏
        - 结果主要用于本地绩效统计与日报/月报，不影响真实账务
        """
        conditions = ["mode = ?"]
        params: List[Any] = [mode]
        if inst_id:
            conditions.append("inst_id = ?")
            params.append(inst_id)

        query = f"""
            SELECT inst_id, ccy, side, fill_px, fill_sz, fee, fee_ccy, ts
            FROM local_fills
            WHERE {" AND ".join(conditions)}
            ORDER BY ts ASC, id ASC
        """

        positions: Dict[str, Dict[str, Decimal]] = {}
        trades: List[Dict[str, Any]] = []

        with self._get_cursor() as cursor:
            cursor.execute(query, params)
            for row in cursor.fetchall():
                trade_inst_id = row["inst_id"]
                base_ccy = row["ccy"]
                side = (row["side"] or "").lower()
                price = Decimal(str(row["fill_px"] or "0"))
                size = Decimal(str(row["fill_sz"] or "0"))
                fee = abs(Decimal(str(row["fee"] or "0")))
                fee_ccy = row["fee_ccy"] or ""
                ts = int(row["ts"] or 0)

                if price <= 0 or size <= 0:
                    continue

                position = positions.setdefault(trade_inst_id, {
                    "qty": Decimal("0"),
                    "cost": Decimal("0"),
                })

                if side == "buy":
                    actual_qty = size
                    total_cost = price * size
                    if fee_ccy == base_ccy:
                        actual_qty = max(Decimal("0"), size - fee)
                    elif fee_ccy in ("", "USDT"):
                        total_cost += fee

                    position["qty"] += actual_qty
                    position["cost"] += total_cost
                    continue

                if side != "sell":
                    continue

                if position["qty"] <= 0:
                    continue

                avg_cost = position["cost"] / position["qty"] if position["qty"] > 0 else Decimal("0")
                extra_fee_qty = fee if fee_ccy == base_ccy else Decimal("0")
                removable_qty = size + extra_fee_qty
                removable_qty = min(removable_qty, position["qty"])

                if removable_qty <= 0:
                    continue

                cost_basis = avg_cost * removable_qty
                proceeds = price * size
                fee_usdt = Decimal("0")
                if fee_ccy in ("", "USDT"):
                    fee_usdt = fee
                elif fee_ccy == base_ccy:
                    fee_usdt = fee * price

                net_proceeds = proceeds - fee_usdt
                realized_pnl = net_proceeds - cost_basis
                return_pct = (realized_pnl / cost_basis * Decimal("100")) if cost_basis > 0 else Decimal("0")

                position["qty"] = max(Decimal("0"), position["qty"] - removable_qty)
                position["cost"] = max(Decimal("0"), position["cost"] - cost_basis)
                if position["qty"] == 0:
                    position["cost"] = Decimal("0")

                trades.append({
                    "inst_id": trade_inst_id,
                    "ccy": base_ccy,
                    "side": side,
                    "fill_px": float(price),
                    "fill_sz": float(size),
                    "fee": float(fee),
                    "fee_ccy": fee_ccy,
                    "cost_basis": float(cost_basis),
                    "turnover": float(proceeds),
                    "realized_pnl": float(realized_pnl),
                    "return_pct": float(return_pct),
                    "ts": ts,
                    "date": datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d"),
                    "month": datetime.fromtimestamp(ts / 1000).strftime("%Y-%m"),
                })

        return trades

    def get_trade_performance(
        self,
        mode: str,
        inst_id: str = "",
        group_by: str = "day",
    ) -> Dict[str, Any]:
        """
        获取本地成交绩效统计。

        Returns:
            {
              "summary": {...},
              "periods": [...],
              "recent_trades": [...]
            }
        """
        trades = self._build_realized_trade_records(mode=mode, inst_id=inst_id)
        group_key = "month" if group_by == "month" else "date"

        gross_profit = Decimal("0")
        gross_loss = Decimal("0")
        total_pnl = Decimal("0")
        cumulative_pnl = Decimal("0")
        peak_pnl = Decimal("0")
        max_drawdown_amount = Decimal("0")
        wins = 0
        losses = 0
        total_trades = len(trades)
        max_win = Decimal("0")
        max_loss = Decimal("0")
        period_map: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "period": "",
            "realized_pnl": Decimal("0"),
            "turnover": Decimal("0"),
            "trade_count": 0,
            "winning_trades": 0,
            "losing_trades": 0,
        })

        for trade in trades:
            pnl = Decimal(str(trade["realized_pnl"]))
            turnover = Decimal(str(trade["turnover"]))
            total_pnl += pnl
            cumulative_pnl += pnl
            peak_pnl = max(peak_pnl, cumulative_pnl)
            max_drawdown_amount = max(max_drawdown_amount, peak_pnl - cumulative_pnl)

            max_win = max(max_win, pnl)
            max_loss = min(max_loss, pnl)

            if pnl >= 0:
                wins += 1
                gross_profit += pnl
            else:
                losses += 1
                gross_loss += pnl

            key = trade[group_key]
            bucket = period_map[key]
            bucket["period"] = key
            bucket["realized_pnl"] += pnl
            bucket["turnover"] += turnover
            bucket["trade_count"] += 1
            if pnl >= 0:
                bucket["winning_trades"] += 1
            else:
                bucket["losing_trades"] += 1

        avg_win = gross_profit / wins if wins else Decimal("0")
        avg_loss = gross_loss / losses if losses else Decimal("0")
        profit_factor = float(gross_profit / abs(gross_loss)) if gross_loss < 0 else 0.0
        pnl_ratio = float(avg_win / abs(avg_loss)) if avg_loss < 0 else 0.0
        max_drawdown_pct = float(max_drawdown_amount / peak_pnl * Decimal("100")) if peak_pnl > 0 else 0.0

        periods = []
        for period in period_map.values():
            trade_count = period["trade_count"]
            win_rate = float(period["winning_trades"] / trade_count * 100) if trade_count else 0.0
            periods.append({
                "period": period["period"],
                "realized_pnl": round(float(period["realized_pnl"]), 2),
                "turnover": round(float(period["turnover"]), 2),
                "trade_count": trade_count,
                "winning_trades": period["winning_trades"],
                "losing_trades": period["losing_trades"],
                "win_rate": round(win_rate, 2),
            })

        periods.sort(key=lambda item: item["period"], reverse=True)

        summary = {
            "mode": mode,
            "inst_id": inst_id,
            "group_by": "month" if group_by == "month" else "day",
            "trade_count": total_trades,
            "winning_trades": wins,
            "losing_trades": losses,
            "win_rate": round(float(wins / total_trades * 100), 2) if total_trades else 0.0,
            "realized_pnl": round(float(total_pnl), 2),
            "gross_profit": round(float(gross_profit), 2),
            "gross_loss": round(float(gross_loss), 2),
            "profit_factor": round(profit_factor, 2),
            "profit_loss_ratio": round(pnl_ratio, 2),
            "avg_win": round(float(avg_win), 2),
            "avg_loss": round(float(avg_loss), 2),
            "max_win": round(float(max_win), 2),
            "max_loss": round(float(max_loss), 2),
            "max_drawdown_amount": round(float(max_drawdown_amount), 2),
            "max_drawdown_pct": round(max_drawdown_pct, 2),
        }

        recent_trades = list(reversed(trades[-20:]))

        return {
            "summary": summary,
            "periods": periods,
            "recent_trades": recent_trades,
        }

    def calculate_cost_basis(self, mode: str) -> Dict[str, Dict[str, float]]:
        """
        从成交记录计算每个币种的成本基础

        计算逻辑（净成本法）：
        - 净成本 = 总买入花费 - 总卖出收入
        - 当前持仓数量 = 总买入数量 - 总卖出数量
        - 盈亏 = 当前市值 - 净成本

        如果净成本为负，说明已经"回本有余"，剩余持仓是纯利润。

        OKX手续费规则：
        - 买入时：手续费从买到的币中扣（feeCcy=基础货币），实际得到数量减少
        - 卖出时：不收手续费

        Args:
            mode: simulated/live

        Returns:
            {ccy: {avg_cost, total_qty, total_cost, total_fee, total_buy_cost, total_sell_revenue}}
        """
        # 获取所有记录，按时间排序
        query = """
            SELECT ccy, side, fill_px, fill_sz, fee, fee_ccy
            FROM local_fills
            WHERE mode = ?
            ORDER BY ts ASC
        """

        # 用于累计每个币种的数据（使用 Decimal 精确计算）
        positions: Dict[str, Dict[str, Decimal]] = {}

        print(f"[DataStorage] 开始计算成本基础 mode={mode}，使用净成本法")

        with self._get_cursor() as cursor:
            cursor.execute(query, (mode,))
            for row in cursor.fetchall():
                ccy = row["ccy"]
                side = row["side"]
                # 从数据库读取时转为 Decimal，保持精度
                price = Decimal(str(row["fill_px"]))
                size = Decimal(str(row["fill_sz"]))
                fee = Decimal(str(row["fee"] or 0))
                fee_ccy = row["fee_ccy"] or ""

                if ccy not in positions:
                    positions[ccy] = {
                        "total_buy_cost": Decimal("0"),     # 总买入花费（USDT）
                        "total_buy_qty": Decimal("0"),      # 总买入数量
                        "total_sell_revenue": Decimal("0"), # 总卖出收入（USDT）
                        "total_sell_qty": Decimal("0"),     # 总卖出数量
                        "total_fee": Decimal("0"),          # 总手续费
                    }

                pos = positions[ccy]
                fee_abs = abs(fee)

                if side == "buy":
                    # 买入：花费 USDT 换取币
                    buy_cost = price * size  # 花费的 USDT（不含手续费）

                    # 根据手续费币种确定实际得到的数量和手续费 USDT 等值
                    if fee_ccy == ccy:
                        # 手续费以基础币计，从买到的币中扣，实际得到数量减少
                        actual_qty = size - fee_abs
                        fee_usdt = fee_abs * price
                        # 手续费不额外增加 USDT 支出
                        total_cost = buy_cost
                    elif fee_ccy == "USDT" or fee_ccy == "":
                        # 手续费以 USDT 计，额外的 USDT 支出
                        actual_qty = size
                        fee_usdt = fee_abs
                        # 总成本 = 买币花费 + USDT 手续费
                        total_cost = buy_cost + fee_usdt
                    else:
                        # 手续费以第三方币计（如 OKB），不影响 USDT 或基础币数量
                        actual_qty = size
                        fee_usdt = fee_abs  # 近似为 USDT（口径说明）
                        total_cost = buy_cost

                    pos["total_buy_cost"] += total_cost
                    pos["total_buy_qty"] += actual_qty
                    pos["total_fee"] += fee_usdt

                    print(f"  [BUY] {ccy}: {size} @ {price}, cost={total_cost} USDT, "
                          f"actual_qty={actual_qty}, fee={fee_usdt} (fee_ccy={fee_ccy})")

                elif side == "sell":
                    # 卖出：卖出币换取 USDT
                    sell_revenue = price * size  # 毛收入（不含手续费）

                    # 根据手续费币种计算净收入
                    if fee_ccy == "USDT" or fee_ccy == "":
                        # 手续费以 USDT 计，从卖出收入中扣除
                        fee_usdt = fee_abs
                        actual_revenue = sell_revenue - fee_usdt
                    elif fee_ccy == ccy:
                        # 手续费以基础币计（少见），折算为 USDT 并从收入扣除
                        fee_usdt = fee_abs * price
                        actual_revenue = sell_revenue - fee_usdt
                    else:
                        # 手续费以第三方币计，不影响 USDT 收入
                        fee_usdt = fee_abs  # 近似
                        actual_revenue = sell_revenue

                    pos["total_sell_revenue"] += actual_revenue
                    pos["total_sell_qty"] += size
                    pos["total_fee"] += fee_usdt

                    print(f"  [SELL] {ccy}: {size} @ {price}, gross={sell_revenue} USDT, "
                          f"fee={fee_usdt}, net_revenue={actual_revenue} USDT (fee_ccy={fee_ccy})")

        # 计算最终结果
        print(f"[DataStorage] 成本计算结果:")
        result: Dict[str, Dict[str, float]] = {}

        for ccy, data in positions.items():
            # 当前持仓数量
            current_qty = data["total_buy_qty"] - data["total_sell_qty"]
            current_qty = max(current_qty, Decimal("0"))

            # 净成本 = 总买入 - 总卖出
            net_cost = data["total_buy_cost"] - data["total_sell_revenue"]

            # 平均买入价（参考值）
            if data["total_buy_qty"] > 0:
                avg_buy_price = data["total_buy_cost"] / data["total_buy_qty"]
            else:
                avg_buy_price = Decimal("0")

            print(f"  {ccy}: buy={data['total_buy_cost']} USDT for {data['total_buy_qty']}, "
                  f"sell={data['total_sell_revenue']} USDT for {data['total_sell_qty']}, "
                  f"current_qty={current_qty}, net_cost={net_cost}, avg_buy={avg_buy_price}")

            result[ccy] = {
                "total_qty": float(current_qty),                    # 当前持仓数量
                "total_cost": float(net_cost),                      # 净成本（可能为负）
                "avg_cost": float(avg_buy_price),                   # 平均买入价
                "total_fee": float(data["total_fee"]),              # 总手续费
                "total_buy_cost": float(data["total_buy_cost"]),    # 总买入花费
                "total_sell_revenue": float(data["total_sell_revenue"]),  # 总卖出收入
            }

        return result

    def get_cost_basis(self, mode: str, ccy: str = "") -> Dict[str, Dict[str, float]]:
        """
        获取成本基础

        Args:
            mode: simulated/live
            ccy: 指定币种（可选）

        Returns:
            成本基础数据
        """
        if ccy:
            query = """
                SELECT ccy, avg_cost, total_qty, total_cost, total_fee, total_buy_cost, total_sell_revenue
                FROM cost_basis
                WHERE mode = ? AND ccy = ?
            """
            params = (mode, ccy)
        else:
            query = """
                SELECT ccy, avg_cost, total_qty, total_cost, total_fee, total_buy_cost, total_sell_revenue
                FROM cost_basis
                WHERE mode = ?
            """
            params = (mode,)

        result = {}
        with self._get_cursor() as cursor:
            cursor.execute(query, params)
            for row in cursor.fetchall():
                result[row["ccy"]] = {
                    "avg_cost": float(row["avg_cost"]),
                    "total_qty": float(row["total_qty"]),
                    "total_cost": float(row["total_cost"]),
                    "total_fee": float(row["total_fee"]) if row["total_fee"] else 0,
                    "total_buy_cost": float(row["total_buy_cost"]) if row["total_buy_cost"] else 0,
                    "total_sell_revenue": float(row["total_sell_revenue"]) if row["total_sell_revenue"] else 0,
                }
        return result

    def save_cost_basis(
        self,
        ccy: str,
        mode: str,
        avg_cost: float,
        total_qty: float = 0,
        total_cost: float = 0,
        total_fee: float = 0,
        total_buy_cost: float = 0,
        total_sell_revenue: float = 0
    ) -> bool:
        """
        保存或更新成本基础

        Args:
            ccy: 币种
            mode: simulated/live
            avg_cost: 平均买入价
            total_qty: 当前持仓数量
            total_cost: 净成本
            total_fee: 总手续费
            total_buy_cost: 总买入花费
            total_sell_revenue: 总卖出收入

        Returns:
            是否成功
        """
        query = """
            INSERT INTO cost_basis (ccy, mode, avg_cost, total_qty, total_cost, total_fee,
                                    total_buy_cost, total_sell_revenue, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(ccy, mode) DO UPDATE SET
                avg_cost = excluded.avg_cost,
                total_qty = excluded.total_qty,
                total_cost = excluded.total_cost,
                total_fee = excluded.total_fee,
                total_buy_cost = excluded.total_buy_cost,
                total_sell_revenue = excluded.total_sell_revenue,
                last_updated = CURRENT_TIMESTAMP
        """

        with self._get_cursor() as cursor:
            cursor.execute(query, (ccy, mode, avg_cost, total_qty, total_cost, total_fee,
                                   total_buy_cost, total_sell_revenue))
            return True

    def update_cost_basis_from_fills(self, mode: str) -> Dict[str, Dict[str, float]]:
        """
        从成交记录重新计算并更新成本基础

        Args:
            mode: simulated/live

        Returns:
            更新后的成本基础数据
        """
        # 计算成本基础
        positions = self.calculate_cost_basis(mode)

        # 保存到数据库
        for ccy, data in positions.items():
            if data["total_qty"] > 0 or data.get("total_buy_cost", 0) > 0:
                self.save_cost_basis(
                    ccy=ccy,
                    mode=mode,
                    avg_cost=data["avg_cost"],
                    total_qty=data["total_qty"],
                    total_cost=data["total_cost"],
                    total_fee=data.get("total_fee", 0),
                    total_buy_cost=data.get("total_buy_cost", 0),
                    total_sell_revenue=data.get("total_sell_revenue", 0)
                )

        return positions

