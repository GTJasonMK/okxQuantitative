import json
import uuid
from typing import Any, Dict, List, Optional


class StorageAssistantMixin:
    def create_assistant_session(
        self,
        *,
        title: str = "",
        kind: str = "agent",
        mode: str = "simulated",
        inst_id: str = "",
        inst_type: str = "SPOT",
        status: str = "active",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        session_id = uuid.uuid4().hex
        metadata_json = json.dumps(metadata or {}, ensure_ascii=False)

        query = """
            INSERT INTO assistant_sessions (
                session_id, title, kind, mode, inst_id, inst_type, status, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        with self._get_cursor() as cursor:
            cursor.execute(
                query,
                (
                    session_id,
                    (title or "").strip(),
                    (kind or "agent").strip() or "agent",
                    (mode or "simulated").strip() or "simulated",
                    (inst_id or "").strip(),
                    (inst_type or "SPOT").strip() or "SPOT",
                    (status or "active").strip() or "active",
                    metadata_json,
                ),
            )
        return session_id

    def update_assistant_session(
        self,
        session_id: str,
        *,
        title: Optional[str] = None,
        status: Optional[str] = None,
        last_error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        updates: List[str] = []
        params: List[Any] = []

        if title is not None:
            updates.append("title = ?")
            params.append((title or "").strip())
        if status is not None:
            updates.append("status = ?")
            params.append((status or "").strip())
        if last_error is not None:
            updates.append("last_error = ?")
            params.append((last_error or "").strip())
        if metadata is not None:
            updates.append("metadata_json = ?")
            params.append(json.dumps(metadata, ensure_ascii=False))

        if not updates:
            return False

        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(session_id)

        query = f"""
            UPDATE assistant_sessions
            SET {", ".join(updates)}
            WHERE session_id = ?
        """
        with self._get_cursor() as cursor:
            cursor.execute(query, params)
            return cursor.rowcount > 0

    def append_assistant_message(
        self,
        session_id: str,
        *,
        role: str,
        content: str = "",
        tool_name: str = "",
        tool_call_id: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        metadata_json = json.dumps(metadata or {}, ensure_ascii=False)
        query = """
            INSERT INTO assistant_messages (
                session_id, role, content, tool_name, tool_call_id, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?)
        """
        with self._get_cursor() as cursor:
            cursor.execute(
                query,
                (
                    session_id,
                    (role or "user").strip() or "user",
                    content or "",
                    (tool_name or "").strip(),
                    (tool_call_id or "").strip(),
                    metadata_json,
                ),
            )
            cursor.execute(
                """
                UPDATE assistant_sessions
                SET updated_at = CURRENT_TIMESTAMP
                WHERE session_id = ?
                """,
                (session_id,),
            )
            return cursor.lastrowid

    def append_assistant_step(
        self,
        session_id: str,
        *,
        step_index: int,
        step_type: str,
        title: str,
        status: str = "completed",
        tool_name: str = "",
        input_payload: Optional[Dict[str, Any]] = None,
        output_payload: Optional[Dict[str, Any]] = None,
        error_text: str = "",
    ) -> int:
        query = """
            INSERT INTO assistant_steps (
                session_id, step_index, step_type, title, status, tool_name,
                input_json, output_json, error_text
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        with self._get_cursor() as cursor:
            cursor.execute(
                query,
                (
                    session_id,
                    max(int(step_index), 1),
                    (step_type or "tool").strip() or "tool",
                    (title or "").strip(),
                    (status or "completed").strip() or "completed",
                    (tool_name or "").strip(),
                    json.dumps(input_payload or {}, ensure_ascii=False),
                    json.dumps(output_payload or {}, ensure_ascii=False),
                    error_text or "",
                ),
            )
            cursor.execute(
                """
                UPDATE assistant_sessions
                SET updated_at = CURRENT_TIMESTAMP
                WHERE session_id = ?
                """,
                (session_id,),
            )
            return cursor.lastrowid

    def update_assistant_step(
        self,
        step_id: int,
        *,
        title: Optional[str] = None,
        status: Optional[str] = None,
        tool_name: Optional[str] = None,
        input_payload: Optional[Dict[str, Any]] = None,
        output_payload: Optional[Dict[str, Any]] = None,
        error_text: Optional[str] = None,
    ) -> bool:
        updates: List[str] = []
        params: List[Any] = []

        if title is not None:
            updates.append("title = ?")
            params.append((title or "").strip())
        if status is not None:
            updates.append("status = ?")
            params.append((status or "").strip() or "completed")
        if tool_name is not None:
            updates.append("tool_name = ?")
            params.append((tool_name or "").strip())
        if input_payload is not None:
            updates.append("input_json = ?")
            params.append(json.dumps(input_payload, ensure_ascii=False))
        if output_payload is not None:
            updates.append("output_json = ?")
            params.append(json.dumps(output_payload, ensure_ascii=False))
        if error_text is not None:
            updates.append("error_text = ?")
            params.append(error_text or "")

        if not updates:
            return False

        params.append(int(step_id))
        query = f"""
            UPDATE assistant_steps
            SET {", ".join(updates)}
            WHERE id = ?
        """
        with self._get_cursor() as cursor:
            cursor.execute(query, params)
            updated = cursor.rowcount > 0
            if updated:
                cursor.execute(
                    """
                    UPDATE assistant_sessions
                    SET updated_at = CURRENT_TIMESTAMP
                    WHERE session_id = (
                        SELECT session_id FROM assistant_steps WHERE id = ?
                    )
                    """,
                    (int(step_id),),
                )
            return updated

    def list_assistant_sessions(self, *, kind: str = "", limit: int = 30) -> List[Dict[str, Any]]:
        query = """
            SELECT session_id, title, kind, mode, inst_id, inst_type, status,
                   last_error, metadata_json, created_at, updated_at
            FROM assistant_sessions
            WHERE 1 = 1
        """
        params: List[Any] = []
        if kind:
            query += " AND kind = ?"
            params.append(kind)
        query += " ORDER BY updated_at DESC, created_at DESC LIMIT ?"
        params.append(max(int(limit), 1))

        results: List[Dict[str, Any]] = []
        with self._get_cursor() as cursor:
            cursor.execute(query, params)
            for row in cursor.fetchall():
                results.append(self._serialize_assistant_session_row(row))
        return results

    def get_assistant_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        query = """
            SELECT session_id, title, kind, mode, inst_id, inst_type, status,
                   last_error, metadata_json, created_at, updated_at
            FROM assistant_sessions
            WHERE session_id = ?
        """
        with self._get_cursor() as cursor:
            cursor.execute(query, (session_id,))
            row = cursor.fetchone()
        if not row:
            return None
        return self._serialize_assistant_session_row(row)

    def get_assistant_messages(self, session_id: str) -> List[Dict[str, Any]]:
        query = """
            SELECT id, session_id, role, content, tool_name, tool_call_id, metadata_json, created_at
            FROM assistant_messages
            WHERE session_id = ?
            ORDER BY id ASC
        """
        results: List[Dict[str, Any]] = []
        with self._get_cursor() as cursor:
            cursor.execute(query, (session_id,))
            for row in cursor.fetchall():
                results.append({
                    "id": row["id"],
                    "session_id": row["session_id"],
                    "role": row["role"],
                    "content": row["content"] or "",
                    "tool_name": row["tool_name"] or "",
                    "tool_call_id": row["tool_call_id"] or "",
                    "metadata": self._load_json(row["metadata_json"]),
                    "created_at": row["created_at"],
                })
        return results

    def get_assistant_steps(self, session_id: str) -> List[Dict[str, Any]]:
        query = """
            SELECT id, session_id, step_index, step_type, title, status, tool_name,
                   input_json, output_json, error_text, created_at
            FROM assistant_steps
            WHERE session_id = ?
            ORDER BY step_index ASC, id ASC
        """
        results: List[Dict[str, Any]] = []
        with self._get_cursor() as cursor:
            cursor.execute(query, (session_id,))
            for row in cursor.fetchall():
                results.append({
                    "id": row["id"],
                    "session_id": row["session_id"],
                    "step_index": row["step_index"],
                    "step_type": row["step_type"],
                    "title": row["title"],
                    "status": row["status"],
                    "tool_name": row["tool_name"] or "",
                    "input": self._load_json(row["input_json"]),
                    "output": self._load_json(row["output_json"]),
                    "error_text": row["error_text"] or "",
                    "created_at": row["created_at"],
                })
        return results

    def get_assistant_session_detail(self, session_id: str) -> Optional[Dict[str, Any]]:
        session = self.get_assistant_session(session_id)
        if not session:
            return None
        return {
            "session": session,
            "messages": self.get_assistant_messages(session_id),
            "steps": self.get_assistant_steps(session_id),
            "order_drafts": self.list_assistant_order_drafts(session_id=session_id, limit=50),
            "level_snapshots": self.list_assistant_level_snapshots(session_id=session_id, limit=50),
        }

    def create_assistant_order_draft(
        self,
        *,
        session_id: str = "",
        source: str = "assistant",
        title: str = "",
        status: str = "draft",
        mode: str = "simulated",
        inst_id: str,
        inst_type: str = "SPOT",
        side: str,
        order_type: str = "limit",
        td_mode: str = "cash",
        pos_side: str = "",
        reduce_only: bool = False,
        size: str,
        price: str = "",
        stop_loss_price: str = "",
        take_profit_prices: Optional[List[Any]] = None,
        risk_payload: Optional[Dict[str, Any]] = None,
        plan_payload: Optional[Dict[str, Any]] = None,
        annotations: Optional[List[Dict[str, Any]]] = None,
        summary: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        draft_id = uuid.uuid4().hex
        query = """
            INSERT INTO assistant_order_drafts (
                draft_id, session_id, source, title, status, mode,
                inst_id, inst_type, side, order_type, td_mode, pos_side, reduce_only,
                size, price, stop_loss_price, take_profit_prices_json,
                risk_json, plan_json, annotations_json, summary, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        with self._get_cursor() as cursor:
            cursor.execute(
                query,
                (
                    draft_id,
                    (session_id or "").strip(),
                    (source or "assistant").strip() or "assistant",
                    (title or "").strip(),
                    (status or "draft").strip() or "draft",
                    (mode or "simulated").strip() or "simulated",
                    (inst_id or "").strip(),
                    (inst_type or "SPOT").strip() or "SPOT",
                    (side or "").strip(),
                    (order_type or "limit").strip() or "limit",
                    (td_mode or "cash").strip() or "cash",
                    (pos_side or "").strip(),
                    1 if reduce_only else 0,
                    str(size or "").strip(),
                    str(price or "").strip(),
                    str(stop_loss_price or "").strip(),
                    json.dumps(take_profit_prices or [], ensure_ascii=False),
                    json.dumps(risk_payload or {}, ensure_ascii=False),
                    json.dumps(plan_payload or {}, ensure_ascii=False),
                    json.dumps(annotations or [], ensure_ascii=False),
                    summary or "",
                    json.dumps(metadata or {}, ensure_ascii=False),
                ),
            )
        return draft_id

    def update_assistant_order_draft(
        self,
        draft_id: str,
        *,
        title: Optional[str] = None,
        status: Optional[str] = None,
        size: Optional[str] = None,
        price: Optional[str] = None,
        stop_loss_price: Optional[str] = None,
        take_profit_prices: Optional[List[Any]] = None,
        risk_payload: Optional[Dict[str, Any]] = None,
        plan_payload: Optional[Dict[str, Any]] = None,
        annotations: Optional[List[Dict[str, Any]]] = None,
        summary: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        confirmed: Optional[bool] = None,
    ) -> bool:
        updates: List[str] = []
        params: List[Any] = []

        if title is not None:
            updates.append("title = ?")
            params.append((title or "").strip())
        if status is not None:
            updates.append("status = ?")
            params.append((status or "").strip() or "draft")
        if size is not None:
            updates.append("size = ?")
            params.append(str(size or "").strip())
        if price is not None:
            updates.append("price = ?")
            params.append(str(price or "").strip())
        if stop_loss_price is not None:
            updates.append("stop_loss_price = ?")
            params.append(str(stop_loss_price or "").strip())
        if take_profit_prices is not None:
            updates.append("take_profit_prices_json = ?")
            params.append(json.dumps(take_profit_prices, ensure_ascii=False))
        if risk_payload is not None:
            updates.append("risk_json = ?")
            params.append(json.dumps(risk_payload, ensure_ascii=False))
        if plan_payload is not None:
            updates.append("plan_json = ?")
            params.append(json.dumps(plan_payload, ensure_ascii=False))
        if annotations is not None:
            updates.append("annotations_json = ?")
            params.append(json.dumps(annotations, ensure_ascii=False))
        if summary is not None:
            updates.append("summary = ?")
            params.append(summary or "")
        if metadata is not None:
            updates.append("metadata_json = ?")
            params.append(json.dumps(metadata, ensure_ascii=False))
        if confirmed is True:
            updates.append("status = ?")
            params.append("confirmed")
            updates.append("confirmed_at = CURRENT_TIMESTAMP")

        if not updates:
            return False

        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append((draft_id or "").strip())
        query = f"""
            UPDATE assistant_order_drafts
            SET {", ".join(updates)}
            WHERE draft_id = ?
        """
        with self._get_cursor() as cursor:
            cursor.execute(query, params)
            return cursor.rowcount > 0

    def get_assistant_order_draft(self, draft_id: str) -> Optional[Dict[str, Any]]:
        query = """
            SELECT * FROM assistant_order_drafts
            WHERE draft_id = ?
        """
        with self._get_cursor() as cursor:
            cursor.execute(query, ((draft_id or "").strip(),))
            row = cursor.fetchone()
        if not row:
            return None
        return self._serialize_assistant_order_draft_row(row)

    def list_assistant_order_drafts(
        self,
        *,
        session_id: str = "",
        inst_id: str = "",
        status: str = "",
        limit: int = 30,
    ) -> List[Dict[str, Any]]:
        query = """
            SELECT * FROM assistant_order_drafts
            WHERE 1 = 1
        """
        params: List[Any] = []
        if session_id:
            query += " AND session_id = ?"
            params.append((session_id or "").strip())
        if inst_id:
            query += " AND inst_id = ?"
            params.append((inst_id or "").strip())
        if status:
            query += " AND status = ?"
            params.append((status or "").strip())
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(max(int(limit), 1))

        results: List[Dict[str, Any]] = []
        with self._get_cursor() as cursor:
            cursor.execute(query, params)
            for row in cursor.fetchall():
                results.append(self._serialize_assistant_order_draft_row(row))
        return results

    def create_assistant_level_snapshot(
        self,
        *,
        session_id: str = "",
        source: str = "assistant",
        title: str = "",
        inst_id: str,
        inst_type: str = "SPOT",
        timeframes: Optional[List[str]] = None,
        current_price: float = 0.0,
        supports: Optional[List[Dict[str, Any]]] = None,
        resistances: Optional[List[Dict[str, Any]]] = None,
        invalidation_levels: Optional[List[Dict[str, Any]]] = None,
        chart_annotations: Optional[List[Dict[str, Any]]] = None,
        summary: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        snapshot_id = uuid.uuid4().hex
        query = """
            INSERT INTO assistant_level_snapshots (
                snapshot_id, session_id, source, title,
                inst_id, inst_type, timeframes_json, current_price,
                supports_json, resistances_json, invalidation_levels_json,
                chart_annotations_json, summary_json, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        with self._get_cursor() as cursor:
            cursor.execute(
                query,
                (
                    snapshot_id,
                    (session_id or "").strip(),
                    (source or "assistant").strip() or "assistant",
                    (title or "").strip(),
                    (inst_id or "").strip(),
                    (inst_type or "SPOT").strip() or "SPOT",
                    json.dumps(timeframes or [], ensure_ascii=False),
                    float(current_price or 0.0),
                    json.dumps(supports or [], ensure_ascii=False),
                    json.dumps(resistances or [], ensure_ascii=False),
                    json.dumps(invalidation_levels or [], ensure_ascii=False),
                    json.dumps(chart_annotations or [], ensure_ascii=False),
                    json.dumps(summary or {}, ensure_ascii=False),
                    json.dumps(metadata or {}, ensure_ascii=False),
                ),
            )
        return snapshot_id

    def get_assistant_level_snapshot(self, snapshot_id: str) -> Optional[Dict[str, Any]]:
        query = """
            SELECT * FROM assistant_level_snapshots
            WHERE snapshot_id = ?
        """
        with self._get_cursor() as cursor:
            cursor.execute(query, ((snapshot_id or "").strip(),))
            row = cursor.fetchone()
        if not row:
            return None
        return self._serialize_assistant_level_snapshot_row(row)

    def list_assistant_level_snapshots(
        self,
        *,
        session_id: str = "",
        inst_id: str = "",
        source: str = "",
        limit: int = 30,
    ) -> List[Dict[str, Any]]:
        query = """
            SELECT * FROM assistant_level_snapshots
            WHERE 1 = 1
        """
        params: List[Any] = []
        if session_id:
            query += " AND session_id = ?"
            params.append((session_id or "").strip())
        if inst_id:
            query += " AND inst_id = ?"
            params.append((inst_id or "").strip())
        if source:
            query += " AND source = ?"
            params.append((source or "").strip())
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(max(int(limit), 1))

        results: List[Dict[str, Any]] = []
        with self._get_cursor() as cursor:
            cursor.execute(query, params)
            for row in cursor.fetchall():
                results.append(self._serialize_assistant_level_snapshot_row(row))
        return results

    def create_assistant_patrol_run(
        self,
        *,
        run_id: str = "",
        trigger: str = "scheduled",
        inst_type: str = "SWAP",
        mode: str = "simulated",
        summary: Optional[Dict[str, Any]] = None,
        candidates: Optional[List[Dict[str, Any]]] = None,
        result: Optional[Dict[str, Any]] = None,
        event: Optional[Dict[str, Any]] = None,
        settings: Optional[Dict[str, Any]] = None,
    ) -> str:
        run_id = (run_id or "").strip() or uuid.uuid4().hex
        query = """
            INSERT INTO assistant_patrol_runs (
                run_id, trigger, inst_type, mode,
                summary_json, candidates_json, result_json, event_json, settings_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        with self._get_cursor() as cursor:
            cursor.execute(
                query,
                (
                    run_id,
                    (trigger or "scheduled").strip() or "scheduled",
                    (inst_type or "SWAP").strip() or "SWAP",
                    (mode or "simulated").strip() or "simulated",
                    json.dumps(summary or {}, ensure_ascii=False),
                    json.dumps(candidates or [], ensure_ascii=False),
                    json.dumps(result or {}, ensure_ascii=False),
                    json.dumps(event or {}, ensure_ascii=False),
                    json.dumps(settings or {}, ensure_ascii=False),
                ),
            )
        return run_id

    def get_assistant_patrol_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        query = """
            SELECT * FROM assistant_patrol_runs
            WHERE run_id = ?
        """
        with self._get_cursor() as cursor:
            cursor.execute(query, ((run_id or "").strip(),))
            row = cursor.fetchone()
        if not row:
            return None
        return self._serialize_assistant_patrol_run_row(row)

    def list_assistant_patrol_runs(
        self,
        *,
        inst_type: str = "",
        mode: str = "",
        trigger: str = "",
        limit: int = 30,
    ) -> List[Dict[str, Any]]:
        query = """
            SELECT * FROM assistant_patrol_runs
            WHERE 1 = 1
        """
        params: List[Any] = []
        if inst_type:
            query += " AND inst_type = ?"
            params.append((inst_type or "").strip())
        if mode:
            query += " AND mode = ?"
            params.append((mode or "").strip())
        if trigger:
            query += " AND trigger = ?"
            params.append((trigger or "").strip())
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(max(int(limit), 1))

        results: List[Dict[str, Any]] = []
        with self._get_cursor() as cursor:
            cursor.execute(query, params)
            for row in cursor.fetchall():
                results.append(self._serialize_assistant_patrol_run_row(row))
        return results

    def _serialize_assistant_session_row(self, row: Any) -> Dict[str, Any]:
        return {
            "session_id": row["session_id"],
            "title": row["title"] or "",
            "kind": row["kind"] or "agent",
            "mode": row["mode"] or "simulated",
            "inst_id": row["inst_id"] or "",
            "inst_type": row["inst_type"] or "SPOT",
            "status": row["status"] or "active",
            "last_error": row["last_error"] or "",
            "metadata": self._load_json(row["metadata_json"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def _serialize_assistant_order_draft_row(self, row: Any) -> Dict[str, Any]:
        return {
            "draft_id": row["draft_id"],
            "session_id": row["session_id"] or "",
            "source": row["source"] or "assistant",
            "title": row["title"] or "",
            "status": row["status"] or "draft",
            "mode": row["mode"] or "simulated",
            "inst_id": row["inst_id"] or "",
            "inst_type": row["inst_type"] or "SPOT",
            "side": row["side"] or "",
            "order_type": row["order_type"] or "limit",
            "td_mode": row["td_mode"] or "cash",
            "pos_side": row["pos_side"] or "",
            "reduce_only": bool(row["reduce_only"]),
            "size": row["size"] or "",
            "price": row["price"] or "",
            "stop_loss_price": row["stop_loss_price"] or "",
            "take_profit_prices": self._load_json_value(row["take_profit_prices_json"], default=[]),
            "risk": self._load_json_value(row["risk_json"], default={}),
            "plan": self._load_json_value(row["plan_json"], default={}),
            "annotations": self._load_json_value(row["annotations_json"], default=[]),
            "summary": row["summary"] or "",
            "metadata": self._load_json_value(row["metadata_json"], default={}),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "confirmed_at": row["confirmed_at"],
        }

    def _serialize_assistant_level_snapshot_row(self, row: Any) -> Dict[str, Any]:
        return {
            "snapshot_id": row["snapshot_id"],
            "session_id": row["session_id"] or "",
            "source": row["source"] or "assistant",
            "title": row["title"] or "",
            "inst_id": row["inst_id"] or "",
            "inst_type": row["inst_type"] or "SPOT",
            "timeframes": self._load_json_value(row["timeframes_json"], default=[]),
            "current_price": row["current_price"] or 0.0,
            "supports": self._load_json_value(row["supports_json"], default=[]),
            "resistances": self._load_json_value(row["resistances_json"], default=[]),
            "invalidation_levels": self._load_json_value(row["invalidation_levels_json"], default=[]),
            "chart_annotations": self._load_json_value(row["chart_annotations_json"], default=[]),
            "summary": self._load_json_value(row["summary_json"], default={}),
            "metadata": self._load_json_value(row["metadata_json"], default={}),
            "created_at": row["created_at"],
        }

    def _serialize_assistant_patrol_run_row(self, row: Any) -> Dict[str, Any]:
        return {
            "run_id": row["run_id"],
            "trigger": row["trigger"] or "scheduled",
            "inst_type": row["inst_type"] or "SWAP",
            "mode": row["mode"] or "simulated",
            "summary": self._load_json_value(row["summary_json"], default={}),
            "candidates": self._load_json_value(row["candidates_json"], default=[]),
            "result": self._load_json_value(row["result_json"], default={}),
            "event": self._load_json_value(row["event_json"], default={}),
            "settings": self._load_json_value(row["settings_json"], default={}),
            "created_at": row["created_at"],
        }

    def _load_json(self, raw: Any) -> Dict[str, Any]:
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except Exception:
            return {}

    def _load_json_value(self, raw: Any, *, default: Any) -> Any:
        if not raw:
            return default
        try:
            return json.loads(raw)
        except Exception:
            return default
