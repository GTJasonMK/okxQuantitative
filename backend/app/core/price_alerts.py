from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional

from ..config import CONFIG_DIR
from ..utils.files import atomic_write_json, read_json_file


ALERTS_FILE = CONFIG_DIR / "market_alerts.json"


def _utc_now_iso() -> str:
    """返回 UTC ISO 时间字符串，便于前后端统一展示。"""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _now_ms() -> int:
    return int(time.time() * 1000)


def _infer_inst_type(inst_id: str, inst_type: str = "") -> str:
    value = (inst_type or "").upper().strip()
    if value:
        return value
    if inst_id.endswith("-SWAP"):
        return "SWAP"
    return "SPOT"


def _normalize_inst_id(inst_id: str) -> str:
    value = (inst_id or "").upper().strip()
    if not value:
        raise ValueError("inst_id 不能为空")
    return value


class PriceAlertStore:
    """价格提醒持久化与触发判断。"""

    def __init__(self, path: str | Path = ALERTS_FILE):
        self.path = Path(path)
        self._lock = Lock()

    def _load_state(self) -> Dict[str, Any]:
        data = read_json_file(self.path, default={"alerts": []})
        alerts = data.get("alerts") if isinstance(data, dict) else []
        if not isinstance(alerts, list):
            alerts = []
        return {"alerts": alerts}

    def _save_state(self, alerts: List[Dict[str, Any]]) -> None:
        atomic_write_json(self.path, {"alerts": alerts}, ensure_ascii=False, indent=2)

    def list_alerts(self, *, inst_id: str = "", inst_type: str = "") -> List[Dict[str, Any]]:
        target_inst_id = _normalize_inst_id(inst_id) if inst_id else ""
        target_inst_type = (inst_type or "").upper().strip()
        with self._lock:
            alerts = self._load_state()["alerts"]
            result = []
            for alert in alerts:
                if target_inst_id and alert.get("inst_id") != target_inst_id:
                    continue
                if target_inst_type and alert.get("inst_type") != target_inst_type:
                    continue
                result.append(dict(alert))
            result.sort(key=lambda item: item.get("created_at", ""), reverse=True)
            return result

    def create_alert(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        now_iso = _utc_now_iso()
        alert = {
            "id": uuid.uuid4().hex[:12],
            "inst_id": _normalize_inst_id(payload.get("inst_id", "")),
            "symbol": (payload.get("symbol") or payload.get("inst_id") or "").upper().replace("-SWAP", ""),
            "inst_type": _infer_inst_type(payload.get("inst_id", ""), payload.get("inst_type", "")),
            "alert_type": (payload.get("alert_type") or "price").lower(),
            "direction": (payload.get("direction") or "above").lower(),
            "target_price": float(payload["target_price"]) if payload.get("target_price") is not None else None,
            "change_percent": float(payload["change_percent"]) if payload.get("change_percent") is not None else None,
            "note": str(payload.get("note") or "").strip(),
            "enabled": bool(payload.get("enabled", True)),
            "trigger_once": bool(payload.get("trigger_once", True)),
            "cooldown_seconds": max(0, int(payload.get("cooldown_seconds", 300))),
            "created_at": now_iso,
            "updated_at": now_iso,
            "triggered_at": None,
            "last_value": None,
            "last_trigger_value": None,
            "last_trigger_ts": 0,
        }
        self._validate_alert(alert)

        with self._lock:
            state = self._load_state()
            alerts = state["alerts"]
            alerts.append(alert)
            self._save_state(alerts)
        return dict(alert)

    def update_alert(self, alert_id: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        with self._lock:
            state = self._load_state()
            alerts = state["alerts"]
            for index, alert in enumerate(alerts):
                if alert.get("id") != alert_id:
                    continue

                updated = dict(alert)
                if "inst_id" in payload:
                    updated["inst_id"] = _normalize_inst_id(payload.get("inst_id", ""))
                if "inst_type" in payload or "inst_id" in payload:
                    updated["inst_type"] = _infer_inst_type(updated["inst_id"], str(payload.get("inst_type", updated.get("inst_type", ""))))
                if "symbol" in payload:
                    updated["symbol"] = str(payload.get("symbol") or "").upper().replace("-SWAP", "")
                if "alert_type" in payload:
                    updated["alert_type"] = str(payload.get("alert_type") or "").lower()
                if "direction" in payload:
                    updated["direction"] = str(payload.get("direction") or "").lower()
                if "target_price" in payload:
                    updated["target_price"] = float(payload["target_price"]) if payload.get("target_price") is not None else None
                if "change_percent" in payload:
                    updated["change_percent"] = float(payload["change_percent"]) if payload.get("change_percent") is not None else None
                if "note" in payload:
                    updated["note"] = str(payload.get("note") or "").strip()
                if "enabled" in payload:
                    updated["enabled"] = bool(payload.get("enabled"))
                if "trigger_once" in payload:
                    updated["trigger_once"] = bool(payload.get("trigger_once"))
                if "cooldown_seconds" in payload:
                    updated["cooldown_seconds"] = max(0, int(payload.get("cooldown_seconds", 300)))

                updated["updated_at"] = _utc_now_iso()
                self._validate_alert(updated)
                alerts[index] = updated
                self._save_state(alerts)
                return dict(updated)

        return None

    def delete_alert(self, alert_id: str) -> bool:
        with self._lock:
            state = self._load_state()
            alerts = state["alerts"]
            next_alerts = [item for item in alerts if item.get("id") != alert_id]
            if len(next_alerts) == len(alerts):
                return False
            self._save_state(next_alerts)
            return True

    def evaluate_ticker(
        self,
        *,
        inst_id: str,
        inst_type: str,
        last_price: float,
        change_24h: Optional[float],
        ticker_ts: int,
    ) -> List[Dict[str, Any]]:
        normalized_inst_id = _normalize_inst_id(inst_id)
        triggered: List[Dict[str, Any]] = []
        now_ms = _now_ms()
        changed = False

        with self._lock:
            state = self._load_state()
            alerts = state["alerts"]

            for alert in alerts:
                if not alert.get("enabled", True):
                    continue
                if alert.get("inst_id") != normalized_inst_id:
                    continue
                if alert.get("inst_type") and alert.get("inst_type") != _infer_inst_type(normalized_inst_id, inst_type):
                    continue

                current_value = last_price if alert.get("alert_type") == "price" else change_24h
                if current_value is None:
                    continue

                threshold = alert.get("target_price") if alert.get("alert_type") == "price" else alert.get("change_percent")
                prev_value = alert.get("last_value")
                direction = alert.get("direction", "above")

                crossed = False
                if direction == "above":
                    crossed = current_value >= threshold and (prev_value is None or prev_value < threshold)
                elif direction == "below":
                    crossed = current_value <= threshold and (prev_value is None or prev_value > threshold)

                alert["last_value"] = float(current_value)

                last_trigger_ts = int(alert.get("last_trigger_ts") or 0)
                cooldown_ms = max(0, int(alert.get("cooldown_seconds", 300))) * 1000
                cooldown_ready = cooldown_ms == 0 or now_ms - last_trigger_ts >= cooldown_ms

                if crossed and cooldown_ready:
                    alert["last_trigger_ts"] = now_ms
                    alert["last_trigger_value"] = float(current_value)
                    alert["triggered_at"] = _utc_now_iso()
                    alert["updated_at"] = alert["triggered_at"]
                    changed = True

                    if alert.get("trigger_once", True):
                        alert["enabled"] = False

                    triggered.append(self._build_trigger_payload(
                        alert=alert,
                        current_value=float(current_value),
                        last_price=float(last_price),
                        change_24h=float(change_24h) if change_24h is not None else None,
                        ticker_ts=ticker_ts,
                    ))

            if changed:
                self._save_state(alerts)

        return triggered

    def _validate_alert(self, alert: Dict[str, Any]) -> None:
        alert_type = alert.get("alert_type")
        direction = alert.get("direction")

        if alert_type not in {"price", "change"}:
            raise ValueError("alert_type 仅支持 price 或 change")
        if direction not in {"above", "below"}:
            raise ValueError("direction 仅支持 above 或 below")

        if alert_type == "price":
            target_price = alert.get("target_price")
            if target_price is None or float(target_price) <= 0:
                raise ValueError("价格提醒必须提供大于 0 的 target_price")
        elif alert_type == "change":
            change_percent = alert.get("change_percent")
            if change_percent is None:
                raise ValueError("涨跌幅提醒必须提供 change_percent")

    def _build_trigger_payload(
        self,
        *,
        alert: Dict[str, Any],
        current_value: float,
        last_price: float,
        change_24h: Optional[float],
        ticker_ts: int,
    ) -> Dict[str, Any]:
        is_price_alert = alert.get("alert_type") == "price"
        target_value = alert.get("target_price") if is_price_alert else alert.get("change_percent")
        unit = "USDT" if is_price_alert else "%"
        direction_text = "上破" if alert.get("direction") == "above" else "下破"
        inst_id = alert.get("inst_id", "")
        market_label = "永续合约" if alert.get("inst_type") == "SWAP" else "现货"

        message = (
            f"{inst_id}（{market_label}）{direction_text}"
            f"{target_value:.4f}{unit if is_price_alert else ''}"
            if is_price_alert
            else f"{inst_id}（{market_label}）24H 涨跌幅{direction_text}{target_value:.2f}%"
        )
        if alert.get("note"):
            message = f"{message}｜备注：{alert['note']}"

        return {
            "id": alert.get("id"),
            "inst_id": inst_id,
            "symbol": alert.get("symbol"),
            "inst_type": alert.get("inst_type"),
            "alert_type": alert.get("alert_type"),
            "direction": alert.get("direction"),
            "target_value": target_value,
            "current_value": current_value,
            "last_price": last_price,
            "change_24h": change_24h,
            "triggered_at": alert.get("triggered_at"),
            "ticker_ts": ticker_ts,
            "title": f"{inst_id} 价格提醒",
            "message": message,
            "note": alert.get("note", ""),
        }


price_alert_store = PriceAlertStore()
