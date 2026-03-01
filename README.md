# 🤖 EASY WAY Bot (A + B + C)

Telegram-бот для рабочих чатов команды: учёт активности, check-in/EOD, Sales/Logistics события, отчёты и контроль неактивности.

---

## 📌 Что умеет бот

### 🗂 Week 1 — учёт активности

Бот считает активность **по сотрудникам** в рабочих чатах:
- 💬 количество сообщений за день;
- 🕘 время первой активности;
- 🌙 время последней активности.

⚠️ Тексты сообщений **не хранятся** — только метаданные активности.

Отчёты:
- 📊 ежедневный (daily) в Admin-чат;
- 🗓 еженедельный (weekly) в Admin-чат.

---

### ✅ Week 2 — check-in и EOD

#### 🌅 Утренний check-in
- В `CHECKIN_TIME` бот отправляет в общий чат кнопку `✅ На связи`.
- Кнопка содержит дневной токен (`checkin:YYYY-MM-DD`):
  - старые кнопки не принимаются;
  - повторная отметка тем же пользователем не создаёт дублей.
- Есть fallback-команда `/checkin` (если кнопку неудобно нажимать).

#### 🌆 Вечерний отчёт (EOD)
- В `EOD_TIME` бот отправляет напоминание с кнопкой перехода в ЛС бота.
- Если в группе выполнить `/eod`, бот даст кнопку перехода в личный чат.
- В личном чате запускается форма в 4 шага (команда `/eod` или deep-link `/start eod`):
  1. Сделано сегодня
  2. В работе
  3. Проблемы
  4. Нужна помощь
- Через 1 час в Admin-чат уходит список, кто не сдал EOD.

---

### 💼 Week 3 — Sales / Logistics события

#### 💰 Sales
Команда в Sales-чате: `/sale`

Форма:
- Клиент
- Сумма
- Статус (`lead` / `invoice` / `paid`)
- Комментарий

После сохранения бот публикует лог вида:
`#sale @username 20000.00aed paid`

#### 📦 Logistics
Команда в Logistics-чате: `/shipment`

Форма:
- Номер клиента
- Статус (`created` / `shipped` / `delivered` / `delayed`)
- Причина (если `delayed`)

После сохранения бот публикует лог отправки.

---

### ⏱ Week 4 — контроль неактивности

Периодическая проверка каждые 10 минут:
- в рабочем диапазоне (`WORK_START`..`WORK_END`);
- только для сотрудников, сделавших check-in;
- роль `finance` исключается;
- если нет активности дольше `INACTIVITY_MINUTES`, бот шлёт алерт в Admin-чат;
- лимит: не более 2 алертов в день на сотрудника.

---

## 👮 Owner-команды

> Работают только для `OWNER_IDS`.

- `/status` — статус бота и runtime-настройки.
- `/report today` — daily отчёт вручную.
- `/week` — weekly отчёт + KPI вручную.
- `/checkin` — ручной check-in сотрудника.
- `/myid` — сотрудник получает свой user_id для передачи админу.
- `/chatinfo` — показать ID и тип текущего чата.
- `/add_employee role=sales|logistics|finance|general` — добавить/обновить сотрудника:
  - owner должен **ответить (reply)** на сообщение сотрудника этой командой.
- `/set_checkin_time HH:MM` — сохранить время check-in в БД.
- `/set_eod_time HH:MM` — сохранить время EOD в БД.
- `/set_report_time HH:MM` — сохранить время автоотчётов в БД.
- `/export csv` — выгрузка активности за текущий день.
- `/admin` — полноценная админ-панель на русском (инструкции + кнопки тестов + логи).
- `/admin_test` — алиас для совместимости (открывает то же меню).

---

## 🧪 Временное админ-меню для тестов

Команда: `/admin` (или `/admin_test`)

Открывает интерактивные подменю:
- 🧪 Тесты сценариев (check-in/eod/reports/inactivity)
- ⚙️ Меню переменных (ввод ID чатов, WORK_CHAT_IDS, времени)
- 👥 Меню сотрудников (добавление по user_id и роли)
- 📄 Логи (tail + скачать файл)
- ⬅️ Кнопки «Назад» для удобной навигации

Это удобно, чтобы быстро проверить весь функционал в реальных чатах.

---

## 🧼 Режим “чистого чата”

Чтобы не засорять рабочие чаты:
- бот старается удалять служебные командные сообщения;
- короткие технические ответы (например usage/ошибки ввода) отправляются временно и авто-удаляются.

> ⚠️ Для удаления сообщений боту нужны права администратора в группе (`Delete messages`).

---

## 📜 Логирование

Бот ведёт полноценные логи:
- 🖥 в stdout (удобно для `journalctl`)
- 📁 в файл `logs/bot.log` (ротация 2MB x 5 файлов)

Через `/admin` можно:
- посмотреть последние 50 строк
- скачать файл логов в Telegram

---

## 🧱 Технический стек

- 🐍 Python 3.10+
- 🤖 aiogram 3.x
- ⏰ APScheduler
- 🗃 SQLite (по умолчанию)
- 🌍 timezone: `Asia/Dubai`

---

## 📁 Структура проекта

