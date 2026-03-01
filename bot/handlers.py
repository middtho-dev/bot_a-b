from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandObject
from aiogram.filters.state import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot import scheduler as scheduler_jobs
from bot.config import Employee, Settings
from bot.db import Database
from bot.reports import build_daily_report, build_kpi_block, build_weekly_report

logger = logging.getLogger(__name__)


class AdminConfigState(StatesGroup):
    wait_report_time = State()
    wait_checkin_time = State()
    wait_eod_time = State()
    wait_work_start = State()
    wait_work_end = State()
    wait_inactivity_minutes = State()
    wait_employee_id = State()
    wait_employee_full_name = State()
    wait_employee_username = State()
    wait_admin_chat_id = State()
    wait_general_chat_id = State()
    wait_sales_chat_id = State()
    wait_logistics_chat_id = State()
    wait_work_chat_ids = State()


ADMIN_HELP_TEXT = """🛠 <b>Админ-панель EasyWay</b>

👋 Здесь можно проверить все функции бота и настроить рабочую конфигурацию <b>без .env</b>.

<b>📌 Основные команды:</b>
• /status — состояние бота
• /report today — дневной отчёт вручную
• /week — недельный отчёт + KPI
• /checkin — ручной check-in
• /eod — запуск вечерней формы
• /sale — форма продажи (только Sales чат)
• /shipment — форма отправки (только Logistics чат)
• /myid — показать ваш user_id (для добавления в систему)
• /chatinfo — показать ID текущего чата
• /add_employee role=sales|logistics|finance|general — reply на сотрудника
• /export csv — выгрузка активности

<b>⚙️ Настройки через меню:</b>
• ID чатов (admin/general/sales/logistics)
• рабочие чаты
• времена check-in/eod/report
• рабочие часы
• порог неактивности

<b>🧪 Тестовые кнопки:</b>
• имитация check-in/eod/report/inactivity
• просмотр/скачивание логов
"""


@dataclass
class RuntimeConfig:
    report_time: str
    checkin_time: str
    eod_time: str
    inactivity_minutes: int


VARIABLE_META = {
    "admin_chat_id": {
        "title": "👑 ADMIN_CHAT_ID",
        "description": "Чат для админ-алертов и системных отчётов.",
        "prompt": "Введите ADMIN_CHAT_ID (например -1001234567890). Подсказка: /chatinfo",
        "state": AdminConfigState.wait_admin_chat_id,
    },
    "general_chat_id": {
        "title": "💬 GENERAL_CHAT_ID",
        "description": "Общий чат для check-in/EOD напоминаний.",
        "prompt": "Введите GENERAL_CHAT_ID (например -1001234567890). Подсказка: /chatinfo",
        "state": AdminConfigState.wait_general_chat_id,
    },
    "sales_chat_id": {
        "title": "💰 SALES_CHAT_ID",
        "description": "Чат отдела продаж для команды /sale.",
        "prompt": "Введите SALES_CHAT_ID. Подсказка: /chatinfo",
        "state": AdminConfigState.wait_sales_chat_id,
    },
    "logistics_chat_id": {
        "title": "📦 LOGISTICS_CHAT_ID",
        "description": "Чат логистики для команды /shipment.",
        "prompt": "Введите LOGISTICS_CHAT_ID. Подсказка: /chatinfo",
        "state": AdminConfigState.wait_logistics_chat_id,
    },
    "work_chat_ids": {
        "title": "🧩 WORK_CHAT_IDS",
        "description": "Список рабочих чатов, где учитывается активность и проверяется тишина.",
        "prompt": "Введите WORK_CHAT_IDS через запятую. Пример: -1001111111111,-1002222222222",
        "state": AdminConfigState.wait_work_chat_ids,
    },
    "report_time": {
        "title": "📊 REPORT_TIME",
        "description": "Время отправки дневного отчёта в админ-чат.",
        "prompt": "Введите REPORT_TIME (HH:MM)",
        "state": AdminConfigState.wait_report_time,
    },
    "checkin_time": {
        "title": "🌅 CHECKIN_TIME",
        "description": "Время публикации check-in кнопки в общий чат.",
        "prompt": "Введите CHECKIN_TIME (HH:MM)",
        "state": AdminConfigState.wait_checkin_time,
    },
    "eod_time": {
        "title": "🌆 EOD_TIME",
        "description": "Время публикации напоминания о вечернем отчёте.",
        "prompt": "Введите EOD_TIME (HH:MM)",
        "state": AdminConfigState.wait_eod_time,
    },
    "work_start": {
        "title": "🟢 WORK_START",
        "description": "Начало рабочего окна для проверки неактивности.",
        "prompt": "Введите WORK_START (HH:MM)",
        "state": AdminConfigState.wait_work_start,
    },
    "work_end": {
        "title": "🔴 WORK_END",
        "description": "Конец рабочего окна для проверки неактивности.",
        "prompt": "Введите WORK_END (HH:MM)",
        "state": AdminConfigState.wait_work_end,
    },
    "inactivity_minutes": {
        "title": "⏱ INACTIVITY_MINUTES",
        "description": "Через сколько минут тишины бот отправляет алерт о неактивности.",
        "prompt": "Введите INACTIVITY_MINUTES (например 60)",
        "state": AdminConfigState.wait_inactivity_minutes,
    },
}


