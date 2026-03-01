from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandObject
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


def get_runtime_config(settings: Settings, db: Database) -> RuntimeConfig:
    return RuntimeConfig(
        report_time=db.get_setting("report_time") or settings.report_time.strftime("%H:%M"),
        checkin_time=db.get_setting("checkin_time") or settings.checkin_time.strftime("%H:%M"),
        eod_time=db.get_setting("eod_time") or settings.eod_time.strftime("%H:%M"),
        inactivity_minutes=int(db.get_setting("inactivity_minutes") or settings.inactivity_minutes),
    )


def build_router(settings: Settings, db: Database) -> Router:
    router = Router()

    @router.message(F.from_user != None, ~F.text.startswith("/"))
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
        await state.set_state(EODStates.done_today)
        await _safe_delete_message(message)
        await message.answer("Вечерний отчёт\n1) Сделано сегодня?")

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
        await message.answer("Sale: Клиент?")

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
        await message.answer("Shipment: Номер клиента?")

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
        if not _is_owner(message, settings):
            return
        runtime = get_runtime_config(settings, db)
        cfg = _build_runtime_overview(db, settings)
        await _answer_temp(message, f"✅ Bot is running\nreport={runtime.report_time}, checkin={runtime.checkin_time}, eod={runtime.eod_time}, inactivity={runtime.inactivity_minutes}m\n\n{cfg}", ttl=30)

    @router.message(Command("report"))
    async def cmd_report(message: Message, command: CommandObject) -> None:
        if not _is_owner(message, settings):
            return
        if (command.args or "").strip().lower() != "today":
            await _answer_temp(message, "Usage: /report today")
            return
        today = datetime.now(settings.timezone).date()
        await _safe_delete_message(message)
        await message.answer(build_daily_report(today, db.get_activity_for_day(today), settings.employees))

    @router.message(Command("week"))
    async def cmd_week(message: Message) -> None:
        if not _is_owner(message, settings):
            return
        today = datetime.now(settings.timezone).date()
        start = today - timedelta(days=6)
        await _safe_delete_message(message)
        await message.answer(build_weekly_report(today, db.get_activity_between(start, today), settings.employees))
        await message.answer(build_kpi_block(db.get_sales_between(start.isoformat(), today.isoformat()), db.get_shipments_between(start.isoformat(), today.isoformat()), settings.employees, start.isoformat(), today.isoformat()))

    @router.message(Command("add_employee"))
    async def cmd_add_employee(message: Message, command: CommandObject) -> None:
        if not _is_owner(message, settings):
            return

        role = _parse_role_from_args(command.args or "")
        if role is None:
            await _answer_temp(message, "Usage: reply to a user with /add_employee role=sales|logistics|finance|general")
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
        if not _is_owner(message, settings):
            return
        arg = (command.args or "").strip()
        db.set_setting("checkin_time", arg)
        logger.info("⚙️ setting updated checkin_time=%s", arg)
        await _answer_temp(message, f"checkin_time updated: {arg}")

    @router.message(Command("set_eod_time"))
    async def cmd_set_eod(message: Message, command: CommandObject) -> None:
        if not _is_owner(message, settings):
            return
        arg = (command.args or "").strip()
        db.set_setting("eod_time", arg)
        logger.info("⚙️ setting updated eod_time=%s", arg)
        await _answer_temp(message, f"eod_time updated: {arg}")

    @router.message(Command("set_report_time"))
    async def cmd_set_report(message: Message, command: CommandObject) -> None:
        if not _is_owner(message, settings):
            return
        arg = (command.args or "").strip()
        db.set_setting("report_time", arg)
        logger.info("⚙️ setting updated report_time=%s", arg)
        await _answer_temp(message, f"report_time updated: {arg}")

    @router.message(Command("export"))
    async def cmd_export(message: Message, command: CommandObject) -> None:
        if not _is_owner(message, settings):
            return
        if (command.args or "").strip().lower() != "csv":
            await _answer_temp(message, "Usage: /export csv")
            return
        day = datetime.now(settings.timezone).date().isoformat()
        path = f"export_{day}.csv"
        db.export_csv(path, day)
        await _safe_delete_message(message)
        await message.answer_document(FSInputFile(path))

    @router.message(Command("admin"))
    async def cmd_admin(message: Message) -> None:
        if not _is_owner(message, settings):
            return
        await _safe_delete_message(message)
        await message.answer(ADMIN_HELP_TEXT, parse_mode="HTML", reply_markup=_admin_kb())

    @router.message(Command("admin_test"))
    async def cmd_admin_alias(message: Message) -> None:
        if not _is_owner(message, settings):
            return
        await _safe_delete_message(message)
        await message.answer(ADMIN_HELP_TEXT, parse_mode="HTML", reply_markup=_admin_kb())

    @router.callback_query(F.data.startswith("adm:"))
    async def admin_callback(callback: CallbackQuery, state: FSMContext) -> None:
        if callback.from_user.id not in settings.owner_ids:
            await callback.answer("Только для owner", show_alert=True)
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
                await callback.message.answer(f"📄 <b>Последние 50 строк лога</b>\n\n<pre>{tail}</pre>", parse_mode="HTML")
            elif action == "logs_file":
                log_path = Path("logs") / "bot.log"
                if not log_path.exists():
                    await callback.answer("Лог-файл пока не создан", show_alert=True)
                    return
                await callback.message.answer_document(FSInputFile(str(log_path)))
            elif action == "set_admin_here":
                db.set_setting("admin_chat_id", str(callback.message.chat.id))
                await callback.message.answer(f"✅ Admin chat сохранён: {callback.message.chat.id}")
            elif action == "set_general_here":
                db.set_setting("general_chat_id", str(callback.message.chat.id))
                await callback.message.answer(f"✅ General chat сохранён: {callback.message.chat.id}")
            elif action == "set_sales_here":
                db.set_setting("sales_chat_id", str(callback.message.chat.id))
                await callback.message.answer(f"✅ Sales chat сохранён: {callback.message.chat.id}")
            elif action == "set_logistics_here":
                db.set_setting("logistics_chat_id", str(callback.message.chat.id))
                await callback.message.answer(f"✅ Logistics chat сохранён: {callback.message.chat.id}")
            elif action == "add_work_here":
                _set_work_chat(db, settings, callback.message.chat.id, add=True)
                await callback.message.answer(f"✅ Чат добавлен в WORK_CHAT_IDS: {callback.message.chat.id}")
            elif action == "remove_work_here":
                _set_work_chat(db, settings, callback.message.chat.id, add=False)
                await callback.message.answer(f"🧹 Чат удалён из WORK_CHAT_IDS: {callback.message.chat.id}")
            elif action == "show_cfg":
                await callback.message.answer(_build_runtime_overview(db, settings))
            elif action == "ask_report":
                await state.set_state(AdminConfigState.wait_report_time)
                await callback.message.answer("Введите REPORT_TIME (HH:MM)")
            elif action == "ask_checkin":
                await state.set_state(AdminConfigState.wait_checkin_time)
                await callback.message.answer("Введите CHECKIN_TIME (HH:MM)")
            elif action == "ask_eod":
                await state.set_state(AdminConfigState.wait_eod_time)
                await callback.message.answer("Введите EOD_TIME (HH:MM)")
            elif action == "ask_work_start":
                await state.set_state(AdminConfigState.wait_work_start)
                await callback.message.answer("Введите WORK_START (HH:MM)")
            elif action == "ask_work_end":
                await state.set_state(AdminConfigState.wait_work_end)
                await callback.message.answer("Введите WORK_END (HH:MM)")
            elif action == "ask_inactivity":
                await state.set_state(AdminConfigState.wait_inactivity_minutes)
                await callback.message.answer("Введите INACTIVITY_MINUTES (например 60)")
            elif action == "menu":
                await callback.answer("♻️ Меню уже актуально")
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


