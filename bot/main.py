from __future__ import annotations

import asyncio
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from aiogram import Bot, Dispatcher

from bot.config import Employee, load_settings
from bot.db import Database
from bot.handlers import build_router
from bot.scheduler import setup_scheduler


def _configure_logging() -> None:
    log_dir = Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "bot.log"

    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    file_handler = RotatingFileHandler(log_file, maxBytes=2_000_000, backupCount=5, encoding="utf-8")
    file_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()
    root.addHandler(stream_handler)
    root.addHandler(file_handler)


async def run() -> None:
    _configure_logging()

    settings = load_settings()
    db = Database(settings.db_path)

    # persist owner bootstrap employees into DB so runtime/admin tools see them consistently
    for owner_id in settings.owner_ids:
        if owner_id in settings.employees:
            emp = settings.employees[owner_id]
            db.upsert_employee(emp.user_id, emp.username, emp.full_name, emp.role)

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
