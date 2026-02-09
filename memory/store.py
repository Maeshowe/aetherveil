"""Project Memory Store — Persistent SQLite storage for learnings and sessions.

A lightweight memory system that stores project learnings, corrections,
and session data in SQLite with FTS5 full-text search. Survives session
restarts and keeps context across Claude Code conversations.

Usage:
    from memory.store import MemoryStore

    store = MemoryStore()
    store.add_learning("Always validate input before processing", category="quality")
    results = store.search("validation")
    store.start_session("Building the parser module")
    store.end_session(session_id=1, summary="Completed parser with 12 tests")
"""

import sqlite3
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS learnings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'general',
    source TEXT DEFAULT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    session_id INTEGER DEFAULT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS learnings_fts USING fts5(
    content,
    category,
    content='learnings',
    content_rowid='id',
    tokenize='porter unicode61'
);

CREATE TRIGGER IF NOT EXISTS learnings_ai AFTER INSERT ON learnings BEGIN
    INSERT INTO learnings_fts(rowid, content, category)
    VALUES (new.id, new.content, new.category);
END;

CREATE TRIGGER IF NOT EXISTS learnings_ad AFTER DELETE ON learnings BEGIN
    INSERT INTO learnings_fts(learnings_fts, rowid, content, category)
    VALUES ('delete', old.id, old.content, old.category);
END;

CREATE TRIGGER IF NOT EXISTS learnings_au AFTER UPDATE ON learnings BEGIN
    INSERT INTO learnings_fts(learnings_fts, rowid, content, category)
    VALUES ('delete', old.id, old.content, old.category);
    INSERT INTO learnings_fts(rowid, content, category)
    VALUES (new.id, new.content, new.category);
END;

CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    goal TEXT NOT NULL,
    started_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    ended_at TEXT DEFAULT NULL,
    summary TEXT DEFAULT NULL,
    modules_touched TEXT DEFAULT '[]',
    corrections_count INTEGER DEFAULT 0,
    tests_added INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS corrections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    what_i_did TEXT NOT NULL,
    what_was_wrong TEXT NOT NULL,
    correct_approach TEXT NOT NULL,
    became_rule INTEGER DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    session_id INTEGER DEFAULT NULL
);
"""

VALID_CATEGORIES = [
    "navigation",
    "editing",
    "testing",
    "quality",
    "architecture",
    "performance",
    "domain",
    "api",
    "debugging",
    "general",
]


class MemoryStore:
    """Persistent project memory using SQLite with full-text search.

    Stores learnings, corrections, and session data in a local SQLite
    database. Uses FTS5 for fast BM25-ranked search across all learnings.

    Args:
        db_path: Path to SQLite database file.
            Defaults to '.memory/project.db' in the current directory.
    """

    def __init__(self, db_path: str | Path | None = None) -> None:
        if db_path is None:
            db_path = Path(".memory") / "project.db"
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema if not exists."""
        with self._connect() as conn:
            conn.executescript(SCHEMA_SQL)

    def _connect(self) -> sqlite3.Connection:
        """Create a database connection with WAL mode for performance."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    # ── Learnings ──────────────────────────────────────────────

    def add_learning(
        self,
        content: str,
        category: str = "general",
        source: str | None = None,
        session_id: int | None = None,
    ) -> int:
        """Store a new learning.

        Args:
            content: What was learned — a clear, actionable statement.
            category: One of VALID_CATEGORIES.
            source: Where this came from (e.g., 'user correction', 'test failure').
            session_id: Link to a session if applicable.

        Returns:
            The ID of the new learning.

        Raises:
            ValueError: If category is not valid.
        """
        if category not in VALID_CATEGORIES:
            raise ValueError(
                f"Invalid category '{category}'. "
                f"Valid: {', '.join(VALID_CATEGORIES)}"
            )
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO learnings (content, category, source, session_id) "
                "VALUES (?, ?, ?, ?)",
                (content, category, source, session_id),
            )
            return cursor.lastrowid  # type: ignore[return-value]

    def search(self, query: str, limit: int = 10) -> list[dict]:
        """Search learnings using BM25-ranked full-text search.

        Args:
            query: Search terms (supports FTS5 syntax).
            limit: Maximum results to return.

        Returns:
            List of matching learnings, ranked by relevance.
        """
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT l.id, l.content, l.category, l.source, l.created_at, rank "
                "FROM learnings_fts "
                "JOIN learnings l ON l.id = learnings_fts.rowid "
                "WHERE learnings_fts MATCH ? "
                "ORDER BY rank "
                "LIMIT ?",
                (query, limit),
            ).fetchall()
            return [dict(row) for row in rows]

    def list_learnings(
        self,
        category: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """List learnings, optionally filtered by category.

        Args:
            category: Filter by category, or None for all.
            limit: Maximum results.

        Returns:
            List of learnings, newest first.
        """
        with self._connect() as conn:
            if category:
                rows = conn.execute(
                    "SELECT id, content, category, source, created_at "
                    "FROM learnings WHERE category = ? "
                    "ORDER BY created_at DESC LIMIT ?",
                    (category, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, content, category, source, created_at "
                    "FROM learnings ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            return [dict(row) for row in rows]

    def count_learnings(self) -> dict[str, int]:
        """Count learnings per category.

        Returns:
            Dictionary of category → count.
        """
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT category, COUNT(*) as count "
                "FROM learnings GROUP BY category ORDER BY count DESC"
            ).fetchall()
            return {row["category"]: row["count"] for row in rows}

    # ── Corrections ────────────────────────────────────────────

    def add_correction(
        self,
        what_i_did: str,
        what_was_wrong: str,
        correct_approach: str,
        session_id: int | None = None,
    ) -> int:
        """Record a correction from the user.

        Args:
            what_i_did: What Claude did.
            what_was_wrong: Why it was wrong.
            correct_approach: What should have been done.
            session_id: Link to current session.

        Returns:
            The correction ID.
        """
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO corrections "
                "(what_i_did, what_was_wrong, correct_approach, session_id) "
                "VALUES (?, ?, ?, ?)",
                (what_i_did, what_was_wrong, correct_approach, session_id),
            )
            if session_id:
                conn.execute(
                    "UPDATE sessions SET corrections_count = corrections_count + 1 "
                    "WHERE id = ?",
                    (session_id,),
                )
            return cursor.lastrowid  # type: ignore[return-value]

    def promote_correction_to_rule(self, correction_id: int) -> int:
        """Promote a correction to a permanent learning rule.

        Args:
            correction_id: The correction to promote.

        Returns:
            The new learning ID.

        Raises:
            ValueError: If correction not found.
        """
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM corrections WHERE id = ?",
                (correction_id,),
            ).fetchone()
            if not row:
                raise ValueError(f"Correction {correction_id} not found")

            conn.execute(
                "UPDATE corrections SET became_rule = 1 WHERE id = ?",
                (correction_id,),
            )
            content = (
                f"RULE: {row['correct_approach']} "
                f"(Previously incorrect: {row['what_was_wrong']})"
            )
            cursor = conn.execute(
                "INSERT INTO learnings (content, category, source, session_id) "
                "VALUES (?, 'quality', 'correction', ?)",
                (content, row["session_id"]),
            )
            return cursor.lastrowid  # type: ignore[return-value]

    def list_corrections(self, limit: int = 20) -> list[dict]:
        """List recent corrections, newest first."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM corrections ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(row) for row in rows]

    # ── Sessions ───────────────────────────────────────────────

    def start_session(
        self,
        goal: str,
        modules: list[str] | None = None,
    ) -> int:
        """Start a new work session.

        Args:
            goal: What this session aims to accomplish.
            modules: List of modules expected to be touched.

        Returns:
            The session ID.
        """
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO sessions (goal, modules_touched) VALUES (?, ?)",
                (goal, json.dumps(modules or [])),
            )
            return cursor.lastrowid  # type: ignore[return-value]

    def end_session(
        self,
        session_id: int,
        summary: str,
        modules: list[str] | None = None,
        tests_added: int = 0,
    ) -> None:
        """End a work session with a summary.

        Args:
            session_id: The session to end.
            summary: What was accomplished.
            modules: Final list of modules touched.
            tests_added: Number of tests written.
        """
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with self._connect() as conn:
            updates = ["ended_at = ?", "summary = ?", "tests_added = ?"]
            params: list = [now, summary, tests_added]
            if modules is not None:
                updates.append("modules_touched = ?")
                params.append(json.dumps(modules))
            params.append(session_id)
            conn.execute(
                f"UPDATE sessions SET {', '.join(updates)} WHERE id = ?",
                params,
            )

    def get_last_session(self) -> dict | None:
        """Get the most recent session, or None if empty."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM sessions ORDER BY started_at DESC LIMIT 1"
            ).fetchone()
            if row:
                result = dict(row)
                result["modules_touched"] = json.loads(result["modules_touched"])
                return result
            return None

    def get_session_stats(self) -> dict:
        """Get aggregate statistics across all sessions."""
        with self._connect() as conn:
            stats = {}
            for key, query in [
                ("total_sessions", "SELECT COUNT(*) FROM sessions"),
                ("total_learnings", "SELECT COUNT(*) FROM learnings"),
                ("total_corrections", "SELECT COUNT(*) FROM corrections"),
                ("corrections_became_rules", "SELECT COUNT(*) FROM corrections WHERE became_rule = 1"),
                ("total_tests_added", "SELECT COALESCE(SUM(tests_added), 0) FROM sessions"),
            ]:
                stats[key] = conn.execute(query).fetchone()[0]
            return stats

    # ── Context Loading ────────────────────────────────────────

    def get_session_context(self, max_learnings: int = 20) -> str:
        """Generate a context summary for session start.

        Produces a formatted string with recent learnings, last session
        summary, and correction patterns — ready to paste into context.

        Args:
            max_learnings: Maximum recent learnings to include.

        Returns:
            Formatted context string.
        """
        stats = self.get_session_stats()
        last = self.get_last_session()
        recent = self.list_learnings(limit=max_learnings)
        corrections = self.list_corrections(limit=5)

        lines = ["## 📋 Project Memory Context", ""]
        lines.append(
            f"**Stats**: {stats['total_sessions']} sessions, "
            f"{stats['total_learnings']} learnings, "
            f"{stats['total_corrections']} corrections "
            f"({stats['corrections_became_rules']} became rules), "
            f"{stats['total_tests_added']} tests written"
        )
        lines.append("")

        if last:
            lines.append("### Last Session")
            lines.append(f"- **Goal**: {last['goal']}")
            if last.get("summary"):
                lines.append(f"- **Summary**: {last['summary']}")
            if last.get("modules_touched"):
                lines.append(f"- **Modules**: {', '.join(last['modules_touched'])}")
            lines.append("")

        if recent:
            lines.append("### Recent Learnings")
            for item in recent:
                lines.append(f"- [{item['category']}] {item['content']}")
            lines.append("")

        if corrections:
            lines.append("### Recent Corrections (don't repeat these)")
            for c in corrections:
                lines.append(f"- ❌ {c['what_was_wrong']} → ✅ {c['correct_approach']}")
            lines.append("")

        return "\n".join(lines)
