# EASY WAY Activity Bot (A + B)

Стартовая реализация Telegram-бота для **Недели 1** из ТЗ:
- учёт активности сотрудников в существующих рабочих чатах;
- ежедневный отчёт в Admin-чат;
- еженедельный отчёт по активности.

Проект подготовлен для запуска **в контейнере/VPS** и дальнейшего поэтапного расширения (чек-ины, EOD, sales/logistics формы).

## Что уже реализовано (Week 1)

- Сбор активности без хранения текста сообщений:
  - количество сообщений за день;
  - время первой активности;
  - время последней активности.
- Учёт только по разрешённым рабочим чатам и сотрудникам из конфигурации.
- Автоматическая рассылка:
  - daily report в настраиваемое время (`REPORT_TIME`, по умолчанию `19:00`);
  - weekly report по понедельникам.
- Owner-команды:
  - `/status`
  - `/report today`
  - `/week`
- Хранилище: SQLite (по умолчанию), совместимо с Postgres на следующем этапе.

## Структура

```text
.
├── bot/
│   ├── __init__.py
│   ├── config.py
│   ├── db.py
│   ├── handlers.py
│   ├── reports.py
│   ├── scheduler.py
│   └── main.py
├── .env.example
├── requirements.txt
└── README.md
```

## Быстрый старт в контейнере

1. Установить зависимости:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Скопировать env:

```bash
cp .env.example .env
```

3. Заполнить `.env`:
- `BOT_TOKEN`
- `OWNER_IDS`
- `ADMIN_CHAT_ID`
- `WORK_CHAT_IDS`
- `EMPLOYEES_JSON`

4. Запуск:

```bash
python -m bot.main
```

## Настройка сотрудников и чатов

Пример `EMPLOYEES_JSON`:

```json
[
  {"user_id": 111111111, "username": "sales_one", "full_name": "Sales One", "role": "sales"},
  {"user_id": 222222222, "username": "log_two", "full_name": "Logistics Two", "role": "logistics"}
]
```

Пример `WORK_CHAT_IDS`:

```text
-1001111111111,-1002222222222,-1003333333333
```

## Как обновляться прямо из репозитория (в контейнере/VPS)

### Вариант A: обычный git pull

```bash
cd /opt/easyway-bot   # путь к вашему клону
source .venv/bin/activate
git fetch --all
git checkout main
git pull --ff-only origin main
pip install -r requirements.txt
# при systemd
sudo systemctl restart easyway-bot
sudo systemctl status easyway-bot --no-pager
```

### Вариант B: через отдельную ветку и fast-forward merge

```bash
git fetch --all
git checkout main
git merge --ff-only origin/main
pip install -r requirements.txt
sudo systemctl restart easyway-bot
```

## Рекомендуемый systemd unit

Создайте `/etc/systemd/system/easyway-bot.service`:

```ini
[Unit]
Description=EasyWay Telegram Bot
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/opt/easyway-bot
EnvironmentFile=/opt/easyway-bot/.env
ExecStart=/opt/easyway-bot/.venv/bin/python -m bot.main
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Далее:

```bash
sudo systemctl daemon-reload
sudo systemctl enable easyway-bot
sudo systemctl start easyway-bot
```

## Ограничения текущего этапа

- Блок B (check-in, EOD, Sales form, Shipment form) — пока не реализован, будет в следующих итерациях.
- KPI и контроль неактивности (Block C) — запланированы после базовой стабилизации.

## Roadmap (по ТЗ)

1. Week 1 — activity tracking ✅
2. Week 2 — check-in + evening report
3. Week 3 — sales/shipment events
4. Week 4 — KPI tuning
