# 交易 API 路由
# 提供下单、撤单、查询订单等交易功能
# 支持通过 mode 参数指定使用模拟盘或实盘

import asyncio
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from .deps import get_ctx, require_current_mode
from ..core.holdings import build_holdings_base, build_spot_holdings
from ..utils.mode import normalize_mode
from ..utils.numbers import require_positive_decimal_str, require_positive_int_str


# 依赖入口集中到 AppContext，降低 API 模块对底层单例实现的耦合。
def get_trader(mode: str):
    return get_ctx().trader(mode)


def get_account(mode: str):
    return get_ctx().account(mode)


def get_cached_storage():
    return get_ctx().storage()


# 保持现有代码习惯：仍使用 config 变量名
config = get_ctx().cfg


router = APIRouter(prefix="/api/trading", tags=["trading"])


# ========== 请求/响应模型 ==========

class PlaceOrderRequest(BaseModel):
    """下单请求"""
    inst_id: str = Field(..., description="交易对，如 BTC-USDT")
    side: str = Field(..., description="交易方向: buy 或 sell")
    order_type: str = Field(..., description="订单类型: market 或 limit")
    size: str = Field(..., description="委托数量")
    price: Optional[str] = Field(default="", description="委托价格（限价单必填）")
    td_mode: str = Field(default="cash", description="交易模式: cash(现货)")
    client_order_id: Optional[str] = Field(default="", description="客户端订单ID")
    mode: str = Field(default="simulated", description="交易模式: simulated 或 live")


class PlaceOrderResponse(BaseModel):
    """下单响应"""
    success: bool
    order_id: str = ""
    client_order_id: str = ""
    error_code: str = ""
    error_message: str = ""


class CancelOrderRequest(BaseModel):
    """撤单请求"""
    inst_id: str = Field(..., description="交易对")
    order_id: str = Field(default="", description="订单ID")
    client_order_id: str = Field(default="", description="客户端订单ID")
    mode: str = Field(default="simulated", description="交易模式: simulated 或 live")


class CancelOrderResponse(BaseModel):
    """撤单响应"""
    success: bool
    order_id: str = ""
    error_code: str = ""
    error_message: str = ""


class AccountBalanceResponse(BaseModel):
    """账户余额响应"""
    total_equity: str = "0"  # 总权益
    details: List[dict] = []  # 各币种详情
    error: str = ""


class PositionItem(BaseModel):
    """持仓项"""
    inst_id: str       # 交易对
    pos_side: str      # 持仓方向
    pos: str           # 持仓数量
    avg_px: str        # 平均开仓价
    upl: str           # 未实现盈亏
    upl_ratio: str     # 未实现盈亏比例
    lever: str         # 杠杆倍数
    liq_px: str        # 强平价格
    margin: str        # 保证金


class OrderItem(BaseModel):
    """订单项"""
    ord_id: str        # 订单ID
    cl_ord_id: str     # 客户端订单ID
    inst_id: str       # 交易对
    side: str          # 方向
    ord_type: str      # 订单类型
    px: str            # 价格
    sz: str            # 数量
    fill_sz: str       # 已成交数量
    avg_px: str        # 成交均价
    state: str         # 状态
    c_time: str        # 创建时间
    u_time: str        # 更新时间


class FillItem(BaseModel):
    """成交记录项"""
    trade_id: str      # 成交ID
    ord_id: str        # 订单ID
    inst_id: str       # 交易对
    side: str          # 方向
    fill_px: str       # 成交价格
    fill_sz: str       # 成交数量
    fee: str           # 手续费
    fee_ccy: str       # 手续费币种
    ts: str            # 成交时间


def validate_mode(mode: str) -> str:
    """验证并规范化 mode 参数"""
    normalized = normalize_mode(mode)
    if not normalized:
        raise HTTPException(status_code=400, detail="mode 必须是 simulated 或 live")
    return normalized


# ========== API 端点 ==========