def get_runtime_config(settings: Settings, db: Database) -> RuntimeConfig:
    return RuntimeConfig(
        report_time=db.get_setting("report_time") or settings.report_time.strftime("%H:%M"),
        checkin_time=db.get_setting("checkin_time") or settings.checkin_time.strftime("%H:%M"),
        eod_time=db.get_setting("eod_time") or settings.eod_time.strftime("%H:%M"),
        inactivity_minutes=int(db.get_setting("inactivity_minutes") or settings.inactivity_minutes),
    )


def build_router(settings: Settings, db: Database) -> Router:
    router = Router()

    @router.message(StateFilter(None), F.from_user != None, ~F.text.startswith("/"))
    async def collect_activity(message: Message) -> None:
        user = message.from_user
        if not user or user.id not in settings.employees:
            return
        work_chats = scheduler_jobs.get_runtime_work_chat_ids(db, settings)
        if message.chat.id not in work_chats:
            return
        db.record_message(user.id, message.chat.id, datetime.now(settings.timezone))

    @router.callback_query(F.data.startswith("checkin:"))
    async def on_checkin(callback: CallbackQuery) -> None:
        user = callback.from_user
        if user.id not in settings.employees:
            await callback.answer("Вы не в списке сотрудников", show_alert=True)
            return

        now = datetime.now(settings.timezone)
        token_day = (callback.data or "").split(":", 1)[1]
        today = now.date().isoformat()
        if token_day != today:
            await callback.answer("Эта кнопка уже неактуальна", show_alert=True)
            return

        checked = db.checked_in_user_ids(today)
        if user.id in checked:
            await callback.answer("Вы уже отметились сегодня ✅", show_alert=False)
            return

        db.save_checkin(user.id, today, now.isoformat(timespec="seconds"))
        logger.info("✅ checkin accepted user_id=%s day=%s", user.id, today)
        await callback.answer("Отметка принята ✅", show_alert=False)

    @router.message(Command("checkin"))
    async def cmd_checkin(message: Message) -> None:
        user = message.from_user
        if not user or user.id not in settings.employees:
            return
        now = datetime.now(settings.timezone)
        today = now.date().isoformat()
        checked = db.checked_in_user_ids(today)
        if user.id in checked:
            await _answer_temp(message, "Вы уже отметились сегодня ✅", delete_request=True)
            return
        db.save_checkin(user.id, today, now.isoformat(timespec="seconds"))
        logger.info("✅ checkin via command user_id=%s day=%s", user.id, today)
        await _answer_temp(message, "✅ Чек-ин принят", delete_request=True)

    @router.message(Command("eod"))
    async def cmd_eod(message: Message, state: FSMContext) -> None:
        if not message.from_user or message.from_user.id not in settings.employees:
            return
        if message.chat.type != "private":
            await _safe_delete_message(message)
            await message.answer(
                "📝 Для заполнения вечернего отчёта откройте личный чат с ботом и нажмите кнопку ниже.",
                reply_markup=await _eod_private_kb(message),
            )
            return
        await state.set_state(EODStates.done_today)
        await _safe_delete_message(message)
        await message.answer("Вечерний отчёт\n1) Сделано сегодня?")

    @router.message(Command("start"))
    async def cmd_start(message: Message, command: CommandObject, state: FSMContext) -> None:
        args = (command.args or "").strip().lower()
        if args == "eod":
            if not message.from_user or message.from_user.id not in settings.employees:
                await message.answer("⛔ Вы не зарегистрированы как сотрудник. Обратитесь к администратору.")
                return
            await state.set_state(EODStates.done_today)
            await message.answer("Вечерний отчёт\n1) Сделано сегодня?")
            return
        await message.answer("👋 Бот активен. Для меню администратора используйте /admin")

    @router.message(Command("myid"))
    async def cmd_myid(message: Message) -> None:
        uid = message.from_user.id if message.from_user else None
        await message.answer(
            f"🆔 Ваш user_id: <code>{uid}</code>\n"
            "Передайте этот ID администратору, если нужно добавить вас вручную.",
            parse_mode="HTML",
        )

    @router.message(Command("chatinfo"))
    async def cmd_chatinfo(message: Message) -> None:
        title = message.chat.title or message.chat.full_name or "(без названия)"
        await message.answer(
            f"💬 Информация о чате\n"
            f"• название: {title}\n"
            f"• тип: {message.chat.type}\n"
            f"• id: <code>{message.chat.id}</code>",
            parse_mode="HTML",
        )

    @router.message(EODStates.done_today)
    async def eod_done(message: Message, state: FSMContext) -> None:
        await state.update_data(done_today=message.text or "")
        await state.set_state(EODStates.in_progress)
        await _safe_delete_message(message)
        await message.answer("2) В работе?")

    @router.message(EODStates.in_progress)
    async def eod_progress(message: Message, state: FSMContext) -> None:
        await state.update_data(in_progress=message.text or "")
        await state.set_state(EODStates.problems)
        await _safe_delete_message(message)
        await message.answer("3) Проблемы?")

    @router.message(EODStates.problems)
    async def eod_problems(message: Message, state: FSMContext) -> None:
        await state.update_data(problems=message.text or "")
        await state.set_state(EODStates.need_help)
        await _safe_delete_message(message)
        await message.answer("4) Нужна помощь?")

    @router.message(EODStates.need_help)
    async def eod_finish(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        now = datetime.now(settings.timezone)
        uid = int(message.from_user.id) if message.from_user else 0
        db.save_eod(
            user_id=uid,
            day=now.date().isoformat(),
            done_today=str(data.get("done_today", "")),
            in_progress=str(data.get("in_progress", "")),
            problems=str(data.get("problems", "")),
            need_help=message.text or "",
            submitted_at=now.isoformat(timespec="seconds"),
        )
        await state.clear()
        await _safe_delete_message(message)
        logger.info("🌆 eod submitted user_id=%s day=%s", uid, now.date().isoformat())
        await message.answer("✅ EOD отчёт сохранён")

    @router.message(Command("sale"))
    async def cmd_sale(message: Message, state: FSMContext) -> None:
        sales_chat_id = scheduler_jobs.get_runtime_chat_id(db, settings, "sales_chat_id")
        if message.chat.id != sales_chat_id:
            await _answer_temp(message, "Команда доступна только в Sales-чате")
            return
        if not _is_employee_role(message.from_user.id if message.from_user else 0, settings.employees, "sales"):
            return
        await _safe_delete_message(message)
        await state.set_state(SaleStates.client)
        await message.answer("💰 Продажа: клиент?")

    @router.message(SaleStates.client)
    async def sale_client(message: Message, state: FSMContext) -> None:
        await state.update_data(client=message.text or "")
        await state.set_state(SaleStates.amount)
        await _safe_delete_message(message)
        await message.answer("Сумма (число)?")

    @router.message(SaleStates.amount)
    async def sale_amount(message: Message, state: FSMContext) -> None:
        try:
            amount = float((message.text or "0").replace(",", ""))
        except ValueError:
            await _answer_temp(message, "Введите сумму числом", delete_request=False)
            return
        await state.update_data(amount=amount)
        await state.set_state(SaleStates.status)
        await _safe_delete_message(message)
        await message.answer("Статус: lead / invoice / paid")

    @router.message(SaleStates.status)
    async def sale_status(message: Message, state: FSMContext) -> None:
        status = (message.text or "").strip().lower()
        if status not in {"lead", "invoice", "paid"}:
            await _answer_temp(message, "Только: lead / invoice / paid", delete_request=False)
            return
        await state.update_data(status=status)
        await state.set_state(SaleStates.comment)
        await _safe_delete_message(message)
        await message.answer("Комментарий?")

    @router.message(SaleStates.comment)
    async def sale_finish(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        uid = int(message.from_user.id) if message.from_user else 0
        now = datetime.now(settings.timezone)
        db.save_sale(
            user_id=uid,
            day=now.date().isoformat(),
            client=str(data.get("client", "")),
            amount=float(data.get("amount", 0.0)),
            status=str(data.get("status", "lead")),
            comment=message.text or "",
            created_at=now.isoformat(timespec="seconds"),
        )
        await _safe_delete_message(message)
        logger.info("💰 sale saved user_id=%s amount=%s status=%s", uid, data.get("amount"), data.get("status"))
        await message.answer(f"#sale @{message.from_user.username if message.from_user else uid} {float(data.get('amount', 0.0)):.2f}aed {data.get('status', 'lead')}")
        await state.clear()

    @router.message(Command("shipment"))
    async def cmd_shipment(message: Message, state: FSMContext) -> None:
        logistics_chat_id = scheduler_jobs.get_runtime_chat_id(db, settings, "logistics_chat_id")
        if message.chat.id != logistics_chat_id:
            await _answer_temp(message, "Команда доступна только в Logistics-чате")
            return
        if not _is_employee_role(message.from_user.id if message.from_user else 0, settings.employees, "logistics"):
            return
        await _safe_delete_message(message)
        await state.set_state(ShipmentStates.client_number)
        await message.answer("📦 Отправка: номер клиента?")

    @router.message(ShipmentStates.client_number)
    async def shipment_client(message: Message, state: FSMContext) -> None:
        await state.update_data(client_number=message.text or "")
        await state.set_state(ShipmentStates.status)
        await _safe_delete_message(message)
        await message.answer("Статус: created / shipped / delivered / delayed")

    @router.message(ShipmentStates.status)
    async def shipment_status(message: Message, state: FSMContext) -> None:
        status = (message.text or "").strip().lower()
        if status not in {"created", "shipped", "delivered", "delayed"}:
            await _answer_temp(message, "Только: created / shipped / delivered / delayed", delete_request=False)
            return
        await state.update_data(status=status)
        await _safe_delete_message(message)
        if status == "delayed":
            await state.set_state(ShipmentStates.delay_reason)
            await message.answer("Причина задержки?")
            return
        await _finish_shipment(message, state, settings, db, "")

    @router.message(ShipmentStates.delay_reason)
    async def shipment_delay_reason(message: Message, state: FSMContext) -> None:
        await _safe_delete_message(message)
        await _finish_shipment(message, state, settings, db, message.text or "")

    @router.message(Command("status"))
    async def cmd_status(message: Message) -> None:
        if not await _ensure_owner(message, settings):
            return
        runtime = get_runtime_config(settings, db)
        cfg = _build_runtime_overview(db, settings)
        await _answer_temp(message, f"✅ Бот работает\nreport={runtime.report_time}, checkin={runtime.checkin_time}, eod={runtime.eod_time}, inactivity={runtime.inactivity_minutes} мин\n\n{cfg}", ttl=30)

    @router.message(Command("report"))
    async def cmd_report(message: Message, command: CommandObject) -> None:
        if not await _ensure_owner(message, settings):
            return
        if (command.args or "").strip().lower() != "today":
            await _answer_temp(message, "Использование: /report today")
            return
        today = datetime.now(settings.timezone).date()
        await _safe_delete_message(message)
        await message.answer(build_daily_report(today, db.get_activity_for_day(today), settings.employees))

    @router.message(Command("week"))
    async def cmd_week(message: Message) -> None:
        if not await _ensure_owner(message, settings):
            return
        today = datetime.now(settings.timezone).date()
        start = today - timedelta(days=6)
        await _safe_delete_message(message)
        await message.answer(build_weekly_report(today, db.get_activity_between(start, today), settings.employees))
        await message.answer(build_kpi_block(db.get_sales_between(start.isoformat(), today.isoformat()), db.get_shipments_between(start.isoformat(), today.isoformat()), settings.employees, start.isoformat(), today.isoformat()))

    @router.message(Command("add_employee"))
    async def cmd_add_employee(message: Message, command: CommandObject) -> None:
        if not await _ensure_owner(message, settings):
            return

        role = _parse_role_from_args(command.args or "")
        if role is None:
            await _answer_temp(message, "Использование: ответьте на сообщение сотрудника командой /add_employee role=sales|logistics|finance|general")
            return

        source = message.reply_to_message.from_user if message.reply_to_message else None
        if not source:
            await _answer_temp(message, "Нужно ответить на сообщение сотрудника командой /add_employee role=...")
            return

        username = source.username or ""
        full_name = (source.full_name or "").strip() or username or str(source.id)
        db.upsert_employee(source.id, username, full_name, role)
        settings.employees[source.id] = Employee(source.id, username, full_name, role)
        logger.info("👤 employee upsert user_id=%s role=%s", source.id, role)
        await _answer_temp(message, f"✅ Сотрудник добавлен: {full_name} ({role})")

    @router.message(Command("set_checkin_time"))
    async def cmd_set_checkin(message: Message, command: CommandObject) -> None:
        if not await _ensure_owner(message, settings):
            return
        arg = (command.args or "").strip()
        db.set_setting("checkin_time", arg)
        logger.info("⚙️ setting updated checkin_time=%s", arg)
        await _answer_temp(message, f"checkin_time updated: {arg}")

    @router.message(Command("set_eod_time"))
    async def cmd_set_eod(message: Message, command: CommandObject) -> None:
        if not await _ensure_owner(message, settings):
            return
        arg = (command.args or "").strip()
        db.set_setting("eod_time", arg)
        logger.info("⚙️ setting updated eod_time=%s", arg)
        await _answer_temp(message, f"eod_time updated: {arg}")

    @router.message(Command("set_report_time"))
    async def cmd_set_report(message: Message, command: CommandObject) -> None:
        if not await _ensure_owner(message, settings):
            return
        arg = (command.args or "").strip()
        db.set_setting("report_time", arg)
        logger.info("⚙️ setting updated report_time=%s", arg)
        await _answer_temp(message, f"report_time updated: {arg}")

    @router.message(Command("export"))
    async def cmd_export(message: Message, command: CommandObject) -> None:
        if not await _ensure_owner(message, settings):
            return
        if (command.args or "").strip().lower() != "csv":
            await _answer_temp(message, "Использование: /export csv")
            return
        day = datetime.now(settings.timezone).date().isoformat()
        path = f"export_{day}.csv"
        db.export_csv(path, day)
        await _safe_delete_message(message)
        await message.answer_document(FSInputFile(path))


    @router.message(Command("whoami"))
    async def cmd_whoami(message: Message) -> None:
        user_id = message.from_user.id if message.from_user else None
        sender_chat_id = message.sender_chat.id if message.sender_chat else None
        await message.answer(
            "🪪 Диагностика пользователя\n"
            f"from_user.id={user_id}\n"
            f"sender_chat.id={sender_chat_id}\n"
            f"OWNER_IDS={sorted(settings.owner_ids)}\n\n"
            "Если from_user.id не совпадает с OWNER_IDS, команды администратора будут игнорироваться.\n"
            "Если вы админ с анонимным режимом, выключите Anonymous Admin и повторите."
        )

    @router.message(Command("admin"))
    async def cmd_admin(message: Message) -> None:
        if not await _ensure_owner(message, settings):
            return
        await _safe_delete_message(message)
        await message.answer("🛠 Админ-меню", reply_markup=_admin_kb())

    @router.message(Command("admin_test"))
    async def cmd_admin_alias(message: Message) -> None:
        if not await _ensure_owner(message, settings):
            return
        await _safe_delete_message(message)
        await message.answer("🛠 Админ-меню", reply_markup=_admin_kb())

    @router.callback_query(F.data.startswith("adm:"))
    async def admin_callback(callback: CallbackQuery, state: FSMContext) -> None:
        if callback.from_user.id not in settings.owner_ids:
            await callback.answer("Только для администратора", show_alert=True)
            return

        action = (callback.data or "").split(":", 1)[1]
        bot = callback.bot

        try:
            if action == "checkin_prompt":
                await scheduler_jobs._send_checkin_prompt(bot, settings, db)
            elif action == "checkin_missing":
                await scheduler_jobs._send_checkin_missing(bot, settings, db)
            elif action == "eod_prompt":
                await scheduler_jobs._send_eod_prompt(bot, settings, db)
            elif action == "eod_missing":
                await scheduler_jobs._send_eod_missing(bot, settings, db)
            elif action == "daily":
                await scheduler_jobs._send_daily_report(bot, settings, db)
            elif action == "weekly":
                await scheduler_jobs._send_weekly_report(bot, settings, db)
            elif action == "inactivity":
                await scheduler_jobs._check_inactivity(bot, settings, db)
            elif action == "logs_tail":
                tail = _read_log_tail(lines=50)
                await callback.message.answer(f"📄 <b>Последние 50 строк лога</b>\n\n<pre>{tail}</pre>", parse_mode="HTML", reply_markup=_back_main_kb())
            elif action == "logs_file":
                log_path = Path("logs") / "bot.log"
                if not log_path.exists():
                    await callback.answer("Лог-файл пока не создан", show_alert=True)
                    return
                await callback.message.answer_document(FSInputFile(str(log_path)))
                await callback.message.answer("⬅️ Вернуться в админ-меню", reply_markup=_back_main_kb())
            elif action == "open_vars":
                await callback.message.answer("⚙️ Меню переменных", reply_markup=_variables_kb(db, settings))
            elif action.startswith("var:"):
                key = action.split(":", 1)[1]
                if key not in VARIABLE_META:
                    await callback.answer("Неизвестная переменная", show_alert=True)
                    return
                await callback.message.answer(
                    _build_variable_details_text(key, db, settings),
                    parse_mode="HTML",
                    reply_markup=_variable_details_kb(key),
                )
            elif action.startswith("setvar:"):
                key = action.split(":", 1)[1]
                meta = VARIABLE_META.get(key)
                if not meta:
                    await callback.answer("Неизвестная переменная", show_alert=True)
                    return
                await state.set_state(meta["state"])
                await callback.message.answer(meta["prompt"])
            elif action == "open_employees":
                await callback.message.answer("👥 Меню сотрудников", reply_markup=_employees_kb())
            elif action == "employees_list":
                await callback.message.answer(_build_employees_text(settings), parse_mode="HTML", reply_markup=_employees_kb())
            elif action == "back_main":
                await callback.message.answer("🛠 Главное админ-меню", reply_markup=_admin_kb())
            elif action.startswith("emp_add_role:"):
                role = action.split(":", 1)[1]
                await state.set_state(AdminConfigState.wait_employee_id)
                await state.update_data(add_role=role)
                await callback.message.answer(
                    f"🆔 Введите user_id сотрудника для роли <b>{role}</b>.\n"
                    "Пользователь может узнать ID командой /myid",
                    parse_mode="HTML",
                )
            elif action == "show_cfg":
                await callback.message.answer(_build_runtime_overview(db, settings), parse_mode="HTML")
            elif action == "help":
                await callback.message.answer(ADMIN_HELP_TEXT, parse_mode="HTML", reply_markup=_back_main_kb())
            elif action == "menu":
                await callback.message.answer("🛠 Админ-меню", reply_markup=_admin_kb())
                await callback.answer("♻️ Меню обновлено")
                return
            else:
                await callback.answer("Неизвестная команда", show_alert=True)
                return
        except TelegramBadRequest as exc:
            if "message is not modified" in str(exc).lower():
                await callback.answer("♻️ Нечего обновлять")
                return
            logger.exception("❌ TelegramBadRequest action=%s", action)
            await callback.answer("Ошибка Telegram API", show_alert=True)
            return
        except Exception:
            logger.exception("❌ admin callback failed action=%s", action)
            await callback.answer("⚠️ Внутренняя ошибка, смотри логи", show_alert=True)
            return

        logger.info("🧪 admin action executed action=%s by=%s", action, callback.from_user.id)
        await callback.answer("✅ Выполнено")

    @router.message(AdminConfigState.wait_report_time)
    async def cfg_report_time(message: Message, state: FSMContext) -> None:
        await _save_time_setting(message, state, db, "report_time")

    @router.message(AdminConfigState.wait_checkin_time)
    async def cfg_checkin_time(message: Message, state: FSMContext) -> None:
        await _save_time_setting(message, state, db, "checkin_time")

    @router.message(AdminConfigState.wait_eod_time)
    async def cfg_eod_time(message: Message, state: FSMContext) -> None:
        await _save_time_setting(message, state, db, "eod_time")

    @router.message(AdminConfigState.wait_work_start)
    async def cfg_work_start(message: Message, state: FSMContext) -> None:
        await _save_time_setting(message, state, db, "work_start")

    @router.message(AdminConfigState.wait_work_end)
    async def cfg_work_end(message: Message, state: FSMContext) -> None:
        await _save_time_setting(message, state, db, "work_end")

    @router.message(AdminConfigState.wait_employee_id)
    async def cfg_employee_id(message: Message, state: FSMContext) -> None:
        raw = (message.text or "").strip()
        if not raw.lstrip("-").isdigit():
            await _answer_temp(message, "Введите корректный user_id (число)")
            return
        uid = int(raw)
        auto_username = ""
        auto_full_name = ""
        try:
            chat = await message.bot.get_chat(uid)
            auto_username = (chat.username or "").strip()
            auto_full_name = (chat.full_name or chat.first_name or "").strip()
        except Exception:
            pass

        await state.update_data(add_user_id=uid, auto_username=auto_username, auto_full_name=auto_full_name)
        await state.set_state(AdminConfigState.wait_employee_full_name)
        if auto_full_name:
            await _answer_temp(
                message,
                f"🪪 Введите имя сотрудника (или '+' чтобы оставить <b>{auto_full_name}</b>)",
                delete_request=False,
            )
            return
        await _answer_temp(message, "🪪 Введите имя сотрудника (как показывать в отчётах)", delete_request=False)

    @router.message(AdminConfigState.wait_employee_full_name)
    async def cfg_employee_full_name(message: Message, state: FSMContext) -> None:
        full_name = (message.text or "").strip()
        data = await state.get_data()
        auto_full_name = str(data.get("auto_full_name", "")).strip()
        if full_name == "+" and auto_full_name:
            full_name = auto_full_name
        if not full_name:
            await _answer_temp(message, "Имя не может быть пустым")
            return
        await state.update_data(add_full_name=full_name)
        await state.set_state(AdminConfigState.wait_employee_username)
        auto_username = str(data.get("auto_username", "")).strip()
        if auto_username:
            await _answer_temp(message, f"📛 Введите username (или '+' чтобы оставить @{auto_username}, '-' если нет)", delete_request=False)
            return
        await _answer_temp(message, "📛 Введите username в формате @username (или '-' если нет)", delete_request=False)

    @router.message(AdminConfigState.wait_employee_username)
    async def cfg_employee_username(message: Message, state: FSMContext) -> None:
        raw = (message.text or "").strip()
        data = await state.get_data()
        auto_username = str(data.get("auto_username", "")).strip()
        if raw == "-":
            username = ""
        elif raw == "+" and auto_username:
            username = auto_username
        else:
            username = raw.lstrip("@")
            if username and (" " in username or username.startswith("-")):
                await _answer_temp(message, "Имя пользователя должно быть в формате @username, '+' или '-'")
                return

        role = str(data.get("add_role", "general"))
        uid = int(data.get("add_user_id", 0))
        full_name = str(data.get("add_full_name", "")).strip() or f"Сотрудник {uid}"
        db.upsert_employee(uid, username=username, full_name=full_name, role=role)
        settings.employees[uid] = Employee(uid, username, full_name, role)
        await state.clear()
        logger.info("👤 employee added from menu user_id=%s role=%s username=%s", uid, role, username)
        username_part = f" (@{username})" if username else ""
        await _answer_temp(message, f"✅ Сотрудник добавлен: {full_name}{username_part}, роль={role}", delete_request=False)
        await message.answer("👥 Обновлённый список сотрудников", parse_mode="HTML", reply_markup=_employees_kb())
        await message.answer(_build_employees_text(settings), parse_mode="HTML")

    @router.message(AdminConfigState.wait_inactivity_minutes)
    async def cfg_inactivity(message: Message, state: FSMContext) -> None:
        val = (message.text or "").strip()
        if not val.isdigit():
            await _answer_temp(message, "Введите целое число минут")
            return
        db.set_setting("inactivity_minutes", val)
        await state.clear()
        logger.info("⚙️ setting updated inactivity_minutes=%s", val)
        await _answer_temp(message, f"✅ INACTIVITY_MINUTES={val}")

    @router.message(AdminConfigState.wait_admin_chat_id)
    async def cfg_admin_chat_id(message: Message, state: FSMContext) -> None:
        await _save_chat_id_setting(message, state, db, "admin_chat_id")

    @router.message(AdminConfigState.wait_general_chat_id)
    async def cfg_general_chat_id(message: Message, state: FSMContext) -> None:
        await _save_chat_id_setting(message, state, db, "general_chat_id")

    @router.message(AdminConfigState.wait_sales_chat_id)
    async def cfg_sales_chat_id(message: Message, state: FSMContext) -> None:
        await _save_chat_id_setting(message, state, db, "sales_chat_id")

    @router.message(AdminConfigState.wait_logistics_chat_id)
    async def cfg_logistics_chat_id(message: Message, state: FSMContext) -> None:
        await _save_chat_id_setting(message, state, db, "logistics_chat_id")

    @router.message(AdminConfigState.wait_work_chat_ids)
    async def cfg_work_chat_ids(message: Message, state: FSMContext) -> None:
        raw = (message.text or "").strip()
        parsed = [x.strip() for x in raw.split(",") if x.strip()]
        if not parsed or not all(v.lstrip("-").isdigit() for v in parsed):
            await _answer_temp(message, "Формат неверный. Пример: -1001111111111,-1002222222222")
            return
        db.set_setting("work_chat_ids", ",".join(parsed))
        await state.clear()
        logger.info("⚙️ setting updated work_chat_ids=%s", ",".join(parsed))
        await _answer_temp(message, f"✅ WORK_CHAT_IDS сохранены ({len(parsed)} чатов)")

    return router


class EODStates(StatesGroup):
    done_today = State()
    in_progress = State()
    problems = State()
    need_help = State()


class SaleStates(StatesGroup):
    client = State()
    amount = State()
    status = State()
    comment = State()


class ShipmentStates(StatesGroup):
    client_number = State()
    status = State()
    delay_reason = State()


async def _save_time_setting(message: Message, state: FSMContext, db: Database, key: str) -> None:
    val = (message.text or "").strip()
    if not _is_hhmm(val):
        await _answer_temp(message, "Формат времени должен быть HH:MM")
        return
    db.set_setting(key, val)
    await state.clear()
    logger.info("⚙️ setting updated %s=%s", key, val)
    await _answer_temp(message, f"✅ {key.upper()}={val}")


async def _save_chat_id_setting(message: Message, state: FSMContext, db: Database, key: str) -> None:
    raw = (message.text or "").strip()
    if not raw.lstrip("-").isdigit():
        await _answer_temp(message, "Введите корректный ID чата (число)")
        return
    db.set_setting(key, raw)
    await state.clear()
    logger.info("⚙️ setting updated %s=%s", key, raw)
    await _answer_temp(message, f"✅ {key.upper()}={raw}")


async def _finish_shipment(message: Message, state: FSMContext, settings: Settings, db: Database, delay_reason: str) -> None:
    data = await state.get_data()
    now = datetime.now(settings.timezone)
    uid = int(message.from_user.id) if message.from_user else 0
    db.save_shipment(user_id=uid, day=now.date().isoformat(), client_number=str(data.get("client_number", "")), status=str(data.get("status", "created")), delay_reason=delay_reason, created_at=now.isoformat(timespec="seconds"))
    logger.info("📦 shipment saved user_id=%s status=%s", uid, data.get("status"))
    await message.answer(f"📦 Отправка сохранена: {data.get('client_number')}, статус={data.get('status')}")
    await state.clear()


async def _safe_delete_message(message: Message | None) -> None:
    if not message:
        return
    try:
        await message.delete()
    except Exception:
        return


async def _delete_later(message: Message, seconds: int = 20) -> None:
    try:
        await asyncio.sleep(seconds)
        await message.delete()
    except Exception:
        return


async def _answer_temp(message: Message, text: str, delete_request: bool = True, ttl: int = 20) -> None:
    response = await message.answer(text)
    if delete_request:
        await _safe_delete_message(message)
    asyncio.create_task(_delete_later(response, ttl))


def _admin_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Отправить чек-ин", callback_data="adm:checkin_prompt")],
            [InlineKeyboardButton(text="📋 Кто НЕ чек-ин", callback_data="adm:checkin_missing")],
            [InlineKeyboardButton(text="🌆 Отправить напоминание EOD", callback_data="adm:eod_prompt")],
            [InlineKeyboardButton(text="📭 Кто НЕ сдал EOD", callback_data="adm:eod_missing")],
            [InlineKeyboardButton(text="📊 Отправить дневной отчёт", callback_data="adm:daily")],
            [InlineKeyboardButton(text="🗓 Отправить недельный отчёт + KPI", callback_data="adm:weekly")],
            [InlineKeyboardButton(text="⚠️ Проверка неактивности", callback_data="adm:inactivity")],
            [InlineKeyboardButton(text="⚙️ Меню переменных", callback_data="adm:open_vars")],
            [InlineKeyboardButton(text="👥 Меню сотрудников", callback_data="adm:open_employees")],
            [InlineKeyboardButton(text="📘 Инструкции и команды", callback_data="adm:help")],
            [InlineKeyboardButton(text="📄 Последние 50 строк лога", callback_data="adm:logs_tail")],
            [InlineKeyboardButton(text="⬇️ Скачать лог", callback_data="adm:logs_file")],
            [InlineKeyboardButton(text="♻️ Обновить", callback_data="adm:menu")],
        ]
    )