```text
bot/
  __init__.py
  config.py       # env-конфигурация, валидация
  db.py           # SQLite схема и операции
  handlers.py     # команды, FSM, admin test menu
  reports.py      # сборка текстов отчётов
  scheduler.py    # периодические задания
  main.py         # точка входа
.env.example
requirements.txt
README.md
```

---

## ⚙️ Переменные окружения (.env)

Скопируйте шаблон:

```bash
cp .env.example .env
```

Минимально обязательные:
- `BOT_TOKEN`
- `OWNER_IDS`
- ✅ owner из `OWNER_IDS` добавляется автоматически как сотрудник `general` (даже при пустом `EMPLOYEES_JSON`)

Остальные настройки теперь можно задать из меню `/admin` (кнопками), поэтому в `.env` их держать не обязательно.

Опционально можно оставить bootstrap-значения:
- `ADMIN_CHAT_ID`, `GENERAL_CHAT_ID`, `SALES_CHAT_ID`, `LOGISTICS_CHAT_ID`
- `WORK_CHAT_IDS`
- `REPORT_TIME`, `CHECKIN_TIME`, `EOD_TIME`
- `WORK_START`, `WORK_END`, `INACTIVITY_MINUTES`
- `EMPLOYEES_JSON`
- `TIMEZONE=Asia/Dubai`

Пример `EMPLOYEES_JSON`:

```json
[
  {"user_id": 111111111, "username": "sales_1", "full_name": "Sales One", "role": "sales"},
  {"user_id": 222222222, "username": "sales_2", "full_name": "Sales Two", "role": "sales"},
  {"user_id": 333333333, "username": "log_1", "full_name": "Logistics One", "role": "logistics"},
  {"user_id": 444444444, "username": "log_2", "full_name": "Logistics Two", "role": "logistics"},
  {"user_id": 555555555, "username": "log_3", "full_name": "Logistics Three", "role": "logistics"},
  {"user_id": 666666666, "username": "fin_1", "full_name": "Finance One", "role": "finance"}
]
```

---

## 🚀 Установка с нуля на сервер (Ubuntu)

### 1) Установить системные пакеты

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip tzdata
```

### 2) Клонировать репозиторий

```bash
cd /opt
git clone https://github.com/middtho-dev/bot_a-b.git
cd /opt/bot_a-b
```

### 3) Создать virtualenv и установить зависимости

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4) Настроить `.env`

```bash
cp .env.example .env
nano .env
```

### 5) Запустить бота вручную

```bash
source .venv/bin/activate
python -m bot.main
```

---

## 🛠 Запуск как systemd service (рекомендуется)

Создайте файл:
`/etc/systemd/system/easyway-bot.service`

```ini
[Unit]
Description=EasyWay Telegram Bot
After=network.target

[Service]
User=root
WorkingDirectory=/opt/bot_a-b
EnvironmentFile=/opt/bot_a-b/.env
ExecStart=/opt/bot_a-b/.venv/bin/python -m bot.main
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Применить:

```bash
sudo systemctl daemon-reload
sudo systemctl enable easyway-bot
sudo systemctl start easyway-bot
sudo systemctl status easyway-bot --no-pager
```

Логи:

```bash
sudo journalctl -u easyway-bot -f
```

---

## 🔄 Как обновляться с GitHub

```bash
cd /opt/bot_a-b
source .venv/bin/activate
git fetch --all
git checkout main
git pull --ff-only origin main
pip install -r requirements.txt
sudo systemctl restart easyway-bot
sudo systemctl status easyway-bot --no-pager
```

---

## ✅ Быстрый чек после запуска

1. От owner отправить `/status`.
2. Запустить `/admin` (или `/admin_test`).
3. Нажать по очереди:
   - Check-in prompt
   - Check-in missing
   - EOD prompt
   - EOD missing
   - Daily report
   - Weekly report + KPI
4. Проверить, что сообщения приходят в нужные чаты.
5. Проверить `/export csv`.

---

## 🧯 Troubleshooting

### ❗ `ZoneInfoNotFoundError`
Проверьте timezone:
- в `.env` должно быть `TIMEZONE=Asia/Dubai`
- установлен `tzdata`

### ❗ `python: command not found`
Используйте `python3` для создания venv:

```bash
python3 -m venv .venv
```

### ❗ `fatal: not a git repository`
Вы не в папке репозитория. Перейдите:

```bash
cd /opt/bot_a-b
```

### ❗ Бот не удаляет сообщения
Проверьте права бота в группе:
- admin права
- разрешение `Delete messages`

---

## 🔐 Безопасность

- Никогда не публикуйте реальный `BOT_TOKEN`.
- Если токен утёк — срочно перевыпустите в BotFather.
- Не коммитьте `.env` (он уже в `.gitignore`).

---

## 🗺 Рекомендованный порядок внедрения

1. ✅ Сначала Week 1 (активность + отчёты)
2. ✅ Потом Week 2 (check-in + EOD)
3. ✅ Затем Week 3 (sale/shipment)
4. ✅ После — Week 4 (inactivity alerts)
5. 🧪 На каждом шаге прогонять `/admin`

---

## 🙌 Полезно знать

- Команды `set_*` записываются в БД как runtime-переопределения.
- На старте бот подгружает сотрудников из БД (добавленных через `/add_employee`).
- Для максимально чистого UX используйте команды и формы в профильных чатах (sales/logistics/general).

Удачного запуска! 🚀