@router.get("/account")
async def get_account_balance(mode: str = Query(default="simulated", description="交易模式: simulated 或 live")):
    """
    获取账户余额

    返回账户总权益和各币种详情
    """
    mode = validate_mode(mode)
    print(f"[Trading API] /account 请求到达, mode={mode}")
    account = get_account(mode)
    print(f"[Trading API] account.is_available = {account.is_available}")
    if not account.is_available:
        raise HTTPException(status_code=503, detail="账户 API 未初始化，请检查 API 密钥配置")

    try:
        balance = await asyncio.to_thread(account.get_balance)
    except Exception as e:
        print(f"[Trading API] get_balance 异常: {e}")
        raise HTTPException(status_code=500, detail=f"获取余额异常: {str(e)}")

    if "error" in balance:
        raise HTTPException(status_code=500, detail=balance["error"])

    # 解析余额数据
    total_equity = balance.get("totalEq", "0")
    details = balance.get("details", [])

    # 格式化详情
    formatted_details = []
    for d in details:
        formatted_details.append({
            "ccy": d.get("ccy", ""),           # 币种
            "eq": d.get("eq", "0"),             # 币种总权益
            "cash_bal": d.get("cashBal", "0"),  # 现金余额
            "avail_bal": d.get("availBal", "0"), # 可用余额
            "frozen_bal": d.get("frozenBal", "0"), # 冻结余额
            "upl": d.get("upl", "0"),           # 未实现盈亏
        })

    return {
        "total_equity": total_equity,
        "details": formatted_details,
        "mode": mode
    }


@router.get("/positions")
async def get_positions(
    inst_type: str = "",
    inst_id: str = "",
    mode: str = Query(default="simulated", description="交易模式: simulated 或 live")
):
    """
    获取持仓列表

    Args:
        inst_type: 交易类型，SPOT/SWAP/FUTURES（可选）
        inst_id: 交易对（可选）
        mode: 交易模式

    Returns:
        持仓列表
    """
    mode = validate_mode(mode)
    account = get_account(mode)
    if not account.is_available:
        raise HTTPException(status_code=503, detail="账户 API 未初始化")

    positions = await asyncio.to_thread(account.get_positions, inst_type, inst_id)

    # 格式化持仓数据
    formatted = []
    for p in positions:
        formatted.append({
            "inst_id": p.get("instId", ""),
            "pos_side": p.get("posSide", ""),
            "pos": p.get("pos", "0"),
            "avg_px": p.get("avgPx", "0"),
            "upl": p.get("upl", "0"),
            "upl_ratio": p.get("uplRatio", "0"),
            "lever": p.get("lever", "1"),
            "liq_px": p.get("liqPx", ""),
            "margin": p.get("margin", "0"),
        })

    return {"positions": formatted, "mode": mode}


@router.get("/spot-holdings")
async def get_spot_holdings(mode: str = Query(default="simulated", description="交易模式: simulated 或 live")):
    """
    获取现货持仓（从账户余额中提取非稳定币的持仓）

    对于现货交易，"持仓"就是账户中持有的各种币种。
    此接口会计算每个币种的市值和基于成本的盈亏。
    """
    mode = validate_mode(mode)
    account = get_account(mode)
    if not account.is_available:
        raise HTTPException(status_code=503, detail="账户 API 未初始化")

    # 并行获取账户余额和行情数据（两个独立的 API 调用）
    fetcher = get_ctx().fetcher()

    try:
        # 使用 asyncio.to_thread 并行执行同步 API 调用
        balance, all_tickers = await asyncio.gather(
            asyncio.to_thread(account.get_balance),
            asyncio.to_thread(fetcher.get_tickers_cached, "SPOT")
        )
    except Exception as e:
        print(f"[Trading API] get_spot_holdings - 并行获取数据异常: {e}")
        raise HTTPException(status_code=500, detail=f"获取数据异常: {str(e)}")

    if "error" in balance:
        raise HTTPException(status_code=500, detail=balance["error"])

    details = balance.get("details", [])

    # 获取成本基础数据
    try:
        storage = get_cached_storage()
        cost_data = await asyncio.to_thread(storage.get_cost_basis, mode)
    except Exception as e:
        print(f"[Trading API] 获取成本基础失败: {e}")
        cost_data = {}

    holdings, totals = build_spot_holdings(
        balance_details=details,
        tickers=all_tickers,
        cost_data=cost_data,
    )
    return {"holdings": holdings, **totals, "mode": mode}


