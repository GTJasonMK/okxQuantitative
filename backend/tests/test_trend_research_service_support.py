from app.core.trend_research import service_support


class _DummyFetcher:
    def get_mark_price(self, inst_id):
        return {
            "ts": "1712365200000",
            "mark_price": "65000",
        }

    def get_index_price(self, inst_id):
        return {
            "index_price": "64950",
        }

    def get_open_interest(self, inst_id):
        return {
            "open_interest": "123456",
        }

    def get_funding_rate(self, inst_id):
        return {
            "funding_rate": "0.0001",
            "premium": "0.0015",
        }


def test_build_contract_state_snapshot_uses_local_receive_time(monkeypatch):
    monkeypatch.setattr(service_support.time, "time", lambda: 1712365209.5)

    snapshot = service_support.build_contract_state_snapshot(
        _DummyFetcher(),
        "BTC-USDT-SWAP",
    )

    assert snapshot.ts_exchange == 1712365200.0
    assert snapshot.ts_local == 1712365209.5