def _variables_kb(db: Database, settings: Settings) -> InlineKeyboardMarkup:
    rows = []
    for key, meta in VARIABLE_META.items():
        icon = "⭐" if _is_variable_set(key, db, settings) else "⚪"
        rows.append([InlineKeyboardButton(text=f"{icon} {meta['title']}", callback_data=f"adm:var:{key}")])
    rows.append([InlineKeyboardButton(text="📌 Показать сводную конфигурацию", callback_data="adm:show_cfg")])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="adm:back_main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _variable_details_kb(key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Установить значение", callback_data=f"adm:setvar:{key}")],
            [InlineKeyboardButton(text="⬅️ Назад к переменным", callback_data="adm:open_vars")],
            [InlineKeyboardButton(text="⬅️ В главное меню", callback_data="adm:back_main")],
        ]
    )




def _back_main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="adm:back_main")]])

def _employees_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📋 Список сотрудников", callback_data="adm:employees_list")],
            [InlineKeyboardButton(text="➕ Добавить сотрудника (продажи)", callback_data="adm:emp_add_role:sales")],
            [InlineKeyboardButton(text="➕ Добавить сотрудника (логистика)", callback_data="adm:emp_add_role:logistics")],
            [InlineKeyboardButton(text="➕ Добавить сотрудника (финансы)", callback_data="adm:emp_add_role:finance")],
            [InlineKeyboardButton(text="➕ Добавить сотрудника (общая роль)", callback_data="adm:emp_add_role:general")],
            [InlineKeyboardButton(text="ℹ️ Как добавить: сотрудник пишет /myid", callback_data="adm:help")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="adm:back_main")],
        ]
    )


