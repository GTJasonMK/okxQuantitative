# 持仓计算（复用模块）
#
# 目标：
# - 把“现货持仓 + 成本基础 + 行情”的聚合逻辑从 API 层抽离为可复用的纯函数
# - 让同一套计算可以被 REST / WS / 脚本 / 单测复用

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple


# 稳定币：默认不参与盈亏计算（视为锚定 1 USDT）
STABLECOINS = {"USDT", "USDC", "DAI", "BUSD", "TUSD", "USDP"}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def build_holdings_base(
    *,
    balance_details: Iterable[Mapping[str, Any]],
    cost_data: Mapping[str, Mapping[str, Any]],
    stablecoins: Optional[set[str]] = None,
) -> List[Dict[str, Any]]:
    """
    构建“持仓基础数据”（不含行情）

    返回字段对齐 `/api/trading/holdings-base` 既有输出，便于前端复用。
    """
    stables = stablecoins or STABLECOINS
    holdings: List[Dict[str, Any]] = []

    for d in balance_details:
        ccy = (d.get("ccy", "") or "").upper()
        if not ccy:
            continue

        avail_bal = _safe_float(d.get("availBal", 0))
        frozen_bal = _safe_float(d.get("frozenBal", 0))
        total_bal = avail_bal + frozen_bal
        if total_bal <= 0:
            continue

        is_stablecoin = ccy in stables

        ccy_cost = cost_data.get(ccy)
        if ccy_cost and _safe_float(ccy_cost.get("avg_cost", 0)) > 0:
            avg_cost = _safe_float(ccy_cost.get("avg_cost", 0))
            total_cost = _safe_float(ccy_cost.get("total_cost", 0))
            total_fee = _safe_float(ccy_cost.get("total_fee", 0))
        else:
            avg_cost = None
            total_cost = None
            total_fee = None

        holdings.append(
            {
                "ccy": ccy,
                "total": str(total_bal),
                "available": str(avail_bal),
                "frozen": str(frozen_bal),
                "avg_cost": str(round(avg_cost, 6)) if avg_cost is not None else None,
                "total_cost": str(round(total_cost, 2)) if total_cost is not None else None,
                "total_fee": str(round(total_fee, 4)) if total_fee is not None else None,
                "is_stablecoin": is_stablecoin,
            }
        )

    # 按币种排序（稳定币在前）
    holdings.sort(key=lambda x: (not x["is_stablecoin"], x["ccy"]))
    return holdings


def build_spot_holdings(
    *,
    balance_details: Iterable[Mapping[str, Any]],
    tickers: Mapping[str, Any],
    cost_data: Mapping[str, Mapping[str, Any]],
    stablecoins: Optional[set[str]] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    """
    构建“现货持仓展示数据”（含行情与盈亏汇总）

    返回：
    - holdings: 列表（字段对齐 `/api/trading/spot-holdings` 既有输出）
    - totals: 汇总字段（字符串化，保持向后兼容）
    """
    stables = stablecoins or STABLECOINS

    holdings: List[Dict[str, Any]] = []
    total_value_usdt = 0.0
    total_cost_usdt = 0.0
    total_value_with_cost = 0.0
    total_fee_usdt = 0.0

    for d in balance_details:
        ccy = (d.get("ccy", "") or "").upper()
        if not ccy:
            continue

        avail_bal = _safe_float(d.get("availBal", 0))
        frozen_bal = _safe_float(d.get("frozenBal", 0))
        total_bal = avail_bal + frozen_bal

        if total_bal <= 0:
            continue

        # 稳定币单独处理（不参与盈亏计算）
        if ccy in stables:
            holdings.append(
                {
                    "ccy": ccy,
                    "total": str(total_bal),
                    "available": str(avail_bal),
                    "frozen": str(frozen_bal),
                    "price_usdt": "1.0",
                    "value_usdt": str(round(total_bal, 2)),
                    "avg_cost": "-",
                    "cost_total": "-",
                    "fee_total": "-",
                    "pnl_usdt": "-",
                    "pnl_percent": "-",
                    "is_stablecoin": True,
                }
            )
            total_value_usdt += total_bal
            continue

        inst_id = f"{ccy}-USDT"
        ticker = tickers.get(inst_id)

        if ticker:
            price = _safe_float(getattr(ticker, "last", None))
            value = total_bal * price

            ccy_cost = cost_data.get(ccy)
            if ccy_cost and _safe_float(ccy_cost.get("avg_cost", 0)) > 0:
                avg_cost = _safe_float(ccy_cost.get("avg_cost", 0))
                cost_total = _safe_float(ccy_cost.get("total_cost", 0))
                fee_total = _safe_float(ccy_cost.get("total_fee", 0))

                pnl_usdt = value - cost_total
                pnl_percent = ((price - avg_cost) / avg_cost * 100) if avg_cost > 0 else 0.0

                total_cost_usdt += cost_total
                total_value_with_cost += value
                total_fee_usdt += fee_total
            else:
                avg_cost = None
                cost_total = None
                fee_total = None
                pnl_usdt = None
                pnl_percent = None

            holdings.append(
                {
                    "ccy": ccy,
                    "total": str(total_bal),
                    "available": str(avail_bal),
                    "frozen": str(frozen_bal),
                    "price_usdt": str(round(price, 4)),
                    "value_usdt": str(round(value, 2)),
                    "avg_cost": str(round(avg_cost, 4)) if avg_cost is not None else "-",
                    "cost_total": str(round(cost_total, 2)) if cost_total is not None else "-",
                    "fee_total": str(round(fee_total, 2)) if fee_total is not None else "-",
                    "pnl_usdt": str(round(pnl_usdt, 2)) if pnl_usdt is not None else "-",
                    "pnl_percent": str(round(pnl_percent, 2)) if pnl_percent is not None else "-",
                    "is_stablecoin": False,
                }
            )
            total_value_usdt += value
        else:
            holdings.append(
                {
                    "ccy": ccy,
                    "total": str(total_bal),
                    "available": str(avail_bal),
                    "frozen": str(frozen_bal),
                    "price_usdt": "-",
                    "value_usdt": "-",
                    "avg_cost": "-",
                    "cost_total": "-",
                    "fee_total": "-",
                    "pnl_usdt": "-",
                    "pnl_percent": "-",
                    "is_stablecoin": False,
                }
            )

    # 按市值排序（稳定币在前，其他按市值降序）
    holdings.sort(
        key=lambda x: (
            not x["is_stablecoin"],
            -_safe_float(x["value_usdt"]) if x["value_usdt"] != "-" else 0,
        )
    )

    if total_cost_usdt > 0:
        total_pnl_usdt = total_value_with_cost - total_cost_usdt
        total_pnl_percent = (total_pnl_usdt / total_cost_usdt * 100)
    else:
        total_pnl_usdt = 0.0
        total_pnl_percent = 0.0

    totals = {
        "total_value_usdt": str(round(total_value_usdt, 2)),
        "total_value_with_cost": str(round(total_value_with_cost, 2)),
        "total_cost_usdt": str(round(total_cost_usdt, 2)),
        "total_fee_usdt": str(round(total_fee_usdt, 2)),
        "total_pnl_usdt": str(round(total_pnl_usdt, 2)),
        "total_pnl_percent": str(round(total_pnl_percent, 2)),
    }

    return holdings, totals

