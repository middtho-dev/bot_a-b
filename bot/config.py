from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import time
from zoneinfo import ZoneInfo

from dotenv import load_dotenv


@dataclass(frozen=True)
class Employee:
    user_id: int
    username: str
    full_name: str
    role: str


@dataclass(frozen=True)
class Settings:
    bot_token: str
    timezone: ZoneInfo
    owner_ids: set[int]
    admin_chat_id: int
    work_chat_ids: set[int]
    report_time: time
    employees: dict[int, Employee]
    db_path: str


def _parse_csv_int(raw: str) -> set[int]:
    return {int(part.strip()) for part in raw.split(",") if part.strip()}


def _parse_report_time(raw: str) -> time:
    hh, mm = raw.split(":")
    return time(hour=int(hh), minute=int(mm))


def load_settings() -> Settings:
    load_dotenv()

    bot_token = os.getenv("BOT_TOKEN", "").strip()
    if not bot_token:
        raise ValueError("BOT_TOKEN is required")

    timezone = ZoneInfo(os.getenv("TIMEZONE", "Europe/Dubai"))
    owner_ids = _parse_csv_int(os.getenv("OWNER_IDS", ""))
    if not owner_ids:
        raise ValueError("OWNER_IDS is required")

    admin_chat_id = int(os.getenv("ADMIN_CHAT_ID", "0"))
    if not admin_chat_id:
        raise ValueError("ADMIN_CHAT_ID is required")

    work_chat_ids = _parse_csv_int(os.getenv("WORK_CHAT_IDS", ""))
    if not work_chat_ids:
        raise ValueError("WORK_CHAT_IDS is required")

    report_time = _parse_report_time(os.getenv("REPORT_TIME", "19:00"))
    db_path = os.getenv("DATABASE_PATH", "bot_data.sqlite3")

    raw_employees = os.getenv("EMPLOYEES_JSON", "[]")
    parsed = json.loads(raw_employees)
    employees: dict[int, Employee] = {}
    for item in parsed:
        employee = Employee(
            user_id=int(item["user_id"]),
            username=item.get("username", ""),
            full_name=item.get("full_name", ""),
            role=item.get("role", "general").lower(),
        )
        employees[employee.user_id] = employee

    if not employees:
        raise ValueError("EMPLOYEES_JSON must contain at least one employee")

    return Settings(
        bot_token=bot_token,
        timezone=timezone,
        owner_ids=owner_ids,
        admin_chat_id=admin_chat_id,
        work_chat_ids=work_chat_ids,
        report_time=report_time,
        employees=employees,
        db_path=db_path,
    )
