# 回测API路由
# 提供策略回测接口（支持统一API和旧式独立端点）

import asyncio
import inspect
import math
from itertools import product
from pathlib import Path
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from ..core.app_context import AppContext
from .deps import get_ctx
from ..strategies import create_dual_ma_strategy, create_grid_strategy
from ..strategies.registry import (
    get_strategy,
    get_strategy_source,
    list_strategies,
    discover_strategies,
    reload_strategies,
    get_all_strategies,
)
from ..backtest import BacktestEngine, BacktestConfig
from ..config import config
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


class BacktestScanRequest(BaseModel):
    """参数扫描请求"""
    symbol: str = Field(default="BTC-USDT", description="交易对")
    inst_type: str = Field(default="SPOT", description="交易类型（SPOT/SWAP等）")
    timeframe: str = Field(default="1H", description="时间周期")
    days: int = Field(default=30, ge=1, le=365, description="回测天数")
    initial_capital: float = Field(default=10000, gt=0, description="初始资金")
    position_size: float = Field(default=0.5, ge=0.1, le=1.0, description="仓位比例")
    stop_loss: float = Field(default=0.05, ge=0, le=0.5, description="止损比例")
    take_profit: float = Field(default=0.10, ge=0, le=1.0, description="止盈比例")
    metric: str = Field(default="total_return", description="排序指标")
    scan_params: Dict[str, List[Any]] = Field(default_factory=dict, description="待扫描参数和值列表")
    base_params: Dict[str, Any] = Field(default_factory=dict, description="固定参数")
    persist_results: bool = Field(default=False, description="是否把每次扫描结果写入历史")


class ExternalStrategyFileRequest(BaseModel):
    """外部策略文件保存请求"""
    filename: str = Field(..., description="文件名，必须以 .py 结尾")
    source: str = Field(default="", description="Python 源码")


def _get_external_strategy_dir() -> Path:
    path = config.strategy.external_dir or (config.database.path.parent.parent / "external_strategies")
    path.mkdir(parents=True, exist_ok=True)
    return path


def _validate_external_strategy_filename(filename: str) -> str:
    safe_name = Path(filename).name
    if safe_name != filename:
        raise HTTPException(status_code=400, detail="文件名不合法，禁止包含路径")
    if not safe_name.endswith(".py"):
        raise HTTPException(status_code=400, detail="外部策略文件必须以 .py 结尾")
    if safe_name.startswith("."):
        raise HTTPException(status_code=400, detail="外部策略文件名不能以 . 开头")
    return safe_name


def _serialize_numeric(value: Any, digits: int = 6) -> Optional[float]:
    """把指标/价格序列安全转成前端可消费的数值。"""
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(numeric) or math.isinf(numeric):
        return None
    return round(numeric, digits)


def _align_indicator_series(values: Any, target_length: int) -> List[Any]:
    """把指标序列长度对齐到 K 线长度，便于前端按索引联动。"""
    if not isinstance(values, list):
        return []

    aligned = list(values)
    if len(aligned) == target_length:
        return aligned
    if len(aligned) > target_length:
        return aligned[-target_length:]
    return [None] * (target_length - len(aligned)) + aligned


def _build_visualization_payload(strategy: Any, candles: List[Any], max_points: int = 1200) -> Dict[str, Any]:
    """
    构建回测可视化数据。

    包含：
    - 采样后的 K 线
    - 与 K 线同采样步长的指标序列
    """
    if not candles:
        return {"candles": [], "indicators": {}, "sample_step": 1}

    sample_step = max(1, math.ceil(len(candles) / max_points))
    sampled_candles = [
        {
            "timestamp": candle.timestamp,
            "open": _serialize_numeric(candle.open, digits=6) or 0.0,
            "high": _serialize_numeric(candle.high, digits=6) or 0.0,
            "low": _serialize_numeric(candle.low, digits=6) or 0.0,
            "close": _serialize_numeric(candle.close, digits=6) or 0.0,
            "volume": _serialize_numeric(candle.volume, digits=4) or 0.0,
        }
        for candle in candles[::sample_step]
    ]

    sampled_indicators: Dict[str, List[Optional[float]]] = {}
    try:
        raw_indicators = strategy.calculate_indicators(candles) or {}
    except Exception as e:
        print(f"[Backtest API] 计算可视化指标失败: {e}")
        raw_indicators = {}

    for key, values in raw_indicators.items():
        aligned_values = _align_indicator_series(values, len(candles))
        if not aligned_values:
            continue
        sampled_indicators[key] = [
            _serialize_numeric(value, digits=6)
            for value in aligned_values[::sample_step]
        ]

    return {
        "candles": sampled_candles,
        "indicators": sampled_indicators,
        "sample_step": sample_step,
    }


