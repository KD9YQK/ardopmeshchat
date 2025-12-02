# chat_store.py

from __future__ import annotations

import sqlite3
import time
from typing import List, Tuple, Optional


class ChatStore:
    """
    Persistent chat log using SQLite.

    - One DB file per node (configurable via path).
    - Deduplicates messages by (origin_id, seqno).
    """

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._init_schema()

    def _init_schema(self) -> None:
        create_sql = """
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            origin_id BLOB NOT NULL,
            seqno INTEGER NOT NULL,
            channel TEXT NOT NULL,
            nick TEXT NOT NULL,
            text TEXT NOT NULL,
            ts REAL NOT NULL,
            UNIQUE(origin_id, seqno)
        );
        """
        self._conn.execute(create_sql)
        self._conn.commit()

    def add_message(
        self,
        origin_id: bytes,
        seqno: int,
        channel: str,
        nick: str,
        text: str,
        ts: Optional[float] = None,
    ) -> None:
        """
        Insert a message, ignoring if already present.
        """
        if ts is None:
            ts = time.time()

        insert_sql = """
        INSERT OR IGNORE INTO chat_messages
            (origin_id, seqno, channel, nick, text, ts)
        VALUES (?, ?, ?, ?, ?, ?);
        """
        self._conn.execute(
            insert_sql,
            (origin_id, seqno, channel, nick, text, ts),
        )
        self._conn.commit()

    def has_message(self, origin_id: bytes, seqno: int) -> bool:
        sql = """
        SELECT 1 FROM chat_messages
        WHERE origin_id = ? AND seqno = ?
        LIMIT 1;
        """
        cur = self._conn.execute(sql, (origin_id, seqno))
        row = cur.fetchone()
        return row is not None

    def get_recent_messages(
        self,
        channel: str,
        limit: int = 100,
    ) -> List[Tuple[bytes, int, str, str, str, float]]:
        """
        Return latest messages in a channel, newest last.
        """
        sql = """
        SELECT origin_id, seqno, channel, nick, text, ts
        FROM chat_messages
        WHERE channel = ?
        ORDER BY ts ASC
        LIMIT ?;
        """
        cur = self._conn.execute(sql, (channel, limit))
        rows = cur.fetchall()
        return rows

    def get_messages_since(
        self,
        channel: str,
        since_ts: float,
        limit: int = 100,
    ) -> List[Tuple[bytes, int, str, str, str, float]]:
        """
        Return messages in a channel with ts > since_ts, ordered by ts.
        """
        sql = """
        SELECT origin_id, seqno, channel, nick, text, ts
        FROM chat_messages
        WHERE channel = ? AND ts > ?
        ORDER BY ts ASC
        LIMIT ?;
        """
        cur = self._conn.execute(sql, (channel, since_ts, limit))
        rows = cur.fetchall()
        return rows

    def close(self) -> None:
        self._conn.close()
