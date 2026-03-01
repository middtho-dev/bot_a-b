from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class DailyActivity:
    user_id: int
    chat_id: int
    day: str
    message_count: int
    first_activity_at: str
    last_activity_at: str


class Database:
    def __init__(self, path: str):
        self.path = path
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS activity_daily (
                    user_id INTEGER NOT NULL,
                    chat_id INTEGER NOT NULL,
                    day TEXT NOT NULL,
                    message_count INTEGER NOT NULL,
                    first_activity_at TEXT NOT NULL,
                    last_activity_at TEXT NOT NULL,
                    PRIMARY KEY (user_id, chat_id, day)
                )
                """
            )

    def record_message(self, user_id: int, chat_id: int, ts: datetime) -> None:
        day = ts.date().isoformat()
        stamp = ts.isoformat(timespec="seconds")
        with self._connect() as conn:
            existing = conn.execute(
                """
                SELECT message_count, first_activity_at, last_activity_at
                FROM activity_daily
                WHERE user_id = ? AND chat_id = ? AND day = ?
                """,
                (user_id, chat_id, day),
            ).fetchone()

            if existing:
                conn.execute(
                    """
                    UPDATE activity_daily
                    SET message_count = ?,
                        first_activity_at = ?,
                        last_activity_at = ?
                    WHERE user_id = ? AND chat_id = ? AND day = ?
                    """,
                    (
                        int(existing["message_count"]) + 1,
                        min(existing["first_activity_at"], stamp),
                        max(existing["last_activity_at"], stamp),
                        user_id,
                        chat_id,
                        day,
                    ),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO activity_daily (
                        user_id, chat_id, day, message_count, first_activity_at, last_activity_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (user_id, chat_id, day, 1, stamp, stamp),
                )

    def get_activity_for_day(self, target_day: date) -> list[DailyActivity]:
        day = target_day.isoformat()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT user_id, chat_id, day, message_count, first_activity_at, last_activity_at
                FROM activity_daily
                WHERE day = ?
                ORDER BY user_id, chat_id
                """,
                (day,),
            ).fetchall()
        return [DailyActivity(**dict(row)) for row in rows]

    def get_activity_between(self, start_day: date, end_day: date) -> list[DailyActivity]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT user_id, chat_id, day, message_count, first_activity_at, last_activity_at
                FROM activity_daily
                WHERE day >= ? AND day <= ?
                ORDER BY day, user_id, chat_id
                """,
                (start_day.isoformat(), end_day.isoformat()),
            ).fetchall()
        return [DailyActivity(**dict(row)) for row in rows]
