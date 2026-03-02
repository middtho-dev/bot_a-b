from __future__ import annotations

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
• /export_csv — выгрузка активности
• /export csv — старый формат (оставлен для совместимости)

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

ADMIN_MENU_BUTTONS = [
    ("🚀 Отправить чек-ин", "adm:checkin_prompt"),
    ("📋 Кто не чек-ин", "adm:checkin_missing"),
    ("🌆 Отправить напоминание о EOD", "adm:eod_prompt"),
    ("📭 Кто не сдал EOD", "adm:eod_missing"),
    ("📊 Отправить дневной отчёт", "adm:daily"),
    ("🗓 Отправить недельный отчёт + KPI", "adm:weekly"),
    ("⚠️ Проверка неактивности", "adm:inactivity"),
    ("⚙️ Меню переменных", "adm:open_vars"),
    ("👥 Меню сотрудников", "adm:open_employees"),
    ("📘 Инструкции и команды", "adm:help"),
    ("📄 Последние 50 строк лога", "adm:logs_tail"),
    ("⬇️ Скачать лог", "adm:logs_file"),
    ("♻️ Обновить", "adm:menu"),
]

EMPLOYEE_MENU_BUTTONS = [
    ("📋 Список сотрудников", "adm:employees_list"),
    ("📅 Графики сотрудников", "adm:employees_schedule_menu"),
    ("🗑 Удалить сотрудника", "adm:employees_remove_menu"),
    ("➕ Добавить сотрудника (продажи)", "adm:emp_add_role:sales"),
    ("➕ Добавить сотрудника (логистика)", "adm:emp_add_role:logistics"),
    ("➕ Добавить сотрудника (финансы)", "adm:emp_add_role:finance"),
    ("➕ Добавить сотрудника (общая роль)", "adm:emp_add_role:general"),
    ("ℹ️ Как добавить: сотрудник пишет /myid", "adm:help"),
    ("⬅️ Назад", "adm:back_main"),
]

VAR_MENU_SUMMARY_BUTTON = "📌 Показать сводную конфигурацию"
BTN_BACK = "⬅️ Назад"
BTN_BACK_TO_VARS = "⬅️ Назад к переменным"
BTN_BACK_TO_MAIN = "⬅️ В главное меню"
BTN_SET_VALUE = "✏️ Установить значение"
BTN_FILL_EOD_PRIVATE = "📝 Заполнить EOD в личном чате"

HANDLER_TEXTS = {
    "not_employee": "Вы не в списке сотрудников",
    "stale_button": "Эта кнопка уже неактуальна",
    "already_checked": "Вы уже отметились сегодня ✅",
    "checkin_ok": "Отметка принята ✅",
    "checkin_saved": "✅ Чек-ин принят",
    "eod_go_private": "📝 Для заполнения вечернего отчёта откройте личный чат с ботом и нажмите кнопку ниже.",
    "eod_q1": "Вечерний отчёт\n1) Сделано сегодня?",
    "eod_q2": "2) В работе?",
    "eod_q3": "3) Проблемы?",
    "eod_q4": "4) Нужна помощь?",
    "eod_saved": "✅ EOD отчёт сохранён",
    "start_hint": "👋 Бот активен. Для меню администратора используйте /admin",
    "not_registered": "⛔ Вы не зарегистрированы как сотрудник. Обратитесь к администратору.",
    "sale_chat_only": "Команда доступна только в чате продаж",
    "sale_role_only": "Команда /sale доступна только сотрудникам с ролью sales",
    "sale_q_client": "💰 Продажа: клиент?",
    "sale_q_amount": "Сумма (число)?",
    "sale_bad_amount": "Введите сумму числом",
    "sale_q_status": "Статус: лид / счёт / оплачено (lead / invoice / paid)",
    "sale_bad_status": "Только: lead / invoice / paid",
    "sale_q_comment": "Комментарий?",
    "shipment_chat_only": "Команда доступна только в чате логистики",
    "shipment_role_only": "Команда /shipment доступна только сотрудникам с ролью logistics",
    "shipment_q_client": "📦 Отправка: номер клиента?",
    "shipment_q_status": "Статус: создана / отправлена / доставлена / задержана (created / shipped / delivered / delayed)",
    "shipment_bad_status": "Только: created / shipped / delivered / delayed",
    "shipment_q_delay": "Причина задержки?",
    "status_usage": "Использование: /report today",
    "export_usage": "Использование: /export csv",
    "admin_title": "🛠 Админ-меню",
    "only_owner": "Только для администратора",
    "unknown_var": "Неизвестная переменная",
    "unknown_action": "Неизвестная команда",
    "telegram_api_error": "Ошибка Telegram API",
    "internal_error": "⚠️ Внутренняя ошибка, смотри логи",
    "done": "✅ Выполнено",
    "cfg_vars_title": "⚙️ Меню переменных",
    "cfg_employees_title": "👥 Меню сотрудников",
    "remove_title": "🗑 Выберите сотрудника для удаления",
    "remove_owner_forbidden": "⛔ Нельзя удалить owner из системы",
    "schedule_menu_title": "📅 Выберите сотрудника для настройки графика",
    "main_menu_title": "🛠 Главное админ-меню",
    "bad_user_id": "Введите корректный user_id (число)",
    "name_empty": "Имя не может быть пустым",
    "bad_username": "Имя пользователя должно быть в формате @username, '+' или '-'",
    "bad_minutes": "Введите целое число минут",
    "bad_chat_id": "Введите корректный ID чата (число)",
    "bad_work_chats": "Формат неверный. Пример: -1001111111111,-1002222222222",
    "bad_time": "Формат времени должен быть HH:MM",
    "owner_only": "⛔ Команда только для администратора.\nВаш from_user.id={user_id}, sender_chat.id={sender_chat_id}.\nOWNER_IDS={owner_ids}\n💡 Если вы анонимный админ в группе, отключите Anonymous Admin.",
    "logs_missing": "Лог-файл пока не создан",
    "logs_back": "⬅️ Вернуться в админ-меню",
}