@router.get("/holdings-base")
async def get_holdings_base(mode: str = Query(default="simulated", description="交易模式: simulated 或 live")):
    """
    获取持仓基础数据（轻量版，不查询行情）

    只返回账户余额和成本基础数据，价格计算由前端通过 WebSocket 实时行情完成。
    相比 spot-holdings 接口，省去了批量行情查询，响应更快。
    """
    mode = validate_mode(mode)
    account = get_account(mode)
    if not account.is_available:
        raise HTTPException(status_code=503, detail="账户 API 未初始化")

    # 只获取账户余额（无需行情）
    try:
        balance = await asyncio.to_thread(account.get_balance)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取余额异常: {str(e)}")

    if "error" in balance:
        raise HTTPException(status_code=500, detail=balance["error"])

    details = balance.get("details", [])

    # 获取成本基础数据
    try:
        storage = get_cached_storage()
        cost_data = await asyncio.to_thread(storage.get_cost_basis, mode)
    except Exception as e:
        print(f"[Trading API] 获取成本基础失败: {e}")
        cost_data = {}

    holdings = build_holdings_base(balance_details=details, cost_data=cost_data)

    return {
        "holdings": holdings,
        "cost_data": {k: {
            "avg_cost": v["avg_cost"],
            "total_cost": v["total_cost"],
            "total_fee": v.get("total_fee", 0),
        } for k, v in cost_data.items()},
        "mode": mode
    }


@router.post("/order", response_model=PlaceOrderResponse)
async def place_order(request: PlaceOrderRequest):
    """
    下单

    支持市价单和限价单
    """
    mode = validate_mode(request.mode)
    require_current_mode(mode, action="现货下单")
    trader = get_trader(mode)
    if not trader.is_available:
        raise HTTPException(status_code=503, detail="交易 API 未初始化，请检查 API 密钥配置")

    # 验证参数
    if request.side not in ("buy", "sell"):
        raise HTTPException(status_code=400, detail="side 必须是 buy 或 sell")
    if request.order_type not in ("market", "limit"):
        raise HTTPException(status_code=400, detail="order_type 必须是 market 或 limit")

    # 数量必须为正数（字符串是为了兼容 OKX SDK 参数类型）
    try:
        size_str = require_positive_decimal_str(request.size)
    except ValueError:
        raise HTTPException(status_code=400, detail="size 必须是正数")

    # 限价单价格必须为正数
    price_str = (request.price or "").strip()
    if request.order_type == "limit":
        if not price_str:
            raise HTTPException(status_code=400, detail="限价单必须指定价格")
        try:
            price_str = require_positive_decimal_str(price_str)
        except ValueError:
            raise HTTPException(status_code=400, detail="price 必须是正数")

    result = await asyncio.to_thread(
        trader.place_order,
        request.inst_id,
        request.side,
        request.order_type,
        size_str,
        price_str if request.order_type == "limit" else "",
        request.td_mode,
        request.client_order_id or ""
    )

    return PlaceOrderResponse(
        success=result.success,
        order_id=result.order_id,
        client_order_id=result.client_order_id,
        error_code=result.error_code,
        error_message=result.error_message
    )


@router.delete("/order/{order_id}")
async def cancel_order(
    order_id: str,
    inst_id: str,
    mode: str = Query(default="simulated", description="交易模式: simulated 或 live")
):
    """
    撤销订单

    Args:
        order_id: 订单ID（路径参数）
        inst_id: 交易对（查询参数）
        mode: 交易模式
    """
    mode = validate_mode(mode)
    require_current_mode(mode, action="撤单")
    trader = get_trader(mode)
    if not trader.is_available:
        raise HTTPException(status_code=503, detail="交易 API 未初始化")

    result = await asyncio.to_thread(trader.cancel_order, inst_id, order_id)

    return CancelOrderResponse(
        success=result.success,
        order_id=result.order_id,
        error_code=result.error_code,
        error_message=result.error_message
    )


@router.post("/order/cancel")
async def cancel_order_post(request: CancelOrderRequest):
    """
    撤销订单（POST 方式）

    支持通过订单ID或客户端订单ID撤单
    """
    mode = validate_mode(request.mode)
    require_current_mode(mode, action="撤单")
    trader = get_trader(mode)
    if not trader.is_available:
        raise HTTPException(status_code=503, detail="交易 API 未初始化")

    if not request.order_id and not request.client_order_id:
        raise HTTPException(status_code=400, detail="必须指定 order_id 或 client_order_id")

    result = await asyncio.to_thread(
        trader.cancel_order,
        request.inst_id,
        request.order_id,
        request.client_order_id
    )

    return CancelOrderResponse(
        success=result.success,
        order_id=result.order_id,
        error_code=result.error_code,
        error_message=result.error_message
    )


