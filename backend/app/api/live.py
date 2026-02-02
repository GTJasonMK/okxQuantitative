# 实时交易 API 路由
# 提供策略启动、停止、状态查询等功能

import asyncio
from typing import Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel, Field

from ..live import get_live_engine, EngineStatus
from ..strategies import get_strategy
from ..core.app_context import AppContext
from .deps import get_ctx


router = APIRouter(prefix="/api/live", tags=["live-trading"])


# ========== 请求/响应模型 ==========

class StartStrategyRequest(BaseModel):
    """启动策略请求"""
    strategy_id: str = Field(..., description="策略ID")
    symbol: str = Field(default="BTC-USDT", description="交易对")
    timeframe: str = Field(default="1H", description="时间周期")
    inst_type: str = Field(default="SPOT", description="交易类型: SPOT/SWAP/FUTURES（实时交易目前仅支持 SPOT）")
    initial_capital: float = Field(default=10000, gt=0, description="初始资金")
    position_size: float = Field(default=0.1, gt=0, le=1.0, description="仓位比例 (0-1)")
    stop_loss: float = Field(default=0.05, ge=0, le=1.0, description="止损比例 (0-1)")
    take_profit: float = Field(default=0.10, ge=0, le=1.0, description="止盈比例 (0-1)")
    check_interval: int = Field(default=60, ge=1, description="检查间隔（秒，>=1）")
    params: dict = Field(default_factory=dict, description="策略特定参数")


class StrategyStatusResponse(BaseModel):
    """策略状态响应"""
    status: str
    strategy_id: str
    strategy_name: str
    symbol: str
    timeframe: str
    inst_type: str
    start_time: Optional[str]
    last_signal_time: Optional[str]
    last_signal_type: str
    total_signals: int
    total_orders: int
    successful_orders: int
    failed_orders: int
    error_message: str
    check_interval: int


# ========== API 端点 ==========

@router.post("/start")
async def start_strategy(
    request: StartStrategyRequest,
    _background_tasks: BackgroundTasks,
    ctx: AppContext = Depends(get_ctx),
):
    """
    启动策略实时交易

    注意：策略将在后台运行，通过 /status 接口查看运行状态
    """
    engine = get_live_engine()

    # 检查是否已在运行/启动中（防止重复启动导致重复下单）
    if engine.is_running:
        raise HTTPException(status_code=400, detail=f"引擎正在运行或启动中 (策略: {engine.state.strategy_name})")

    # 获取策略类
    strategy_cls = get_strategy(request.strategy_id)
    if not strategy_cls:
        raise HTTPException(
            status_code=404,
            detail=f"策略 '{request.strategy_id}' 不存在"
        )

    # 风险控制：实时策略交易目前仅实现现货下单逻辑（OKXTrader.place_order）。
    # 若允许 SWAP/FUTURES，会出现“用户以为跑合约，但实际走现货/或下单失败”的高风险错配。
    inst_type = (request.inst_type or "SPOT").upper()
    if inst_type != "SPOT":
        raise HTTPException(
            status_code=400,
            detail=f"实时策略交易暂不支持 inst_type={inst_type}（仅支持 SPOT）。合约请使用手动交易接口或先完善合约下单逻辑。",
        )

    # 创建策略实例
    try:
        strategy = strategy_cls.create_instance(
            symbol=request.symbol,
            timeframe=request.timeframe,
            initial_capital=request.initial_capital,
            position_size=request.position_size,
            stop_loss=request.stop_loss,
            take_profit=request.take_profit,
            inst_type=inst_type,
            **request.params
        )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"创建策略实例失败: {str(e)}"
        )

    # 启动引擎（内部加锁，避免并发 start/覆盖配置）
    try:
        # 依赖注入：由 API 层统一装配 trader/account/manager/storage，降低 LiveTradingEngine 与全局单例的耦合
        mode = ctx.default_mode()
        await engine.start_with_strategy(
            strategy=strategy,
            check_interval=request.check_interval,
            trader=ctx.trader(mode),
            account=ctx.account(mode),
            candle_manager=ctx.manager(),
            storage=ctx.storage(),
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"引擎启动失败: {str(e)}")

    return {
        "success": True,
        "message": f"策略 '{strategy.name}' 已启动",
        "strategy_id": request.strategy_id,
        "symbol": request.symbol,
        "timeframe": request.timeframe,
    }


@router.post("/stop")
async def stop_strategy():
    """
    停止策略实时交易
    """
    engine = get_live_engine()

    if not engine.is_running:
        return {
            "success": True,
            "message": "引擎未在运行"
        }

    await engine.stop()

    return {
        "success": True,
        "message": "策略已停止"
    }


@router.get("/status", response_model=StrategyStatusResponse)
async def get_strategy_status():
    """
    获取策略运行状态
    """
    engine = get_live_engine()
    return engine.get_status_dict()


@router.get("/orders")
async def get_order_history(limit: int = 50, ctx: AppContext = Depends(get_ctx)):
    """
    获取策略执行的订单历史

    从数据库中读取持久化的订单记录，重启后数据不丢失。

    Args:
        limit: 返回数量限制
    """
    try:
        storage = ctx.storage()
        db_orders = await asyncio.to_thread(storage.get_live_orders, limit=limit)
        return {"orders": db_orders}
    except Exception as e:
        print(f"[Live API] 获取订单历史失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取订单历史失败: {str(e)}")


@router.get("/available-strategies")
async def get_available_strategies():
    """
    获取可用于实时交易的策略列表
    """
    from ..strategies import list_strategies

    strategies = list_strategies()

    return {
        "strategies": [
            {
                "id": s["id"],
                "name": s["name"],
                "description": s.get("description", ""),
                "params": s.get("params", []),
            }
            for s in strategies
        ]
    }
