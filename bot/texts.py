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
