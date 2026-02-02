# FastAPI 主应用入口
# 配置路由、中间件、CORS等

import time
import sys
import os
import asyncio
import platform
import traceback
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .config import config, DATA_DIR, CONFIG_DIR
from .api import market, backtest, trading, live, preferences, websocket
from .core.app_context import get_app_context
from .strategies import discover_strategies, load_external_strategies, get_strategy_count

# 记录启动时间
_start_time = time.time()


def _handle_task_exception(loop, context):
    """处理未捕获的 asyncio Task 异常"""
    exception = context.get("exception")
    message = context.get("message", "")
    task = context.get("task")
    task_name = task.get_name() if task else "unknown"

    # 对于 WebSocket 登录失败，降低日志级别
    if exception:
        error_str = str(exception)
        if "Login failed" in error_str or "4001" in error_str:
            print(f"[WS-Private] 后台任务登录失败，API 密钥可能无效: {error_str}")
            return

    # 其他异常正常打印
    print(f"[AsyncIO] 任务 {task_name} 异常: {message}")
    if exception:
        print(f"  异常详情: {exception}")


def _validate_config():
    """启动时验证配置"""
    warnings = []
    errors = []

    # 检查 OKX API 配置（模拟盘/实盘两组密钥）
    current_mode = "simulated" if config.okx.is_simulated else "live"
    if current_mode == "simulated":
        current_creds = config.okx.demo
        current_envs = "OKX_DEMO_API_KEY/OKX_DEMO_SECRET_KEY/OKX_DEMO_PASSPHRASE"
        current_label = "模拟盘"
    else:
        current_creds = config.okx.live
        current_envs = "OKX_LIVE_API_KEY/OKX_LIVE_SECRET_KEY/OKX_LIVE_PASSPHRASE"
        current_label = "实盘"

    if not current_creds.is_valid():
        warnings.append(f"OKX {current_label} API 密钥未完整配置（{current_envs}），交易/私有 WS 将不可用")

    # 另一套密钥未配置时给出提示：避免用户切换模式后误以为“已配置但不可用”
    if current_mode != "simulated" and not config.okx.demo.is_valid():
        warnings.append("OKX 模拟盘密钥未完整配置（OKX_DEMO_API_KEY/OKX_DEMO_SECRET_KEY/OKX_DEMO_PASSPHRASE）")
    if current_mode != "live" and not config.okx.live.is_valid():
        warnings.append("OKX 实盘密钥未完整配置（OKX_LIVE_API_KEY/OKX_LIVE_SECRET_KEY/OKX_LIVE_PASSPHRASE）")

    # 检查数据目录
    if not DATA_DIR.exists():
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            errors.append(f"无法创建数据目录 {DATA_DIR}: {e}")

    # 检查数据库路径是否可写
    db_path = config.database.path
    db_dir = db_path.parent
    if not db_dir.exists():
        try:
            db_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            errors.append(f"无法创建数据库目录 {db_dir}: {e}")

    # 检查端口范围
    if not (1 <= config.api.port <= 65535):
        errors.append(f"API端口 {config.api.port} 无效，必须在1-65535之间")

    # 检查缓存配置
    if config.cache.candle_cache_size < 10:
        warnings.append(f"K线缓存大小 {config.cache.candle_cache_size} 过小，建议至少100")
    if config.cache.sync_cooldown < 60:
        warnings.append(f"同步冷却时间 {config.cache.sync_cooldown}秒 过短，可能导致频繁同步")

    return warnings, errors


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 设置全局 asyncio 异常处理器
    loop = asyncio.get_event_loop()
    loop.set_exception_handler(_handle_task_exception)

    # 启动时配置验证
    warnings, errors = _validate_config()

    print("=" * 50)
    print("OKX量化交易系统 - 后端服务启动")
    print(f"模式: {'模拟盘' if config.okx.is_simulated else '实盘'}")
    print(f"地址: http://{config.api.host}:{config.api.port}")
    print(f"文档: http://{config.api.host}:{config.api.port}/docs")
    print(f"数据库: {config.database.path}")

    # 加载策略插件
    print("-" * 50)
    print("策略插件加载:")
    discover_strategies()
    print(f"  [+] 内置策略: {get_strategy_count()} 个")

    # 加载外部策略（如果配置了）
    if config.strategy.external_dir:
        ext_count = load_external_strategies(config.strategy.external_dir)
        print(f"  [+] 外部策略: {ext_count} 个 (来自 {config.strategy.external_dir})")

    # 启动 WebSocket 实时行情服务
    print("-" * 50)
    print("WebSocket 服务:")
    try:
        from .core.app_context import get_app_context
        await get_app_context().start_ws()
        print("  [+] OKX WebSocket 连接已建立")
    except Exception as e:
        print(f"  [!] WebSocket 启动失败: {e}")

    # 显示配置警告
    if warnings:
        print("-" * 50)
        print("配置警告:")
        for w in warnings:
            print(f"  [!] {w}")

    # 显示配置错误
    if errors:
        print("-" * 50)
        print("配置错误:")
        for e in errors:
            print(f"  [X] {e}")
        print("请检查配置文件后重新启动")

    print("=" * 50)

    yield

    # 关闭时执行
    print("正在关闭服务...")
    try:
        from .core.app_context import get_app_context
        await get_app_context().stop_ws()
        print("WebSocket 连接已关闭")
    except Exception as e:
        print(f"关闭 WebSocket 失败: {e}")
    print("服务关闭")


