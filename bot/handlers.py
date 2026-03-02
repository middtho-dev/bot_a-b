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
from bot.texts import (
    ADMIN_HELP_TEXT,
    ADMIN_MENU_BUTTONS,
    BTN_BACK,
    BTN_BACK_TO_MAIN,
    BTN_BACK_TO_VARS,
    BTN_FILL_EOD_PRIVATE,
    BTN_SET_VALUE,
    EMPLOYEE_MENU_BUTTONS,
    HANDLER_TEXTS,
    VAR_MENU_SUMMARY_BUTTON,
    VARIABLE_TEXT_META,
    WEEKDAY_LABELS,
)

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
    wait_schedule_anchor = State()




@dataclass
class RuntimeConfig:
    report_time: str
    checkin_time: str
    eod_time: str
    inactivity_minutes: int


VARIABLE_META = {
    "admin_chat_id": {"title": VARIABLE_TEXT_META["admin_chat_id"][0], "description": VARIABLE_TEXT_META["admin_chat_id"][1], "prompt": VARIABLE_TEXT_META["admin_chat_id"][2], "state": AdminConfigState.wait_admin_chat_id},
    "general_chat_id": {"title": VARIABLE_TEXT_META["general_chat_id"][0], "description": VARIABLE_TEXT_META["general_chat_id"][1], "prompt": VARIABLE_TEXT_META["general_chat_id"][2], "state": AdminConfigState.wait_general_chat_id},
    "sales_chat_id": {"title": VARIABLE_TEXT_META["sales_chat_id"][0], "description": VARIABLE_TEXT_META["sales_chat_id"][1], "prompt": VARIABLE_TEXT_META["sales_chat_id"][2], "state": AdminConfigState.wait_sales_chat_id},
    "logistics_chat_id": {"title": VARIABLE_TEXT_META["logistics_chat_id"][0], "description": VARIABLE_TEXT_META["logistics_chat_id"][1], "prompt": VARIABLE_TEXT_META["logistics_chat_id"][2], "state": AdminConfigState.wait_logistics_chat_id},
    "work_chat_ids": {"title": VARIABLE_TEXT_META["work_chat_ids"][0], "description": VARIABLE_TEXT_META["work_chat_ids"][1], "prompt": VARIABLE_TEXT_META["work_chat_ids"][2], "state": AdminConfigState.wait_work_chat_ids},
    "report_time": {"title": VARIABLE_TEXT_META["report_time"][0], "description": VARIABLE_TEXT_META["report_time"][1], "prompt": VARIABLE_TEXT_META["report_time"][2], "state": AdminConfigState.wait_report_time},
    "checkin_time": {"title": VARIABLE_TEXT_META["checkin_time"][0], "description": VARIABLE_TEXT_META["checkin_time"][1], "prompt": VARIABLE_TEXT_META["checkin_time"][2], "state": AdminConfigState.wait_checkin_time},
    "eod_time": {"title": VARIABLE_TEXT_META["eod_time"][0], "description": VARIABLE_TEXT_META["eod_time"][1], "prompt": VARIABLE_TEXT_META["eod_time"][2], "state": AdminConfigState.wait_eod_time},
    "work_start": {"title": VARIABLE_TEXT_META["work_start"][0], "description": VARIABLE_TEXT_META["work_start"][1], "prompt": VARIABLE_TEXT_META["work_start"][2], "state": AdminConfigState.wait_work_start},
    "work_end": {"title": VARIABLE_TEXT_META["work_end"][0], "description": VARIABLE_TEXT_META["work_end"][1], "prompt": VARIABLE_TEXT_META["work_end"][2], "state": AdminConfigState.wait_work_end},
    "inactivity_minutes": {"title": VARIABLE_TEXT_META["inactivity_minutes"][0], "description": VARIABLE_TEXT_META["inactivity_minutes"][1], "prompt": VARIABLE_TEXT_META["inactivity_minutes"][2], "state": AdminConfigState.wait_inactivity_minutes},
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
            await callback.answer(HANDLER_TEXTS["not_employee"], show_alert=True)
            return

        now = datetime.now(settings.timezone)
        token_day = (callback.data or "").split(":", 1)[1]
        today = now.date().isoformat()
        if token_day != today:
            await callback.answer(HANDLER_TEXTS["stale_button"], show_alert=True)
            return

        checked = db.checked_in_user_ids(today)
        if user.id in checked:
            await callback.answer(HANDLER_TEXTS["already_checked"], show_alert=False)
            return

        db.save_checkin(user.id, today, now.isoformat(timespec="seconds"))
        logger.info("✅ checkin accepted user_id=%s day=%s", user.id, today)
        await callback.answer(HANDLER_TEXTS["checkin_ok"], show_alert=False)

    @router.message(Command("checkin"))
    async def cmd_checkin(message: Message) -> None:
        user = message.from_user
        if not user or user.id not in settings.employees:
            return
        now = datetime.now(settings.timezone)
        today = now.date().isoformat()
        checked = db.checked_in_user_ids(today)
        if user.id in checked:
            await _answer_temp(message, HANDLER_TEXTS["already_checked"], delete_request=True)
            return
        db.save_checkin(user.id, today, now.isoformat(timespec="seconds"))
        logger.info("✅ checkin via command user_id=%s day=%s", user.id, today)
        await _answer_temp(message, HANDLER_TEXTS["checkin_saved"], delete_request=True)

    @router.message(Command("eod"))
    async def cmd_eod(message: Message, state: FSMContext) -> None:
        if not message.from_user or message.from_user.id not in settings.employees:
            return
        if message.chat.type != "private":
            await _safe_delete_message(message)
            await message.answer(
                HANDLER_TEXTS["eod_go_private"],
                reply_markup=await _eod_private_kb(message),
            )
            return
        await state.set_state(EODStates.done_today)
        await _safe_delete_message(message)
        await message.answer(HANDLER_TEXTS["eod_q1"])

    @router.message(Command("start"))
    async def cmd_start(message: Message, command: CommandObject, state: FSMContext) -> None:
        args = (command.args or "").strip().lower()
        if args == "eod":
            if not message.from_user or message.from_user.id not in settings.employees:
                await message.answer(HANDLER_TEXTS["not_registered"])
                return
            await state.set_state(EODStates.done_today)
            await message.answer(HANDLER_TEXTS["eod_q1"])
            return
        await message.answer(HANDLER_TEXTS["start_hint"])

    @router.message(Command("myid"))
    async def cmd_myid(message: Message) -> None:
        uid = message.from_user.id if message.from_user else None
        await message.answer(
            f"🆔 Ваш user_id: <code>{uid}</code>\n" + HANDLER_TEXTS["myid_hint"],
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
        await message.answer(HANDLER_TEXTS["eod_q2"])

    @router.message(EODStates.in_progress)
    async def eod_progress(message: Message, state: FSMContext) -> None:
        await state.update_data(in_progress=message.text or "")
        await state.set_state(EODStates.problems)
        await _safe_delete_message(message)
        await message.answer(HANDLER_TEXTS["eod_q3"])

    @router.message(EODStates.problems)
    async def eod_problems(message: Message, state: FSMContext) -> None:
        await state.update_data(problems=message.text or "")
        await state.set_state(EODStates.need_help)
        await _safe_delete_message(message)
        await message.answer(HANDLER_TEXTS["eod_q4"])

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
        await message.answer(HANDLER_TEXTS["eod_saved"])

    @router.message(Command("sale"))
    async def cmd_sale(message: Message, state: FSMContext) -> None:
        sales_chat_id = scheduler_jobs.get_runtime_chat_id(db, settings, "sales_chat_id")
        if message.chat.id != sales_chat_id:
            await _answer_temp(message, HANDLER_TEXTS["sale_chat_only"])
            return
        if not _is_employee_role(message.from_user.id if message.from_user else 0, settings.employees, "sales"):
            await _answer_temp(message, HANDLER_TEXTS["sale_role_only"])
            return
        await _safe_delete_message(message)
        await state.set_state(SaleStates.client)
        await message.answer(HANDLER_TEXTS["sale_q_client"])

    @router.message(SaleStates.client)
    async def sale_client(message: Message, state: FSMContext) -> None:
        await state.update_data(client=message.text or "")
        await state.set_state(SaleStates.amount)
        await _safe_delete_message(message)
        await message.answer(HANDLER_TEXTS["sale_q_amount"])

    @router.message(SaleStates.amount)
    async def sale_amount(message: Message, state: FSMContext) -> None:
        try:
            amount = float((message.text or "0").replace(",", ""))
        except ValueError:
            await _answer_temp(message, HANDLER_TEXTS["sale_bad_amount"], delete_request=False)
            return
        await state.update_data(amount=amount)
        await state.set_state(SaleStates.status)
        await _safe_delete_message(message)
        await message.answer(HANDLER_TEXTS["sale_q_status"])

    @router.message(SaleStates.status)
    async def sale_status(message: Message, state: FSMContext) -> None:
        status = (message.text or "").strip().lower()
        if status not in {"lead", "invoice", "paid"}:
            await _answer_temp(message, HANDLER_TEXTS["sale_bad_status"], delete_request=False)
            return
        await state.update_data(status=status)
        await state.set_state(SaleStates.comment)
        await _safe_delete_message(message)
        await message.answer(HANDLER_TEXTS["sale_q_comment"])

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
            await _answer_temp(message, HANDLER_TEXTS["shipment_chat_only"])
            return
        if not _is_employee_role(message.from_user.id if message.from_user else 0, settings.employees, "logistics"):
            await _answer_temp(message, HANDLER_TEXTS["shipment_role_only"])
            return
        await _safe_delete_message(message)
        await state.set_state(ShipmentStates.client_number)
        await message.answer(HANDLER_TEXTS["shipment_q_client"])

    @router.message(ShipmentStates.client_number)
    async def shipment_client(message: Message, state: FSMContext) -> None:
        await state.update_data(client_number=message.text or "")
        await state.set_state(ShipmentStates.status)
        await _safe_delete_message(message)
        await message.answer(HANDLER_TEXTS["shipment_q_status"])

    @router.message(ShipmentStates.status)
    async def shipment_status(message: Message, state: FSMContext) -> None:
        status = (message.text or "").strip().lower()
        if status not in {"created", "shipped", "delivered", "delayed"}:
            await _answer_temp(message, HANDLER_TEXTS["shipment_bad_status"], delete_request=False)
            return
        await state.update_data(status=status)
        await _safe_delete_message(message)
        if status == "delayed":
            await state.set_state(ShipmentStates.delay_reason)
            await message.answer(HANDLER_TEXTS["shipment_q_delay"])
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
        await _answer_temp(message, HANDLER_TEXTS["status_runtime"].format(report=runtime.report_time, checkin=runtime.checkin_time, eod=runtime.eod_time, inactivity=runtime.inactivity_minutes, cfg=cfg), ttl=30)

    @router.message(Command("report"))
    async def cmd_report(message: Message, command: CommandObject) -> None:
        if not await _ensure_owner(message, settings):
            return
        if (command.args or "").strip().lower() != "today":
            await _answer_temp(message, HANDLER_TEXTS["status_usage"])
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
            await _answer_temp(message, HANDLER_TEXTS["add_employee_usage_reply"])
            return

        source = message.reply_to_message.from_user if message.reply_to_message else None
        if not source:
            await _answer_temp(message, HANDLER_TEXTS["add_employee_need_reply"])
            return

        username = source.username or ""
        full_name = (source.full_name or "").strip() or username or str(source.id)
        db.upsert_employee(source.id, username, full_name, role)
        settings.employees[source.id] = Employee(source.id, username, full_name, role)
        logger.info("👤 employee upsert user_id=%s role=%s", source.id, role)
        await _answer_temp(message, HANDLER_TEXTS["employee_added_short"].format(full_name=full_name, role=role))

    @router.message(Command("set_checkin_time"))
    async def cmd_set_checkin(message: Message, command: CommandObject) -> None:
        if not await _ensure_owner(message, settings):
            return
        arg = (command.args or "").strip()
        db.set_setting("checkin_time", arg)
        logger.info("⚙️ setting updated checkin_time=%s", arg)
        await _answer_temp(message, HANDLER_TEXTS["checkin_time_updated"].format(value=arg))

    @router.message(Command("set_eod_time"))
    async def cmd_set_eod(message: Message, command: CommandObject) -> None:
        if not await _ensure_owner(message, settings):
            return
        arg = (command.args or "").strip()
        db.set_setting("eod_time", arg)
        logger.info("⚙️ setting updated eod_time=%s", arg)
        await _answer_temp(message, HANDLER_TEXTS["eod_time_updated"].format(value=arg))

    @router.message(Command("set_report_time"))
    async def cmd_set_report(message: Message, command: CommandObject) -> None:
        if not await _ensure_owner(message, settings):
            return
        arg = (command.args or "").strip()
        db.set_setting("report_time", arg)
        logger.info("⚙️ setting updated report_time=%s", arg)
        await _answer_temp(message, HANDLER_TEXTS["report_time_updated"].format(value=arg))

    @router.message(Command("export"))
    async def cmd_export(message: Message, command: CommandObject) -> None:
        if not await _ensure_owner(message, settings):
            return
        if (command.args or "").strip().lower() != "csv":
            await _answer_temp(message, HANDLER_TEXTS["export_usage"])
            return
        day = datetime.now(settings.timezone).date().isoformat()
        path = f"export_{day}.csv"
        db.export_csv(path, day)
        await _safe_delete_message(message)
        await message.answer_document(FSInputFile(path))



    @router.message(Command("export_csv"))
    async def cmd_export_csv(message: Message) -> None:
        if not await _ensure_owner(message, settings):
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
            f"OWNER_IDS={sorted(settings.owner_ids)}\n\n" + HANDLER_TEXTS["whoami_hint"]
        )

    @router.message(Command("admin"))
    async def cmd_admin(message: Message) -> None:
        if not await _ensure_owner(message, settings):
            return
        await _safe_delete_message(message)
        await message.answer(HANDLER_TEXTS["admin_title"], reply_markup=_admin_kb())

    @router.message(Command("admin_test"))
    async def cmd_admin_alias(message: Message) -> None:
        if not await _ensure_owner(message, settings):
            return
        await _safe_delete_message(message)
        await message.answer(HANDLER_TEXTS["admin_title"], reply_markup=_admin_kb())

    @router.callback_query(F.data.startswith("adm:"))
    async def admin_callback(callback: CallbackQuery, state: FSMContext) -> None:
        if callback.from_user.id not in settings.owner_ids:
            await callback.answer(HANDLER_TEXTS["only_owner"], show_alert=True)
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
                await callback.message.answer(HANDLER_TEXTS["logs_tail_title"].format(tail=tail), parse_mode="HTML", reply_markup=_back_main_kb())
            elif action == "logs_file":
                log_path = Path("logs") / "bot.log"
                if not log_path.exists():
                    await callback.answer(HANDLER_TEXTS["logs_missing"], show_alert=True)
                    return
                await callback.message.answer_document(FSInputFile(str(log_path)))
                await callback.message.answer(HANDLER_TEXTS["logs_back"], reply_markup=_back_main_kb())
            elif action == "open_vars":
                await callback.message.answer(HANDLER_TEXTS["cfg_vars_title"], reply_markup=_variables_kb(db, settings))
            elif action.startswith("var:"):
                key = action.split(":", 1)[1]
                if key not in VARIABLE_META:
                    await callback.answer(HANDLER_TEXTS["unknown_var"], show_alert=True)
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
                    await callback.answer(HANDLER_TEXTS["unknown_var"], show_alert=True)
                    return
                await state.set_state(meta["state"])
                await callback.message.answer(meta["prompt"])
            elif action == "open_employees":
                await callback.message.answer(HANDLER_TEXTS["cfg_employees_title"], reply_markup=_employees_kb())
            elif action == "employees_list":
                await callback.message.answer(_build_employees_text(settings), parse_mode="HTML", reply_markup=_employees_kb())
            elif action == "employees_remove_menu":
                await callback.message.answer(HANDLER_TEXTS["remove_title"], parse_mode="HTML", reply_markup=_employees_remove_kb(settings))
            elif action.startswith("emp_remove:"):
                uid = int(action.split(":", 1)[1])
                if uid in settings.owner_ids:
                    await callback.message.answer(HANDLER_TEXTS["remove_owner_forbidden"], reply_markup=_employees_kb())
                else:
                    db.delete_employee(uid)
                    settings.employees.pop(uid, None)
                    await callback.message.answer(HANDLER_TEXTS["removed_employee"].format(uid=uid), parse_mode="HTML", reply_markup=_employees_kb())
            elif action == "employees_schedule_menu":
                await callback.message.answer(HANDLER_TEXTS["schedule_menu_title"], reply_markup=_employees_schedule_kb(settings))
            elif action.startswith("emp_schedule:"):
                uid = int(action.split(":", 1)[1])
                await callback.message.answer(_build_employee_schedule_text(uid, settings, db), parse_mode="HTML", reply_markup=_employee_schedule_kb(uid, db))
            elif action.startswith("sched_toggle:"):
                _, uid_raw, wd_raw = action.split(":")
                uid = int(uid_raw)
                wd = int(wd_raw)
                sched = db.get_employee_schedule(uid)
                enabled = {int(x) for x in sched.get("weekdays", "").split(",") if x.isdigit()}
                if wd in enabled:
                    enabled.remove(wd)
                else:
                    enabled.add(wd)
                weekdays = ",".join(str(x) for x in sorted(enabled))
                db.set_employee_schedule(uid, sched.get("mode", "weekdays"), weekdays, sched.get("cycle_anchor", datetime.now(settings.timezone).date().isoformat()))
                await callback.message.answer(_build_employee_schedule_text(uid, settings, db), parse_mode="HTML", reply_markup=_employee_schedule_kb(uid, db))
            elif action.startswith("sched_mode_week:"):
                uid = int(action.split(":", 1)[1])
                sched = db.get_employee_schedule(uid)
                db.set_employee_schedule(uid, "weekdays", sched.get("weekdays", "0,1,2,3,4,5,6"), sched.get("cycle_anchor", datetime.now(settings.timezone).date().isoformat()))
                await callback.message.answer(_build_employee_schedule_text(uid, settings, db), parse_mode="HTML", reply_markup=_employee_schedule_kb(uid, db))
            elif action.startswith("sched_mode_22:"):
                uid = int(action.split(":", 1)[1])
                sched = db.get_employee_schedule(uid)
                db.set_employee_schedule(uid, "cycle_2_2", sched.get("weekdays", "0,1,2,3,4,5,6"), sched.get("cycle_anchor", datetime.now(settings.timezone).date().isoformat()))
                await callback.message.answer(_build_employee_schedule_text(uid, settings, db), parse_mode="HTML", reply_markup=_employee_schedule_kb(uid, db))
            elif action.startswith("sched_set_anchor:"):
                uid = int(action.split(":", 1)[1])
                await state.set_state(AdminConfigState.wait_schedule_anchor)
                await state.update_data(schedule_user_id=uid)
                await callback.message.answer(HANDLER_TEXTS["schedule_anchor_prompt"])
            elif action == "back_main":
                await callback.message.answer(HANDLER_TEXTS["main_menu_title"], reply_markup=_admin_kb())
            elif action.startswith("emp_add_role:"):
                role = action.split(":", 1)[1]
                await state.set_state(AdminConfigState.wait_employee_id)
                await state.update_data(add_role=role)
                await callback.message.answer(
                    HANDLER_TEXTS["employee_id_prompt_role"].format(role=role),
                    parse_mode="HTML",
                )
            elif action == "show_cfg":
                await callback.message.answer(_build_runtime_overview(db, settings), parse_mode="HTML")
            elif action == "help":
                await callback.message.answer(ADMIN_HELP_TEXT, parse_mode="HTML", reply_markup=_back_main_kb())
            elif action == "menu":
                await callback.message.answer(HANDLER_TEXTS["admin_title"], reply_markup=_admin_kb())
                await callback.answer("♻️ Меню обновлено")
                return
            else:
                await callback.answer(HANDLER_TEXTS["unknown_action"], show_alert=True)
                return
        except TelegramBadRequest as exc:
            if "message is not modified" in str(exc).lower():
                await callback.answer("♻️ Нечего обновлять")
                return
            logger.exception("❌ TelegramBadRequest action=%s", action)
            await callback.answer(HANDLER_TEXTS["telegram_api_error"], show_alert=True)
            return
        except Exception:
            logger.exception("❌ admin callback failed action=%s", action)
            await callback.answer(HANDLER_TEXTS["internal_error"], show_alert=True)
            return

        logger.info("🧪 admin action executed action=%s by=%s", action, callback.from_user.id)
        await callback.answer(HANDLER_TEXTS["done"])

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
            await _answer_temp(message, HANDLER_TEXTS["bad_user_id"])
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
                HANDLER_TEXTS["employee_name_prompt_auto"].format(full_name=auto_full_name),
                delete_request=False,
            )
            return
        await _answer_temp(message, HANDLER_TEXTS["employee_name_prompt"], delete_request=False)

    @router.message(AdminConfigState.wait_employee_full_name)
    async def cfg_employee_full_name(message: Message, state: FSMContext) -> None:
        full_name = (message.text or "").strip()
        data = await state.get_data()
        auto_full_name = str(data.get("auto_full_name", "")).strip()
        if full_name == "+" and auto_full_name:
            full_name = auto_full_name
        if not full_name:
            await _answer_temp(message, HANDLER_TEXTS["name_empty"])
            return
        await state.update_data(add_full_name=full_name)
        await state.set_state(AdminConfigState.wait_employee_username)
        auto_username = str(data.get("auto_username", "")).strip()
        if auto_username:
            await _answer_temp(message, HANDLER_TEXTS["employee_username_prompt_auto"].format(username=auto_username), delete_request=False)
            return
        await _answer_temp(message, HANDLER_TEXTS["employee_username_prompt"], delete_request=False)

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
                await _answer_temp(message, HANDLER_TEXTS["bad_username"])
                return

        role = str(data.get("add_role", "general"))
        uid = int(data.get("add_user_id", 0))
        full_name = str(data.get("add_full_name", "")).strip() or HANDLER_TEXTS["employee_fallback_name"].format(uid=uid)
        db.upsert_employee(uid, username=username, full_name=full_name, role=role)
        settings.employees[uid] = Employee(uid, username, full_name, role)
        await state.clear()
        logger.info("👤 employee added from menu user_id=%s role=%s username=%s", uid, role, username)
        username_part = f" (@{username})" if username else ""
        await _answer_temp(message, HANDLER_TEXTS["employee_added_full"].format(full_name=full_name, username_part=username_part, role=role), delete_request=False)
        await message.answer(HANDLER_TEXTS["employee_list_updated"], parse_mode="HTML", reply_markup=_employees_kb())
        await message.answer(_build_employees_text(settings), parse_mode="HTML")

    @router.message(AdminConfigState.wait_schedule_anchor)
    async def cfg_schedule_anchor(message: Message, state: FSMContext) -> None:
        raw = (message.text or "").strip()
        try:
            datetime.strptime(raw, "%Y-%m-%d")
        except ValueError:
            await _answer_temp(message, HANDLER_TEXTS["schedule_bad_date"])
            return
        data = await state.get_data()
        uid = int(data.get("schedule_user_id", 0))
        sched = db.get_employee_schedule(uid)
        db.set_employee_schedule(uid, sched.get("mode", "cycle_2_2"), sched.get("weekdays", "0,1,2,3,4,5,6"), raw)
        await state.clear()
        await _answer_temp(message, HANDLER_TEXTS["schedule_anchor_set"].format(uid=uid, date=raw), delete_request=False)
        await message.answer(_build_employee_schedule_text(uid, settings, db), parse_mode="HTML", reply_markup=_employee_schedule_kb(uid, db))

    @router.message(AdminConfigState.wait_inactivity_minutes)
    async def cfg_inactivity(message: Message, state: FSMContext) -> None:
        val = (message.text or "").strip()
        if not val.isdigit():
            await _answer_temp(message, HANDLER_TEXTS["bad_minutes"])
            return
        db.set_setting("inactivity_minutes", val)
        await state.clear()
        logger.info("⚙️ setting updated inactivity_minutes=%s", val)
        await _answer_temp(message, HANDLER_TEXTS["inactivity_updated"].format(value=val))

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
            await _answer_temp(message, HANDLER_TEXTS["bad_work_chats"])
            return
        db.set_setting("work_chat_ids", ",".join(parsed))
        await state.clear()
        logger.info("⚙️ setting updated work_chat_ids=%s", ",".join(parsed))
        await _answer_temp(message, HANDLER_TEXTS["work_chats_saved"].format(count=len(parsed)))

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
        await _answer_temp(message, HANDLER_TEXTS["bad_time"])
        return
    db.set_setting(key, val)
    await state.clear()
    logger.info("⚙️ setting updated %s=%s", key, val)
    await _answer_temp(message, HANDLER_TEXTS["setting_saved"].format(key=key.upper(), value=val))


