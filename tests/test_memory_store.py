"""Tests for the persistent memory store."""

import pytest
from pathlib import Path
from memory.store import MemoryStore, VALID_CATEGORIES


@pytest.fixture
def store(tmp_path: Path) -> MemoryStore:
    """Create a fresh MemoryStore with a temporary database."""
    return MemoryStore(db_path=tmp_path / "test.db")


class TestLearnings:

    def test_add_and_retrieve(self, store: MemoryStore) -> None:
        learning_id = store.add_learning("Test learning", category="general")
        assert learning_id == 1
        results = store.list_learnings()
        assert len(results) == 1
        assert results[0]["content"] == "Test learning"

    def test_invalid_category_raises(self, store: MemoryStore) -> None:
        with pytest.raises(ValueError, match="Invalid category"):
            store.add_learning("Test", category="nonexistent")

    def test_all_categories_valid(self, store: MemoryStore) -> None:
        for cat in VALID_CATEGORIES:
            assert store.add_learning(f"Test {cat}", category=cat) > 0

    def test_search_finds_match(self, store: MemoryStore) -> None:
        store.add_learning("DarkShare must be between 0 and 1", category="domain")
        store.add_learning("Use pytest fixtures for database tests", category="testing")
        results = store.search("DarkShare")
        assert len(results) == 1
        assert "DarkShare" in results[0]["content"]

    def test_search_empty_for_no_match(self, store: MemoryStore) -> None:
        store.add_learning("Something about Python", category="general")
        assert store.search("nonexistent_xyz") == []

    def test_filter_by_category(self, store: MemoryStore) -> None:
        store.add_learning("API quirk", category="api")
        store.add_learning("Domain insight", category="domain")
        store.add_learning("Another API quirk", category="api")
        results = store.list_learnings(category="api")
        assert len(results) == 2
        assert all(r["category"] == "api" for r in results)

    def test_count_learnings(self, store: MemoryStore) -> None:
        store.add_learning("One", category="api")
        store.add_learning("Two", category="api")
        store.add_learning("Three", category="domain")
        counts = store.count_learnings()
        assert counts["api"] == 2
        assert counts["domain"] == 1


class TestCorrections:

    def test_add_correction(self, store: MemoryStore) -> None:
        cid = store.add_correction("Used fillna", "Spec forbids it", "Propagate NaN")
        assert cid == 1
        corrections = store.list_corrections()
        assert len(corrections) == 1
        assert corrections[0]["became_rule"] == 0

    def test_promote_to_rule(self, store: MemoryStore) -> None:
        cid = store.add_correction("Used fillna", "Spec forbids it", "Propagate NaN")
        lid = store.promote_correction_to_rule(cid)
        assert lid > 0
        assert store.list_corrections()[0]["became_rule"] == 1
        learnings = store.list_learnings()
        assert any("RULE:" in l["content"] for l in learnings)

    def test_promote_nonexistent_raises(self, store: MemoryStore) -> None:
        with pytest.raises(ValueError, match="not found"):
            store.promote_correction_to_rule(999)

    def test_correction_increments_session_counter(self, store: MemoryStore) -> None:
        sid = store.start_session("Test session")
        store.add_correction("X", "Y", "Z", session_id=sid)
        assert store.get_last_session()["corrections_count"] == 1


class TestSessions:

    def test_start_and_end(self, store: MemoryStore) -> None:
        sid = store.start_session("Build parser", modules=["src/parser.py"])
        store.end_session(sid, "Completed parser", modules=["src/parser.py", "tests/test_parser.py"], tests_added=8)
        last = store.get_last_session()
        assert last["summary"] == "Completed parser"
        assert last["tests_added"] == 8
        assert "tests/test_parser.py" in last["modules_touched"]

    def test_empty_returns_none(self, store: MemoryStore) -> None:
        assert store.get_last_session() is None

    def test_stats(self, store: MemoryStore) -> None:
        store.start_session("S1")
        store.start_session("S2")
        store.add_learning("L1", category="general")
        store.add_correction("X", "Y", "Z")
        stats = store.get_session_stats()
        assert stats["total_sessions"] == 2
        assert stats["total_learnings"] == 1
        assert stats["total_corrections"] == 1


class TestContext:

    def test_context_with_data(self, store: MemoryStore) -> None:
        sid = store.start_session("Build features")
        store.add_learning("API returns integers", category="api")
        store.add_correction("Used float", "Should be int", "Cast to int")
        store.end_session(sid, "Done", tests_added=5)
        context = store.get_session_context()
        assert "Project Memory Context" in context
        assert "API returns integers" in context
        assert "Should be int" in context

    def test_context_empty(self, store: MemoryStore) -> None:
        context = store.get_session_context()
        assert "0 sessions" in context