# 创建FastAPI应用
app = FastAPI(
    title="OKX量化交易系统",
    description="量化交易策略可视化验证系统API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# 配置CORS（允许Electron前端访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 开发阶段允许所有来源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 全局异常处理器 - 确保即使发生异常也返回正确的JSON响应
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """捕获所有未处理的异常，返回标准JSON错误响应"""
    # HTTPException 应该由 FastAPI 默认处理器处理，不要在这里捕获
    if isinstance(exc, HTTPException):
        raise exc

    error_detail = str(exc)
    print(f"[ERROR] {request.method} {request.url.path}: {error_detail}")
    print(traceback.format_exc())

    return JSONResponse(
        status_code=500,
        content={
            "code": 500,
            "message": "服务器内部错误",
            "detail": error_detail,
        },
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
        }
    )


# 注册路由
app.include_router(market.router, prefix="/api")
app.include_router(backtest.router, prefix="/api")
app.include_router(trading.router)  # trading 路由已带 /api/trading 前缀
app.include_router(live.router)     # live 路由已带 /api/live 前缀
app.include_router(preferences.router)  # preferences 路由已带 /api/preferences 前缀
app.include_router(websocket.router)  # WebSocket 路由 /ws 前缀


# 根路由
@app.get("/", tags=["系统"])
async def root():
    """系统信息"""
    ctx = get_app_context()
    return {
        "name": "OKX量化交易系统",
        "version": "0.1.0",
        "status": "running",
        "mode": ctx.default_mode(),
    }


@app.get("/health", tags=["系统"])
async def health_check():
    """健康检查"""
    return {"status": "healthy"}


