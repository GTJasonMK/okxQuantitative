# 回测API路由
# 提供策略回测接口（支持统一API和旧式独立端点）

import asyncio
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from ..core.app_context import AppContext
from .deps import get_ctx
from ..strategies import create_dual_ma_strategy, create_grid_strategy
from ..strategies.registry import get_strategy, get_strategy_source, list_strategies, discover_strategies, reload_strategies
from ..backtest import BacktestEngine, BacktestConfig
from ..config import DATA_DIR
from ..utils.timeframes import calculate_candle_count


router = APIRouter(prefix="/backtest", tags=["策略回测"])


# ==================== 请求模型 ====================

class UnifiedBacktestRequest(BaseModel):
    """通用回测请求模型"""
    symbol: str = Field(default="BTC-USDT", description="交易对")
    inst_type: str = Field(default="SPOT", description="交易类型（SPOT/SWAP等）")
    timeframe: str = Field(default="1H", description="时间周期")
    days: int = Field(default=30, ge=1, le=365, description="回测天数")
    initial_capital: float = Field(default=10000, gt=0, description="初始资金")
    position_size: float = Field(default=0.5, ge=0.1, le=1.0, description="仓位比例")
    stop_loss: float = Field(default=0.05, ge=0, le=0.5, description="止损比例")
    take_profit: float = Field(default=0.10, ge=0, le=1.0, description="止盈比例")
    params: Dict[str, Any] = Field(default_factory=dict, description="策略特定参数")

class DualMABacktestRequest(BaseModel):
    """双均线策略回测请求"""
    symbol: str = Field(default="BTC-USDT", description="交易对")
    inst_type: str = Field(default="SPOT", description="交易类型（SPOT/SWAP等）")
    timeframe: str = Field(default="1H", description="时间周期")
    days: int = Field(default=30, ge=1, le=365, description="回测天数")
    initial_capital: float = Field(default=10000, gt=0, description="初始资金")
    # 策略参数
    short_period: int = Field(default=5, ge=2, le=50, description="短期均线周期")
    long_period: int = Field(default=20, ge=5, le=200, description="长期均线周期")
    use_ema: bool = Field(default=False, description="是否使用EMA")
    # 风控参数
    stop_loss: float = Field(default=0.05, ge=0, le=0.5, description="止损比例")
    take_profit: float = Field(default=0.10, ge=0, le=1.0, description="止盈比例")
    position_size: float = Field(default=0.5, ge=0.1, le=1.0, description="仓位比例")


class GridBacktestRequest(BaseModel):
    """网格策略回测请求"""
    symbol: str = Field(default="BTC-USDT", description="交易对")
    inst_type: str = Field(default="SPOT", description="交易类型（SPOT/SWAP等）")
    timeframe: str = Field(default="1H", description="时间周期")
    days: int = Field(default=30, ge=1, le=365, description="回测天数")
    initial_capital: float = Field(default=10000, gt=0, description="初始资金")
    # 策略参数
    upper_price: float = Field(..., description="网格上限价格")
    lower_price: float = Field(..., description="网格下限价格")
    grid_count: int = Field(default=10, ge=2, le=100, description="网格数量")
    position_size: float = Field(default=0.8, ge=0.1, le=1.0, description="总仓位比例")
    grid_type: str = Field(default="arithmetic", description="网格类型")


class BacktestResponse(BaseModel):
    """回测响应"""
    code: int = 0
    message: str = "success"
    data: Optional[Dict[str, Any]] = None


# ==================== 回测接口 ====================

@router.post("/dual_ma", response_model=BacktestResponse, summary="双均线策略回测")
async def backtest_dual_ma(
    request: DualMABacktestRequest,
    ctx: AppContext = Depends(get_ctx)
):
    """
    运行双均线策略回测

    策略逻辑：
    - 金叉（短期均线上穿长期均线）买入
    - 死叉（短期均线下穿长期均线）卖出
    - 支持止损止盈
    """
    try:
        # 验证参数
        if request.short_period >= request.long_period:
            raise HTTPException(
                status_code=400,
                detail="短期均线周期必须小于长期均线周期"
            )

        # 获取K线数据（根据时间周期计算正确的K线数量）
        candle_count = calculate_candle_count(timeframe=request.timeframe, days=request.days)
        manager = ctx.manager()
        candles = await asyncio.to_thread(
            manager.get_candles_with_sync,
            inst_id=request.symbol,
            timeframe=request.timeframe,
            count=candle_count,
            auto_sync=True,
            inst_type=request.inst_type,
        )

        if len(candles) < request.long_period + 10:
            raise HTTPException(
                status_code=400,
                detail=f"K线数据不足，需要至少{request.long_period + 10}根K线"
            )

        # 创建策略
        strategy = create_dual_ma_strategy(
            symbol=request.symbol,
            timeframe=request.timeframe,
            inst_type=request.inst_type,
            initial_capital=request.initial_capital,
            short_period=request.short_period,
            long_period=request.long_period,
            stop_loss=request.stop_loss,
            take_profit=request.take_profit,
            position_size=request.position_size,
            use_ema=request.use_ema,
        )

        # 运行回测
        engine = BacktestEngine()
        result = await asyncio.to_thread(engine.run, strategy, candles)

        # 保存回测结果到数据库
        result_dict = result.to_dict()
        try:
            storage = ctx.storage()
            # 写库可能较慢，避免阻塞事件循环
            await asyncio.to_thread(
                storage.save_backtest_result,
                result_dict=result_dict,
                strategy_id="dual_ma",
                params={
                    "short_period": request.short_period,
                    "long_period": request.long_period,
                    "use_ema": request.use_ema,
                    "stop_loss": request.stop_loss,
                    "take_profit": request.take_profit,
                    "position_size": request.position_size,
                },
            )
        except Exception as e:
            print(f"[Backtest API] 保存回测结果失败: {e}")

        return BacktestResponse(data=result_dict)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"回测执行失败: {str(e)}")


