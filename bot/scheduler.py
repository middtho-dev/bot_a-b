from __future__ import annotations

from datetime import datetime, timedelta

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from bot.config import Settings
from bot.db import Database
from bot.reports import build_daily_report, build_kpi_block, build_missing_report, build_weekly_report


def setup_scheduler(bot: Bot, settings: Settings, db: Database) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=settings.timezone)

    report_hh, report_mm = _get_hhmm(db.get_setting("report_time") or settings.report_time.strftime("%H:%M"))
    check_hh, check_mm = _get_hhmm(db.get_setting("checkin_time") or settings.checkin_time.strftime("%H:%M"))
    eod_hh, eod_mm = _get_hhmm(db.get_setting("eod_time") or settings.eod_time.strftime("%H:%M"))

    scheduler.add_job(
        _send_checkin_prompt,
        CronTrigger(hour=check_hh, minute=check_mm),
        kwargs={"bot": bot, "settings": settings, "db": db},
        id="checkin_prompt",
        replace_existing=True,
    )
    scheduler.add_job(
        _send_checkin_missing,
        CronTrigger(hour=check_hh, minute=(check_mm + 30) % 60),
        kwargs={"bot": bot, "settings": settings, "db": db},
        id="checkin_missing",
        replace_existing=True,
    )
    scheduler.add_job(
        _send_eod_prompt,
        CronTrigger(hour=eod_hh, minute=eod_mm),
        kwargs={"bot": bot, "settings": settings},
        id="eod_prompt",
        replace_existing=True,
    )
    scheduler.add_job(
        _send_eod_missing,
        CronTrigger(hour=(eod_hh + 1) % 24, minute=eod_mm),
        kwargs={"bot": bot, "settings": settings, "db": db},
        id="eod_missing",
        replace_existing=True,
    )
    scheduler.add_job(
        _send_daily_report,
        CronTrigger(hour=report_hh, minute=report_mm),
        kwargs={"bot": bot, "settings": settings, "db": db},
        id="daily_report",
        replace_existing=True,
    )
    scheduler.add_job(
        _send_weekly_report,
        CronTrigger(day_of_week="mon", hour=report_hh, minute=report_mm),
        kwargs={"bot": bot, "settings": settings, "db": db},
        id="weekly_report",
        replace_existing=True,
    )
    scheduler.add_job(
        _check_inactivity,
        CronTrigger(minute="*/10"),
        kwargs={"bot": bot, "settings": settings, "db": db},
        id="inactivity_watchdog",
        replace_existing=True,
    )

    scheduler.start()
    return scheduler


def _get_hhmm(raw: str) -> tuple[int, int]:
    hh, mm = raw.split(":")
    return int(hh), int(mm)


async def _send_checkin_prompt(bot: Bot, settings: Settings, db: Database) -> None:
    if not settings.general_chat_id:
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ На связи", callback_data=f"checkin:{datetime.now(settings.timezone).date().isoformat()}")]])
    await bot.send_message(
        settings.general_chat_id,
        "Подтвердите начало рабочего дня\nКнопка актуальна только сегодня. Также можно командой /checkin",
        reply_markup=kb,
    )


async def _send_checkin_missing(bot: Bot, settings: Settings, db: Database) -> None:
    today = datetime.now(settings.timezone).date().isoformat()
    checked = db.checked_in_user_ids(today)
    missing = [
        f"@{emp.username}" if emp.username else emp.full_name
        for uid, emp in settings.employees.items()
        if uid not in checked
    ]
    await bot.send_message(settings.admin_chat_id, build_missing_report("Check-in", today, missing))


async def _send_eod_prompt(bot: Bot, settings: Settings) -> None:
    if not settings.general_chat_id:
        return
    await bot.send_message(settings.general_chat_id, "Заполните вечерний отчёт. Команда: /eod")


async def _send_eod_missing(bot: Bot, settings: Settings, db: Database) -> None:
    today = datetime.now(settings.timezone).date().isoformat()
    submitted = db.eod_user_ids(today)
    missing = [
        f"@{emp.username}" if emp.username else emp.full_name
        for uid, emp in settings.employees.items()
        if uid not in submitted
    ]
    await bot.send_message(settings.admin_chat_id, build_missing_report("EOD", today, missing))


async def _send_daily_report(bot: Bot, settings: Settings, db: Database) -> None:
    today = datetime.now(settings.timezone).date()
    rows = db.get_activity_for_day(today)
    report = build_daily_report(today, rows, settings.employees)
    await bot.send_message(settings.admin_chat_id, report)


async def _send_weekly_report(bot: Bot, settings: Settings, db: Database) -> None:
    today = datetime.now(settings.timezone).date()
    start = today - timedelta(days=6)
    rows = db.get_activity_between(start, today)
    report = build_weekly_report(today, rows, settings.employees)
    kpi = build_kpi_block(
        db.get_sales_between(start.isoformat(), today.isoformat()),
        db.get_shipments_between(start.isoformat(), today.isoformat()),
        settings.employees,
        start.isoformat(),
        today.isoformat(),
    )
    await bot.send_message(settings.admin_chat_id, report)
    await bot.send_message(settings.admin_chat_id, kpi)


async def _check_inactivity(bot: Bot, settings: Settings, db: Database) -> None:
    now = datetime.now(settings.timezone)
    now_t = now.time().replace(second=0, microsecond=0)
    if now_t < settings.work_start or now_t > settings.work_end:
        return

    minutes = int(db.get_setting("inactivity_minutes") or settings.inactivity_minutes)
    day = now.date().isoformat()
    checked = db.checked_in_user_ids(day)

    for uid, emp in settings.employees.items():
        if emp.role == "finance" or uid not in checked:
            continue
        if db.get_inactivity_alert_count(uid, day) >= 2:
            continue

        last_activity = db.get_last_activity_at(uid, day)
        if not last_activity:
            continue
        last_dt = datetime.fromisoformat(last_activity)
        if (now - last_dt).total_seconds() >= minutes * 60:
            await bot.send_message(
                settings.admin_chat_id,
                f"⚠️ Нет активности более {minutes} минут: @{emp.username or uid} (последняя активность {last_dt.strftime('%H:%M')})",
            )
            db.increment_inactivity_alert_count(uid, day)
