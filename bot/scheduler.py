from __future__ import annotations

from datetime import datetime, timedelta

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from bot.config import Settings
from bot.db import Database
from bot.reports import build_daily_report, build_weekly_report


def setup_scheduler(bot: Bot, settings: Settings, db: Database) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=settings.timezone)

    scheduler.add_job(
        _send_daily_report,
        CronTrigger(hour=settings.report_time.hour, minute=settings.report_time.minute),
        kwargs={"bot": bot, "settings": settings, "db": db},
        id="daily_report",
        replace_existing=True,
    )

    scheduler.add_job(
        _send_weekly_report,
        CronTrigger(day_of_week="mon", hour=settings.report_time.hour, minute=settings.report_time.minute),
        kwargs={"bot": bot, "settings": settings, "db": db},
        id="weekly_report",
        replace_existing=True,
    )

    scheduler.start()
    return scheduler


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
    await bot.send_message(settings.admin_chat_id, report)