@router.get("/orders")
async def get_pending_orders(
    inst_type: str = "SPOT",
    inst_id: str = "",
    mode: str = Query(default="simulated", description="交易模式: simulated 或 live")
):
    """
    获取当前未成交订单

    Args:
        inst_type: 交易类型，默认 SPOT
        inst_id: 交易对（可选）
        mode: 交易模式
    """
    mode = validate_mode(mode)
    trader = get_trader(mode)
    if not trader.is_available:
        raise HTTPException(status_code=503, detail="交易 API 未初始化")

    orders = await asyncio.to_thread(trader.get_pending_orders, inst_type, inst_id)

    # 格式化订单数据
    formatted = []
    for o in orders:
        formatted.append({
            "ord_id": o.get("ordId", ""),
            "cl_ord_id": o.get("clOrdId", ""),
            "inst_id": o.get("instId", ""),
            "side": o.get("side", ""),
            "ord_type": o.get("ordType", ""),
            "px": o.get("px", "0"),
            "sz": o.get("sz", "0"),
            "fill_sz": o.get("fillSz", "0"),
            "avg_px": o.get("avgPx", "0"),
            "state": o.get("state", ""),
            "c_time": o.get("cTime", ""),
            "u_time": o.get("uTime", ""),
        })

    return {"orders": formatted, "mode": mode}


@router.get("/orders/history")
async def get_order_history(
    inst_type: str = "SPOT",
    inst_id: str = "",
    limit: str = "50",
    mode: str = Query(default="simulated", description="交易模式: simulated 或 live")
):
    """
    获取历史订单（最近7天）

    Args:
        inst_type: 交易类型
        inst_id: 交易对（可选）
        limit: 返回数量，默认50
        mode: 交易模式
    """
    mode = validate_mode(mode)
    trader = get_trader(mode)
    if not trader.is_available:
        raise HTTPException(status_code=503, detail="交易 API 未初始化")

    orders = await asyncio.to_thread(trader.get_order_history, inst_type, inst_id, limit)

    # 格式化订单数据
    formatted = []
    for o in orders:
        formatted.append({
            "ord_id": o.get("ordId", ""),
            "cl_ord_id": o.get("clOrdId", ""),
            "inst_id": o.get("instId", ""),
            "side": o.get("side", ""),
            "ord_type": o.get("ordType", ""),
            "px": o.get("px", "0"),
            "sz": o.get("sz", "0"),
            "fill_sz": o.get("fillSz", "0"),
            "avg_px": o.get("avgPx", "0"),
            "state": o.get("state", ""),
            "c_time": o.get("cTime", ""),
            "u_time": o.get("uTime", ""),
            "pnl": o.get("pnl", "0"),
            "fee": o.get("fee", "0"),
        })

    return {"orders": formatted, "mode": mode}


@router.get("/fills")
async def get_fills(
    inst_type: str = "SPOT",
    inst_id: str = "",
    limit: str = "50",
    mode: str = Query(default="simulated", description="交易模式: simulated 或 live")
):
    """
    获取成交记录（最近3天）

    Args:
        inst_type: 交易类型
        inst_id: 交易对（可选）
        limit: 返回数量
        mode: 交易模式
    """
    mode = validate_mode(mode)
    trader = get_trader(mode)
    if not trader.is_available:
        raise HTTPException(status_code=503, detail="交易 API 未初始化")

    fills = await asyncio.to_thread(trader.get_fills, inst_type, inst_id, limit)

    # 格式化成交数据
    formatted = []
    for f in fills:
        side = f.get("side", "")
        # 按交易所返回的原始数据返回手续费，不做任何修改
        fee = f.get("fee", "0")
        fee_ccy = f.get("feeCcy", "")

        formatted.append({
            "trade_id": f.get("tradeId", ""),
            "ord_id": f.get("ordId", ""),
            "inst_id": f.get("instId", ""),
            "side": side,
            "fill_px": f.get("fillPx", "0"),
            "fill_sz": f.get("fillSz", "0"),
            "fee": fee,
            "fee_ccy": fee_ccy,
            "ts": f.get("ts", ""),
        })

    return {"fills": formatted, "mode": mode}