async def _eod_private_kb(message: Message) -> InlineKeyboardMarkup:
    me = await message.bot.get_me()
    url = f"https://t.me/{me.username}?start=eod"
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📝 Заполнить EOD в личке", url=url)]])


def _set_work_chat(db: Database, settings: Settings, chat_id: int, add: bool) -> None:
    current = scheduler_jobs.get_runtime_work_chat_ids(db, settings)
    if add:
        current.add(chat_id)
    else:
        current.discard(chat_id)
    db.set_setting("work_chat_ids", ",".join(str(x) for x in sorted(current)))


def _runtime_value(key: str, db: Database, settings: Settings) -> str:
    if key == "work_chat_ids":
        val = sorted(scheduler_jobs.get_runtime_work_chat_ids(db, settings))
        return ",".join(str(x) for x in val)
    if key in {"admin_chat_id", "general_chat_id", "sales_chat_id", "logistics_chat_id"}:
        return str(scheduler_jobs.get_runtime_chat_id(db, settings, key))
    if key in {"report_time", "checkin_time", "eod_time", "work_start", "work_end", "inactivity_minutes"}:
        defaults = {
            "report_time": settings.report_time.strftime("%H:%M"),
            "checkin_time": settings.checkin_time.strftime("%H:%M"),
            "eod_time": settings.eod_time.strftime("%H:%M"),
            "work_start": settings.work_start.strftime("%H:%M"),
            "work_end": settings.work_end.strftime("%H:%M"),
            "inactivity_minutes": str(settings.inactivity_minutes),
        }
        return db.get_setting(key) or defaults[key]
    return db.get_setting(key) or ""


