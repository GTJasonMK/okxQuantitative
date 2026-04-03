from pathlib import Path

import pytest

import app.core.assistant_patrol as assistant_patrol_module
from app.core.assistant_patrol import AssistantOpportunityPatrol
from app.core.data_storage import DataStorage


class FakeCtx:
    def __init__(self, storage):
        self._storage = storage

    def storage(self):
        return self._storage


@pytest.mark.asyncio
async def test_assistant_patrol_persists_run_records(tmp_path: Path, monkeypatch):
    storage = DataStorage(tmp_path / "market.db")
    patrol = AssistantOpportunityPatrol(FakeCtx(storage))

    monkeypatch.setattr(
        assistant_patrol_module.AgentQueryService,
        "patrol_market_opportunities",
        lambda self, request: {
            "inst_type": "SWAP",
            "candidates": [
                {
                    "symbol": "BTC-USDT",
                    "inst_id": "BTC-USDT-SWAP",
                    "priority_score": 82.5,
                    "bias": "bullish",
                    "action": "关注回踩低吸",
                },
            ],
            "summary": {
                "candidate_count": 1,
                "scan_count": 3,
                "message": "发现 1 个可继续跟踪的候选机会。",
            },
        },
        raising=True,
    )

    result = await patrol.run_cycle(trigger="manual", force=True)
    runs = storage.list_assistant_patrol_runs(limit=10)

    assert result["run_id"].startswith("assistant-patrol-run-")
    assert len(runs) == 1
    assert runs[0]["run_id"] == result["run_id"]
    assert runs[0]["summary"]["candidate_count"] == 1
    assert runs[0]["candidates"][0]["inst_id"] == "BTC-USDT-SWAP"
