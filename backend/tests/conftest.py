import asyncio

import pytest


@pytest.fixture(autouse=True)
def _avoid_asyncio_default_executor_hang(monkeypatch):
    """
    在当前运行环境中，asyncio.to_thread() 会创建默认线程池；
    pytest/asyncio 在关闭事件循环时可能卡在 shutdown_default_executor。

    单元测试里我们把 to_thread 改为“同步执行并立即返回”，避免测试进程挂死。
    """

    async def _to_thread(func, /, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setattr(asyncio, 'to_thread', _to_thread, raising=True)