async def _finish_shipment(message: Message, state: FSMContext, settings: Settings, db: Database, delay_reason: str) -> None:
    data = await state.get_data()
    now = datetime.now(settings.timezone)
    uid = int(message.from_user.id) if message.from_user else 0
    db.save_shipment(user_id=uid, day=now.date().isoformat(), client_number=str(data.get("client_number", "")), status=str(data.get("status", "created")), delay_reason=delay_reason, created_at=now.isoformat(timespec="seconds"))
    logger.info("📦 shipment saved user_id=%s status=%s", uid, data.get("status"))
    await message.answer(f"📦 shipment logged: {data.get('client_number')} status={data.get('status')}")
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
            [InlineKeyboardButton(text="🚀 Отправить Check-in кнопку", callback_data="adm:checkin_prompt")],
            [InlineKeyboardButton(text="📋 Кто НЕ чек-ин", callback_data="adm:checkin_missing")],
            [InlineKeyboardButton(text="🌆 Отправить EOD", callback_data="adm:eod_prompt")],
            [InlineKeyboardButton(text="📭 Кто НЕ сдал EOD", callback_data="adm:eod_missing")],
            [InlineKeyboardButton(text="📊 Daily report", callback_data="adm:daily")],
            [InlineKeyboardButton(text="🗓 Weekly + KPI", callback_data="adm:weekly")],
            [InlineKeyboardButton(text="⚠️ Проверка неактивности", callback_data="adm:inactivity")],
            [InlineKeyboardButton(text="📄 Последние 50 строк лога", callback_data="adm:logs_tail")],
            [InlineKeyboardButton(text="⬇️ Скачать лог", callback_data="adm:logs_file")],
            [InlineKeyboardButton(text="⚙️ Установить ADMIN_CHAT_ID = этот чат", callback_data="adm:set_admin_here")],
            [InlineKeyboardButton(text="⚙️ Установить GENERAL_CHAT_ID = этот чат", callback_data="adm:set_general_here")],
            [InlineKeyboardButton(text="⚙️ Установить SALES_CHAT_ID = этот чат", callback_data="adm:set_sales_here")],
            [InlineKeyboardButton(text="⚙️ Установить LOGISTICS_CHAT_ID = этот чат", callback_data="adm:set_logistics_here")],
            [InlineKeyboardButton(text="➕ Добавить этот чат в WORK_CHAT_IDS", callback_data="adm:add_work_here")],
            [InlineKeyboardButton(text="➖ Убрать этот чат из WORK_CHAT_IDS", callback_data="adm:remove_work_here")],
            [InlineKeyboardButton(text="🕒 Настроить REPORT_TIME", callback_data="adm:ask_report")],
            [InlineKeyboardButton(text="🌅 Настроить CHECKIN_TIME", callback_data="adm:ask_checkin")],
            [InlineKeyboardButton(text="🌆 Настроить EOD_TIME", callback_data="adm:ask_eod")],
            [InlineKeyboardButton(text="🟢 Настроить WORK_START", callback_data="adm:ask_work_start")],
            [InlineKeyboardButton(text="🔴 Настроить WORK_END", callback_data="adm:ask_work_end")],
            [InlineKeyboardButton(text="⏱ Настроить INACTIVITY_MINUTES", callback_data="adm:ask_inactivity")],
            [InlineKeyboardButton(text="📌 Показать текущую конфигурацию", callback_data="adm:show_cfg")],
            [InlineKeyboardButton(text="♻️ Обновить меню", callback_data="adm:menu")],
        ]
    )


