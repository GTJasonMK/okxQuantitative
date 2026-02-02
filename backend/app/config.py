# 配置管理模块
# 负责加载和管理应用配置，包括API密钥、数据库路径等

import os
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field
from dotenv import load_dotenv


# 项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent.parent
CONFIG_DIR = BASE_DIR / "config"
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"

# 确保目录存在
DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

# 加载环境变量
load_dotenv(CONFIG_DIR / ".env")


@dataclass
class OKXApiCredentials:
    """OKX API 凭证（单组密钥）"""
    api_key: str = ""
    secret_key: str = ""
    passphrase: str = ""

    def is_valid(self) -> bool:
        """检查凭证是否完整"""
        return all([self.api_key, self.secret_key, self.passphrase])


@dataclass
class OKXConfig:
    """OKX交易所配置（支持模拟盘和实盘两组密钥）"""
    demo: OKXApiCredentials = field(default_factory=OKXApiCredentials)  # 模拟盘
    live: OKXApiCredentials = field(default_factory=OKXApiCredentials)  # 实盘
    use_simulated: bool = True  # True=使用模拟盘, False=使用实盘

    # 兼容旧代码的属性
    @property
    def api_key(self) -> str:
        """获取当前模式的 API Key"""
        return self.demo.api_key if self.use_simulated else self.live.api_key

    @property
    def secret_key(self) -> str:
        """获取当前模式的 Secret Key"""
        return self.demo.secret_key if self.use_simulated else self.live.secret_key

    @property
    def passphrase(self) -> str:
        """获取当前模式的 Passphrase"""
        return self.demo.passphrase if self.use_simulated else self.live.passphrase

    @property
    def is_simulated(self) -> bool:
        """兼容旧代码：是否使用模拟盘"""
        return self.use_simulated

    @is_simulated.setter
    def is_simulated(self, value: bool):
        """兼容旧代码：设置是否使用模拟盘"""
        self.use_simulated = value

    @property
    def flag(self) -> str:
        """获取OKX API的flag参数"""
        return "1" if self.use_simulated else "0"

    def is_valid(self) -> bool:
        """检查当前模式的配置是否有效"""
        if self.use_simulated:
            return self.demo.is_valid()
        return self.live.is_valid()

    def get_current_credentials(self) -> OKXApiCredentials:
        """获取当前模式的凭证"""
        return self.demo if self.use_simulated else self.live


@dataclass
class DatabaseConfig:
    """数据库配置"""
    path: Path = field(default_factory=lambda: DATA_DIR / "market.db")

    @property
    def url(self) -> str:
        """获取SQLAlchemy连接URL"""
        return f"sqlite:///{self.path}"


@dataclass
class APIConfig:
    """API服务配置"""
    host: str = "127.0.0.1"
    port: int = 8000
    debug: bool = True


@dataclass
class CacheConfig:
    """缓存配置"""
    # 缓存最大内存（MB）
    max_memory_mb: int = 100
    # K线缓存条目数（作为备用限制）
    candle_cache_size: int = 10000
    # 同步冷却时间（秒）- 同一交易对/周期在此时间内不重复同步
    sync_cooldown: int = 300
    # Ticker缓存时间（秒）
    ticker_cache_ttl: int = 15
    # OKX API限制（每分钟）
    okx_rate_limit: int = 3000


@dataclass
class StrategyPluginConfig:
    """策略插件配置"""
    # 外部策略目录（用户可放置自定义策略）
    external_dir: Optional[Path] = None