@router.post("/grid", response_model=BacktestResponse, summary="网格策略回测")
async def backtest_grid(
    request: GridBacktestRequest,
    ctx: AppContext = Depends(get_ctx)
):
    """
    运行网格策略回测

    策略逻辑：
    - 在价格区间内设置多个网格
    - 价格下跌触及网格线时买入
    - 价格上涨触及网格线时卖出
    - 适合震荡行情
    """
    try:
        # 验证参数
        if request.upper_price <= request.lower_price:
            raise HTTPException(
                status_code=400,
                detail="网格上限价格必须大于下限价格"
            )

        # 验证网格价差是否合理
        price_range_ratio = (request.upper_price - request.lower_price) / request.lower_price
        if price_range_ratio < 0.01:
            raise HTTPException(
                status_code=400,
                detail="网格价格区间过小（至少1%），无法有效套利"
            )

        # 获取K线数据（根据时间周期计算正确的K线数量）
        candle_count = calculate_candle_count(timeframe=request.timeframe, days=request.days)
        manager = ctx.manager()
        candles = await asyncio.to_thread(
            manager.get_candles_with_sync,
            inst_id=request.symbol,
            timeframe=request.timeframe,
            count=candle_count,
            auto_sync=True,
            inst_type=request.inst_type,
        )

        if len(candles) < 10:
            raise HTTPException(status_code=400, detail="K线数据不足，需要至少10根K线")

        # 验证网格价格是否在数据范围内
        data_high = max(c.high for c in candles)
        data_low = min(c.low for c in candles)

        # 检查网格是否与数据有交集
        if request.lower_price > data_high:
            raise HTTPException(
                status_code=400,
                detail=f"网格下限({request.lower_price:.2f})高于数据最高价({data_high:.2f})，无法触发交易"
            )
        if request.upper_price < data_low:
            raise HTTPException(
                status_code=400,
                detail=f"网格上限({request.upper_price:.2f})低于数据最低价({data_low:.2f})，无法触发交易"
            )

        # 创建策略
        strategy = create_grid_strategy(
            symbol=request.symbol,
            timeframe=request.timeframe,
            inst_type=request.inst_type,
            initial_capital=request.initial_capital,
            upper_price=request.upper_price,
            lower_price=request.lower_price,
            grid_count=request.grid_count,
            position_size=request.position_size,
            grid_type=request.grid_type,
        )

        # 运行回测
        engine = BacktestEngine()
        result = await asyncio.to_thread(engine.run, strategy, candles)

        # 保存回测结果到数据库
        result_dict = result.to_dict()
        try:
            storage = ctx.storage()
            # 写库可能较慢，避免阻塞事件循环
            await asyncio.to_thread(
                storage.save_backtest_result,
                result_dict=result_dict,
                strategy_id="grid",
                params={
                    "upper_price": request.upper_price,
                    "lower_price": request.lower_price,
                    "grid_count": request.grid_count,
                    "position_size": request.position_size,
                    "grid_type": request.grid_type,
                },
            )
        except Exception as e:
            print(f"[Backtest API] 保存回测结果失败: {e}")

        return BacktestResponse(data=result_dict)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"回测执行失败: {str(e)}")


@router.get("/strategies", summary="获取可用策略列表")
async def get_strategies():
    """
    获取系统支持的策略列表

    返回所有已注册策略的元数据，包括：
    - id: 策略唯一标识
    - name: 策略名称
    - description: 策略描述
    - params: 策略参数列表（含类型、默认值、范围等）
    """
    # 确保策略已发现
    discover_strategies()

    strategies = list_strategies()
    return {"code": 0, "message": "success", "data": strategies}


@router.post("/strategies/reload", summary="热加载策略")
async def reload_all_strategies():
    """
    热加载：重新加载所有策略模块

    无需重启服务即可：
    - 加载新添加的策略文件
    - 更新已修改的策略代码
    - 移除已删除的策略

    适用于开发调试和动态添加策略场景
    """
    try:
        result = reload_strategies()
        return {
            "code": 0,
            "message": f"策略热加载完成，共加载 {result['total']} 个策略",
            "data": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"策略热加载失败: {str(e)}")


