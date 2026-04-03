# 交易日志 API
# 提供日志条目的 CRUD 和统计接口

import asyncio
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from ..core.app_context import get_app_context
from ..models.schemas import JournalEntryCreate, JournalEntryUpdate

router = APIRouter(prefix="/api/journal", tags=["journal"])


def _get_storage():
    ctx = get_app_context()
    return ctx.storage


# ==================== 日志条目 CRUD ====================


@router.post("/entries")
async def create_journal_entry(body: JournalEntryCreate):
    """创建交易日志条目"""
    storage = _get_storage()
    entry_id = await asyncio.to_thread(
        storage.save_journal_entry, body.model_dump()
    )
    entry = await asyncio.to_thread(storage.get_journal_entry, entry_id)
    return {"success": True, "data": entry}


@router.get("/entries")
async def list_journal_entries(
    mode: str = Query("", description="交易模式筛选"),
    inst_id: str = Query("", description="交易对筛选"),
    tags: Optional[str] = Query(None, description="标签筛选，逗号分隔"),
    strategy_id: str = Query("", description="策略ID筛选"),
    date_from: str = Query("", description="开始日期 YYYY-MM-DD"),
    date_to: str = Query("", description="结束日期 YYYY-MM-DD"),
    limit: int = Query(50, ge=1, le=200, description="每页数量"),
    offset: int = Query(0, ge=0, description="偏移量"),
):
    """查询日志列表，支持多维度筛选"""
    storage = _get_storage()
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None

    entries = await asyncio.to_thread(
        storage.get_journal_entries,
        mode=mode,
        inst_id=inst_id,
        tags=tag_list,
        strategy_id=strategy_id,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    total = await asyncio.to_thread(
        storage.get_journal_entries_count,
        mode=mode,
        inst_id=inst_id,
        tags=tag_list,
        strategy_id=strategy_id,
        date_from=date_from,
        date_to=date_to,
    )
    return {"success": True, "data": entries, "total": total}


@router.get("/entries/{entry_id}")
async def get_journal_entry(entry_id: str):
    """获取单条日志"""
    storage = _get_storage()
    entry = await asyncio.to_thread(storage.get_journal_entry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="日志条目不存在")
    return {"success": True, "data": entry}


@router.put("/entries/{entry_id}")
async def update_journal_entry(entry_id: str, body: JournalEntryUpdate):
    """更新日志条目"""
    storage = _get_storage()
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="无更新内容")
    ok = await asyncio.to_thread(storage.update_journal_entry, entry_id, updates)
    if not ok:
        raise HTTPException(status_code=404, detail="日志条目不存在")
    entry = await asyncio.to_thread(storage.get_journal_entry, entry_id)
    return {"success": True, "data": entry}


@router.delete("/entries/{entry_id}")
async def delete_journal_entry(entry_id: str):
    """删除日志条目"""
    storage = _get_storage()
    ok = await asyncio.to_thread(storage.delete_journal_entry, entry_id)
    if not ok:
        raise HTTPException(status_code=404, detail="日志条目不存在")
    return {"success": True, "message": "日志已删除"}


# ==================== 标签管理 ====================


@router.get("/tags")
async def list_journal_tags():
    """获取所有标签及使用计数"""
    storage = _get_storage()
    tags = await asyncio.to_thread(storage.get_journal_tags)
    return {"success": True, "data": tags}


# ==================== 统计分析 ====================


@router.get("/stats")
async def get_journal_stats(
    mode: str = Query("", description="交易模式筛选"),
    group_by: str = Query("tag", description="分组维度: tag / strategy"),
):
    """按标签或策略统计日志绩效"""
    storage = _get_storage()
    stats = await asyncio.to_thread(
        storage.get_journal_stats, mode=mode, group_by=group_by
    )
    return {"success": True, "data": stats}