@dataclass
class AppConfig:
    """应用总配置"""
    okx: OKXConfig = field(default_factory=OKXConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    api: APIConfig = field(default_factory=APIConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    strategy: StrategyPluginConfig = field(default_factory=StrategyPluginConfig)

    @classmethod
    def from_env(cls) -> "AppConfig":
        """从环境变量加载配置"""
        # 处理数据库路径（空字符串时使用默认值）
        db_path_str = os.getenv("DATABASE_PATH", "")
        db_path = Path(db_path_str) if db_path_str else DATA_DIR / "market.db"

        # 处理外部策略目录
        ext_strategy_dir = os.getenv("EXTERNAL_STRATEGIES_DIR", "")
        ext_strategy_path = Path(ext_strategy_dir) if ext_strategy_dir else None

        # 加载模拟盘密钥（优先使用新变量名，兼容旧变量名）
        demo_api_key = os.getenv("OKX_DEMO_API_KEY", "")
        demo_secret_key = os.getenv("OKX_DEMO_SECRET_KEY", "")
        demo_passphrase = os.getenv("OKX_DEMO_PASSPHRASE", "")

        # 加载实盘密钥
        live_api_key = os.getenv("OKX_LIVE_API_KEY", "")
        live_secret_key = os.getenv("OKX_LIVE_SECRET_KEY", "")
        live_passphrase = os.getenv("OKX_LIVE_PASSPHRASE", "")

        # 向后兼容：如果旧变量存在且新变量为空，则使用旧变量
        # 旧变量根据 OKX_SIMULATED 决定填充到哪组
        old_api_key = os.getenv("OKX_API_KEY", "")
        old_secret_key = os.getenv("OKX_SECRET_KEY", "")
        old_passphrase = os.getenv("OKX_PASSPHRASE", "")
        old_is_simulated = os.getenv("OKX_SIMULATED", "true").lower() == "true"

        if old_api_key and old_secret_key and old_passphrase:
            if old_is_simulated:
                # 旧配置是模拟盘，填充到 demo
                if not demo_api_key:
                    demo_api_key = old_api_key
                    demo_secret_key = old_secret_key
                    demo_passphrase = old_passphrase
            else:
                # 旧配置是实盘，填充到 live
                if not live_api_key:
                    live_api_key = old_api_key
                    live_secret_key = old_secret_key
                    live_passphrase = old_passphrase

        # 当前使用模式：优先使用新变量名 OKX_USE_SIMULATED，兼容旧变量名 OKX_SIMULATED
        use_simulated_str = os.getenv("OKX_USE_SIMULATED", "")
        if use_simulated_str:
            use_simulated = use_simulated_str.lower() == "true"
        else:
            use_simulated = old_is_simulated

        return cls(
            okx=OKXConfig(
                demo=OKXApiCredentials(
                    api_key=demo_api_key,
                    secret_key=demo_secret_key,
                    passphrase=demo_passphrase,
                ),
                live=OKXApiCredentials(
                    api_key=live_api_key,
                    secret_key=live_secret_key,
                    passphrase=live_passphrase,
                ),
                use_simulated=use_simulated,
            ),
            database=DatabaseConfig(path=db_path),
            api=APIConfig(
                host=os.getenv("API_HOST", "127.0.0.1"),
                port=int(os.getenv("API_PORT", "8000")),
                debug=os.getenv("API_DEBUG", "true").lower() == "true"
            ),
            cache=CacheConfig(
                candle_cache_size=int(os.getenv("CACHE_CANDLE_SIZE", "10000")),
                sync_cooldown=int(os.getenv("CACHE_SYNC_COOLDOWN", "300")),
                ticker_cache_ttl=int(os.getenv("CACHE_TICKER_TTL", "15")),
                okx_rate_limit=int(os.getenv("OKX_RATE_LIMIT", "3000")),
            ),
            strategy=StrategyPluginConfig(
                external_dir=ext_strategy_path,
            )
        )


# 全局配置实例
config = AppConfig.from_env()


# 支持的时间周期
TIMEFRAMES = {
    "1m": "1分钟",
    "3m": "3分钟",
    "5m": "5分钟",
    "15m": "15分钟",
    "30m": "30分钟",
    "1H": "1小时",
    "2H": "2小时",
    "4H": "4小时",
    "6H": "6小时",
    "12H": "12小时",
    "1D": "1天",
    "1W": "1周",
    "1M": "1月",
}

# 支持的交易类型
INST_TYPES = {
    "SPOT": "现货",
    "SWAP": "永续合约",
    "FUTURES": "交割合约",
    "OPTION": "期权",
}

# 常用交易对
DEFAULT_SYMBOLS = [
    "BTC-USDT",
    "ETH-USDT",
    "SOL-USDT",
    "DOGE-USDT",
    "XRP-USDT",
]
