"""Local persistent store for Athena Memory.

The store uses only Python's standard library and SQLite FTS5.  It keeps
provenance and trust metadata outside recalled prose so a memory cannot promote
its own authority through prompt injection.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
import threading
import time
import unicodedata
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


_SCHEMA = """
CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'fact',
    scope TEXT NOT NULL DEFAULT 'global',
    importance REAL NOT NULL DEFAULT 0.5,
    confidence REAL NOT NULL DEFAULT 0.7,
    trust_origin TEXT NOT NULL DEFAULT 'agent',
    source TEXT NOT NULL DEFAULT 'athena_memory',
    session_id TEXT NOT NULL DEFAULT '',
    supersedes_id INTEGER,
    status TEXT NOT NULL DEFAULT 'active',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    last_accessed_at REAL,
    access_count INTEGER NOT NULL DEFAULT 0,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (supersedes_id) REFERENCES memories(id)
);

CREATE UNIQUE INDEX IF NOT EXISTS memories_active_content
ON memories(content_hash, scope)
WHERE status = 'active';

CREATE INDEX IF NOT EXISTS memories_scope_status
ON memories(scope, status, updated_at DESC);

CREATE INDEX IF NOT EXISTS memories_kind_status
ON memories(kind, status, importance DESC);

CREATE TABLE IF NOT EXISTS memory_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    memory_id INTEGER NOT NULL,
    event TEXT NOT NULL,
    created_at REAL NOT NULL,
    details_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS memory_events_memory_time
ON memory_events(memory_id, created_at DESC);

CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
    content,
    kind,
    scope,
    content='memories',
    content_rowid='id',
    tokenize='unicode61 remove_diacritics 2'
);

CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
    INSERT INTO memories_fts(rowid, content, kind, scope)
    VALUES (new.id, new.content, new.kind, new.scope);
END;

CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, content, kind, scope)
    VALUES ('delete', old.id, old.content, old.kind, old.scope);
END;

CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, content, kind, scope)
    VALUES ('delete', old.id, old.content, old.kind, old.scope);
    INSERT INTO memories_fts(rowid, content, kind, scope)
    VALUES (new.id, new.content, new.kind, new.scope);
