# 扫描方案存储混入
# 持久化扫描方案和扫描结果

import json
from typing import Any, Dict, List, Optional


class StorageScannerMixin:
    """扫描器存储，管理扫描方案和历史结果。"""

    def save_scanner_profile(self, profile: Dict[str, Any]) -> str:
        """保存或更新扫描方案。"""
        profile_id = profile.get("profile_id", "")
        if not profile_id:
            import uuid
            profile_id = f"sp_{uuid.uuid4().hex[:12]}"

        with self._get_cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO scanner_profiles
                    (profile_id, name, conditions_json, logic, symbols_json,
                     timeframe, inst_type, enabled, interval_seconds,
                     created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(profile_id) DO UPDATE SET
                    name = excluded.name,
                    conditions_json = excluded.conditions_json,
                    logic = excluded.logic,
                    symbols_json = excluded.symbols_json,
                    timeframe = excluded.timeframe,
                    inst_type = excluded.inst_type,
                    enabled = excluded.enabled,
                    interval_seconds = excluded.interval_seconds,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    profile_id,
                    profile.get("name", ""),
                    json.dumps(profile.get("conditions", []), ensure_ascii=False),
                    profile.get("logic", "and"),
                    json.dumps(profile.get("symbols", []), ensure_ascii=False),
                    profile.get("timeframe", "1H"),
                    profile.get("inst_type", "SPOT"),
                    1 if profile.get("enabled", True) else 0,
                    profile.get("interval_seconds", 300),
                ),
            )
        return profile_id

    def get_scanner_profiles(self) -> List[Dict[str, Any]]:
        """获取所有扫描方案。"""
        profiles: List[Dict[str, Any]] = []
        with self._get_cursor() as cursor:
            cursor.execute(
                "SELECT * FROM scanner_profiles ORDER BY updated_at DESC"
            )
            for row in cursor.fetchall():
                profiles.append(self._row_to_scanner_profile(row))
        return profiles

    def get_scanner_profile(self, profile_id: str) -> Optional[Dict[str, Any]]:
        """获取单个扫描方案。"""
        with self._get_cursor() as cursor:
            cursor.execute(
                "SELECT * FROM scanner_profiles WHERE profile_id = ?",
                (profile_id,),
            )
            row = cursor.fetchone()
            return self._row_to_scanner_profile(row) if row else None

    def delete_scanner_profile(self, profile_id: str) -> bool:
        """删除扫描方案及其历史结果。"""
        with self._get_cursor() as cursor:
            cursor.execute(
                "DELETE FROM scanner_profiles WHERE profile_id = ?",
                (profile_id,),
            )
            deleted = cursor.rowcount > 0
            cursor.execute(
                "DELETE FROM scanner_results WHERE profile_id = ?",
                (profile_id,),
            )
            return deleted

    def save_scanner_results(
        self,
        profile_id: str,
        results: List[Dict[str, Any]],
    ) -> int:
        """批量保存扫描结果。"""
        count = 0
        with self._get_cursor() as cursor:
            for r in results:
                cursor.execute(
                    """
                    INSERT INTO scanner_results
                        (profile_id, inst_id, inst_type, timeframe,
                         matched_conditions_json, indicator_values_json,
                         price, scan_time)
                    VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                    (
                        profile_id,
                        r.get("inst_id", ""),
                        r.get("inst_type", "SPOT"),
                        r.get("timeframe", "1H"),
                        json.dumps(r.get("matched_conditions", []), ensure_ascii=False),
                        json.dumps(r.get("indicator_values", {}), ensure_ascii=False),
                        r.get("price", 0.0),
                    ),
                )
                count += 1
        return count

    def get_scanner_results(
        self,
        profile_id: str = "",
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """获取扫描历史结果。"""
        results: List[Dict[str, Any]] = []
        if profile_id:
            query = "SELECT * FROM scanner_results WHERE profile_id = ? ORDER BY scan_time DESC LIMIT ?"
            params = (profile_id, limit)
        else:
            query = "SELECT * FROM scanner_results ORDER BY scan_time DESC LIMIT ?"
            params = (limit,)

        with self._get_cursor() as cursor:
            cursor.execute(query, params)
            for row in cursor.fetchall():
                results.append({
                    "id": row["id"],
                    "profile_id": row["profile_id"],
                    "inst_id": row["inst_id"],
                    "inst_type": row["inst_type"],
                    "timeframe": row["timeframe"],
                    "matched_conditions": json.loads(row["matched_conditions_json"] or "[]"),
                    "indicator_values": json.loads(row["indicator_values_json"] or "{}"),
                    "price": row["price"],
                    "scan_time": row["scan_time"],
                })
        return results

    @staticmethod
    def _row_to_scanner_profile(row) -> Dict[str, Any]:
        return {
            "profile_id": row["profile_id"],
            "name": row["name"],
            "conditions": json.loads(row["conditions_json"] or "[]"),
            "logic": row["logic"],
            "symbols": json.loads(row["symbols_json"] or "[]"),
            "timeframe": row["timeframe"],
            "inst_type": row["inst_type"],
            "enabled": bool(row["enabled"]),
            "interval_seconds": row["interval_seconds"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