@router.get("/strategies/{strategy_id}/source", summary="获取策略源代码")
async def get_strategy_source_code(strategy_id: str):
    """
    获取策略的 Python 源代码

    用于在前端策略页面直接展示策略实现代码
    """
    discover_strategies()

    source_info = get_strategy_source(strategy_id)
    if not source_info:
        raise HTTPException(status_code=404, detail=f"策略不存在或无法获取源码: {strategy_id}")

    return {
        "code": 0,
        "message": "success",
        "data": source_info
    }


# ==================== 通用回测接口（插件化架构） ====================

@router.post("/run/{strategy_id}", response_model=BacktestResponse, summary="通用策略回测")
async def backtest_strategy(
    strategy_id: str,
    request: UnifiedBacktestRequest,
    ctx: AppContext = Depends(get_ctx)
):
    """
    通用策略回测接口

    支持所有已注册的策略，通过 strategy_id 指定要运行的策略，
    策略特定参数通过 params 字段传递。

    Args:
        strategy_id: 策略ID（如 dual_ma, grid）
        request: 回测请求参数
    """
    # 确保策略已发现
    discover_strategies()

    try:
        # 1. 获取策略类
        strategy_cls = get_strategy(strategy_id)
        if not strategy_cls:
            raise HTTPException(
                status_code=404,
                detail=f"策略不存在: {strategy_id}"
            )

        # 2. 验证策略参数
        try:
            strategy_cls.validate_params(request.params)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"参数验证失败: {str(e)}")

        # 3. 获取K线数据
        candle_count = calculate_candle_count(timeframe=request.timeframe, days=request.days)
        manager = ctx.manager()
        candles = await asyncio.to_thread(
            manager.get_candles_with_sync,
            inst_id=request.symbol,
            timeframe=request.timeframe,
            count=candle_count,
            auto_sync=True,
            inst_type=request.inst_type,
        )

        if len(candles) < 10:
            raise HTTPException(status_code=400, detail="K线数据不足，需要至少10根K线")

        # 4. 创建策略实例
        strategy = strategy_cls.create_instance(
            symbol=request.symbol,
            timeframe=request.timeframe,
            initial_capital=request.initial_capital,
            position_size=request.position_size,
            stop_loss=request.stop_loss,
            take_profit=request.take_profit,
            inst_type=request.inst_type,
            **request.params
        )

        # 5. 运行回测
        engine = BacktestEngine()
        result = await asyncio.to_thread(engine.run, strategy, candles)

        # 6. 保存回测结果到数据库
        result_dict = result.to_dict()
        try:
            storage = ctx.storage()
            # 写库可能较慢，避免阻塞事件循环
            await asyncio.to_thread(
                storage.save_backtest_result,
                result_dict=result_dict,
                strategy_id=strategy_id,
                params={
                    **request.params,
                    "stop_loss": request.stop_loss,
                    "take_profit": request.take_profit,
                    "position_size": request.position_size,
                },
            )
        except Exception as e:
            print(f"[Backtest API] 保存回测结果失败: {e}")

        return BacktestResponse(data=result_dict)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"回测执行失败: {str(e)}")


# ==================== 旧式独立端点（向后兼容） ====================


@router.get("/history", summary="获取回测历史")
async def get_backtest_history(
    limit: int = 50,
    strategy_id: str = "",
    symbol: str = "",
    ctx: AppContext = Depends(get_ctx),
):
    """
    获取回测历史记录列表

    Args:
        limit: 返回数量限制，默认50
        strategy_id: 按策略ID过滤
        symbol: 按交易对过滤
    """
    try:
        storage = ctx.storage()
        results = await asyncio.to_thread(
            storage.get_backtest_results,
            limit=limit,
            strategy_id=strategy_id,
            symbol=symbol,
        )
        return {
            "code": 0,
            "message": "success",
            "data": results
        }
    except Exception as e:
        print(f"[Backtest API] 获取回测历史失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取回测历史失败: {str(e)}")


@router.get("/history/{result_id}", summary="获取回测详情")
async def get_backtest_detail(result_id: int, ctx: AppContext = Depends(get_ctx)):
    """
    获取单条回测结果的完整数据（含资金曲线和交易记录）

    Args:
        result_id: 回测记录ID
    """
    try:
        storage = ctx.storage()
        result = await asyncio.to_thread(storage.get_backtest_result_detail, result_id)
        if not result:
            raise HTTPException(status_code=404, detail="回测记录不存在")
        return {
            "code": 0,
            "message": "success",
            "data": result
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"[Backtest API] 获取回测详情失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取回测详情失败: {str(e)}")


@router.delete("/history/{result_id}", summary="删除回测记录")
async def delete_backtest_history(result_id: int, ctx: AppContext = Depends(get_ctx)):
    """
    删除指定的回测历史记录

    Args:
        result_id: 回测记录ID
    """
    try:
        storage = ctx.storage()
        deleted = await asyncio.to_thread(storage.delete_backtest_result, result_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="回测记录不存在")
        return {
            "code": 0,
            "message": "已删除"
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"[Backtest API] 删除回测记录失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")
