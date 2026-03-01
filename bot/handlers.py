from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, FSInputFile, Message

from bot.config import Employee, Settings
from bot.db import Database
from bot.reports import build_daily_report, build_kpi_block, build_weekly_report


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

    @router.message(F.chat.id.in_(settings.work_chat_ids), F.from_user != None)
    async def collect_activity(message: Message) -> None:
        user = message.from_user
        if not user or user.id not in settings.employees:
            return
        db.record_message(user.id, message.chat.id, datetime.now(settings.timezone))

    @router.callback_query(F.data == "checkin")
    async def on_checkin(callback: CallbackQuery) -> None:
        user = callback.from_user
        if user.id not in settings.employees:
            await callback.answer("Вы не в списке сотрудников", show_alert=True)
            return
        now = datetime.now(settings.timezone)
        db.save_checkin(user.id, now.date().isoformat(), now.isoformat(timespec="seconds"))
        await callback.answer("Отметка принята ✅")
        await callback.message.answer(f"✅ @{user.username or user.id} отметил(а) начало дня")

    @router.message(Command("eod"))
    async def cmd_eod(message: Message, state: FSMContext) -> None:
        if not message.from_user or message.from_user.id not in settings.employees:
            return
        await state.set_state(EODStates.done_today)
        await message.answer("Вечерний отчёт\n1) Сделано сегодня?")

    @router.message(EODStates.done_today)
    async def eod_done(message: Message, state: FSMContext) -> None:
        await state.update_data(done_today=message.text or "")
        await state.set_state(EODStates.in_progress)
        await message.answer("2) В работе?")

    @router.message(EODStates.in_progress)
    async def eod_progress(message: Message, state: FSMContext) -> None:
        await state.update_data(in_progress=message.text or "")
        await state.set_state(EODStates.problems)
        await message.answer("3) Проблемы?")

    @router.message(EODStates.problems)
    async def eod_problems(message: Message, state: FSMContext) -> None:
        await state.update_data(problems=message.text or "")
        await state.set_state(EODStates.need_help)
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
        await message.answer("✅ EOD отчёт сохранён")

    @router.message(Command("sale"))
    async def cmd_sale(message: Message, state: FSMContext) -> None:
        if message.chat.id != settings.sales_chat_id:
            await message.answer("Команда доступна только в Sales-чате")
            return
        if not _is_employee_role(message.from_user.id if message.from_user else 0, settings.employees, "sales"):
            return
        await state.set_state(SaleStates.client)
        await message.answer("Sale: Клиент?")

    @router.message(SaleStates.client)
    async def sale_client(message: Message, state: FSMContext) -> None:
        await state.update_data(client=message.text or "")
        await state.set_state(SaleStates.amount)
        await message.answer("Сумма (число)?")

    @router.message(SaleStates.amount)
    async def sale_amount(message: Message, state: FSMContext) -> None:
        try:
            amount = float((message.text or "0").replace(",", ""))
        except ValueError:
            await message.answer("Введите сумму числом")
            return
        await state.update_data(amount=amount)
        await state.set_state(SaleStates.status)
        await message.answer("Статус: lead / invoice / paid")

    @router.message(SaleStates.status)
    async def sale_status(message: Message, state: FSMContext) -> None:
        status = (message.text or "").strip().lower()
        if status not in {"lead", "invoice", "paid"}:
            await message.answer("Только: lead / invoice / paid")
            return
        await state.update_data(status=status)
        await state.set_state(SaleStates.comment)
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
        await message.answer(
            f"#sale @{message.from_user.username if message.from_user else uid} {float(data.get('amount', 0.0)):.2f}aed {data.get('status', 'lead')}"
        )
        await state.clear()

    @router.message(Command("shipment"))
    async def cmd_shipment(message: Message, state: FSMContext) -> None:
        if message.chat.id != settings.logistics_chat_id:
            await message.answer("Команда доступна только в Logistics-чате")
            return
        if not _is_employee_role(message.from_user.id if message.from_user else 0, settings.employees, "logistics"):
            return
        await state.set_state(ShipmentStates.client_number)
        await message.answer("Shipment: Номер клиента?")

    @router.message(ShipmentStates.client_number)
    async def shipment_client(message: Message, state: FSMContext) -> None:
        await state.update_data(client_number=message.text or "")
        await state.set_state(ShipmentStates.status)
        await message.answer("Статус: created / shipped / delivered / delayed")

    @router.message(ShipmentStates.status)
    async def shipment_status(message: Message, state: FSMContext) -> None:
        status = (message.text or "").strip().lower()
        if status not in {"created", "shipped", "delivered", "delayed"}:
            await message.answer("Только: created / shipped / delivered / delayed")
            return
        await state.update_data(status=status)
        if status == "delayed":
            await state.set_state(ShipmentStates.delay_reason)
            await message.answer("Причина задержки?")
            return
        await _finish_shipment(message, state, "")

    @router.message(ShipmentStates.delay_reason)
    async def shipment_delay_reason(message: Message, state: FSMContext) -> None:
        await _finish_shipment(message, state, message.text or "")

    @router.message(Command("status"))
    async def cmd_status(message: Message) -> None:
        if not _is_owner(message, settings):
            return
        runtime = get_runtime_config(settings, db)
        await message.answer(
            "✅ Bot is running\n"
            f"report={runtime.report_time}, checkin={runtime.checkin_time}, eod={runtime.eod_time}, inactivity={runtime.inactivity_minutes}m"
        )

    @router.message(Command("report"))
    async def cmd_report(message: Message, command: CommandObject) -> None:
        if not _is_owner(message, settings):
            return
        if (command.args or "").strip().lower() != "today":
            await message.answer("Usage: /report today")
            return
        today = datetime.now(settings.timezone).date()
        await message.answer(build_daily_report(today, db.get_activity_for_day(today), settings.employees))

    @router.message(Command("week"))
    async def cmd_week(message: Message) -> None:
        if not _is_owner(message, settings):
            return
        today = datetime.now(settings.timezone).date()
        start = today - timedelta(days=6)
        await message.answer(build_weekly_report(today, db.get_activity_between(start, today), settings.employees))
        await message.answer(
            build_kpi_block(
                db.get_sales_between(start.isoformat(), today.isoformat()),
                db.get_shipments_between(start.isoformat(), today.isoformat()),
                settings.employees,
                start.isoformat(),
                today.isoformat(),
            )
        )

    @router.message(Command("add_employee"))
    async def cmd_add_employee(message: Message, command: CommandObject) -> None:
        if not _is_owner(message, settings):
            return
        await message.answer("Для текущей версии добавление сотрудников делается через EMPLOYEES_JSON + рестарт")

    @router.message(Command("set_checkin_time"))
    async def cmd_set_checkin(message: Message, command: CommandObject) -> None:
        if not _is_owner(message, settings):
            return
        arg = (command.args or "").strip()
        db.set_setting("checkin_time", arg)
        await message.answer(f"checkin_time updated: {arg}")

    @router.message(Command("set_eod_time"))
    async def cmd_set_eod(message: Message, command: CommandObject) -> None:
        if not _is_owner(message, settings):
            return
        arg = (command.args or "").strip()
        db.set_setting("eod_time", arg)
        await message.answer(f"eod_time updated: {arg}")

    @router.message(Command("set_report_time"))
    async def cmd_set_report(message: Message, command: CommandObject) -> None:
        if not _is_owner(message, settings):
            return
        arg = (command.args or "").strip()
        db.set_setting("report_time", arg)
        await message.answer(f"report_time updated: {arg}")

    @router.message(Command("export"))
    async def cmd_export(message: Message, command: CommandObject) -> None:
        if not _is_owner(message, settings):
            return
        if (command.args or "").strip().lower() != "csv":
            await message.answer("Usage: /export csv")
            return
        day = datetime.now(settings.timezone).date().isoformat()
        path = f"export_{day}.csv"
        db.export_csv(path, day)
        await message.answer_document(FSInputFile(path))

    return router


async def _finish_shipment(message: Message, state: FSMContext, delay_reason: str) -> None:
    data = await state.get_data()
    settings: Settings = message.bot["settings"]
    db: Database = message.bot["db"]
    now = datetime.now(settings.timezone)
    uid = int(message.from_user.id) if message.from_user else 0
    db.save_shipment(
        user_id=uid,
        day=now.date().isoformat(),
        client_number=str(data.get("client_number", "")),
        status=str(data.get("status", "created")),
        delay_reason=delay_reason,
        created_at=now.isoformat(timespec="seconds"),
    )
    await message.answer(f"📦 shipment logged: {data.get('client_number')} status={data.get('status')}")
    await state.clear()


def _is_owner(message: Message, settings: Settings) -> bool:
    user = message.from_user
    return bool(user and user.id in settings.owner_ids)


def _is_employee_role(user_id: int, employees: dict[int, Employee], role: str) -> bool:
    emp = employees.get(user_id)
    return bool(emp and emp.role == role)
