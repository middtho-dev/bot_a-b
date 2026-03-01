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
    general_chat_id: int
    sales_chat_id: int
    logistics_chat_id: int
    work_chat_ids: set[int]
    report_time: time
    checkin_time: time
    eod_time: time
    work_start: time
    work_end: time
    inactivity_minutes: int
    employees: dict[int, Employee]
    db_path: str


def _parse_csv_int(raw: str) -> set[int]:
    return {int(part.strip()) for part in raw.split(",") if part.strip()}


def _parse_hhmm(raw: str, default: str) -> time:
    source = (raw or default).strip()
    hh, mm = source.split(":")
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

    report_time = _parse_hhmm(os.getenv("REPORT_TIME", "19:00"), "19:00")
    checkin_time = _parse_hhmm(os.getenv("CHECKIN_TIME", "10:00"), "10:00")
    eod_time = _parse_hhmm(os.getenv("EOD_TIME", "22:00"), "22:00")
    work_start = _parse_hhmm(os.getenv("WORK_START", "09:00"), "09:00")
    work_end = _parse_hhmm(os.getenv("WORK_END", "22:00"), "22:00")
    inactivity_minutes = int(os.getenv("INACTIVITY_MINUTES", "60"))

    db_path = os.getenv("DATABASE_PATH", "bot_data.sqlite3")

    general_chat_id = int(os.getenv("GENERAL_CHAT_ID", "0"))
    sales_chat_id = int(os.getenv("SALES_CHAT_ID", "0"))
    logistics_chat_id = int(os.getenv("LOGISTICS_CHAT_ID", "0"))

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
        general_chat_id=general_chat_id,
        sales_chat_id=sales_chat_id,
        logistics_chat_id=logistics_chat_id,
        work_chat_ids=work_chat_ids,
        report_time=report_time,
        checkin_time=checkin_time,
        eod_time=eod_time,
        work_start=work_start,
        work_end=work_end,
        inactivity_minutes=inactivity_minutes,
        employees=employees,
        db_path=db_path,
    )
