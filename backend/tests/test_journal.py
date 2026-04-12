# 交易日志功能测试
# 覆盖 storage CRUD、标签统计、API 端点

import json
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.data_storage import DataStorage
from app.main import app


# ==================== Storage 层测试 ====================


@pytest.fixture
def storage(tmp_path):
    """临时数据库的 DataStorage 实例"""
    db_path = tmp_path / "test_journal.db"
    return DataStorage(db_path)


class TestStorageJournal:
    """日志存储层测试"""

    def test_create_and_get_entry(self, storage):
        """创建并读取日志条目"""
        entry_id = storage.save_journal_entry({
            "title": "BTC 突破测试",
            "content": "在 65000 突破后追多",
            "mode": "simulated",
            "inst_id": "BTC-USDT",
            "tags": ["突破", "趋势"],
            "rating": 4,
            "pnl_snapshot": 150.5,
        })

        assert entry_id.startswith("je_")
        entry = storage.get_journal_entry(entry_id)
        assert entry is not None
        assert entry["title"] == "BTC 突破测试"
        assert entry["inst_id"] == "BTC-USDT"
        assert entry["tags"] == ["突破", "趋势"]
        assert entry["rating"] == 4
        assert entry["pnl_snapshot"] == 150.5

    def test_update_entry(self, storage):
        """更新日志条目"""
        entry_id = storage.save_journal_entry({
            "title": "初始标题",
            "mode": "simulated",
        })

        ok = storage.update_journal_entry(entry_id, {
            "title": "更新后标题",
            "rating": 3,
            "tags": ["新标签"],
        })
        assert ok is True

        entry = storage.get_journal_entry(entry_id)
        assert entry["title"] == "更新后标题"
        assert entry["rating"] == 3
        assert entry["tags"] == ["新标签"]

    def test_delete_entry(self, storage):
        """删除日志条目"""
        entry_id = storage.save_journal_entry({
            "title": "待删除",
            "mode": "simulated",
        })
        assert storage.get_journal_entry(entry_id) is not None

        ok = storage.delete_journal_entry(entry_id)
        assert ok is True
        assert storage.get_journal_entry(entry_id) is None

    def test_delete_nonexistent(self, storage):
        """删除不存在的条目返回 False"""
        assert storage.delete_journal_entry("nonexistent") is False

    def test_list_entries_with_filters(self, storage):
        """列表查询与筛选"""
        storage.save_journal_entry({
            "title": "ETH 做空",
            "mode": "simulated",
            "inst_id": "ETH-USDT",
            "tags": ["做空"],
        })
        storage.save_journal_entry({
            "title": "BTC 做多",
            "mode": "live",
            "inst_id": "BTC-USDT",
            "tags": ["做多"],
        })
        storage.save_journal_entry({
            "title": "SOL 网格",
            "mode": "simulated",
            "inst_id": "SOL-USDT",
            "tags": ["网格"],
        })

        # 按模式筛选
        sim_entries = storage.get_journal_entries(mode="simulated")
        assert len(sim_entries) == 2

        # 按交易对筛选
        btc_entries = storage.get_journal_entries(inst_id="BTC-USDT")
        assert len(btc_entries) == 1
        assert btc_entries[0]["title"] == "BTC 做多"

        # 按标签筛选
        short_entries = storage.get_journal_entries(tags=["做空"])
        assert len(short_entries) == 1

    def test_pagination(self, storage):
        """分页功能"""
        for i in range(10):
            storage.save_journal_entry({
                "title": f"日志 {i}",
                "mode": "simulated",
            })

        page1 = storage.get_journal_entries(limit=3, offset=0)
        assert len(page1) == 3

        page2 = storage.get_journal_entries(limit=3, offset=3)
        assert len(page2) == 3

        # 确认不重叠
        ids1 = {e["entry_id"] for e in page1}
        ids2 = {e["entry_id"] for e in page2}
        assert ids1.isdisjoint(ids2)

        total = storage.get_journal_entries_count()
        assert total == 10

    def test_tags_management(self, storage):
        """标签创建和计数"""
        storage.save_journal_entry({
            "title": "测试1",
            "mode": "simulated",
            "tags": ["趋势", "突破"],
        })
        storage.save_journal_entry({
            "title": "测试2",
            "mode": "simulated",
            "tags": ["趋势"],
        })

        tags = storage.get_journal_tags()
        tag_map = {t["tag"]: t["usage_count"] for t in tags}
        assert tag_map["趋势"] == 2
        assert tag_map["突破"] == 1

    def test_stats_by_tag(self, storage):
        """按标签统计"""
        storage.save_journal_entry({
            "title": "盈利交易",
            "mode": "simulated",
            "tags": ["趋势"],
            "pnl_snapshot": 200.0,
        })
        storage.save_journal_entry({
            "title": "亏损交易",
            "mode": "simulated",
            "tags": ["趋势"],
            "pnl_snapshot": -50.0,
        })
        storage.save_journal_entry({
            "title": "网格盈利",
            "mode": "simulated",
            "tags": ["网格"],
            "pnl_snapshot": 80.0,
        })

        stats = storage.get_journal_stats(mode="simulated", group_by="tag")
        assert stats["total_entries"] == 3
        assert stats["group_by"] == "tag"

        group_map = {g["key"]: g for g in stats["groups"]}
        assert group_map["趋势"]["count"] == 2
        assert group_map["趋势"]["total_pnl"] == 150.0
        assert group_map["趋势"]["win_rate"] == 50.0
        assert group_map["网格"]["count"] == 1
        assert group_map["网格"]["win_rate"] == 100.0