async def _save_chat_id_setting(message: Message, state: FSMContext, db: Database, key: str) -> None:
    raw = (message.text or "").strip()
    if not raw.lstrip("-").isdigit():
        await _answer_temp(message, HANDLER_TEXTS["bad_chat_id"])
        return
    db.set_setting(key, raw)
    await state.clear()
    logger.info("⚙️ setting updated %s=%s", key, raw)
    await _answer_temp(message, HANDLER_TEXTS["setting_saved"].format(key=key.upper(), value=raw))


async def _finish_shipment(message: Message, state: FSMContext, settings: Settings, db: Database, delay_reason: str) -> None:
    data = await state.get_data()
    now = datetime.now(settings.timezone)
    uid = int(message.from_user.id) if message.from_user else 0
    db.save_shipment(user_id=uid, day=now.date().isoformat(), client_number=str(data.get("client_number", "")), status=str(data.get("status", "created")), delay_reason=delay_reason, created_at=now.isoformat(timespec="seconds"))
    logger.info("📦 shipment saved user_id=%s status=%s", uid, data.get("status"))
    await message.answer(HANDLER_TEXTS["shipment_saved"].format(client=data.get("client_number"), status=data.get("status")))
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
        inline_keyboard=[[InlineKeyboardButton(text=text, callback_data=callback)] for text, callback in ADMIN_MENU_BUTTONS]
    )