def _is_variable_set(key: str, db: Database, settings: Settings) -> bool:
    if key == "work_chat_ids":
        return bool(scheduler_jobs.get_runtime_work_chat_ids(db, settings))
    if key in {"admin_chat_id", "general_chat_id", "sales_chat_id", "logistics_chat_id"}:
        return scheduler_jobs.get_runtime_chat_id(db, settings, key) != 0
    return db.get_setting(key) is not None


def _build_variable_details_text(key: str, db: Database, settings: Settings) -> str:
    meta = VARIABLE_META[key]
    current = _runtime_value(key, db, settings)
    is_set = _is_variable_set(key, db, settings)
    state_icon = "⭐ Установлено" if is_set else "⚪ Не задано"
    source = "runtime (из БД)" if db.get_setting(key) is not None else "значение по умолчанию"
    pretty = current if current else "(пусто)"
    return (
        f"<b>{meta['title']}</b>\n"
        f"{state_icon}\n\n"
        f"📝 {meta['description']}\n"
        f"📌 Текущее значение: <code>{pretty}</code>\n"
        f"🧭 Источник: {source}"
    )


def _build_employees_text(settings: Settings) -> str:
    lines = ["<b>👥 Сотрудники</b>"]
    for uid, emp in sorted(settings.employees.items(), key=lambda i: (i[1].role, i[1].full_name.lower(), i[0])):
        uname = f"@{emp.username}" if emp.username else "без @username"
        lines.append(f"• <b>{emp.full_name}</b> ({emp.role}) — {uname}, id=<code>{uid}</code>")
    if len(lines) == 1:
        lines.append("⚪ Список пуст")
    return "\n".join(lines)


