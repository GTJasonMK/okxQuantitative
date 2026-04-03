# 交易日志存储混入
# 提供日志条目和标签的 CRUD 操作

import json
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class StorageJournalMixin:
    """交易日志存储，管理日志条目与标签。"""

    def save_journal_entry(self, entry: Dict[str, Any]) -> str:
        """
        创建或更新日志条目。

        Args:
            entry: 日志数据字典

        Returns:
            entry_id
        """
        entry_id = entry.get("entry_id") or f"je_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()

        with self._get_cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO journal_entries (
                    entry_id, title, content, mode, inst_id, inst_type,
                    trade_ids_json, order_ids_json, tags_json,
                    strategy_id, strategy_name, rating, emotion,
                    screenshots_json, pnl_snapshot, metadata_json,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(entry_id) DO UPDATE SET
                    title = excluded.title,
                    content = excluded.content,
                    mode = excluded.mode,
                    inst_id = excluded.inst_id,
                    inst_type = excluded.inst_type,
                    trade_ids_json = excluded.trade_ids_json,
                    order_ids_json = excluded.order_ids_json,
                    tags_json = excluded.tags_json,
                    strategy_id = excluded.strategy_id,
                    strategy_name = excluded.strategy_name,
                    rating = excluded.rating,
                    emotion = excluded.emotion,
                    screenshots_json = excluded.screenshots_json,
                    pnl_snapshot = excluded.pnl_snapshot,
                    metadata_json = excluded.metadata_json,
                    updated_at = excluded.updated_at
                """,
                (
                    entry_id,
                    entry.get("title", ""),
                    entry.get("content", ""),
                    entry.get("mode", "simulated"),
                    entry.get("inst_id", ""),
                    entry.get("inst_type", "SPOT"),
                    json.dumps(entry.get("trade_ids", []), ensure_ascii=False),
                    json.dumps(entry.get("order_ids", []), ensure_ascii=False),
                    json.dumps(entry.get("tags", []), ensure_ascii=False),
                    entry.get("strategy_id", ""),
                    entry.get("strategy_name", ""),
                    entry.get("rating", 0),
                    entry.get("emotion", ""),
                    json.dumps(entry.get("screenshots", []), ensure_ascii=False),
                    entry.get("pnl_snapshot", 0.0),
                    json.dumps(entry.get("metadata", {}), ensure_ascii=False),
                    entry.get("created_at", now),
                    now,
                ),
            )

            # 更新标签使用计数
            tags = entry.get("tags", [])
            for tag in tags:
                if not tag:
                    continue
                cursor.execute(
                    """
                    INSERT INTO journal_tags (tag, usage_count, created_at)
                    VALUES (?, 1, CURRENT_TIMESTAMP)
                    ON CONFLICT(tag) DO UPDATE SET
                        usage_count = journal_tags.usage_count + 1
                    """,
                    (tag,),
                )

        return entry_id

    def update_journal_entry(self, entry_id: str, updates: Dict[str, Any]) -> bool:
        """更新日志条目的部分字段。"""
        allowed_fields = {
            "title", "content", "mode", "inst_id", "inst_type",
            "strategy_id", "strategy_name", "rating", "emotion",
            "pnl_snapshot",
        }
        json_fields = {
            "trade_ids": "trade_ids_json",
            "order_ids": "order_ids_json",
            "tags": "tags_json",
            "screenshots": "screenshots_json",
            "metadata": "metadata_json",
        }

        set_clauses = ["updated_at = ?"]
        params: List[Any] = [datetime.now(timezone.utc).isoformat()]

        for key, value in updates.items():
            if key in allowed_fields:
                set_clauses.append(f"{key} = ?")
                params.append(value)
            elif key in json_fields:
                set_clauses.append(f"{json_fields[key]} = ?")
                params.append(json.dumps(value, ensure_ascii=False))

        if len(set_clauses) <= 1:
            return False

        params.append(entry_id)
        query = f"UPDATE journal_entries SET {', '.join(set_clauses)} WHERE entry_id = ?"

        with self._get_cursor() as cursor:
            cursor.execute(query, params)
            return cursor.rowcount > 0

    def delete_journal_entry(self, entry_id: str) -> bool:
        """删除日志条目。"""
        with self._get_cursor() as cursor:
            cursor.execute(
                "DELETE FROM journal_entries WHERE entry_id = ?",
                (entry_id,),
            )
            return cursor.rowcount > 0

    def get_journal_entry(self, entry_id: str) -> Optional[Dict[str, Any]]:
        """获取单条日志。"""
        with self._get_cursor() as cursor:
            cursor.execute(
                "SELECT * FROM journal_entries WHERE entry_id = ?",
                (entry_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_journal_entry(row)

    def get_journal_entries(
        self,
        mode: str = "",
        inst_id: str = "",
        tags: Optional[List[str]] = None,
        strategy_id: str = "",
        date_from: str = "",
        date_to: str = "",
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """查询日志列表，支持多维度筛选。"""
        conditions: List[str] = []
        params: List[Any] = []

        if mode:
            conditions.append("mode = ?")
            params.append(mode)
        if inst_id:
            conditions.append("inst_id = ?")
            params.append(inst_id)
        if strategy_id:
            conditions.append("strategy_id = ?")
            params.append(strategy_id)
        if date_from:
            conditions.append("created_at >= ?")
            params.append(date_from)
        if date_to:
            conditions.append("created_at <= ?")
            params.append(date_to)
        if tags:
            # 按标签筛选：任意匹配
            tag_conditions = []
            for tag in tags:
                tag_conditions.append("tags_json LIKE ?")
                params.append(f'%"{tag}"%')
            conditions.append(f"({' OR '.join(tag_conditions)})")

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        query = f"""
            SELECT * FROM journal_entries
            {where}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])

        entries: List[Dict[str, Any]] = []
        with self._get_cursor() as cursor:
            cursor.execute(query, params)
            for row in cursor.fetchall():
                entries.append(self._row_to_journal_entry(row))
        return entries

    def get_journal_entries_count(
        self,
        mode: str = "",
        inst_id: str = "",
        tags: Optional[List[str]] = None,
        strategy_id: str = "",
        date_from: str = "",
        date_to: str = "",
    ) -> int:
        """获取符合条件的日志总数。"""
        conditions: List[str] = []
        params: List[Any] = []

        if mode:
            conditions.append("mode = ?")
            params.append(mode)
        if inst_id:
            conditions.append("inst_id = ?")
            params.append(inst_id)
        if strategy_id:
            conditions.append("strategy_id = ?")
            params.append(strategy_id)
        if date_from:
            conditions.append("created_at >= ?")
            params.append(date_from)
        if date_to:
            conditions.append("created_at <= ?")
            params.append(date_to)
        if tags:
            tag_conditions = []
            for tag in tags:
                tag_conditions.append("tags_json LIKE ?")
                params.append(f'%"{tag}"%')
            conditions.append(f"({' OR '.join(tag_conditions)})")

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        query = f"SELECT COUNT(*) AS cnt FROM journal_entries {where}"

        with self._get_cursor() as cursor:
            cursor.execute(query, params)
            row = cursor.fetchone()
            return row["cnt"] if row else 0

    def get_journal_tags(self) -> List[Dict[str, Any]]:
        """获取所有标签及使用计数。"""
        tags: List[Dict[str, Any]] = []
        with self._get_cursor() as cursor:
            cursor.execute(
                "SELECT tag, color, usage_count, created_at FROM journal_tags ORDER BY usage_count DESC"
            )
            for row in cursor.fetchall():
                tags.append({
                    "tag": row["tag"],
                    "color": row["color"],
                    "usage_count": row["usage_count"],
                    "created_at": row["created_at"],
                })
        return tags

    def get_journal_stats(
        self,
        mode: str = "",
        group_by: str = "tag",
    ) -> Dict[str, Any]:
        """
        按标签或策略统计日志绩效。

        Args:
            mode: 交易模式筛选
            group_by: 'tag' 或 'strategy'

        Returns:
            统计结果
        """
        conditions: List[str] = []
        params: List[Any] = []
        if mode:
            conditions.append("mode = ?")
            params.append(mode)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        query = f"SELECT * FROM journal_entries {where} ORDER BY created_at ASC"

        entries: List[Dict[str, Any]] = []
        with self._get_cursor() as cursor:
            cursor.execute(query, params)
            for row in cursor.fetchall():
                entries.append(self._row_to_journal_entry(row))

        if group_by == "strategy":
            return self._stats_by_field(entries, "strategy_id")
        return self._stats_by_tags(entries)

    # ------ 内部辅助方法 ------

    @staticmethod
    def _row_to_journal_entry(row) -> Dict[str, Any]:
        """将数据库行转换为字典。"""
        return {
            "entry_id": row["entry_id"],
            "title": row["title"],
            "content": row["content"],
            "mode": row["mode"],
            "inst_id": row["inst_id"],
            "inst_type": row["inst_type"],
            "trade_ids": json.loads(row["trade_ids_json"] or "[]"),
            "order_ids": json.loads(row["order_ids_json"] or "[]"),
            "tags": json.loads(row["tags_json"] or "[]"),
            "strategy_id": row["strategy_id"],
            "strategy_name": row["strategy_name"],
            "rating": row["rating"],
            "emotion": row["emotion"],
            "screenshots": json.loads(row["screenshots_json"] or "[]"),
            "pnl_snapshot": row["pnl_snapshot"],
            "metadata": json.loads(row["metadata_json"] or "{}"),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    @staticmethod
    def _stats_by_tags(entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """按标签分组统计。"""
        buckets: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "count": 0,
            "total_pnl": 0.0,
            "positive": 0,
            "negative": 0,
            "avg_rating": 0.0,
            "ratings_sum": 0,
        })

        for entry in entries:
            tags = entry.get("tags") or ["未标记"]
            pnl = float(entry.get("pnl_snapshot", 0) or 0)
            rating = int(entry.get("rating", 0) or 0)
            for tag in tags:
                b = buckets[tag]
                b["count"] += 1
                b["total_pnl"] += pnl
                if pnl > 0:
                    b["positive"] += 1
                elif pnl < 0:
                    b["negative"] += 1
                b["ratings_sum"] += rating

        groups = []
        for tag, b in buckets.items():
            groups.append({
                "key": tag,
                "count": b["count"],
                "total_pnl": round(b["total_pnl"], 2),
                "win_rate": round(b["positive"] / b["count"] * 100, 2) if b["count"] else 0,
                "avg_rating": round(b["ratings_sum"] / b["count"], 1) if b["count"] else 0,
            })

        groups.sort(key=lambda x: x["count"], reverse=True)
        return {"group_by": "tag", "groups": groups, "total_entries": len(entries)}

    @staticmethod
    def _stats_by_field(entries: List[Dict[str, Any]], field: str) -> Dict[str, Any]:
        """按单个字段分组统计。"""
        buckets: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "count": 0,
            "total_pnl": 0.0,
            "positive": 0,
            "negative": 0,
        })

        for entry in entries:
            key = entry.get(field) or "未知"
            pnl = float(entry.get("pnl_snapshot", 0) or 0)
            b = buckets[key]
            b["count"] += 1
            b["total_pnl"] += pnl
            if pnl > 0:
                b["positive"] += 1
            elif pnl < 0:
                b["negative"] += 1

        groups = []
        for key, b in buckets.items():
            groups.append({
                "key": key,
                "count": b["count"],
                "total_pnl": round(b["total_pnl"], 2),
                "win_rate": round(b["positive"] / b["count"] * 100, 2) if b["count"] else 0,
            })

        groups.sort(key=lambda x: x["count"], reverse=True)
        return {"group_by": field, "groups": groups, "total_entries": len(entries)}
