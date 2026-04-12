from __future__ import annotations

from .models import OKXOutboundRule


PUBLIC = "public"
PRIVATE = "private"
TRADE = "trade"
WS_CONTROL = "ws_control"
REST = "rest"
WS = "ws"
PUBLIC_IP_INST = "public_ip_inst"


class OKXRateRuleRegistry:
    def __init__(self):
        self._rules = {
            "market.ticker": OKXOutboundRule("market.ticker", "public_ip", REST, PUBLIC, 2, 20),
            "market.tickers": OKXOutboundRule("market.tickers", "public_ip", REST, PUBLIC, 2, 20),
            "market.books": OKXOutboundRule("market.books", "public_ip", REST, PUBLIC, 2, 40),
            "market.books_full": OKXOutboundRule("market.books_full", "public_ip", REST, PUBLIC, 2, 10),
            "market.candles": OKXOutboundRule("market.candles", "public_ip", REST, PUBLIC, 2, 40),
            "market.history_candles": OKXOutboundRule("market.history_candles", "public_ip", REST, PUBLIC, 2, 20),
            "market.trades": OKXOutboundRule("market.trades", "public_ip", REST, PUBLIC, 2, 100),
            "market.mark_price": OKXOutboundRule("market.mark_price", PUBLIC_IP_INST, REST, PUBLIC, 2, 10),
            "market.index_ticker": OKXOutboundRule("market.index_ticker", "public_ip", REST, PUBLIC, 2, 20),
            "market.open_interest": OKXOutboundRule("market.open_interest", PUBLIC_IP_INST, REST, PUBLIC, 2, 20),
            "market.funding_rate": OKXOutboundRule("market.funding_rate", PUBLIC_IP_INST, REST, PUBLIC, 2, 10),
            "public.instruments": OKXOutboundRule("public.instruments", "public_ip", REST, PUBLIC, 2, 20),
            "account.balance": OKXOutboundRule("account.balance", "private_user", REST, PRIVATE, 2, 10),
            "account.positions": OKXOutboundRule("account.positions", "private_user", REST, PRIVATE, 2, 10),
            "account.max_avail_size": OKXOutboundRule("account.max_avail_size", "private_user", REST, PRIVATE, 2, 20),
            "account.max_size": OKXOutboundRule("account.max_size", "private_user", REST, PRIVATE, 2, 20),
            "account.config": OKXOutboundRule("account.config", "private_user", REST, PRIVATE, 2, 5),
            "account.set_position_mode": OKXOutboundRule("account.set_position_mode", "private_user", REST, TRADE, 2, 5),
            "account.set_leverage": OKXOutboundRule("account.set_leverage", "private_user", REST, TRADE, 2, 20),
            "account.get_leverage": OKXOutboundRule("account.get_leverage", "private_user", REST, PRIVATE, 2, 20),
            "trade.order_detail": OKXOutboundRule("trade.order_detail", "trade_user_inst", REST, TRADE, 2, 60),
            "trade.orders_pending": OKXOutboundRule("trade.orders_pending", "private_user", REST, TRADE, 2, 60),
            "trade.orders_history": OKXOutboundRule("trade.orders_history", "private_user", REST, TRADE, 2, 40),
            "trade.fills": OKXOutboundRule("trade.fills", "private_user", REST, TRADE, 2, 60),
            "trade.fills_history": OKXOutboundRule("trade.fills_history", "private_user", REST, TRADE, 2, 10),
            "trade.place_order": OKXOutboundRule("trade.place_order", "trade_user_inst", REST, TRADE, 2, 60),
            "trade.cancel_order": OKXOutboundRule("trade.cancel_order", "trade_user_inst", REST, TRADE, 2, 60),
            "ws.connect": OKXOutboundRule("ws.connect", "ws_connect_ip", WS, WS_CONTROL, 1, 3),
            "ws.login": OKXOutboundRule("ws.login", "ws_conn_ops", WS, WS_CONTROL, 3600, 480),
            "ws.subscribe": OKXOutboundRule("ws.subscribe", "ws_conn_ops", WS, WS_CONTROL, 3600, 480),
            "ws.unsubscribe": OKXOutboundRule("ws.unsubscribe", "ws_conn_ops", WS, WS_CONTROL, 3600, 480),
        }

    def get(self, op_key: str) -> OKXOutboundRule:
        try:
            return self._rules[op_key]
        except KeyError as exc:
            raise KeyError(f"未注册的 OKX 出站操作: {op_key}") from exc

    def all_rules(self) -> dict[str, OKXOutboundRule]:
        return dict(self._rules)