END;
"""


_KINDS = {
    "fact",
    "preference",
    "decision",
    "project",
    "person",
    "commitment",
    "lesson",
    "episode",
}
_TRUST_ORIGINS = {"owner", "agent", "untrusted", "system"}
_TRUST_RANK = {"untrusted": 0, "agent": 1, "system": 2, "owner": 3}
_TOKEN_RE = re.compile(r"[\w@./:+-]+", re.UNICODE)


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _normalize_content(content: str) -> str:
    return " ".join(str(content).strip().split())


def _content_hash(content: str) -> str:
    normalized = _normalize_content(content).casefold()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _fts_query(query: str) -> str:
    tokens = _TOKEN_RE.findall(query)
    tokens = [token.replace('"', '""') for token in tokens if token.strip("-_")]
    return " OR ".join(f'"{token}"' for token in tokens[:24])


def _similarity_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", str(value).casefold())
    return " ".join(
        "".join(ch for ch in token if ch.isalnum())
        for token in decomposed.split()
        if any(ch.isalnum() for ch in token)
    )


def _fuzzy_similarity(left: str, right: str) -> float:
    """Local typo/morphology similarity used beside SQLite FTS.

    This is intentionally deterministic and dependency-free. It is not sold as
    an embedding model; it recovers useful candidates that exact token FTS
    misses (accents, suffixes, minor misspellings and joined identifiers).
    """

    a = _similarity_text(left)
    b = _similarity_text(right)
    if not a or not b:
        return 0.0
    if a in b or b in a:
        substring = 1.0
    else:
        substring = 0.0
    a_terms = {term if len(term) <= 5 else term[:5] for term in a.split()}
    b_terms = {term if len(term) <= 5 else term[:5] for term in b.split()}
    union = a_terms | b_terms
    term_score = len(a_terms & b_terms) / len(union) if union else 0.0
    compact_a = a.replace(" ", "_")
    compact_b = b.replace(" ", "_")
    a_grams = {compact_a[i:i + 3] for i in range(max(1, len(compact_a) - 2))}
    b_grams = {compact_b[i:i + 3] for i in range(max(1, len(compact_b) - 2))}
    denom = len(a_grams) + len(b_grams)
    trigram = (2.0 * len(a_grams & b_grams) / denom) if denom else 0.0
    return min(1.0, 0.55 * term_score + 0.35 * trigram + 0.10 * substring)


class AthenaMemoryStore:
    """Thread-safe SQLite store for durable, correctable memory records."""

    def __init__(self, db_path: str, *, temporal_half_life_days: float = 120.0):
        self.db_path = Path(db_path).expanduser().resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.temporal_half_life_days = max(0.0, float(temporal_half_life_days))
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA busy_timeout = 5000")
        try:
            from athena_state import apply_wal_with_fallback

            apply_wal_with_fallback(self._conn, db_label="athena_memory.db")
        except Exception:
            try:
                self._conn.execute("PRAGMA journal_mode = WAL")
            except sqlite3.DatabaseError:
                self._conn.execute("PRAGMA journal_mode = DELETE")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def _record_event(self, memory_id: int, event: str, details_json: str = "{}") -> None:
        self._conn.execute(
            "INSERT INTO memory_events(memory_id, event, created_at, details_json) VALUES (?, ?, ?, ?)",
            (int(memory_id), str(event), time.time(), str(details_json or "{}")),
        )

    @staticmethod
    def _validate_kind(kind: str) -> str:
        normalized = str(kind or "fact").strip().lower()
        if normalized not in _KINDS:
            raise ValueError(f"unsupported memory kind: {kind}")
        return normalized

    @staticmethod
    def _validate_trust(trust_origin: str) -> str:
        normalized = str(trust_origin or "agent").strip().lower()
        if normalized not in _TRUST_ORIGINS:
            raise ValueError(f"unsupported trust origin: {trust_origin}")
        return normalized

    def remember(
        self,
        content: str,
        *,
        kind: str = "fact",
        scope: str = "global",
        importance: float = 0.5,
        confidence: float = 0.7,
        trust_origin: str = "agent",
        source: str = "athena_memory",
        session_id: str = "",
        supersedes_id: Optional[int] = None,
        metadata_json: str = "{}",
    ) -> Dict[str, Any]:
        clean = _normalize_content(content)
        if not clean:
            raise ValueError("memory content must not be empty")
        if len(clean) > 12000:
            raise ValueError("memory content exceeds 12000 characters")
        kind = self._validate_kind(kind)
        trust_origin = self._validate_trust(trust_origin)
        scope = str(scope or "global").strip() or "global"
        digest = _content_hash(clean)
        now = time.time()

        with self._lock:
            existing = self._conn.execute(
                """
                SELECT * FROM memories
                WHERE content_hash = ? AND scope = ? AND status = 'active'
                """,
                (digest, scope),
            ).fetchone()
            if existing is not None:
                existing_trust = str(existing["trust_origin"])
                evidence_is_stronger = (
                    _TRUST_RANK[trust_origin] >= _TRUST_RANK.get(existing_trust, 0)
                )
                effective_trust = trust_origin if evidence_is_stronger else existing_trust
                effective_kind = kind if evidence_is_stronger else str(existing["kind"])
                effective_source = (
                    str(source or "athena_memory")
                    if evidence_is_stronger
                    else str(existing["source"])
                )
                effective_metadata = (
                    str(metadata_json or "{}")
                    if evidence_is_stronger
                    else str(existing["metadata_json"])
                )
                self._conn.execute(
                    """
                    UPDATE memories
                    SET importance = MAX(importance, ?),
                        confidence = MAX(confidence, ?),
                        updated_at = ?,
                        trust_origin = ?,
                        kind = ?,
                        source = ?,
                        metadata_json = ?,
                        session_id = CASE WHEN ? = '' THEN session_id ELSE ? END
                    WHERE id = ?
                    """,
                    (
                        _clamp(importance),
                        _clamp(confidence),
                        now,
                        effective_trust,
                        effective_kind,
                        effective_source,
                        effective_metadata,
                        str(session_id or ""),
                        str(session_id or ""),
                        existing["id"],
                    ),
                )
                self._record_event(int(existing["id"]), "reinforced")
                self._conn.commit()
                result = self.get(int(existing["id"]))
                result["created"] = False
                return result

            if supersedes_id is not None:
                self._conn.execute(
                    "UPDATE memories SET status = 'superseded', updated_at = ? WHERE id = ?",
                    (now, int(supersedes_id)),
                )
                self._record_event(int(supersedes_id), "superseded")

            cursor = self._conn.execute(
                """
                INSERT INTO memories (
                    content, content_hash, kind, scope, importance, confidence,
                    trust_origin, source, session_id, supersedes_id, status,
                    created_at, updated_at, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)
                """,
                (
                    clean,
                    digest,
                    kind,
                    scope,
                    _clamp(importance),
                    _clamp(confidence),
                    trust_origin,
                    str(source or "athena_memory"),
                    str(session_id or ""),
                    supersedes_id,
                    now,
                    now,
                    str(metadata_json or "{}"),
                ),
            )
            self._record_event(int(cursor.lastrowid), "created")
            self._conn.commit()
            result = self.get(int(cursor.lastrowid))
            result["created"] = True
            return result

    def get(self, memory_id: int) -> Dict[str, Any]:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM memories WHERE id = ?", (int(memory_id),)
            ).fetchone()
        if row is None:
            raise KeyError(f"memory {memory_id} not found")
        return dict(row)

    def _scope_clause(self, scope: Optional[str]) -> tuple[str, List[Any]]:
        if not scope or scope == "all":
            return "", []
        if scope == "global":
            return " AND m.scope = ?", ["global"]
        return " AND m.scope IN (?, 'global')", [scope]

    def recall(
        self,
        query: str,
        *,
        scope: Optional[str] = None,
        kind: Optional[str] = None,
        limit: int = 6,
        min_score: float = 0.0,
    ) -> List[Dict[str, Any]]:
        clean_query = str(query or "").strip()
        if not clean_query:
            return []
        limit = max(1, min(int(limit), 50))
        candidate_limit = max(limit * 4, 12)
        scope_sql, scope_params = self._scope_clause(scope)
        kind_sql = ""
        kind_params: List[Any] = []
        if kind:
            kind_sql = " AND m.kind = ?"
            kind_params.append(self._validate_kind(kind))

        match = _fts_query(clean_query)
        rows: Iterable[sqlite3.Row]
        with self._lock:
            fts_rows: List[sqlite3.Row] = []
            if match:
                try:
                    fts_rows = self._conn.execute(
                        f"""
                        SELECT m.*, bm25(memories_fts) AS lexical_rank
                        FROM memories_fts
                        JOIN memories m ON m.id = memories_fts.rowid
                        WHERE memories_fts MATCH ?
                          AND m.status = 'active'
                          {scope_sql}
                          {kind_sql}
                        ORDER BY lexical_rank ASC, m.importance DESC
                        LIMIT ?
                        """,
                        [match, *scope_params, *kind_params, candidate_limit],
                    ).fetchall()
                except sqlite3.OperationalError:
                    fts_rows = self._fallback_recall(
                        clean_query,
                        scope=scope,
                        kind=kind,
                        limit=candidate_limit,
                    )
            else:
                fts_rows = []

            # A bounded fuzzy candidate pool complements FTS for accents,
            # suffixes, typos and identifier formatting. The cap keeps recall
            # predictable even when a profile accumulates thousands of facts.
            fuzzy_limit = min(max(candidate_limit * 8, 100), 500)
            fuzzy_rows = self._conn.execute(
                f"""
                SELECT m.*, 0.0 AS lexical_rank
                FROM memories m
                WHERE m.status = 'active' {scope_sql} {kind_sql}
                ORDER BY m.importance DESC, m.updated_at DESC
                LIMIT ?
                """,
                [*scope_params, *kind_params, fuzzy_limit],
            ).fetchall()

            seen: set[int] = set()
            row_list: List[sqlite3.Row] = []
            fts_positions: Dict[int, int] = {}
            for position, row in enumerate(fts_rows):
                memory_id = int(row["id"])
                if memory_id in seen:
                    continue
                seen.add(memory_id)
                fts_positions[memory_id] = position
                row_list.append(row)
            for row in fuzzy_rows:
                memory_id = int(row["id"])
                if memory_id not in seen:
                    seen.add(memory_id)
                    row_list.append(row)

            now = time.time()
            ranked: List[Dict[str, Any]] = []
            for row in row_list:
                item = dict(row)
                memory_id = int(item["id"])
                fts_position = fts_positions.get(memory_id)
                lexical = 0.0 if fts_position is None else 1.0 / (1.0 + fts_position)
                fuzzy = _fuzzy_similarity(clean_query, str(item["content"]))
                if fts_position is None and fuzzy < 0.12:
                    continue
                age_days = max(0.0, (now - float(item["updated_at"])) / 86400.0)
                if self.temporal_half_life_days > 0:
                    recency = math.exp(
                        -math.log(2.0) * age_days / self.temporal_half_life_days
                    )
                else:
                    recency = 1.0
                score = (
                    0.42 * lexical
                    + 0.23 * fuzzy
                    + 0.15 * float(item["importance"])
                    + 0.10 * float(item["confidence"])
                    + 0.10 * recency
                )
                item["score"] = round(score, 6)
                item["lexical_score"] = round(lexical, 6)
                item["similarity_score"] = round(fuzzy, 6)
                item["retrieval"] = "fts+fuzzy" if lexical else "fuzzy"
                item["recency_score"] = round(recency, 6)
                item.pop("content_hash", None)
                item.pop("metadata_json", None)
                if score >= float(min_score):
                    ranked.append(item)

            ranked.sort(key=lambda item: (item["score"], item["importance"]), reverse=True)
            ranked = ranked[:limit]
            if ranked:
                ids = [int(item["id"]) for item in ranked]
                placeholders = ",".join("?" for _ in ids)
                self._conn.execute(
                    f"""
                    UPDATE memories
                    SET access_count = access_count + 1, last_accessed_at = ?
                    WHERE id IN ({placeholders})
                    """,
                    [now, *ids],
                )
                self._conn.commit()
            return ranked

    def _fallback_recall(
        self,
        query: str,
        *,
        scope: Optional[str],
        kind: Optional[str],
        limit: int,
    ) -> List[sqlite3.Row]:
        tokens = _TOKEN_RE.findall(query)[:8]
        if not tokens:
            return []
        where = " OR ".join("m.content LIKE ?" for _ in tokens)
        params: List[Any] = [f"%{token}%" for token in tokens]
        scope_sql, scope_params = self._scope_clause(scope)
        kind_sql = ""
        kind_params: List[Any] = []
        if kind:
            kind_sql = " AND m.kind = ?"
            kind_params.append(self._validate_kind(kind))
        return self._conn.execute(
            f"""
            SELECT m.*, 0.0 AS lexical_rank
            FROM memories m
            WHERE m.status = 'active' AND ({where}) {scope_sql} {kind_sql}
            ORDER BY m.importance DESC, m.updated_at DESC
            LIMIT ?
            """,
            [*params, *scope_params, *kind_params, int(limit)],
        ).fetchall()

    def list_memories(
        self,
        *,
        scope: Optional[str] = None,
        kind: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        limit = max(1, min(int(limit), 100))
        clauses = ["status = 'active'"]
        params: List[Any] = []
        if scope and scope != "all":
            clauses.append("scope = ?")
            params.append(scope)
        if kind:
            clauses.append("kind = ?")
            params.append(self._validate_kind(kind))
        params.append(limit)
        with self._lock:
            rows = self._conn.execute(
                f"""
                SELECT * FROM memories
                WHERE {' AND '.join(clauses)}
                ORDER BY importance DESC, updated_at DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [dict(row) for row in rows]

    def update(
        self,
        memory_id: int,
        *,
        content: Optional[str] = None,
        kind: Optional[str] = None,
        scope: Optional[str] = None,
        importance: Optional[float] = None,
        confidence: Optional[float] = None,
        _event: str = "updated",
    ) -> Dict[str, Any]:
        current = self.get(memory_id)
        assignments = ["updated_at = ?"]
        params: List[Any] = [time.time()]
        if content is not None:
            clean = _normalize_content(content)
            if not clean:
                raise ValueError("memory content must not be empty")
            assignments.extend(["content = ?", "content_hash = ?"])
            params.extend([clean, _content_hash(clean)])
        if kind is not None:
            assignments.append("kind = ?")
            params.append(self._validate_kind(kind))
        if scope is not None:
            normalized_scope = str(scope).strip()
            if not normalized_scope:
                raise ValueError("scope must not be empty")
            assignments.append("scope = ?")
            params.append(normalized_scope)
        if importance is not None:
            assignments.append("importance = ?")
            params.append(_clamp(importance))
        if confidence is not None:
            assignments.append("confidence = ?")
            params.append(_clamp(confidence))
        params.append(int(memory_id))
        with self._lock:
            self._conn.execute(
                f"UPDATE memories SET {', '.join(assignments)} WHERE id = ?",
                params,
            )
            self._record_event(int(memory_id), _event)
            self._conn.commit()
        result = self.get(memory_id)
        result["previous"] = current
        return result

    def forget(self, memory_id: int) -> bool:
        """Permanently delete a memory and its FTS entry."""

        with self._lock:
            exists = self._conn.execute(
                "SELECT 1 FROM memories WHERE id = ?", (int(memory_id),)
            ).fetchone()
            if exists is None:
                return False
            cursor = self._conn.execute(
                "DELETE FROM memories WHERE id = ?", (int(memory_id),)
            )
            self._record_event(int(memory_id), "forgotten")
            self._conn.commit()
            return cursor.rowcount > 0

    def forget_content(self, content: str, *, scope: Optional[str] = None) -> int:
        digest = _content_hash(content)
        sql = "DELETE FROM memories WHERE content_hash = ?"
        params: List[Any] = [digest]
        if scope:
            sql += " AND scope = ?"
            params.append(scope)
        with self._lock:
            ids = [
                int(row["id"])
                for row in self._conn.execute(
                    sql.replace("DELETE FROM", "SELECT id FROM", 1), params
                ).fetchall()
            ]
            cursor = self._conn.execute(sql, params)
            for memory_id in ids:
                self._record_event(memory_id, "forgotten")
            self._conn.commit()
            return int(cursor.rowcount)

    def feedback(self, memory_id: int, *, helpful: bool) -> Dict[str, Any]:
        current = self.get(memory_id)
        confidence_delta = 0.05 if helpful else -0.15
        importance_delta = 0.02 if helpful else -0.05
        return self.update(
            memory_id,
            confidence=float(current["confidence"]) + confidence_delta,
            importance=float(current["importance"]) + importance_delta,
            _event="feedback_helpful" if helpful else "feedback_unhelpful",
        )

    def history(self, memory_id: Optional[int] = None, *, limit: int = 50) -> List[Dict[str, Any]]:
        limit = max(1, min(int(limit), 500))
        sql = "SELECT * FROM memory_events"
        params: List[Any] = []
        if memory_id is not None:
            sql += " WHERE memory_id = ?"
            params.append(int(memory_id))
        sql += " ORDER BY created_at DESC, id DESC LIMIT ?"
        params.append(limit)
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def timeline(
        self,
        memory_id: int,
        *,
        before: int = 3,
        after: int = 3,
        same_scope: bool = True,
        same_session: bool = False,
    ) -> Dict[str, Any]:
        """Return chronological context around one memory.

        Search answers *which* records may matter; timeline answers *what was
        happening around* a selected record.  The anchor is included even when
        it has been superseded, while neighbouring records are active only.
        This keeps correction history inspectable without allowing stale
        records to flood ordinary recall.
        """

        before = max(0, min(int(before), 25))
        after = max(0, min(int(after), 25))
        anchor = self.get(memory_id)
        clauses = ["status = 'active'"]
        params: List[Any] = []
        if same_scope:
            clauses.append("scope = ?")
            params.append(str(anchor["scope"]))
        if same_session:
            clauses.append("session_id = ?")
            params.append(str(anchor.get("session_id") or ""))
        filters = " AND ".join(clauses)
        anchor_key = (float(anchor["created_at"]), int(anchor["id"]))

        with self._lock:
            earlier = self._conn.execute(
                f"""
                SELECT * FROM memories
                WHERE {filters}
                  AND (created_at < ? OR (created_at = ? AND id < ?))
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                [*params, anchor_key[0], anchor_key[0], anchor_key[1], before],
            ).fetchall()
            later = self._conn.execute(
                f"""
                SELECT * FROM memories
                WHERE {filters}
                  AND (created_at > ? OR (created_at = ? AND id > ?))
                ORDER BY created_at ASC, id ASC
                LIMIT ?
                """,
                [*params, anchor_key[0], anchor_key[0], anchor_key[1], after],
            ).fetchall()

        items = [dict(row) for row in reversed(earlier)]
        items.append(anchor)
        items.extend(dict(row) for row in later)
        return {
            "anchor_id": int(memory_id),
            "same_scope": bool(same_scope),
            "same_session": bool(same_session),
            "memories": items,
        }

    def review(
        self,
        *,
        limit: int = 200,
        stale_after_days: float = 180.0,
        low_confidence: float = 0.35,
        duplicate_threshold: float = 0.92,
    ) -> Dict[str, Any]:
        """Inspect memory hygiene without changing data.

        Owner and system memories are reported for visibility but are never
        selected for automatic archival.  ``safe_archive_ids`` contains only
        agent/untrusted records that are both stale and weak, or the weaker
        side of a very close duplicate pair.
        """

        limit = max(1, min(int(limit), 500))
        cutoff = time.time() - max(1.0, float(stale_after_days)) * 86400.0
        threshold = _clamp(low_confidence)
        duplicate_threshold = max(0.75, min(float(duplicate_threshold), 1.0))
        with self._lock:
            rows = [
                dict(row)
                for row in self._conn.execute(
                    """
                    SELECT * FROM memories WHERE status = 'active'
                    ORDER BY updated_at ASC, id ASC LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
            ]

        stale = [
            row for row in rows
            if float(row["updated_at"]) < cutoff
            and int(row.get("access_count") or 0) == 0
            and row.get("last_accessed_at") is None
        ]
        weak = [row for row in rows if float(row["confidence"]) < threshold]
        stale_ids = {int(row["id"]) for row in stale}
        weak_ids = {int(row["id"]) for row in weak}
        safe_ids = {
            int(row["id"])
            for row in rows
            if int(row["id"]) in stale_ids & weak_ids
            and str(row["trust_origin"]) in {"agent", "untrusted"}
        }

        duplicates: List[Dict[str, Any]] = []
        # Compare only records in the same scope and kind.  A bounded input
        # keeps this deterministic even for long-lived profiles.
        for index, left in enumerate(rows):
            for right in rows[index + 1:]:
                if left["scope"] != right["scope"] or left["kind"] != right["kind"]:
                    continue
                similarity = _fuzzy_similarity(str(left["content"]), str(right["content"]))
                if similarity < duplicate_threshold:
                    continue
                left_key = (
                    _TRUST_RANK.get(str(left["trust_origin"]), 0),
                    float(left["confidence"]),
                    float(left["importance"]),
                    float(left["updated_at"]),
                )
                right_key = (
                    _TRUST_RANK.get(str(right["trust_origin"]), 0),
                    float(right["confidence"]),
                    float(right["importance"]),
                    float(right["updated_at"]),
                )
                loser, keeper = (left, right) if left_key < right_key else (right, left)
                duplicates.append({
                    "keep_id": int(keeper["id"]),
                    "candidate_id": int(loser["id"]),
                    "similarity": round(similarity, 4),
                    "scope": str(left["scope"]),
                    "kind": str(left["kind"]),
                })
                if str(loser["trust_origin"]) in {"agent", "untrusted"}:
                    safe_ids.add(int(loser["id"]))

        def compact(row: Dict[str, Any]) -> Dict[str, Any]:
            return {
                "id": int(row["id"]),
                "kind": row["kind"],
                "scope": row["scope"],
                "confidence": float(row["confidence"]),
                "trust_origin": row["trust_origin"],
                "updated_at": float(row["updated_at"]),
                "access_count": int(row.get("access_count") or 0),
                "preview": " ".join(str(row["content"]).split())[:240],
            }

        return {
            "reviewed": len(rows),
            "stale_after_days": float(stale_after_days),
            "low_confidence_threshold": threshold,
            "stale": [compact(row) for row in stale],
            "low_confidence": [compact(row) for row in weak],
            "duplicates": duplicates,
            "safe_archive_ids": sorted(safe_ids),
            "protected_origins": ["owner", "system"],
        }

    def archive(self, memory_ids: Iterable[int], *, reason: str = "maintenance") -> int:
        """Soft-archive safe memory candidates; owner/system data is protected."""

        ids = sorted({int(memory_id) for memory_id in memory_ids})
        if not ids:
            return 0
        placeholders = ",".join("?" for _ in ids)
        now = time.time()
        with self._lock:
            eligible = [
                int(row["id"])
                for row in self._conn.execute(
                    f"""
                    SELECT id FROM memories
                    WHERE id IN ({placeholders}) AND status = 'active'
                      AND trust_origin IN ('agent', 'untrusted')
                    """,
                    ids,
                ).fetchall()
            ]
            if not eligible:
                return 0
            eligible_placeholders = ",".join("?" for _ in eligible)
            cursor = self._conn.execute(
                f"UPDATE memories SET status = 'archived', updated_at = ? WHERE id IN ({eligible_placeholders})",
                [now, *eligible],
            )
            details = json.dumps({"reason": str(reason)}, ensure_ascii=False)
            for memory_id in eligible:
                self._record_event(memory_id, "archived", details)
            self._conn.commit()
            return int(cursor.rowcount)

    def maintain(
        self,
        *,
        dry_run: bool = True,
        limit: int = 200,
        stale_after_days: float = 180.0,
        low_confidence: float = 0.35,
    ) -> Dict[str, Any]:
        review = self.review(
            limit=limit,
            stale_after_days=stale_after_days,
            low_confidence=low_confidence,
        )
        archived = 0
        if not dry_run:
            archived = self.archive(
                review["safe_archive_ids"], reason="memory_hygiene_maintenance"
            )
        return {**review, "dry_run": bool(dry_run), "archived": archived}

    def status(self) -> Dict[str, Any]:
        with self._lock:
            total = self._conn.execute(
                "SELECT COUNT(*) FROM memories WHERE status = 'active'"
            ).fetchone()[0]
            by_kind = {
                row["kind"]: row["count"]
                for row in self._conn.execute(
                    """
                    SELECT kind, COUNT(*) AS count FROM memories
                    WHERE status = 'active' GROUP BY kind ORDER BY kind
                    """
                ).fetchall()
            }
            by_scope = {
                row["scope"]: row["count"]
                for row in self._conn.execute(
                    """
                    SELECT scope, COUNT(*) AS count FROM memories
                    WHERE status = 'active' GROUP BY scope ORDER BY scope
                    """
                ).fetchall()
            }
            event_count = self._conn.execute(
                "SELECT COUNT(*) FROM memory_events"
            ).fetchone()[0]
            archived = self._conn.execute(
                "SELECT COUNT(*) FROM memories WHERE status = 'archived'"
            ).fetchone()[0]
        return {
            "database": str(self.db_path),
            "active_memories": int(total),
            "archived_memories": int(archived),
            "by_kind": by_kind,
            "by_scope": by_scope,
            "audit_events": int(event_count),
            "retrieval": "fts5+fuzzy+importance+confidence+recency",
            "temporal_half_life_days": self.temporal_half_life_days,
        }

    def close(self) -> None:
        with self._lock:
            try:
                self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            except sqlite3.DatabaseError:
                pass
            self._conn.close()