@router.get("/max-size/{inst_id}")
async def get_max_avail_size(
    inst_id: str,
    td_mode: str = "cash",
    mode: str = Query(default="simulated", description="交易模式: simulated 或 live")
):
    """
    获取最大可交易数量

    Args:
        inst_id: 交易对
        td_mode: 交易模式
        mode: 交易模式 (simulated/live)
    """
    mode = validate_mode(mode)
    account = get_account(mode)
    if not account.is_available:
        raise HTTPException(status_code=503, detail="账户 API 未初始化")

    # 现货 maxBuy 的口径在不同 OKX 接口/SDK 版本下可能需要用“可用计价币 + 最新价”估算，
    # 这里在 API 层提供 last_price 注入，避免交易模块直接依赖行情/缓存模块。
    last_price = None
    try:
        fetcher = get_ctx().fetcher()
        ticker = await asyncio.to_thread(fetcher.get_ticker_cached, inst_id)
        last_price = getattr(ticker, "last", None) if ticker else None
    except Exception as e:
        print(f"[Trading API] 获取 {inst_id} 最新价失败（将不做估算）: {e}")

    result = await asyncio.to_thread(account.get_max_avail_size, inst_id, td_mode, last_price=last_price)

    return {
        "max_buy": result.get("maxBuy", "0"),
        "max_sell": result.get("maxSell", "0"),
        "mode": mode
    }


@router.get("/status")
async def get_trading_status(mode: str = Query(default="simulated", description="交易模式: simulated 或 live")):
    """
    获取交易模块状态

    返回交易和账户 API 的可用状态
    """
    mode = validate_mode(mode)
    trader = get_trader(mode)
    account = get_account(mode)

    # 按请求的 mode 返回对应的配置状态，避免“页面模式”和“后端当前模式”不一致
    api_configured = config.okx.demo.is_valid() if mode == "simulated" else config.okx.live.is_valid()

    return {
        "trader_available": trader.is_available,
        "account_available": account.is_available,
        "mode": mode,
        "api_configured": api_configured,
    }


# ========== 成本基础相关 API ==========

class UpdateCostBasisRequest(BaseModel):
    """更新成本基础请求"""
    ccy: str = Field(..., description="币种，如 BTC")
    avg_cost: float = Field(..., description="平均成本价")
    mode: str = Field(default="simulated", description="交易模式: simulated 或 live")


@router.post("/fills/sync")
async def sync_fills_to_local(
    mode: str = Query(default="simulated", description="交易模式: simulated 或 live")
):
    """
    同步成交记录到本地数据库

    从 OKX 获取最近3个月的成交记录并保存到本地，用于计算成本基础。
    """
    mode = validate_mode(mode)
    trader = get_trader(mode)

    if not trader.is_available:
        raise HTTPException(status_code=503, detail="交易 API 未初始化，请检查 API 密钥配置")

    try:
        # 获取所有历史成交记录
        fills = await asyncio.to_thread(trader.get_all_fills_history, "SPOT")

        if not fills:
            return {
                "synced_count": 0,
                "new_count": 0,
                "message": "未获取到成交记录",
                "mode": mode
            }

        # 调试：打印前5条成交记录的详细信息
        print(f"[Trading API] 同步成交记录，共 {len(fills)} 条，前5条详情:")
        for i, f in enumerate(fills[:5]):
            print(f"  [{i}] instId={f.get('instId')}, side={f.get('side')}, "
                  f"fillPx={f.get('fillPx')}, fillSz={f.get('fillSz')}, "
                  f"fee={f.get('fee')}, feeCcy={f.get('feeCcy')}")

        # 保存到本地数据库
        storage = get_cached_storage()
        # 批量写入与成本计算可能较慢，必须丢到线程池，避免阻塞事件循环
        def _save_and_recalc():
            new_count = storage.save_fills_batch(fills, mode)
            storage.update_cost_basis_from_fills(mode)
            return new_count

        new_count = await asyncio.to_thread(_save_and_recalc)

        return {
            "synced_count": len(fills),
            "new_count": new_count,
            "message": f"已同步 {len(fills)} 条成交记录，其中 {new_count} 条为新记录",
            "mode": mode
        }

    except Exception as e:
        print(f"[Trading API] 同步成交记录失败: {e}")
        raise HTTPException(status_code=500, detail=f"同步失败: {str(e)}")


@router.post("/fills/rebuild")
async def rebuild_fills_table():
    """
    重建成交记录表（修复精度问题）

    会删除所有现有数据，需要重新同步。
    使用 TEXT 类型存储数值，避免浮点数精度损失。
    """
    try:
        storage = get_cached_storage()
        # 重建表属于写操作，避免阻塞事件循环
        await asyncio.to_thread(storage.rebuild_fills_table)

        return {
            "success": True,
            "message": "成交记录表已重建，请点击'同步记录'重新同步数据"
        }

    except Exception as e:
        print(f"[Trading API] 重建成交记录表失败: {e}")
        raise HTTPException(status_code=500, detail=f"重建失败: {str(e)}")