def _build_runtime_overview(db: Database, settings: Settings) -> str:
    lines = ["📌 <b>Текущая runtime-конфигурация</b>"]
    for key in VARIABLE_META:
        value = _runtime_value(key, db, settings)
        icon = "⭐" if _is_variable_set(key, db, settings) else "⚪"
        pretty = value if value else "(пусто)"
        lines.append(f"{icon} {key.upper()}: <code>{pretty}</code>")
    return "\n".join(lines)


def _read_log_tail(lines: int = 50) -> str:
    path = Path("logs") / "bot.log"
    if not path.exists():
        return "Лог-файл пока пуст или не создан."
    content = path.read_text(encoding="utf-8", errors="replace").splitlines()
    tail = content[-lines:]
    if not tail:
        return "Лог-файл пуст."
    text = "\n".join(tail)
    return text[-3900:]


def _parse_role_from_args(raw: str) -> str | None:
    args = (raw or "").strip().lower()
    for token in args.split():
        if token.startswith("role="):
            role = token.split("=", 1)[1]
            if role in {"sales", "logistics", "finance", "general"}:
                return role
    return None


def _is_hhmm(raw: str) -> bool:
    try:
        hh, mm = raw.split(":")
        h, m = int(hh), int(mm)
        return 0 <= h <= 23 and 0 <= m <= 59
    except Exception:
        return False


async def _ensure_owner(message: Message, settings: Settings) -> bool:
    if _is_owner(message, settings):
        return True

    user_id = message.from_user.id if message.from_user else None
    sender_chat_id = message.sender_chat.id if message.sender_chat else None
    await _answer_temp(
        message,
        "⛔ Команда только для администратора.\n"
        f"Ваш from_user.id={user_id}, sender_chat.id={sender_chat_id}.\n"
        f"OWNER_IDS={sorted(settings.owner_ids)}\n"
        "💡 Если вы анонимный админ в группе, отключите Anonymous Admin.",
        delete_request=False,
        ttl=30,
    )
    return False


def _is_owner(message: Message, settings: Settings) -> bool:
    user = message.from_user
    return bool(user and user.id in settings.owner_ids)


def _is_employee_role(user_id: int, employees: dict[int, Employee], role: str) -> bool:
    emp = employees.get(user_id)
    return bool(emp and emp.role == role)
