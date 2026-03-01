from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta

from bot.config import Employee
from bot.db import DailyActivity


ROLE_LABELS = {
    "sales": "Продажи",
    "logistics": "Логистика",
    "finance": "Финансы",
    "general": "Общий",
}


def _short_ts(iso_str: str) -> str:
    return datetime.fromisoformat(iso_str).strftime("%H:%M")


def _role_label(role: str) -> str:
    return ROLE_LABELS.get(role, role)


def build_daily_report(target_day: date, rows: list[DailyActivity], employees: dict[int, Employee]) -> str:
    by_user: dict[int, dict[str, str | int]] = defaultdict(lambda: {"count": 0, "first": "", "last": ""})
    dept_totals: dict[str, int] = defaultdict(int)

    for row in rows:
        item = by_user[row.user_id]
        item["count"] = int(item["count"]) + row.message_count
        item["first"] = row.first_activity_at if not item["first"] else min(str(item["first"]), row.first_activity_at)
        item["last"] = row.last_activity_at if not item["last"] else max(str(item["last"]), row.last_activity_at)

    lines = [f"📊 Дневной отчёт по активности — {target_day.isoformat()}", ""]
    for user_id, employee in employees.items():
        role = _role_label(employee.role)
        current = by_user.get(user_id)
        if not current:
            lines.append(f"{role} • {employee.full_name} — 0 сообщений")
            continue
        count = int(current["count"])
        first = _short_ts(str(current["first"]))
        last = _short_ts(str(current["last"]))
        lines.append(f"{role} • {employee.full_name} — {count} сообщений ({first}–{last})")
        dept_totals[employee.role] += count

    lines.append("\nИтого по отделам:")
    for role in sorted({emp.role for emp in employees.values()}):
        lines.append(f"- {_role_label(role)}: {dept_totals.get(role, 0)}")
    return "\n".join(lines)


def build_weekly_report(end_day: date, rows: list[DailyActivity], employees: dict[int, Employee]) -> str:
    start_day = end_day - timedelta(days=6)
    days = [(start_day + timedelta(days=i)).isoformat() for i in range(7)]

    by_user_day: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in rows:
        by_user_day[row.user_id][row.day] += row.message_count

    lines = [f"🗓 Недельный отчёт по активности — {start_day.isoformat()} .. {end_day.isoformat()}", ""]
    for user_id, employee in employees.items():
        counters = by_user_day.get(user_id, {})
        total = sum(counters.values())
        avg = round(total / 7, 2)
        silent_days = sum(1 for d in days if counters.get(d, 0) == 0)
        lines.append(
            f"{_role_label(employee.role)} • {employee.full_name}: всего={total}, "
            f"в среднем/день={avg}, дней без активности={silent_days}"
        )
    return "\n".join(lines)


def build_missing_report(title: str, day: str, missing: list[str]) -> str:
    if not missing:
        return f"✅ {title} ({day}): все сотрудники отметились."
    return f"⚠️ {title} ({day})\n" + "\n".join(f"- {item}" for item in missing)


def build_kpi_block(
    sales_rows: list,
    shipment_rows: list,
    employees: dict[int, Employee],
    start_day: str,
    end_day: str,
) -> str:
    sales_by_user: dict[int, dict[str, float]] = defaultdict(lambda: {"count": 0, "sum": 0.0})
    for row in sales_rows:
        sales_by_user[int(row["user_id"])]["count"] += 1
        sales_by_user[int(row["user_id"])]["sum"] += float(row["amount"])

    shipment_by_user: dict[int, dict[str, int]] = defaultdict(lambda: {"count": 0, "delayed": 0})
    for row in shipment_rows:
        shipment_by_user[int(row["user_id"])]["count"] += 1
        if str(row["status"]) == "delayed":
            shipment_by_user[int(row["user_id"])]["delayed"] += 1

    lines = [f"📈 KPI-снимок {start_day}..{end_day}", "Продажи:"]
    for uid, emp in employees.items():
        if emp.role != "sales":
            continue
        item = sales_by_user.get(uid, {"count": 0, "sum": 0.0})
        lines.append(f"- {emp.full_name}: сделок={int(item['count'])}, сумма={item['sum']:.2f} AED")

    lines.append("Логистика:")
    for uid, emp in employees.items():
        if emp.role != "logistics":
            continue
        item = shipment_by_user.get(uid, {"count": 0, "delayed": 0})
        lines.append(f"- {emp.full_name}: отправок={item['count']}, задержек={item['delayed']}")

    return "\n".join(lines)
