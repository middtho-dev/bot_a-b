from __future__ import annotations

from datetime import datetime, timedelta

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from bot.config import Settings
from bot.db import Database
from bot.reports import build_daily_report, build_weekly_report


def build_router(settings: Settings, db: Database) -> Router:
    router = Router()

    @router.message(F.chat.id.in_(settings.work_chat_ids), F.from_user != None)
    async def collect_activity(message: Message) -> None:
        user = message.from_user
        if not user or user.id not in settings.employees:
            return

        now = datetime.now(settings.timezone)
        db.record_message(user.id, message.chat.id, now)

    @router.message(Command("status"))
    async def cmd_status(message: Message) -> None:
        if not _is_owner(message, settings):
            return
        await message.answer("✅ Bot is running. Week 1 activity tracking enabled.")

    @router.message(Command("report"))
    async def cmd_report_today(message: Message, command: CommandObject) -> None:
        if not _is_owner(message, settings):
            return
        arg = (command.args or "").strip().lower()
        if arg != "today":
            await message.answer("Usage: /report today")
            return

        today = datetime.now(settings.timezone).date()
        rows = db.get_activity_for_day(today)
        text = build_daily_report(today, rows, settings.employees)
        await message.answer(text)

    @router.message(Command("week"))
    async def cmd_week(message: Message) -> None:
        if not _is_owner(message, settings):
            return

        today = datetime.now(settings.timezone).date()
        start = today - timedelta(days=6)
        rows = db.get_activity_between(start, today)
        text = build_weekly_report(today, rows, settings.employees)
        await message.answer(text)

    return router


def _is_owner(message: Message, settings: Settings) -> bool:
    user = message.from_user
    return bool(user and user.id in settings.owner_ids)