@router.get("/cost-basis")
async def get_cost_basis(
    mode: str = Query(default="simulated", description="交易模式: simulated 或 live"),
    ccy: str = Query(default="", description="币种（可选，不填返回所有）")
):
    """
    获取成本基础数据

    返回各币种的平均成本、总数量、总成本。
    """
    mode = validate_mode(mode)

    try:
        storage = get_cached_storage()
        cost_data = await asyncio.to_thread(storage.get_cost_basis, mode, ccy)

        return {
            "data": cost_data,
            "mode": mode
        }

    except Exception as e:
        print(f"[Trading API] 获取成本基础失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")


@router.post("/cost-basis")
async def update_cost_basis(request: UpdateCostBasisRequest):
    """
    手动更新成本基础

    用于无法从 API 获取历史数据时，手动录入成本价。
    """
    mode = validate_mode(request.mode)

    if request.avg_cost <= 0:
        raise HTTPException(status_code=400, detail="平均成本必须大于0")

    try:
        # 尝试从账户余额中获取当前持仓数量，用于推导总成本。
        # 否则仅保存 avg_cost 会导致 total_cost=0，从而让盈亏/成本统计严重失真。
        total_qty = 0.0
        try:
            account = get_account(mode)
            if account.is_available:
                balance = await asyncio.to_thread(account.get_balance)
                if balance and "error" not in balance:
                    for d in balance.get("details", []):
                        if (d.get("ccy", "") or "").upper() == request.ccy.upper():
                            avail_bal = float(d.get("availBal", 0) or 0)
                            frozen_bal = float(d.get("frozenBal", 0) or 0)
                            total_qty = avail_bal + frozen_bal
                            break
        except Exception as e:
            # 获取失败不阻塞手动录入，但会退化为仅更新 avg_cost
            print(f"[Trading API] 手动更新成本时获取余额失败: {e}")

        total_cost = request.avg_cost * total_qty if total_qty > 0 else 0

        storage = get_cached_storage()
        await asyncio.to_thread(
            storage.save_cost_basis,
            ccy=request.ccy.upper(),
            mode=mode,
            avg_cost=request.avg_cost,
            total_qty=total_qty,
            total_cost=total_cost,
        )

        return {
            "success": True,
            "message": f"已更新 {request.ccy.upper()} 的成本价为 {request.avg_cost}",
            "mode": mode
        }

    except Exception as e:
        print(f"[Trading API] 更新成本基础失败: {e}")
        raise HTTPException(status_code=500, detail=f"更新失败: {str(e)}")


@router.get("/local-fills")
async def get_local_fills(
    mode: str = Query(default="simulated", description="交易模式: simulated 或 live"),
    ccy: str = Query(default="", description="币种过滤"),
    inst_id: str = Query(default="", description="交易对过滤，如 BTC-USDT"),
    limit: int = Query(default=100, ge=1, le=1000, description="返回数量")
):
    """
    获取本地保存的成交记录
    """
    mode = validate_mode(mode)

    try:
        storage = get_cached_storage()
        # 读取本地成交与统计可能较慢，避免阻塞事件循环
        def _read_local_fills():
            fills = storage.get_fills(mode, ccy=ccy, inst_id=inst_id, limit=limit)
            total = storage.get_fills_count(mode)
            return fills, total

        fills, total = await asyncio.to_thread(_read_local_fills)

        return {
            "fills": fills,
            "count": len(fills),
            "total": total,
            "mode": mode
        }

    except Exception as e:
        print(f"[Trading API] 获取本地成交记录失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")


# ========== 合约交易相关 API ==========

class SetLeverageRequest(BaseModel):
    """设置杠杆请求"""
    inst_id: str = Field(..., description="合约ID，如 BTC-USDT-SWAP")
    lever: str = Field(..., description="杠杆倍数，如 10")
    mgn_mode: str = Field(default="cross", description="保证金模式: cross(全仓) 或 isolated(逐仓)")
    pos_side: str = Field(default="", description="持仓方向（逐仓/双向持仓时需要）: long/short/net")
    mode: str = Field(default="simulated", description="交易模式: simulated 或 live")


