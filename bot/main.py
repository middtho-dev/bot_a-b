from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher

from bot.config import Employee, load_settings
from bot.db import Database
from bot.handlers import build_router
from bot.scheduler import setup_scheduler


async def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")

    settings = load_settings()
    db = Database(settings.db_path)

    # merge runtime employees persisted via /add_employee
    for row in db.get_all_employees():
        settings.employees[int(row["user_id"])] = Employee(
            user_id=int(row["user_id"]),
            username=str(row["username"]),
            full_name=str(row["full_name"]),
            role=str(row["role"]),
        )

    bot = Bot(settings.bot_token)

    dp = Dispatcher()
    dp.include_router(build_router(settings, db))

    setup_scheduler(bot, settings, db)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(run())