# ==================== API 端点测试 ====================


class TestJournalAPI:
    """日志 API 端点测试"""

    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path, monkeypatch):
        """为 API 测试准备临时存储"""
        db_path = tmp_path / "test_api_journal.db"
        test_storage = DataStorage(db_path)

        # 模拟 AppContext
        class FakeCtx:
            def storage(self):
                return test_storage

        monkeypatch.setattr(
            "app.api.journal.get_app_context",
            lambda: FakeCtx(),
        )
        self.client = TestClient(app)

    def test_create_entry(self):
        """POST /api/journal/entries"""
        resp = self.client.post("/api/journal/entries", json={
            "title": "API 测试",
            "mode": "simulated",
            "tags": ["测试"],
            "rating": 3,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["title"] == "API 测试"
        assert data["data"]["tags"] == ["测试"]

    def test_list_entries(self):
        """GET /api/journal/entries"""
        self.client.post("/api/journal/entries", json={"title": "条目1", "mode": "simulated"})
        self.client.post("/api/journal/entries", json={"title": "条目2", "mode": "live"})

        resp = self.client.get("/api/journal/entries")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["total"] == 2

        # 按模式筛选
        resp = self.client.get("/api/journal/entries?mode=live")
        assert resp.json()["total"] == 1

    def test_update_entry(self):
        """PUT /api/journal/entries/{id}"""
        create_resp = self.client.post("/api/journal/entries", json={
            "title": "原标题", "mode": "simulated",
        })
        entry_id = create_resp.json()["data"]["entry_id"]

        resp = self.client.put(f"/api/journal/entries/{entry_id}", json={
            "title": "新标题",
            "rating": 5,
        })
        assert resp.status_code == 200
        assert resp.json()["data"]["title"] == "新标题"
        assert resp.json()["data"]["rating"] == 5

    def test_delete_entry(self):
        """DELETE /api/journal/entries/{id}"""
        create_resp = self.client.post("/api/journal/entries", json={
            "title": "待删除", "mode": "simulated",
        })
        entry_id = create_resp.json()["data"]["entry_id"]

        resp = self.client.delete(f"/api/journal/entries/{entry_id}")
        assert resp.status_code == 200
        assert resp.json()["success"] is True

        # 确认已删除
        resp = self.client.get(f"/api/journal/entries/{entry_id}")
        assert resp.status_code == 404

    def test_get_tags(self):
        """GET /api/journal/tags"""
        self.client.post("/api/journal/entries", json={
            "title": "标签测试", "mode": "simulated", "tags": ["A", "B"],
        })

        resp = self.client.get("/api/journal/tags")
        assert resp.status_code == 200
        tags = resp.json()["data"]
        tag_names = [t["tag"] for t in tags]
        assert "A" in tag_names
        assert "B" in tag_names

    def test_get_stats(self):
        """GET /api/journal/stats"""
        self.client.post("/api/journal/entries", json={
            "title": "盈利", "mode": "simulated",
            "tags": ["趋势"], "pnl_snapshot": 100,
        })
        self.client.post("/api/journal/entries", json={
            "title": "亏损", "mode": "simulated",
            "tags": ["趋势"], "pnl_snapshot": -30,
        })

        resp = self.client.get("/api/journal/stats?mode=simulated&group_by=tag")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total_entries"] == 2