class ContractOrderRequest(BaseModel):
    """合约下单请求"""
    inst_id: str = Field(..., description="合约ID，如 BTC-USDT-SWAP")
    side: str = Field(..., description="交易方向: buy 或 sell")
    pos_side: str = Field(..., description="持仓方向: long(多)/short(空)/net(净)")
    order_type: str = Field(..., description="订单类型: market 或 limit")
    size: str = Field(..., description="委托数量（张数）")
    price: Optional[str] = Field(default="", description="委托价格（限价单必填）")
    td_mode: str = Field(default="cross", description="保证金模式: cross(全仓) 或 isolated(逐仓)")
    reduce_only: bool = Field(default=False, description="是否只减仓")
    client_order_id: Optional[str] = Field(default="", description="客户端订单ID")
    mode: str = Field(default="simulated", description="交易模式: simulated 或 live")


@router.post("/contract/leverage")
async def set_leverage(req: SetLeverageRequest):
    """
    设置合约杠杆倍数

    在开仓前需要先设置杠杆。
    """
    mode = validate_mode(req.mode)
    require_current_mode(mode, action="设置杠杆")
    trader = get_trader(mode)
    if not trader.is_available:
        raise HTTPException(status_code=503, detail="交易 API 未初始化")

    result = await asyncio.to_thread(
        trader.set_leverage,
        req.inst_id,
        req.lever,
        req.mgn_mode,
        req.pos_side
    )

    if result.get("success"):
        return {"success": True, "message": f"杠杆已设置为 {req.lever}x", "data": result.get("data")}
    else:
        raise HTTPException(status_code=400, detail=result.get("error", "设置杠杆失败"))


@router.get("/contract/leverage/{inst_id}")
async def get_leverage(
    inst_id: str,
    mgn_mode: str = Query(default="cross", description="保证金模式"),
    mode: str = Query(default="simulated", description="交易模式")
):
    """
    获取合约杠杆倍数
    """
    mode = validate_mode(mode)
    trader = get_trader(mode)
    if not trader.is_available:
        raise HTTPException(status_code=503, detail="交易 API 未初始化")

    result = await asyncio.to_thread(trader.get_leverage, inst_id, mgn_mode)

    if result.get("success"):
        return {"success": True, "data": result.get("data")}
    else:
        raise HTTPException(status_code=400, detail=result.get("error", "获取杠杆失败"))


@router.post("/contract/order", response_model=PlaceOrderResponse)
async def place_contract_order(req: ContractOrderRequest):
    """
    合约下单

    开多: side=buy, pos_side=long
    开空: side=sell, pos_side=short
    平多: side=sell, pos_side=long
    平空: side=buy, pos_side=short
    """
    mode = validate_mode(req.mode)
    require_current_mode(mode, action="合约下单")
    trader = get_trader(mode)
    if not trader.is_available:
        raise HTTPException(status_code=503, detail="交易 API 未初始化")

    # 验证参数
    if req.side not in ("buy", "sell"):
        raise HTTPException(status_code=400, detail="side 必须是 buy 或 sell")
    if req.pos_side not in ("long", "short", "net"):
        raise HTTPException(status_code=400, detail="pos_side 必须是 long/short/net")
    if req.order_type not in ("market", "limit"):
        raise HTTPException(status_code=400, detail="order_type 必须是 market 或 limit")
    if req.order_type == "limit" and not req.price:
        raise HTTPException(status_code=400, detail="限价单必须提供价格")

    # 合约数量通常为“张数”，这里保守要求为正整数，避免小数导致交易所拒单/误解
    try:
        size_str = require_positive_int_str(req.size)
    except ValueError:
        raise HTTPException(status_code=400, detail="size 必须是正整数（张数）")

    price_str = (req.price or "").strip()
    if req.order_type == "limit":
        if not price_str:
            raise HTTPException(status_code=400, detail="限价单必须提供价格")
        try:
            price_str = require_positive_decimal_str(price_str)
        except ValueError:
            raise HTTPException(status_code=400, detail="price 必须是正数")

    result = await asyncio.to_thread(
        trader.place_contract_order,
        req.inst_id,
        req.side,
        req.pos_side,
        req.order_type,
        size_str,
        price_str if req.order_type == "limit" else "",
        req.td_mode,
        req.reduce_only,
        req.client_order_id
    )

    return PlaceOrderResponse(
        success=result.success,
        order_id=result.order_id,
        client_order_id=result.client_order_id,
        error_code=result.error_code,
        error_message=result.error_message
    )


