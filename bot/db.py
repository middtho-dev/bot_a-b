from __future__ import annotations

import csv
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
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS activity_daily (
                    user_id INTEGER NOT NULL,
                    chat_id INTEGER NOT NULL,
                    day TEXT NOT NULL,
                    message_count INTEGER NOT NULL,
                    first_activity_at TEXT NOT NULL,
                    last_activity_at TEXT NOT NULL,
                    PRIMARY KEY (user_id, chat_id, day)
                );

                CREATE TABLE IF NOT EXISTS checkin_daily (
                    user_id INTEGER NOT NULL,
                    day TEXT NOT NULL,
                    checked_at TEXT NOT NULL,
                    PRIMARY KEY (user_id, day)
                );

                CREATE TABLE IF NOT EXISTS eod_daily (
                    user_id INTEGER NOT NULL,
                    day TEXT NOT NULL,
                    done_today TEXT NOT NULL,
                    in_progress TEXT NOT NULL,
                    problems TEXT NOT NULL,
                    need_help TEXT NOT NULL,
                    submitted_at TEXT NOT NULL,
                    PRIMARY KEY (user_id, day)
                );

                CREATE TABLE IF NOT EXISTS sales_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    day TEXT NOT NULL,
                    client TEXT NOT NULL,
                    amount REAL NOT NULL,
                    status TEXT NOT NULL,
                    comment TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS shipment_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    day TEXT NOT NULL,
                    client_number TEXT NOT NULL,
                    status TEXT NOT NULL,
                    delay_reason TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS app_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS employees (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT NOT NULL,
                    full_name TEXT NOT NULL,
                    role TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS inactivity_alerts (
                    user_id INTEGER NOT NULL,
                    day TEXT NOT NULL,
                    alert_count INTEGER NOT NULL,
                    PRIMARY KEY (user_id, day)
                );

                CREATE TABLE IF NOT EXISTS employee_work_schedule (
                    user_id INTEGER PRIMARY KEY,
                    mode TEXT NOT NULL,
                    weekdays TEXT NOT NULL,
                    cycle_anchor TEXT NOT NULL
                );
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
                    SET message_count = ?, first_activity_at = ?, last_activity_at = ?
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

    def save_checkin(self, user_id: int, day: str, checked_at: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO checkin_daily (user_id, day, checked_at)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id, day) DO UPDATE SET checked_at=excluded.checked_at
                """,
                (user_id, day, checked_at),
            )

    def save_eod(
        self,
        user_id: int,
        day: str,
        done_today: str,
        in_progress: str,
        problems: str,
        need_help: str,
        submitted_at: str,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO eod_daily (
                    user_id, day, done_today, in_progress, problems, need_help, submitted_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, day) DO UPDATE SET
                    done_today=excluded.done_today,
                    in_progress=excluded.in_progress,
                    problems=excluded.problems,
                    need_help=excluded.need_help,
                    submitted_at=excluded.submitted_at
                """,
                (user_id, day, done_today, in_progress, problems, need_help, submitted_at),
            )

    def save_sale(
        self,
        user_id: int,
        day: str,
        client: str,
        amount: float,
        status: str,
        comment: str,
        created_at: str,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sales_events (user_id, day, client, amount, status, comment, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (user_id, day, client, amount, status, comment, created_at),
            )

    def save_shipment(
        self,
        user_id: int,
        day: str,
        client_number: str,
        status: str,
        delay_reason: str,
        created_at: str,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO shipment_events (user_id, day, client_number, status, delay_reason, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_id, day, client_number, status, delay_reason, created_at),
            )

    def get_activity_for_day(self, target_day: date) -> list[DailyActivity]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT user_id, chat_id, day, message_count, first_activity_at, last_activity_at
                FROM activity_daily
                WHERE day = ?
                ORDER BY user_id, chat_id
                """,
                (target_day.isoformat(),),
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

    def checked_in_user_ids(self, day: str) -> set[int]:
        with self._connect() as conn:
            rows = conn.execute("SELECT user_id FROM checkin_daily WHERE day = ?", (day,)).fetchall()
        return {int(row["user_id"]) for row in rows}

    def eod_user_ids(self, day: str) -> set[int]:
        with self._connect() as conn:
            rows = conn.execute("SELECT user_id FROM eod_daily WHERE day = ?", (day,)).fetchall()
        return {int(row["user_id"]) for row in rows}

    def get_setting(self, key: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute("SELECT value FROM app_settings WHERE key = ?", (key,)).fetchone()
            return None if not row else str(row["value"])

    def set_setting(self, key: str, value: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO app_settings (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, value),
            )

    def get_last_activity_at(self, user_id: int, day: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT MAX(last_activity_at) AS ts FROM activity_daily WHERE user_id = ? AND day = ?",
                (user_id, day),
            ).fetchone()
            return None if not row or row["ts"] is None else str(row["ts"])

    def get_inactivity_alert_count(self, user_id: int, day: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT alert_count FROM inactivity_alerts WHERE user_id = ? AND day = ?",
                (user_id, day),
            ).fetchone()
        return 0 if not row else int(row["alert_count"])

    def increment_inactivity_alert_count(self, user_id: int, day: str) -> None:
        current = self.get_inactivity_alert_count(user_id, day)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO inactivity_alerts (user_id, day, alert_count)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id, day) DO UPDATE SET alert_count = excluded.alert_count
                """,
                (user_id, day, current + 1),
            )

    def export_csv(self, out_path: str, day: str) -> None:
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
        with open(out_path, "w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(["user_id", "chat_id", "day", "message_count", "first_activity_at", "last_activity_at"])
            for row in rows:
                writer.writerow([row["user_id"], row["chat_id"], row["day"], row["message_count"], row["first_activity_at"], row["last_activity_at"]])



    def upsert_employee(self, user_id: int, username: str, full_name: str, role: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO employees (user_id, username, full_name, role)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    username = excluded.username,
                    full_name = excluded.full_name,
                    role = excluded.role
                """,
                (user_id, username, full_name, role),
            )

    def get_all_employees(self) -> list[sqlite3.Row]:
        with self._connect() as conn:
            return conn.execute(
                "SELECT user_id, username, full_name, role FROM employees ORDER BY user_id"
            ).fetchall()

    def delete_employee(self, user_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM employees WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM employee_work_schedule WHERE user_id = ?", (user_id,))

    def get_employee_schedule(self, user_id: int) -> dict[str, str]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT mode, weekdays, cycle_anchor FROM employee_work_schedule WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        if not row:
            return {"mode": "weekdays", "weekdays": "0,1,2,3,4,5,6", "cycle_anchor": date.today().isoformat()}
        return {"mode": str(row["mode"]), "weekdays": str(row["weekdays"]), "cycle_anchor": str(row["cycle_anchor"])}

    def set_employee_schedule(self, user_id: int, mode: str, weekdays: str, cycle_anchor: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO employee_work_schedule (user_id, mode, weekdays, cycle_anchor)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    mode = excluded.mode,
                    weekdays = excluded.weekdays,
                    cycle_anchor = excluded.cycle_anchor
                """,
                (user_id, mode, weekdays, cycle_anchor),
            )

    def is_employee_working_on(self, user_id: int, target_day: date) -> bool:
        schedule = self.get_employee_schedule(user_id)
        mode = schedule.get("mode", "weekdays")
        if mode == "cycle_2_2":
            try:
                anchor = date.fromisoformat(schedule.get("cycle_anchor", target_day.isoformat()))
            except ValueError:
                anchor = target_day
            delta_days = (target_day - anchor).days
            return delta_days % 4 in {0, 1}

        weekdays_raw = schedule.get("weekdays", "0,1,2,3,4,5,6")
        enabled = {int(x.strip()) for x in weekdays_raw.split(",") if x.strip().isdigit()}
        return target_day.weekday() in enabled

    def get_sales_between(self, start_day: str, end_day: str) -> list[sqlite3.Row]:
        with self._connect() as conn:
            return conn.execute(
                "SELECT user_id, day, amount, status FROM sales_events WHERE day >= ? AND day <= ?",
                (start_day, end_day),
            ).fetchall()

    def get_shipments_between(self, start_day: str, end_day: str) -> list[sqlite3.Row]:
        with self._connect() as conn:
            return conn.execute(
                "SELECT user_id, day, status FROM shipment_events WHERE day >= ? AND day <= ?",
                (start_day, end_day),
            ).fetchall()