def _variables_kb(db: Database, settings: Settings) -> InlineKeyboardMarkup:
    rows = []
    for key, meta in VARIABLE_META.items():
        icon = "⭐" if _is_variable_set(key, db, settings) else "⚪"
        rows.append([InlineKeyboardButton(text=f"{icon} {meta['title']}", callback_data=f"adm:var:{key}")])
    rows.append([InlineKeyboardButton(text=VAR_MENU_SUMMARY_BUTTON, callback_data="adm:show_cfg")])
    rows.append([InlineKeyboardButton(text=BTN_BACK, callback_data="adm:back_main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _variable_details_kb(key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=BTN_SET_VALUE, callback_data=f"adm:setvar:{key}")],
            [InlineKeyboardButton(text=BTN_BACK_TO_VARS, callback_data="adm:open_vars")],
            [InlineKeyboardButton(text=BTN_BACK_TO_MAIN, callback_data="adm:back_main")],
        ]
    )




def _back_main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=BTN_BACK, callback_data="adm:back_main")]])

def _employees_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=text, callback_data=callback)] for text, callback in EMPLOYEE_MENU_BUTTONS]
    )


def _employees_remove_kb(settings: Settings) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for uid, emp in sorted(settings.employees.items(), key=lambda i: i[0]):
        rows.append([InlineKeyboardButton(text=HANDLER_TEXTS["remove_employee_btn"].format(full_name=emp.full_name, uid=uid), callback_data=f"adm:emp_remove:{uid}")])
    rows.append([InlineKeyboardButton(text=HANDLER_TEXTS["back_to_employees"], callback_data="adm:open_employees")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _employees_schedule_kb(settings: Settings) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for uid, emp in sorted(settings.employees.items(), key=lambda i: i[0]):
        rows.append([InlineKeyboardButton(text=HANDLER_TEXTS["schedule_employee_btn"].format(full_name=emp.full_name, uid=uid), callback_data=f"adm:emp_schedule:{uid}")])
    rows.append([InlineKeyboardButton(text=HANDLER_TEXTS["back_to_employees"], callback_data="adm:open_employees")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _employee_schedule_kb(user_id: int, db: Database) -> InlineKeyboardMarkup:
    sched = db.get_employee_schedule(user_id)
    enabled = {int(x) for x in sched.get("weekdays", "").split(",") if x.isdigit()}
    rows: list[list[InlineKeyboardButton]] = []
    day_buttons = []
    for wd, label in enumerate(WEEKDAY_LABELS):
        mark = "✅" if wd in enabled else "⚪"
        day_buttons.append(InlineKeyboardButton(text=f"{mark} {label}", callback_data=f"adm:sched_toggle:{user_id}:{wd}"))
    rows.append(day_buttons)
    rows.append([
        InlineKeyboardButton(text=HANDLER_TEXTS["sched_mode_week"], callback_data=f"adm:sched_mode_week:{user_id}"),
        InlineKeyboardButton(text=HANDLER_TEXTS["sched_mode_22"], callback_data=f"adm:sched_mode_22:{user_id}"),
    ])
    rows.append([InlineKeyboardButton(text=HANDLER_TEXTS["sched_set_anchor"], callback_data=f"adm:sched_set_anchor:{user_id}")])
    rows.append([InlineKeyboardButton(text=HANDLER_TEXTS["sched_back_pick"], callback_data="adm:employees_schedule_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _build_employee_schedule_text(user_id: int, settings: Settings, db: Database) -> str:
    emp = settings.employees.get(user_id)
    if not emp:
        return HANDLER_TEXTS["schedule_not_found"]
    sched = db.get_employee_schedule(user_id)
    mode = sched.get("mode", "weekdays")
    enabled = {int(x) for x in sched.get("weekdays", "").split(",") if x.isdigit()}
    day_marks = " ".join(f"{'✅' if i in enabled else '⚪'} {name}" for i, name in enumerate(WEEKDAY_LABELS))
    mode_text = HANDLER_TEXTS["schedule_mode_weekdays"] if mode == "weekdays" else HANDLER_TEXTS["schedule_mode_cycle"]
    today_work = HANDLER_TEXTS["schedule_today_work"] if db.is_employee_working_on(user_id, datetime.now(settings.timezone).date()) else HANDLER_TEXTS["schedule_today_off"]
    return HANDLER_TEXTS["schedule_card"].format(
        full_name=emp.full_name,
        uid=user_id,
        mode=mode_text,
        anchor=sched.get("cycle_anchor"),
        today=today_work,
        days=day_marks,
    )


async def _eod_private_kb(message: Message) -> InlineKeyboardMarkup:
    me = await message.bot.get_me()
    url = f"https://t.me/{me.username}?start=eod"
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=BTN_FILL_EOD_PRIVATE, url=url)]])


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
    source = HANDLER_TEXTS["source_db"] if db.get_setting(key) is not None else HANDLER_TEXTS["source_default"]
    pretty = current if current else "(пусто)"
    return (
        f"<b>{meta['title']}</b>\n"
        f"{state_icon}\n\n"
        f"📝 {meta['description']}\n"
        f"📌 Текущее значение: <code>{pretty}</code>\n"
        f"🧭 Источник: {source}"
    )


def _build_employees_text(settings: Settings) -> str:
    lines = [HANDLER_TEXTS["employees_title"]]
    for uid, emp in sorted(settings.employees.items(), key=lambda i: (i[1].role, i[1].full_name.lower(), i[0])):
        uname = f"@{emp.username}" if emp.username else HANDLER_TEXTS["employees_empty_username"]
        lines.append(HANDLER_TEXTS["employees_line"].format(full_name=emp.full_name, role=emp.role, username=uname, uid=uid))
    if len(lines) == 1:
        lines.append(HANDLER_TEXTS["employees_empty"])
    return "\n".join(lines)


def _build_runtime_overview(db: Database, settings: Settings) -> str:
    lines = [HANDLER_TEXTS["runtime_overview_title"]]
    for key in VARIABLE_META:
        value = _runtime_value(key, db, settings)
        icon = "⭐" if _is_variable_set(key, db, settings) else "⚪"
        pretty = value if value else "(пусто)"
        lines.append(HANDLER_TEXTS["runtime_overview_line"].format(icon=icon, key=key.upper(), value=pretty))
    return "\n".join(lines)


def _read_log_tail(lines: int = 50) -> str:
    path = Path("logs") / "bot.log"
    if not path.exists():
        return HANDLER_TEXTS["log_absent"]
    content = path.read_text(encoding="utf-8", errors="replace").splitlines()
    tail = content[-lines:]
    if not tail:
        return HANDLER_TEXTS["log_empty"]
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
        HANDLER_TEXTS["owner_only"].format(
            user_id=user_id,
            sender_chat_id=sender_chat_id,
            owner_ids=sorted(settings.owner_ids),
        ),
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