def _format_uptime(seconds: float) -> str:
    """格式化运行时间"""
    days = int(seconds // 86400)
    hours = int((seconds % 86400) // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    parts.append(f"{secs}s")
    return " ".join(parts)


def _get_db_size() -> str:
    """获取数据库文件大小"""
    db_path = DATA_DIR / "market.db"
    if db_path.exists():
        size = db_path.stat().st_size
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        else:
            return f"{size / (1024 * 1024):.1f} MB"
    return "0 B"


@app.get("/status", tags=["系统"])
async def system_status():
    """综合系统状态"""
    uptime = time.time() - _start_time
    ctx = get_app_context()
    cfg = ctx.cfg

    # psutil 非硬依赖：缺失时不应导致 /status 接口直接崩溃
    memory_mb = None
    cpu_percent = None
    try:
        import psutil  # type: ignore

        process = psutil.Process(os.getpid())
        mem_info = process.memory_info()
        memory_mb = round(mem_info.rss / (1024 * 1024), 1)
        cpu_percent = process.cpu_percent(interval=0)
    except Exception as e:
        print(f"[Status] psutil 不可用，跳过进程资源统计: {e}")

    # 缓存状态
    cache_info = {"candle_entries": 0, "sync_cooldowns": 0, "ticker_entries": 0}
    try:
        cache_info.update(ctx.manager().get_cache_stats())
        cache_info.update(ctx.fetcher().get_cache_stats())
    except Exception:
        pass

    # 本地数据统计
    data_info = {"symbol_count": 0, "candle_count": 0, "db_size": _get_db_size()}
    try:
        storage = ctx.storage()
        # 数据库读取可能较慢，放到线程池避免阻塞事件循环
        symbols = await asyncio.to_thread(storage.get_available_symbols)
        data_info["symbol_count"] = len(symbols)
        sync_status = await asyncio.to_thread(storage.get_sync_status)
        data_info["candle_count"] = sum(s.get("candle_count", 0) for s in sync_status)
        if sync_status:
            last_sync = max(
                (s.get("last_sync_time") for s in sync_status if s.get("last_sync_time")),
                default=None,
            )
            data_info["last_sync"] = last_sync
    except Exception:
        pass

    # OKX API状态
    okx_info = {
        "api_configured": cfg.okx.is_valid(),
        "mode": ctx.default_mode(),
        "api_accessible": False,
        "data_timestamp": None,
    }
    try:
        f = ctx.fetcher()
        if f.fetcher:
            # 使用带计数的方法获取ticker
            # 可能触发同步网络请求，放到线程池避免阻塞事件循环
            ticker = await asyncio.to_thread(f.get_ticker_cached, "BTC-USDT")
            okx_info["api_accessible"] = ticker is not None
            if ticker:
                okx_info["btc_price"] = ticker.last
                okx_info["data_timestamp"] = ticker.timestamp
    except Exception:
        pass

    # API调用频率统计
    rate_limit_info = {
        "total_calls": 0,
        "calls_per_minute": 0,
        "rate_limit": 3000,
        "remaining_quota": 3000,
        "usage_percent": 0,
    }
    try:
        rate_limit_info = ctx.rate_limiter().get_stats()
    except Exception:
        pass

    return {
        "system": {
            "uptime": _format_uptime(uptime),
            "uptime_seconds": int(uptime),
            "python_version": platform.python_version(),
            "os": f"{platform.system()} {platform.release()}",
            "pid": os.getpid(),
            "memory_mb": memory_mb,
            "cpu_percent": cpu_percent,
        },
        "cache": cache_info,
        "data": data_info,
        "okx": okx_info,
        "rate_limit": rate_limit_info,
    }


class OKXCredentialsRequest(BaseModel):
    """单组 OKX API 凭证"""
    api_key: str = ""
    secret_key: str = ""
    passphrase: str = ""


class OKXConfigRequest(BaseModel):
    """OKX配置请求模型（模拟盘 + 实盘两组密钥）"""
    demo: OKXCredentialsRequest = OKXCredentialsRequest()
    live: OKXCredentialsRequest = OKXCredentialsRequest()
    use_simulated: bool = True


@app.get("/config/okx", tags=["配置"])
async def get_okx_config():
    """获取OKX配置（密钥会被遮蔽）"""
    return {
        "demo": {
            "api_key": _mask_key(config.okx.demo.api_key),
            "secret_key": _mask_key(config.okx.demo.secret_key),
            "passphrase": _mask_key(config.okx.demo.passphrase),
            "is_configured": config.okx.demo.is_valid(),
        },
        "live": {
            "api_key": _mask_key(config.okx.live.api_key),
            "secret_key": _mask_key(config.okx.live.secret_key),
            "passphrase": _mask_key(config.okx.live.passphrase),
            "is_configured": config.okx.live.is_valid(),
        },
        "use_simulated": config.okx.use_simulated,
        "is_configured": config.okx.is_valid(),
    }


def _mask_key(key: str) -> str:
    """遮蔽密钥，只显示前4位和后4位"""
    if not key or len(key) < 10:
        return "*" * len(key) if key else ""
    return key[:4] + "*" * (len(key) - 8) + key[-4:]


@app.post("/config/okx", tags=["配置"])
async def save_okx_config(req: OKXConfigRequest):
    """保存OKX配置到.env文件（支持模拟盘和实盘两组密钥）"""
    env_path = CONFIG_DIR / ".env"

    # 风险控制：实时策略运行中禁止切换密钥/模式。
    # 否则会出现“引擎仍持有旧 trader/account 实例”或“策略状态不匹配新环境”的风险，
    # 在实盘场景可能造成资金损失。
    try:
        from .live import get_live_engine
        if get_live_engine().is_running:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "message": "实时交易引擎运行中，禁止修改 OKX 配置/切换模式。请先在“实时交易”页停止策略后再保存配置。",
                },
            )
    except Exception as e:
        # 不阻塞保存，但记录日志便于排障
        print(f"[Config] 检查实时引擎状态失败: {e}")

    # 读取现有配置（保留注释和原始结构）
    existing_lines = []
    existing_keys = set()
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                existing_lines.append(line.rstrip("\n\r"))
                stripped = line.strip()
                if stripped and not stripped.startswith("#") and "=" in stripped:
                    key = stripped.split("=", 1)[0].strip()
                    existing_keys.add(key)

    # 兼容前端“密钥遮蔽回填/密钥不回填”的行为：
    # - 请求体为空字符串：保留已有配置（避免只切换模式就把密钥清空）
    # - 请求体为遮蔽值（包含 *）：视为“未修改”，保留已有配置（避免无法同时配置模拟盘/实盘）
    def _sanitize_credential(field_name: str, incoming: str, existing: str) -> str:
        s = (incoming or "").strip()
        if not s:
            return existing
        if "*" in s:
            if existing:
                return existing
            raise ValueError(f"{field_name} 为遮蔽值，请输入真实密钥")
        return s

    try:
        demo_api_key = _sanitize_credential("demo.api_key", req.demo.api_key, config.okx.demo.api_key)
        demo_secret_key = _sanitize_credential("demo.secret_key", req.demo.secret_key, config.okx.demo.secret_key)
        demo_passphrase = _sanitize_credential("demo.passphrase", req.demo.passphrase, config.okx.demo.passphrase)

        live_api_key = _sanitize_credential("live.api_key", req.live.api_key, config.okx.live.api_key)
        live_secret_key = _sanitize_credential("live.secret_key", req.live.secret_key, config.okx.live.secret_key)
        live_passphrase = _sanitize_credential("live.passphrase", req.live.passphrase, config.okx.live.passphrase)
    except ValueError as e:
        return JSONResponse(status_code=400, content={"success": False, "message": str(e)})

    # 要更新的OKX配置（新变量名）
    okx_updates = {
        "OKX_DEMO_API_KEY": demo_api_key,
        "OKX_DEMO_SECRET_KEY": demo_secret_key,
        "OKX_DEMO_PASSPHRASE": demo_passphrase,
        "OKX_LIVE_API_KEY": live_api_key,
        "OKX_LIVE_SECRET_KEY": live_secret_key,
        "OKX_LIVE_PASSPHRASE": live_passphrase,
        "OKX_USE_SIMULATED": "true" if req.use_simulated else "false",
    }

    # 清理旧变量名（如果存在则移除）
    old_keys_to_remove = {"OKX_API_KEY", "OKX_SECRET_KEY", "OKX_PASSPHRASE", "OKX_SIMULATED"}

    # 更新现有行或追加新配置
    updated_keys = set()
    new_lines = []
    for line in existing_lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in okx_updates:
                new_lines.append(f"{key}={okx_updates[key]}")
                updated_keys.add(key)
            elif key in old_keys_to_remove:
                # 跳过旧变量名，不再写入
                continue
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)

    # 追加未出现的OKX配置项
    missing_keys = set(okx_updates.keys()) - updated_keys
    if missing_keys:
        if new_lines and new_lines[-1] != "":
            new_lines.append("")
        new_lines.append("# OKX API 配置 - 模拟盘")
        for key in ["OKX_DEMO_API_KEY", "OKX_DEMO_SECRET_KEY", "OKX_DEMO_PASSPHRASE"]:
            if key in missing_keys:
                new_lines.append(f"{key}={okx_updates[key]}")
        new_lines.append("")
        new_lines.append("# OKX API 配置 - 实盘")
        for key in ["OKX_LIVE_API_KEY", "OKX_LIVE_SECRET_KEY", "OKX_LIVE_PASSPHRASE"]:
            if key in missing_keys:
                new_lines.append(f"{key}={okx_updates[key]}")
        if "OKX_USE_SIMULATED" in missing_keys:
            new_lines.append("")
            new_lines.append("# 当前使用模式 (true=模拟盘, false=实盘)")
            new_lines.append(f"OKX_USE_SIMULATED={okx_updates['OKX_USE_SIMULATED']}")

    # 写入文件（保留所有原有配置）
    CONFIG_DIR.mkdir(exist_ok=True)
    with open(env_path, "w", encoding="utf-8") as f:
        f.write("\n".join(new_lines))
        if new_lines:
            f.write("\n")

    # 更新运行时配置
    config.okx.demo.api_key = demo_api_key
    config.okx.demo.secret_key = demo_secret_key
    config.okx.demo.passphrase = demo_passphrase
    config.okx.live.api_key = live_api_key
    config.okx.live.secret_key = live_secret_key
    config.okx.live.passphrase = live_passphrase
    config.okx.use_simulated = req.use_simulated

    # 重新创建 fetcher
    try:
        from .core.cache import CachedDataFetcher
        from .core.data_fetcher import create_fetcher
        fetcher_instance = CachedDataFetcher()
        # 行情数据属于公共接口：始终使用非 Demo 的公共行情环境，避免 Demo 环境缺少部分交易对K线。
        fetcher_instance._fetcher = create_fetcher(is_simulated=False)
    except Exception as e:
        print(f"重新创建fetcher失败: {e}")

    # 重新初始化交易模块（模拟盘和实盘都需要重新初始化）
    try:
        from .core.app_context import get_app_context
        get_app_context().trading_manager().reinit()
    except Exception as e:
        print(f"重新初始化交易模块失败: {e}")

    # 重启 WebSocket 连接（切换模拟盘/实盘需要重连不同服务器）
    try:
        from .core.app_context import get_app_context
        await get_app_context().restart_ws()
    except Exception as e:
        print(f"重启 WebSocket 失败: {e}")

    mode_text = "模拟盘" if req.use_simulated else "实盘"
    return {
        "success": True,
        "message": f"配置已保存并生效（当前模式: {mode_text}）",
    }


