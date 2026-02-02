# 策略注册表和发现模块
# 负责策略的自动发现、注册和管理
# 支持热加载：运行时重新加载策略无需重启服务

import importlib
import importlib.util
import sys
from pathlib import Path
from typing import Dict, Type, List, Optional

from .base import BaseStrategy, _strategy_registry


def discover_strategies() -> int:
    """
    自动发现并加载 strategies 目录下的所有策略模块

    扫描规则：
    - 跳过以 _ 开头的文件（如 __init__.py）
    - 跳过 base.py 和 registry.py
    - 导入模块时，策略类会通过 __init_subclass__ 自动注册

    Returns:
        新加载的策略数量
    """
    strategies_dir = Path(__file__).parent
    skip_modules = {"base", "registry"}
    loaded = 0

    for file in strategies_dir.glob("*.py"):
        if file.name.startswith("_"):
            continue
        if file.stem in skip_modules:
            continue

        try:
            module_name = f"app.strategies.{file.stem}"
            # 检查模块是否已加载
            if module_name not in sys.modules:
                importlib.import_module(f".{file.stem}", package="app.strategies")
                loaded += 1
        except ImportError as e:
            print(f"[警告] 无法加载策略模块 {file.name}: {e}")
        except Exception as e:
            print(f"[错误] 加载策略模块 {file.name} 时发生异常: {e}")

    return loaded


def reload_strategies() -> Dict[str, int]:
    """
    热加载：重新加载所有策略模块

    会清空注册表并重新扫描加载，支持：
    - 更新已有策略的代码
    - 加载新添加的策略文件
    - 移除已删除的策略

    Returns:
        {"reloaded": 重新加载数量, "total": 总策略数}
    """
    strategies_dir = Path(__file__).parent
    skip_modules = {"base", "registry"}
    reloaded = 0

    # 清空注册表（保留引用，清空内容）
    _strategy_registry.clear()

    for file in strategies_dir.glob("*.py"):
        if file.name.startswith("_"):
            continue
        if file.stem in skip_modules:
            continue

        try:
            module_name = f"app.strategies.{file.stem}"

            if module_name in sys.modules:
                # 重新加载已有模块
                module = sys.modules[module_name]
                importlib.reload(module)
            else:
                # 加载新模块
                importlib.import_module(f".{file.stem}", package="app.strategies")

            reloaded += 1
        except Exception as e:
            print(f"[错误] 重新加载策略模块 {file.name} 失败: {e}")

    return {"reloaded": reloaded, "total": len(_strategy_registry)}


def load_external_strategies(path: Path) -> int:
    """
    加载外部策略目录

    Args:
        path: 外部策略目录路径

    Returns:
        成功加载的策略数量
    """
    if not path.exists() or not path.is_dir():
        return 0

    loaded = 0

    # 将目录添加到 Python 路径
    path_str = str(path.resolve())
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

    for file in path.glob("*.py"):
        if file.name.startswith("_"):
            continue

        try:
            # 从文件路径加载模块
            spec = importlib.util.spec_from_file_location(file.stem, file)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                sys.modules[file.stem] = module
                spec.loader.exec_module(module)
                loaded += 1
        except Exception as e:
            print(f"[错误] 加载外部策略 {file.name} 失败: {e}")

    return loaded


def get_strategy(strategy_id: str) -> Optional[Type[BaseStrategy]]:
    """
    根据策略ID获取策略类

    Args:
        strategy_id: 策略唯一标识

    Returns:
        策略类，如果不存在则返回 None
    """
    return _strategy_registry.get(strategy_id)


def list_strategies() -> List[Dict]:
    """
    获取所有已注册策略的元数据列表

    Returns:
        策略元数据列表，每个元素包含 id, name, description, params
    """
    return [cls.get_metadata() for cls in _strategy_registry.values()]


def get_all_strategies() -> Dict[str, Type[BaseStrategy]]:
    """
    获取所有已注册的策略

    Returns:
        策略ID到策略类的映射字典
    """
    return _strategy_registry.copy()


def get_strategy_count() -> int:
    """获取已注册策略数量"""
    return len(_strategy_registry)


def is_strategy_registered(strategy_id: str) -> bool:
    """检查策略是否已注册"""
    return strategy_id in _strategy_registry


def get_strategy_source(strategy_id: str) -> Optional[Dict[str, str]]:
    """
    获取策略的源代码

    Args:
        strategy_id: 策略ID

    Returns:
        {"filename": 文件名, "source": 源代码} 或 None
    """
    strategy_cls = _strategy_registry.get(strategy_id)
    if not strategy_cls:
        return None

    try:
        import inspect
        # 获取策略类所在的模块
        module = inspect.getmodule(strategy_cls)
        if module and hasattr(module, "__file__") and module.__file__:
            filepath = Path(module.__file__)
            if filepath.exists():
                source = filepath.read_text(encoding="utf-8")
                return {
                    "filename": filepath.name,
                    "source": source,
                }
    except Exception as e:
        print(f"[错误] 获取策略源码失败: {e}")

    return None