@router.get("/contract/positions")
async def get_contract_positions(
    inst_type: str = Query(default="SWAP", description="合约类型: SWAP(永续) 或 FUTURES(交割)"),
    inst_id: str = Query(default="", description="合约ID（可选）"),
    mode: str = Query(default="simulated", description="交易模式")
):
    """
    获取合约持仓

    返回当前持有的合约持仓信息，包括持仓数量、开仓均价、未实现盈亏、杠杆、强平价格等。
    """
    mode = validate_mode(mode)
    account = get_account(mode)
    if not account.is_available:
        raise HTTPException(status_code=503, detail="账户 API 未初始化")

    positions = await asyncio.to_thread(account.get_contract_positions, inst_type, inst_id)

    # 格式化持仓数据
    formatted = []
    for p in positions:
        # 只返回有持仓的记录
        pos = p.get("pos", "0")
        try:
            if float(pos) == 0:
                continue
        except (TypeError, ValueError):
            if pos in ("", "0"):
                continue

        formatted.append({
            "inst_id": p.get("instId", ""),
            "inst_type": p.get("instType", ""),
            "pos_side": p.get("posSide", ""),
            "pos": pos,
            "avg_px": p.get("avgPx", "0"),
            "upl": p.get("upl", "0"),
            "upl_ratio": p.get("uplRatio", "0"),
            "lever": p.get("lever", "1"),
            "liq_px": p.get("liqPx", ""),
            "margin": p.get("margin", "0"),
            "mgn_mode": p.get("mgnMode", ""),
            "notional_usd": p.get("notionalUsd", "0"),
            "mark_px": p.get("markPx", "0"),
        })

    return {"positions": formatted, "mode": mode}


@router.get("/contract/max-size/{inst_id}")
async def get_contract_max_size(
    inst_id: str,
    td_mode: str = Query(default="cross", description="保证金模式: cross 或 isolated"),
    mode: str = Query(default="simulated", description="交易模式")
):
    """
    获取合约最大可开仓数量

    返回指定合约在当前保证金模式下的最大可开多和可开空数量。
    """
    mode = validate_mode(mode)
    account = get_account(mode)
    if not account.is_available:
        raise HTTPException(status_code=503, detail="账户 API 未初始化")

    result = await asyncio.to_thread(account.get_max_contract_size, inst_id, td_mode)

    return {
        "inst_id": inst_id,
        "td_mode": td_mode,
        "max_buy": result.get("maxBuy", "0"),
        "max_sell": result.get("maxSell", "0"),
        "mode": mode
    }


@router.post("/contract/position-mode")
async def set_position_mode(
    pos_mode: str = Query(..., description="持仓模式: long_short_mode(双向) 或 net_mode(单向)"),
    mode: str = Query(default="simulated", description="交易模式")
):
    """
    设置持仓模式

    - long_short_mode: 双向持仓，可以同时持有多头和空头
    - net_mode: 单向持仓，多空会相互抵消
    """
    mode = validate_mode(mode)
    require_current_mode(mode, action="设置持仓模式")
    account = get_account(mode)
    if not account.is_available:
        raise HTTPException(status_code=503, detail="账户 API 未初始化")

    if pos_mode not in ("long_short_mode", "net_mode"):
        raise HTTPException(status_code=400, detail="pos_mode 必须是 long_short_mode 或 net_mode")

    result = await asyncio.to_thread(account.set_position_mode, pos_mode)

    if result.get("success"):
        mode_text = "双向持仓" if pos_mode == "long_short_mode" else "单向持仓"
        return {"success": True, "message": f"已切换为{mode_text}模式"}
    else:
        raise HTTPException(status_code=400, detail=result.get("error", "设置持仓模式失败"))


@router.get("/contract/account-config")
async def get_account_config(
    mode: str = Query(default="simulated", description="交易模式")
):
    """
    获取账户配置

    返回账户的持仓模式、账户级别等配置信息。
    """
    mode = validate_mode(mode)
    account = get_account(mode)
    if not account.is_available:
        raise HTTPException(status_code=503, detail="账户 API 未初始化")

    config = await asyncio.to_thread(account.get_account_config)

    return {
        "pos_mode": config.get("posMode", ""),
        "acct_lv": config.get("acctLv", ""),
        "auto_loan": config.get("autoLoan", False),
        "greeks_type": config.get("greeksType", ""),
        "level": config.get("level", ""),
        "level_tmp": config.get("levelTmp", ""),
        "mode": mode
    }
