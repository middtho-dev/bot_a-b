from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta

from bot.config import Employee
from bot.db import DailyActivity


def _short_ts(iso_str: str) -> str:
    return datetime.fromisoformat(iso_str).strftime("%H:%M")


def build_daily_report(
    target_day: date,
    rows: list[DailyActivity],
    employees: dict[int, Employee],
) -> str:
    by_user: dict[int, dict[str, str | int]] = defaultdict(
        lambda: {"count": 0, "first": "", "last": ""}
    )
    dept_totals: dict[str, int] = defaultdict(int)

    for row in rows:
        item = by_user[row.user_id]
        item["count"] = int(item["count"]) + row.message_count
        item["first"] = (
            row.first_activity_at
            if not item["first"]
            else min(str(item["first"]), row.first_activity_at)
        )
        item["last"] = (
            row.last_activity_at
            if not item["last"]
            else max(str(item["last"]), row.last_activity_at)
        )

    lines = [f"📊 Daily activity report — {target_day.isoformat()}", ""]

    for user_id, employee in employees.items():
        current = by_user.get(user_id)
        role = employee.role.capitalize()
        if not current:
            lines.append(f"{role} {employee.full_name} — 0 сообщений")
            continue

        count = int(current["count"])
        first = _short_ts(str(current["first"]))
        last = _short_ts(str(current["last"]))
        lines.append(f"{role} {employee.full_name} — {count} сообщений ({first}–{last})")
        dept_totals[employee.role] += count

    lines.append("")
    lines.append("Итого по отделам:")
    for role in sorted({emp.role for emp in employees.values()}):
        lines.append(f"- {role}: {dept_totals.get(role, 0)}")

    return "\n".join(lines)


def build_weekly_report(
    end_day: date,
    rows: list[DailyActivity],
    employees: dict[int, Employee],
) -> str:
    start_day = end_day - timedelta(days=6)
    days = [(start_day + timedelta(days=i)).isoformat() for i in range(7)]

    by_user_day: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in rows:
        by_user_day[row.user_id][row.day] += row.message_count

    lines = [
        f"🗓 Weekly activity report — {start_day.isoformat()} .. {end_day.isoformat()}",
        "",
    ]

    for user_id, employee in employees.items():
        counters = by_user_day.get(user_id, {})
        total = sum(counters.values())
        avg = round(total / 7, 2)
        silent_days = sum(1 for d in days if counters.get(d, 0) == 0)
        lines.append(
            f"{employee.role.capitalize()} {employee.full_name}: total={total}, avg/day={avg}, no_activity_days={silent_days}"
        )

    return "\n".join(lines)