SCHEDULER_TEXTS = {
    "general_chat_not_set": "⚠️ general_chat_id не настроен",
    "checkin_prompt": "Подтвердите начало рабочего дня\nКнопка актуальна только сегодня. Также можно командой /checkin",
    "checkin_missing_title": "Чек-ин",
    "eod_prompt": "Заполните вечерний отчёт. Нажмите кнопку ниже и заполните форму в личном чате с ботом.",
    "eod_missing_title": "EOD",
    "inactivity_alert": "⚠️ Нет активности более {minutes} минут: @{user} (последняя активность {last_time})",
}

ROLE_LABELS = {
    "sales": "Продажи",
    "logistics": "Логистика",
    "finance": "Финансы",
    "general": "Общий",
}

REPORT_TEXTS = {
    "daily_title": "📊 Дневной отчёт по активности — {day}",
    "weekly_title": "🗓 Недельный отчёт по активности — {start} .. {end}",
    "dept_totals": "\nИтого по отделам:",
    "kpi_title": "📈 KPI-снимок {start}..{end}",
    "kpi_sales": "Продажи:",
    "kpi_logistics": "Логистика:",
    "missing_ok": "✅ {title} ({day}): все сотрудники отметились.",
    "missing_bad": "⚠️ {title} ({day})",
}


HANDLER_TEXTS.update({
    "add_employee_usage_reply": "Использование: ответьте на сообщение сотрудника командой /add_employee role=sales|logistics|finance|general",
    "add_employee_need_reply": "Нужно ответить на сообщение сотрудника командой /add_employee role=...",
    "status_runtime": "✅ Бот работает\nreport={report}, checkin={checkin}, eod={eod}, inactivity={inactivity} мин\n\n{cfg}",
    "employee_added_short": "✅ Сотрудник добавлен: {full_name} ({role})",
    "checkin_time_updated": "✅ Время чек-ина обновлено: {value}",
    "eod_time_updated": "✅ Время EOD обновлено: {value}",
    "report_time_updated": "✅ Время отчёта обновлено: {value}",
    "logs_tail_title": "📄 <b>Последние 50 строк лога</b>\n\n<pre>{tail}</pre>",
    "removed_employee": "🗑 Сотрудник удалён: <code>{uid}</code>",
    "schedule_anchor_prompt": "Введите дату старта цикла 2/2 в формате YYYY-MM-DD",
    "employee_id_prompt_role": "🆔 Введите user_id сотрудника для роли <b>{role}</b>.\nПользователь может узнать ID командой /myid",
    "employee_name_prompt_auto": "🪪 Введите имя сотрудника (или '+' чтобы оставить <b>{full_name}</b>)",
    "employee_name_prompt": "🪪 Введите имя сотрудника (как показывать в отчётах)",
    "employee_username_prompt_auto": "📛 Введите имя пользователя (или '+' чтобы оставить @{username}, '-' если нет)",
    "employee_username_prompt": "📛 Введите имя пользователя в формате @username (или '-' если нет)",
    "employee_added_full": "✅ Сотрудник добавлен: {full_name}{username_part}, роль={role}",
    "employee_list_updated": "👥 Обновлённый список сотрудников",
    "schedule_bad_date": "Неверный формат даты. Используйте YYYY-MM-DD",
    "schedule_anchor_set": "✅ Дата старта цикла для {uid}: {date}",
    "inactivity_updated": "✅ INACTIVITY_MINUTES={value}",
    "work_chats_saved": "✅ WORK_CHAT_IDS сохранены ({count} чатов)",
    "setting_saved": "✅ {key}={value}",
    "shipment_saved": "📦 Отправка сохранена: {client}, статус={status}",
    "remove_employee_btn": "🗑 {full_name} ({uid})",
    "back_to_employees": "⬅️ Назад к сотрудникам",
    "schedule_employee_btn": "📅 {full_name} ({uid})",
    "sched_mode_week": "🗓 Режим: по дням недели",
    "sched_mode_22": "🔁 Режим: 2/2",
    "sched_set_anchor": "📌 Указать старт цикла 2/2",
    "sched_back_pick": "⬅️ Назад к выбору сотрудника",
    "schedule_not_found": "⚠️ Сотрудник не найден",
    "schedule_today_work": "✅ Сегодня рабочий",
    "schedule_today_off": "⚪ Сегодня выходной",
    "schedule_mode_weekdays": "По дням недели",
    "schedule_mode_cycle": "Сменный 2/2",
    "schedule_card": "<b>📅 График: {full_name}</b>\nID: <code>{uid}</code>\nРежим: <b>{mode}</b>\nСтарт цикла 2/2: <code>{anchor}</code>\n{today}\n\nДни недели:\n{days}\n\nℹ️ Для 2/2 выберите режим и задайте старт цикла.",
    "runtime_overview_title": "📌 <b>Текущая runtime-конфигурация</b>",
    "runtime_overview_line": "{icon} {key}: <code>{value}</code>",
    "employees_title": "<b>👥 Сотрудники</b>",
    "employees_empty_username": "без имени пользователя",
    "employees_line": "• <b>{full_name}</b> ({role}) — {username}, id=<code>{uid}</code>",
    "employees_empty": "⚪ Список пуст",
    "log_absent": "Лог-файл пока пуст или не создан.",
    "log_empty": "Лог-файл пуст.",
    "employee_fallback_name": "Сотрудник {uid}",
    "source_db": "из БД",
    "source_default": "значение по умолчанию",
})