def _set_work_chat(db: Database, settings: Settings, chat_id: int, add: bool) -> None:
    current = scheduler_jobs.get_runtime_work_chat_ids(db, settings)
    if add:
        current.add(chat_id)
    else:
        current.discard(chat_id)
    db.set_setting("work_chat_ids", ",".join(str(x) for x in sorted(current)))


def _build_runtime_overview(db: Database, settings: Settings) -> str:
    admin_chat = scheduler_jobs.get_runtime_chat_id(db, settings, "admin_chat_id")
    general_chat = scheduler_jobs.get_runtime_chat_id(db, settings, "general_chat_id")
    sales_chat = scheduler_jobs.get_runtime_chat_id(db, settings, "sales_chat_id")
    logistics_chat = scheduler_jobs.get_runtime_chat_id(db, settings, "logistics_chat_id")
    work_chats = sorted(scheduler_jobs.get_runtime_work_chat_ids(db, settings))
    report = db.get_setting("report_time") or settings.report_time.strftime("%H:%M")
    checkin = db.get_setting("checkin_time") or settings.checkin_time.strftime("%H:%M")
    eod = db.get_setting("eod_time") or settings.eod_time.strftime("%H:%M")
    wstart = db.get_setting("work_start") or settings.work_start.strftime("%H:%M")
    wend = db.get_setting("work_end") or settings.work_end.strftime("%H:%M")
    inactivity = db.get_setting("inactivity_minutes") or str(settings.inactivity_minutes)
    return (
        "📌 <b>Текущая runtime-конфигурация</b>\n"
        f"• ADMIN_CHAT_ID: <code>{admin_chat}</code>\n"
        f"• GENERAL_CHAT_ID: <code>{general_chat}</code>\n"
        f"• SALES_CHAT_ID: <code>{sales_chat}</code>\n"
        f"• LOGISTICS_CHAT_ID: <code>{logistics_chat}</code>\n"
        f"• WORK_CHAT_IDS: <code>{','.join(str(x) for x in work_chats)}</code>\n"
        f"• REPORT_TIME: <code>{report}</code>\n"
        f"• CHECKIN_TIME: <code>{checkin}</code>\n"
        f"• EOD_TIME: <code>{eod}</code>\n"
        f"• WORK_START: <code>{wstart}</code>\n"
        f"• WORK_END: <code>{wend}</code>\n"
        f"• INACTIVITY_MINUTES: <code>{inactivity}</code>"
    )


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


def _is_owner(message: Message, settings: Settings) -> bool:
    user = message.from_user
    return bool(user and user.id in settings.owner_ids)


def _is_employee_role(user_id: int, employees: dict[int, Employee], role: str) -> bool:
    emp = employees.get(user_id)
    return bool(emp and emp.role == role)
