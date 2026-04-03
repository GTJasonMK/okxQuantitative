from app.core.data_fetcher import DataFetcher


def _build_levels(count: int, start_price: float, size: float):
    return [
        [f"{start_price + index * 0.001:.6f}", str(size + index), "0", str((index % 3) + 1)]
        for index in range(count)
    ]


def test_get_orderbook_uses_books_full_for_large_depth(monkeypatch):
    fetcher = object.__new__(DataFetcher)

    monkeypatch.setattr(
        DataFetcher,
        "_get_full_orderbook_payload",
        lambda self, inst_id, size: {
            "asks": _build_levels(500, 1.000, 10),
            "bids": _build_levels(500, 0.999, 11),
            "ts": "1710000000000",
        },
        raising=True,
    )

    orderbook = DataFetcher.get_orderbook(fetcher, "ONT-USDT-SWAP", 500)

    assert orderbook is not None
    assert orderbook["source"] == "books-full"
    assert orderbook["requested_size"] == 500
    assert orderbook["actual_size"] == 500
    assert orderbook["is_truncated"] is False
    assert len(orderbook["asks"]) == 500
    assert len(orderbook["bids"]) == 500


def test_get_orderbook_falls_back_to_standard_books_when_full_depth_fails(monkeypatch):
    class DummyMarketAPI:
        def get_orderbook(self, instId, sz):
            size = int(sz)
            return {
                "code": "0",
                "data": [{
                    "asks": _build_levels(size, 1.000, 10),
                    "bids": _build_levels(size, 0.999, 11),
                    "ts": "1710000000000",
                }],
            }

    fetcher = object.__new__(DataFetcher)
    fetcher.market_api = DummyMarketAPI()

    monkeypatch.setattr(
        DataFetcher,
        "_get_full_orderbook_payload",
        lambda self, inst_id, size: None,
        raising=True,
    )

    orderbook = DataFetcher.get_orderbook(fetcher, "ONT-USDT-SWAP", 500)

    assert orderbook is not None
    assert orderbook["source"] == "books-fallback"
    assert orderbook["requested_size"] == 500
    assert orderbook["actual_size"] == 400
    assert orderbook["is_truncated"] is True
    assert len(orderbook["asks"]) == 400
    assert len(orderbook["bids"]) == 400