def _build_backtest_result_payload(
    result: Any,
    strategy: Any,
    candles: List[Any],
    *,
    strategy_id: str,
    inst_type: str,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """统一补齐回测历史与前端可视化需要的字段。"""
    result_dict = result.to_dict()
    result_dict.update(_build_visualization_payload(strategy, candles))
    result_dict["strategy_id"] = strategy_id
    result_dict["inst_type"] = str(inst_type or "SPOT").upper()
    result_dict["params"] = dict(params or {})
    return result_dict


def _collect_external_strategy_bindings(directory: Path) -> Dict[str, List[str]]:
    bindings: Dict[str, List[str]] = {}
    resolved_dir = directory.resolve()

    for strategy_id, strategy_cls in get_all_strategies().items():
        module = inspect.getmodule(strategy_cls)
        module_file = getattr(module, "__file__", "") if module else ""
        if not module_file:
            continue

        try:
            filepath = Path(module_file).resolve()
        except Exception:
            continue

        if filepath.parent != resolved_dir:
            continue

        bindings.setdefault(filepath.name, []).append(strategy_id)

    for filename in bindings:
        bindings[filename].sort()

    return bindings


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
        result_dict = _build_backtest_result_payload(
            result,
            strategy,
            candles,
            strategy_id="dual_ma",
            inst_type=request.inst_type,
            params={
                "short_period": request.short_period,
                "long_period": request.long_period,
                "use_ema": request.use_ema,
                "stop_loss": request.stop_loss,
                "take_profit": request.take_profit,
                "position_size": request.position_size,
            },
        )
        try:
            storage = ctx.storage()
            # 写库可能较慢，避免阻塞事件循环
            await asyncio.to_thread(
                storage.save_backtest_result,
                result_dict=result_dict,
                strategy_id="dual_ma",
                params=result_dict["params"],
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
        result_dict = _build_backtest_result_payload(
            result,
            strategy,
            candles,
            strategy_id="grid",
            inst_type=request.inst_type,
            params={
                "upper_price": request.upper_price,
                "lower_price": request.lower_price,
                "grid_count": request.grid_count,
                "position_size": request.position_size,
                "grid_type": request.grid_type,
            },
        )
        try:
            storage = ctx.storage()
            # 写库可能较慢，避免阻塞事件循环
            await asyncio.to_thread(
                storage.save_backtest_result,
                result_dict=result_dict,
                strategy_id="grid",
                params=result_dict["params"],
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


@router.get("/external/files", summary="获取外部策略文件列表")
async def list_external_strategy_files():
    """
    获取外部策略目录中的所有 Python 文件。

    返回文件元信息以及已注册到系统中的 strategy_id 列表。
    """
    discover_strategies()

    external_dir = _get_external_strategy_dir()
    bindings = _collect_external_strategy_bindings(external_dir)

    files = []
    for file in sorted(external_dir.glob("*.py")):
        stat = file.stat()
        files.append({
            "filename": file.name,
            "size": stat.st_size,
            "updated_at": int(stat.st_mtime * 1000),
            "strategy_ids": bindings.get(file.name, []),
        })

    return {
        "code": 0,
        "message": "success",
        "data": {
            "directory": str(external_dir),
            "files": files,
        }
    }


@router.get("/external/files/{filename}", summary="读取外部策略文件")
async def get_external_strategy_file(filename: str):
    """
    读取外部策略目录下的指定文件。
    """
    safe_name = _validate_external_strategy_filename(filename)
    external_dir = _get_external_strategy_dir()
    filepath = external_dir / safe_name

    if not filepath.exists() or not filepath.is_file():
        raise HTTPException(status_code=404, detail=f"外部策略文件不存在: {safe_name}")

    bindings = _collect_external_strategy_bindings(external_dir)

    return {
        "code": 0,
        "message": "success",
        "data": {
            "filename": safe_name,
            "source": filepath.read_text(encoding="utf-8"),
            "strategy_ids": bindings.get(safe_name, []),
        }
    }


@router.post("/external/files", summary="保存外部策略文件")
async def save_external_strategy_file(request: ExternalStrategyFileRequest):
    """
    创建或覆盖外部策略文件，并在保存后自动热加载策略注册表。
    """
    safe_name = _validate_external_strategy_filename(request.filename)
    external_dir = _get_external_strategy_dir()
    filepath = external_dir / safe_name

    filepath.write_text(request.source or "", encoding="utf-8")
    reload_result = reload_strategies()
    bindings = _collect_external_strategy_bindings(external_dir)

    return {
        "code": 0,
        "message": f"已保存外部策略文件: {safe_name}",
        "data": {
            "filename": safe_name,
            "strategy_ids": bindings.get(safe_name, []),
            "reload": reload_result,
        }
    }


@router.delete("/external/files/{filename}", summary="删除外部策略文件")
async def delete_external_strategy_file(filename: str):
    """
    删除外部策略目录下的指定文件，并自动刷新策略注册表。
    """
    safe_name = _validate_external_strategy_filename(filename)
    external_dir = _get_external_strategy_dir()
    filepath = external_dir / safe_name

    if not filepath.exists() or not filepath.is_file():
        raise HTTPException(status_code=404, detail=f"外部策略文件不存在: {safe_name}")

    filepath.unlink()
    reload_result = reload_strategies()

    return {
        "code": 0,
        "message": f"已删除外部策略文件: {safe_name}",
        "data": {
            "filename": safe_name,
            "reload": reload_result,
        }
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
        result_dict = _build_backtest_result_payload(
            result,
            strategy,
            candles,
            strategy_id=strategy_id,
            inst_type=request.inst_type,
            params={
                **request.params,
                "stop_loss": request.stop_loss,
                "take_profit": request.take_profit,
                "position_size": request.position_size,
            },
        )
        try:
            storage = ctx.storage()
            await asyncio.to_thread(
                storage.save_backtest_result,
                result_dict=result_dict,
                strategy_id=strategy_id,
                params=result_dict["params"],
            )
        except Exception as e:
            print(f"[Backtest API] 保存回测结果失败: {e}")

        return BacktestResponse(data=result_dict)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"回测执行失败: {str(e)}")


@router.post("/scan/{strategy_id}", response_model=BacktestResponse, summary="策略参数扫描")
async def scan_strategy_parameters(
    strategy_id: str,
    request: BacktestScanRequest,
    ctx: AppContext = Depends(get_ctx)
):
    """
    对策略参数做批量扫描，返回不同参数组合下的关键绩效指标。

    用途：
    - 给前端热力图提供数据源
    - 快速挑选收益率 / 夏普比等指标更优的参数组合
    """
    discover_strategies()

    if not request.scan_params:
        raise HTTPException(status_code=400, detail="scan_params 不能为空")

    strategy_cls = get_strategy(strategy_id)
    if not strategy_cls:
        raise HTTPException(status_code=404, detail=f"策略不存在: {strategy_id}")

    normalized_scan_params: Dict[str, List[Any]] = {}
    total_combinations = 1

    for name, values in request.scan_params.items():
        if not isinstance(values, list) or len(values) < 2:
            raise HTTPException(status_code=400, detail=f"扫描参数 {name} 至少需要 2 个候选值")

        unique_values = []
        seen = set()
        for value in values:
            marker = repr(value)
            if marker in seen:
                continue
            seen.add(marker)
            unique_values.append(value)

        normalized_scan_params[name] = unique_values
        total_combinations *= len(unique_values)

    if total_combinations > 120:
        raise HTTPException(status_code=400, detail=f"参数组合过多（{total_combinations}），请控制在 120 组以内")

    metric = (request.metric or "total_return").strip()
    metric_preference = {
        "total_return": "desc",
        "annual_return": "desc",
        "sharpe_ratio": "desc",
        "sortino_ratio": "desc",
        "calmar_ratio": "desc",
        "win_rate": "desc",
        "profit_factor": "desc",
        "max_drawdown": "asc",
        "total_trades": "desc",
    }
    if metric not in metric_preference:
        raise HTTPException(status_code=400, detail=f"不支持的 metric: {metric}")

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

    if len(candles) < 20:
        raise HTTPException(status_code=400, detail="K线数据不足，至少需要 20 根")

    storage = ctx.storage()
    scan_results: List[Dict[str, Any]] = []
    ordered_items = list(normalized_scan_params.items())
    scan_keys = [item[0] for item in ordered_items]
    scan_value_groups = [item[1] for item in ordered_items]

    for combo_values in product(*scan_value_groups):
        combo_params = dict(request.base_params)
        combo_params.update(dict(zip(scan_keys, combo_values)))

        try:
            strategy_cls.validate_params(combo_params)
        except Exception as e:
            scan_results.append({
                "params": combo_params,
                "error": f"参数验证失败: {str(e)}",
            })
            continue

        strategy = strategy_cls.create_instance(
            symbol=request.symbol,
            timeframe=request.timeframe,
            initial_capital=request.initial_capital,
            position_size=request.position_size,
            stop_loss=request.stop_loss,
            take_profit=request.take_profit,
            inst_type=request.inst_type,
            **combo_params,
        )

        engine = BacktestEngine()

        try:
            result = await asyncio.to_thread(engine.run, strategy, candles)
            result_dict = result.to_dict()
            entry = {
                "params": combo_params,
                "metrics": {
                    "total_return": result_dict.get("total_return", 0),
                    "annual_return": result_dict.get("annual_return", 0),
                    "max_drawdown": result_dict.get("max_drawdown", 0),
                    "sharpe_ratio": result_dict.get("sharpe_ratio", 0),
                    "sortino_ratio": result_dict.get("sortino_ratio", 0),
                    "calmar_ratio": result_dict.get("calmar_ratio", 0),
                    "win_rate": result_dict.get("win_rate", 0),
                    "profit_factor": result_dict.get("profit_factor", 0),
                    "total_trades": result_dict.get("total_trades", 0),
                    "final_capital": result_dict.get("final_capital", request.initial_capital),
                },
                "score": result_dict.get(metric, 0),
            }
            scan_results.append(entry)

            if request.persist_results:
                persisted_result_dict = _build_backtest_result_payload(
                    result,
                    strategy,
                    candles,
                    strategy_id=strategy_id,
                    inst_type=request.inst_type,
                    params={
                        **combo_params,
                        "stop_loss": request.stop_loss,
                        "take_profit": request.take_profit,
                        "position_size": request.position_size,
                    },
                )
                await asyncio.to_thread(
                    storage.save_backtest_result,
                    result_dict=persisted_result_dict,
                    strategy_id=strategy_id,
                    params=persisted_result_dict["params"],
                )
        except Exception as e:
            scan_results.append({
                "params": combo_params,
                "error": f"回测执行失败: {str(e)}",
            })

    valid_results = [item for item in scan_results if not item.get("error")]
    reverse = metric_preference[metric] == "desc"
    ranked_results = sorted(valid_results, key=lambda item: item.get("score", 0), reverse=reverse)

    heatmap = []
    if len(scan_keys) >= 2:
        x_key, y_key = scan_keys[:2]
        x_values = normalized_scan_params[x_key]
        y_values = normalized_scan_params[y_key]
        for item in valid_results:
            x_value = item["params"].get(x_key)
            y_value = item["params"].get(y_key)
            if x_value in x_values and y_value in y_values:
                heatmap.append([
                    x_values.index(x_value),
                    y_values.index(y_value),
                    item["metrics"].get(metric, 0),
                ])
    else:
        x_key = scan_keys[0]
        x_values = normalized_scan_params[x_key]
        y_key = ""
        y_values = []
        for item in valid_results:
            x_value = item["params"].get(x_key)
            if x_value in x_values:
                heatmap.append([
                    x_values.index(x_value),
                    0,
                    item["metrics"].get(metric, 0),
                ])

    return BacktestResponse(data={
        "strategy_id": strategy_id,
        "symbol": request.symbol,
        "timeframe": request.timeframe,
        "inst_type": request.inst_type,
        "metric": metric,
        "scan_keys": scan_keys,
        "scan_values": normalized_scan_params,
        "total_combinations": total_combinations,
        "completed": len(valid_results),
        "failed": len(scan_results) - len(valid_results),
        "results": ranked_results,
        "best_result": ranked_results[0] if ranked_results else None,
        "heatmap": {
            "x_key": x_key,
            "x_values": x_values,
            "y_key": y_key,
            "y_values": y_values,
            "points": heatmap,
        },
        "errors": [item for item in scan_results if item.get("error")][:20],
    })


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
