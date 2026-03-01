from __future__ import annotations

import logging
from datetime import datetime, timedelta

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from bot.config import Settings
from bot.db import Database
from bot.reports import build_daily_report, build_kpi_block, build_missing_report, build_weekly_report

logger = logging.getLogger(__name__)


def setup_scheduler(bot: Bot, settings: Settings, db: Database) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=settings.timezone)

    report_hh, report_mm = _get_hhmm(db.get_setting("report_time") or settings.report_time.strftime("%H:%M"))
    check_hh, check_mm = _get_hhmm(db.get_setting("checkin_time") or settings.checkin_time.strftime("%H:%M"))
    eod_hh, eod_mm = _get_hhmm(db.get_setting("eod_time") or settings.eod_time.strftime("%H:%M"))

    scheduler.add_job(_send_checkin_prompt, CronTrigger(hour=check_hh, minute=check_mm), kwargs={"bot": bot, "settings": settings, "db": db}, id="checkin_prompt", replace_existing=True)
    scheduler.add_job(_send_checkin_missing, CronTrigger(hour=check_hh, minute=(check_mm + 30) % 60), kwargs={"bot": bot, "settings": settings, "db": db}, id="checkin_missing", replace_existing=True)
    scheduler.add_job(_send_eod_prompt, CronTrigger(hour=eod_hh, minute=eod_mm), kwargs={"bot": bot, "settings": settings, "db": db}, id="eod_prompt", replace_existing=True)
    scheduler.add_job(_send_eod_missing, CronTrigger(hour=(eod_hh + 1) % 24, minute=eod_mm), kwargs={"bot": bot, "settings": settings, "db": db}, id="eod_missing", replace_existing=True)
    scheduler.add_job(_send_daily_report, CronTrigger(hour=report_hh, minute=report_mm), kwargs={"bot": bot, "settings": settings, "db": db}, id="daily_report", replace_existing=True)
    scheduler.add_job(_send_weekly_report, CronTrigger(day_of_week="mon", hour=report_hh, minute=report_mm), kwargs={"bot": bot, "settings": settings, "db": db}, id="weekly_report", replace_existing=True)
    scheduler.add_job(_check_inactivity, CronTrigger(minute="*/10"), kwargs={"bot": bot, "settings": settings, "db": db}, id="inactivity_watchdog", replace_existing=True)

    scheduler.start()
    logger.info("🗓️ Планировщик запущен")
    return scheduler


def _get_hhmm(raw: str) -> tuple[int, int]:
    hh, mm = raw.split(":")
    return int(hh), int(mm)


def get_runtime_chat_id(db: Database, settings: Settings, key: str) -> int:
    defaults = {
        "admin_chat_id": settings.admin_chat_id,
        "general_chat_id": settings.general_chat_id,
        "sales_chat_id": settings.sales_chat_id,
        "logistics_chat_id": settings.logistics_chat_id,
    }
    raw = db.get_setting(key)
    return int(raw) if raw else int(defaults.get(key, 0))


def get_runtime_work_chat_ids(db: Database, settings: Settings) -> set[int]:
    raw = db.get_setting("work_chat_ids")
    if raw:
        return {int(x.strip()) for x in raw.split(",") if x.strip()}
    return set(settings.work_chat_ids)


def get_runtime_inactivity_minutes(db: Database, settings: Settings) -> int:
    return int(db.get_setting("inactivity_minutes") or settings.inactivity_minutes)


async def _send_checkin_prompt(bot: Bot, settings: Settings, db: Database) -> None:
    general_chat_id = get_runtime_chat_id(db, settings, "general_chat_id")
    if not general_chat_id:
        logger.warning("⚠️ general_chat_id не настроен")
        return

    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="✅ На связи", callback_data=f"checkin:{datetime.now(settings.timezone).date().isoformat()}")]]
    )
    await bot.send_message(
        general_chat_id,
        "Подтвердите начало рабочего дня\nКнопка актуальна только сегодня. Также можно командой /checkin",
        reply_markup=kb,
    )
    logger.info("🌅 Отправлено напоминание о чек-ине")


