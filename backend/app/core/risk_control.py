"""统一风控配置与风险评估。"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from threading import Lock, RLock
from typing import Any, Dict, Optional, Protocol

from ..config import CONFIG_DIR
from ..core.holdings import build_spot_holdings
from ..utils.files import atomic_write_json, read_json_file


RISK_CONTROL_FILE = CONFIG_DIR / "risk_control.json"


class AccountRiskPort(Protocol):
    @property
    def is_available(self) -> bool: ...

    def get_balance(self, ccy: str = "") -> Dict[str, Any]: ...

    def get_contract_positions(self, inst_type: str = "SWAP", inst_id: str = "") -> Any: ...


class FetcherRiskPort(Protocol):
    def get_ticker_cached(self, inst_id: str): ...

    def get_tickers_cached(self, inst_type: str = "SPOT") -> Dict[str, Any]: ...


@dataclass
class RiskControlConfig:
    enabled: bool = True
    max_single_loss_ratio: float = 0.02
    default_stop_loss_ratio: float = 0.03
    max_total_position_ratio: float = 1.0


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: Any, minimum: float, maximum: float, default: float) -> float:
    number = _safe_float(value, default)
    return max(minimum, min(maximum, number))


def _normalize_config(data: Optional[Dict[str, Any]]) -> RiskControlConfig:
    payload = data or {}
    return RiskControlConfig(
        enabled=bool(payload.get("enabled", True)),
        max_single_loss_ratio=_clamp(payload.get("max_single_loss_ratio"), 0.0, 1.0, 0.02),
        default_stop_loss_ratio=_clamp(payload.get("default_stop_loss_ratio"), 0.0, 1.0, 0.03),
        max_total_position_ratio=_clamp(payload.get("max_total_position_ratio"), 0.0, 10.0, 1.0),
    )


class RiskControlStore:
    """本地 JSON 风控配置存储。"""

    def __init__(self, path=RISK_CONTROL_FILE):
        self._path = path
        self._lock = RLock()

    def get_config(self) -> RiskControlConfig:
        data = read_json_file(self._path, default={})
        config = _normalize_config(data)
        self._ensure_persisted(config)
        return config

    def get_config_dict(self) -> Dict[str, Any]:
        return asdict(self.get_config())

    def update_config(self, partial: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            current = self.get_config_dict()
            current.update(partial or {})
            config = _normalize_config(current)
            atomic_write_json(self._path, asdict(config), ensure_ascii=False, indent=2)
            return asdict(config)

    def _ensure_persisted(self, config: RiskControlConfig):
        if not self._path.exists():
            with self._lock:
                if not self._path.exists():
                    atomic_write_json(self._path, asdict(config), ensure_ascii=False, indent=2)


_risk_store: Optional[RiskControlStore] = None
_risk_store_lock = Lock()


def get_risk_control_store() -> RiskControlStore:
    global _risk_store
    if _risk_store is None:
        with _risk_store_lock:
            if _risk_store is None:
                _risk_store = RiskControlStore()
    return _risk_store


def _extract_spot_metrics(
    balance_details: Any,
    fetcher: Optional[FetcherRiskPort],
    cost_data: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, float]:
    try:
        tickers = fetcher.get_tickers_cached("SPOT") if fetcher else {}
    except Exception as e:
        print(f"[RiskControl] 获取现货行情失败: {e}")
        tickers = {}
    holdings, _totals = build_spot_holdings(
        balance_details=balance_details,
        tickers=tickers,
        cost_data=cost_data or {},
    )

    spot_exposure = 0.0
    spot_cash = 0.0
    spot_unrealized_pnl = 0.0

    for item in holdings:
        value = _safe_float(item.get("value_usdt"))
        if item.get("is_stablecoin"):
            spot_cash += value
            continue

        spot_exposure += value
        spot_unrealized_pnl += _safe_float(item.get("pnl_usdt"))

    return {
        "spot_exposure": round(spot_exposure, 4),
        "spot_cash": round(spot_cash, 4),
        "spot_unrealized_pnl": round(spot_unrealized_pnl, 4),
    }


def _extract_contract_metrics(account: AccountRiskPort) -> Dict[str, float]:
    get_contract_positions = getattr(account, "get_contract_positions", None)
    if not callable(get_contract_positions):
        return {
            "contract_exposure": 0.0,
            "contract_unrealized_pnl": 0.0,
        }

    exposure = 0.0
    unrealized_pnl = 0.0

    for inst_type in ("SWAP", "FUTURES"):
        try:
            positions = get_contract_positions(inst_type, "") or []
        except Exception as e:
            print(f"[RiskControl] 获取 {inst_type} 持仓失败: {e}")
            continue

        for pos in positions:
            quantity = abs(_safe_float(pos.get("pos")))
            if quantity <= 0:
                continue

            notional = abs(_safe_float(pos.get("notionalUsd")))
            if notional <= 0:
                notional = abs(_safe_float(pos.get("markPx")) * quantity)

            exposure += notional
            unrealized_pnl += _safe_float(pos.get("upl"))

    return {
        "contract_exposure": round(exposure, 4),
        "contract_unrealized_pnl": round(unrealized_pnl, 4),
    }


def build_risk_summary(
    *,
    account: AccountRiskPort,
    fetcher: Optional[FetcherRiskPort],
    cost_data: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    if not account.is_available:
        raise RuntimeError("账户 API 未初始化")

    balance = account.get_balance()
    if not isinstance(balance, dict):
        raise RuntimeError("账户余额返回格式异常")
    if "error" in balance:
        raise RuntimeError(balance["error"])

    total_equity = _safe_float(balance.get("totalEq"))
    balance_details = balance.get("details", []) or []

    spot_metrics = _extract_spot_metrics(balance_details, fetcher, cost_data=cost_data)
    contract_metrics = _extract_contract_metrics(account)

    total_exposure = spot_metrics["spot_exposure"] + contract_metrics["contract_exposure"]
    exposure_ratio = (total_exposure / total_equity) if total_equity > 0 else 0.0
    floating_pnl = spot_metrics["spot_unrealized_pnl"] + contract_metrics["contract_unrealized_pnl"]

    return {
        "total_equity": round(total_equity, 4),
        "available_cash": round(spot_metrics["spot_cash"], 4),
        "spot_exposure": round(spot_metrics["spot_exposure"], 4),
        "contract_exposure": round(contract_metrics["contract_exposure"], 4),
        "total_exposure": round(total_exposure, 4),
        "exposure_ratio": round(exposure_ratio, 6),
        "floating_pnl": round(floating_pnl, 4),
    }


def _resolve_reference_price(
    *,
    inst_id: str,
    price: Optional[float],
    fetcher: Optional[FetcherRiskPort],
) -> float:
    if price is not None and price > 0:
        return float(price)

    if fetcher:
        try:
            ticker = fetcher.get_ticker_cached(inst_id)
            if ticker is not None:
                return _safe_float(getattr(ticker, "last", None))
        except Exception as e:
            print(f"[RiskControl] 获取 {inst_id} 参考价格失败: {e}")

    return 0.0


def _is_reducing_order(
    *,
    inst_type: str,
    side: str,
    reduce_only: bool = False,
    pos_side: str = "",
) -> bool:
    if reduce_only:
        return True

    normalized_inst_type = (inst_type or "SPOT").upper()
    normalized_side = (side or "").lower()
    normalized_pos_side = (pos_side or "").lower()

    if normalized_inst_type == "SPOT":
        return normalized_side == "sell"

    return (
        (normalized_side == "sell" and normalized_pos_side == "long")
        or (normalized_side == "buy" and normalized_pos_side == "short")
    )


def evaluate_order_risk(
    *,
    account: AccountRiskPort,
    fetcher: Optional[FetcherRiskPort],
    inst_id: str,
    inst_type: str,
    side: str,
    size: float,
    price: Optional[float] = None,
    stop_loss_ratio: Optional[float] = None,
    reduce_only: bool = False,
    pos_side: str = "",
) -> Dict[str, Any]:
    config = get_risk_control_store().get_config()
    summary = build_risk_summary(account=account, fetcher=fetcher)

    reference_price = _resolve_reference_price(inst_id=inst_id, price=price, fetcher=fetcher)
    order_notional = max(0.0, _safe_float(size) * reference_price)
    total_equity = _safe_float(summary.get("total_equity"))
    is_reducing_order = _is_reducing_order(
        inst_type=inst_type,
        side=side,
        reduce_only=reduce_only,
        pos_side=pos_side,
    )
    applied_stop_loss_ratio = _clamp(
        stop_loss_ratio if stop_loss_ratio is not None else config.default_stop_loss_ratio,
        0.0,
        1.0,
        config.default_stop_loss_ratio,
    )

    projected_exposure = max(
        0.0,
        _safe_float(summary.get("total_exposure")) - order_notional if is_reducing_order
        else _safe_float(summary.get("total_exposure")) + order_notional,
    )
    projected_exposure_ratio = (projected_exposure / total_equity) if total_equity > 0 else 0.0
    estimated_loss_amount = order_notional * applied_stop_loss_ratio
    estimated_loss_ratio = (estimated_loss_amount / total_equity) if total_equity > 0 else 0.0

    result = {
        "allowed": True,
        "message": "",
        "reference_price": round(reference_price, 8),
        "order_notional": round(order_notional, 8),
        "estimated_loss_amount": round(estimated_loss_amount, 8),
        "estimated_loss_ratio": round(estimated_loss_ratio, 8),
        "projected_exposure": round(projected_exposure, 8),
        "projected_exposure_ratio": round(projected_exposure_ratio, 8),
        "is_reducing_order": is_reducing_order,
        "config": asdict(config),
        "summary": summary,
    }

    if not config.enabled:
        return result

    if total_equity <= 0 and order_notional > 0:
        result["allowed"] = False
        result["message"] = "账户总权益为 0，风控已拒绝下单"
        return result

    if not is_reducing_order and order_notional <= 0:
        result["allowed"] = False
        result["message"] = "无法获取有效参考价格，风控已拒绝下单"
        return result

    if not is_reducing_order and config.max_single_loss_ratio > 0 and estimated_loss_ratio > config.max_single_loss_ratio:
        result["allowed"] = False
        result["message"] = (
            f"单笔风险预计为 {estimated_loss_ratio * 100:.2f}% ，超过上限 {config.max_single_loss_ratio * 100:.2f}%"
        )
        return result

    if not is_reducing_order and config.max_total_position_ratio > 0 and projected_exposure_ratio > config.max_total_position_ratio:
        result["allowed"] = False
        result["message"] = (
            f"总风险敞口预计为 {projected_exposure_ratio * 100:.2f}% ，超过上限 {config.max_total_position_ratio * 100:.2f}%"
        )
        return result

    return result