VARIABLE_TEXT_META = {
    "admin_chat_id": ("👑 ADMIN_CHAT_ID", "Чат для админ-алертов и системных отчётов.", "Введите ADMIN_CHAT_ID (например -1001234567890). Подсказка: /chatinfo"),
    "general_chat_id": ("💬 GENERAL_CHAT_ID", "Общий чат для check-in/EOD напоминаний.", "Введите GENERAL_CHAT_ID (например -1001234567890). Подсказка: /chatinfo"),
    "sales_chat_id": ("💰 SALES_CHAT_ID", "Чат отдела продаж для команды /sale.", "Введите SALES_CHAT_ID. Подсказка: /chatinfo"),
    "logistics_chat_id": ("📦 LOGISTICS_CHAT_ID", "Чат логистики для команды /shipment.", "Введите LOGISTICS_CHAT_ID. Подсказка: /chatinfo"),
    "work_chat_ids": ("🧩 WORK_CHAT_IDS", "Список рабочих чатов, где учитывается активность и проверяется тишина.", "Введите WORK_CHAT_IDS через запятую. Пример: -1001111111111,-1002222222222"),
    "report_time": ("📊 REPORT_TIME", "Время отправки дневного отчёта в админ-чат.", "Введите REPORT_TIME (HH:MM)"),
    "checkin_time": ("🌅 CHECKIN_TIME", "Время публикации check-in кнопки в общий чат.", "Введите CHECKIN_TIME (HH:MM)"),
    "eod_time": ("🌆 EOD_TIME", "Время публикации напоминания о вечернем отчёте.", "Введите EOD_TIME (HH:MM)"),
    "work_start": ("🟢 WORK_START", "Начало рабочего окна для проверки неактивности.", "Введите WORK_START (HH:MM)"),
    "work_end": ("🔴 WORK_END", "Конец рабочего окна для проверки неактивности.", "Введите WORK_END (HH:MM)"),
    "inactivity_minutes": ("⏱ INACTIVITY_MINUTES", "Через сколько минут тишины бот отправляет алерт о неактивности.", "Введите INACTIVITY_MINUTES (например 60)"),
}

HANDLER_TEXTS.update({
    "myid_hint": "Передайте этот ID администратору, если нужно добавить вас вручную.",
    "whoami_hint": "Если from_user.id не совпадает с OWNER_IDS, команды администратора будут игнорироваться.\nЕсли вы админ с анонимным режимом, выключите Anonymous Admin и повторите.",
    "schedule_card": "<b>📅 График: {full_name}</b>\nID: <code>{uid}</code>\nРежим: <b>{mode}</b>\nСтарт цикла 2/2: <code>{anchor}</code>\n{today}\n\nДни недели:\n{days}\n\nℹ️ Для 2/2 выберите режим и задайте старт цикла.",
})

SCHEDULER_TEXTS.update({
    "checkin_button": "✅ На связи",
})

REPORT_TEXTS.update({
    "weekly_line": "{role} • {full_name}: всего={total}, в среднем/день={avg}, дней без активности={silent_days}",
})

WEEKDAY_LABELS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


REPORT_TEXTS.update({
    "daily_subtitle": "Активность сотрудников за день:",
    "daily_line_active": "{role} • {full_name}: {count} сообщений ({first}–{last})",
    "daily_line_zero": "{role} • {full_name}: 0 сообщений",
    "daily_total_title": "Итого по отделам:",
    "daily_total_line": "- {role}: {count}",
    "weekly_subtitle": "Сводка за 7 дней:",
    "kpi_sales_line": "- {full_name}: сделок={deals}, сумма={amount:.2f} AED",
    "kpi_logistics_line": "- {full_name}: отправок={shipments}, задержек={delayed}",
})