async def _send_checkin_missing(bot: Bot, settings: Settings, db: Database) -> None:
    admin_chat_id = get_runtime_chat_id(db, settings, "admin_chat_id")
    if not admin_chat_id:
        return
    today = datetime.now(settings.timezone).date().isoformat()
    checked = db.checked_in_user_ids(today)
    missing = [
        f"@{emp.username}" if emp.username else emp.full_name
        for uid, emp in settings.employees.items()
        if uid not in checked and db.is_employee_working_on(uid, datetime.now(settings.timezone).date())
    ]
    await bot.send_message(admin_chat_id, build_missing_report("Чек-ин", today, missing))


async def _send_eod_prompt(bot: Bot, settings: Settings, db: Database) -> None:
    general_chat_id = get_runtime_chat_id(db, settings, "general_chat_id")
    if not general_chat_id:
        return
    me = await bot.get_me()
    url = f"https://t.me/{me.username}?start=eod"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📝 Заполнить EOD в личке", url=url)]])
    await bot.send_message(general_chat_id, "Заполните вечерний отчёт. Нажмите кнопку ниже и заполните форму в личном чате с ботом.", reply_markup=kb)


async def _send_eod_missing(bot: Bot, settings: Settings, db: Database) -> None:
    admin_chat_id = get_runtime_chat_id(db, settings, "admin_chat_id")
    if not admin_chat_id:
        return
    today = datetime.now(settings.timezone).date().isoformat()
    submitted = db.eod_user_ids(today)
    missing = [
        f"@{emp.username}" if emp.username else emp.full_name
        for uid, emp in settings.employees.items()
        if uid not in submitted and db.is_employee_working_on(uid, datetime.now(settings.timezone).date())
    ]
    await bot.send_message(admin_chat_id, build_missing_report("EOD", today, missing))


async def _send_daily_report(bot: Bot, settings: Settings, db: Database) -> None:
    admin_chat_id = get_runtime_chat_id(db, settings, "admin_chat_id")
    if not admin_chat_id:
        return
    today = datetime.now(settings.timezone).date()
    rows = db.get_activity_for_day(today)
    report = build_daily_report(today, rows, settings.employees)
    await bot.send_message(admin_chat_id, report)


async def _send_weekly_report(bot: Bot, settings: Settings, db: Database) -> None:
    admin_chat_id = get_runtime_chat_id(db, settings, "admin_chat_id")
    if not admin_chat_id:
        return
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
    await bot.send_message(admin_chat_id, report)
    await bot.send_message(admin_chat_id, kpi)


async def _check_inactivity(bot: Bot, settings: Settings, db: Database) -> None:
    admin_chat_id = get_runtime_chat_id(db, settings, "admin_chat_id")
    if not admin_chat_id:
        return

    now = datetime.now(settings.timezone)
    now_t = now.time().replace(second=0, microsecond=0)
    work_start = _get_hhmm(db.get_setting("work_start") or settings.work_start.strftime("%H:%M"))
    work_end = _get_hhmm(db.get_setting("work_end") or settings.work_end.strftime("%H:%M"))
    if now_t < datetime.strptime(f"{work_start[0]:02d}:{work_start[1]:02d}", "%H:%M").time() or now_t > datetime.strptime(f"{work_end[0]:02d}:{work_end[1]:02d}", "%H:%M").time():
        return

    minutes = get_runtime_inactivity_minutes(db, settings)
    day = now.date().isoformat()
    checked = db.checked_in_user_ids(day)

    for uid, emp in settings.employees.items():
        if emp.role == "finance" or uid not in checked:
            continue
        if not db.is_employee_working_on(uid, now.date()):
            continue
        if db.get_inactivity_alert_count(uid, day) >= 2:
            continue

        last_activity = db.get_last_activity_at(uid, day)
        if not last_activity:
            continue
        last_dt = datetime.fromisoformat(last_activity)
        if (now - last_dt).total_seconds() >= minutes * 60:
            await bot.send_message(
                admin_chat_id,
                f"⚠️ Нет активности более {minutes} минут: @{emp.username or uid} (последняя активность {last_dt.strftime('%H:%M')})",
            )
            db.increment_inactivity_alert_count(uid, day)
            logger.info("⚠️ inactivity alert sent user_id=%s minutes=%s", uid, minutes)