@app.post("/config/okx/test", tags=["配置"])
async def test_okx_connection():
    """测试OKX API连接（公共行情 + 私有账户权限）"""
    if not config.okx.is_valid():
        return {
            "success": False,
            "message": "API密钥未配置，请先填写完整的API配置信息",
        }

    try:
        ctx = get_app_context()
        fetcher = ctx.fetcher()

        if not fetcher.fetcher:
            return {
                "success": False,
                "message": "数据获取器初始化失败，请检查API配置",
            }

        # 1. 测试公共接口（行情）- 同步网络调用放到线程池，避免阻塞事件循环
        ticker = await asyncio.to_thread(fetcher.get_ticker, "BTC-USDT")
        if not ticker:
            return {
                "success": False,
                "message": "无法获取行情数据，请检查网络连接",
            }

        # 2. 测试私有接口（账户余额），验证密钥和交易权限
        private_ok = False
        private_msg = ""
        try:
            mode = ctx.default_mode()
            account = ctx.trading_manager().get_account(mode)
            balance = await asyncio.to_thread(account.get_balance)
            if balance is not None and "error" not in balance:
                private_ok = True
            else:
                error_detail = balance.get("error", "未知错误") if balance else "返回空"
                private_msg = f"账户查询失败: {error_detail}"
        except Exception as e:
            private_msg = f"私有接口测试失败: {str(e)}"

        mode_text = "模拟盘" if config.okx.is_simulated else "实盘"
        if private_ok:
            return {
                "success": True,
                "message": f"连接成功！模式: {mode_text}，BTC价格: ${ticker.last:,.2f}，账户权限正常",
                "data": {
                    "btc_price": ticker.last,
                    "mode": mode_text,
                    "private_api": True,
                }
            }
        else:
            return {
                "success": True,
                "message": f"公共接口正常（BTC: ${ticker.last:,.2f}），但{private_msg}",
                "data": {
                    "btc_price": ticker.last,
                    "mode": mode_text,
                    "private_api": False,
                }
            }
    except Exception as e:
        return {
            "success": False,
            "message": f"连接测试失败: {str(e)}",
        }
