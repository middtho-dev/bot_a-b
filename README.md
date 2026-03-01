# EASY WAY Bot A + B + C

Полная базовая реализация по этапам из ТЗ в одном контейнерном проекте.

## Что сделано

### Week 1 — учёт активности
- Учёт сообщений по сотрудникам во всех рабочих чатах (`WORK_CHAT_IDS`).
- Считаются: количество сообщений, первая и последняя активность за день.
- Текст сообщений не хранится.
- Авто daily/weekly отчёты в Admin-чат.

### Week 2 — чек-ин и вечерний отчёт
- В `CHECKIN_TIME` бот отправляет в общий чат кнопку `✅ На связи` с дневным токеном (устаревшие кнопки не принимаются).
- Через 30 минут в Admin приходит список не отметившихся. Есть fallback-команда `/checkin` для ручной отметки.
- В `EOD_TIME` бот публикует напоминание о вечернем отчёте (`/eod`).
- EOD-форма: Сделано сегодня / В работе / Проблемы / Нужна помощь.
- Через 1 час в Admin приходит список, кто не сдал EOD.

### Week 3 — события Sales и Logistics
- В Sales-чате команда `/sale` (роль `sales`):
  - Клиент, Сумма, Статус, Комментарий
  - Публикация лога: `#sale @username amountaed status`
- В Logistics-чате команда `/shipment` (роль `logistics`):
  - Номер клиента, Статус, Причина задержки (если delayed)
  - Публикация лога отправки.

### Week 4 — контроль неактивности (Block C)
- Проверка каждые 10 минут в рабочем интервале `WORK_START`..`WORK_END`.
- Условия алерта:
  - сотрудник сделал check-in;
  - не Finance;
  - нет активности более `INACTIVITY_MINUTES`.
- Ограничение: не более 2 алертов в день на одного сотрудника.

## Owner-команды
- `/status`
- `/report today`
- `/week`
- `/set_checkin_time 10:00`
- `/set_eod_time 22:00`
- `/set_report_time 19:00`
- `/add_employee role=sales` (реально работает: ответьте этой командой на сообщение сотрудника)
- `/export csv`

> Временные настройки через `/set_*` пишутся в БД и учитываются после перезапуска бота.

## Быстрый запуск в контейнере

```bash
# в .env используйте TIMEZONE=Asia/Dubai
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
# заполните .env
python -m bot.main
```

## Как обновляться из репо

```bash
cd /opt/easyway-bot
source .venv/bin/activate
git fetch --all
git checkout main
git pull --ff-only origin main
pip install -r requirements.txt
sudo systemctl restart easyway-bot
sudo systemctl status easyway-bot --no-pager
```

## Структура

```text
bot/
  config.py
  db.py
  handlers.py
  reports.py
  scheduler.py
  main.py
```


## Troubleshooting (Ubuntu 24+/Python 3.12)

Если при запуске видите ошибку `ZoneInfoNotFoundError: No time zone found with key Asia/Dubai`, установите timezone data:

```bash
# вариант 1: системно
sudo apt update && sudo apt install -y tzdata

# вариант 2: в virtualenv
source .venv/bin/activate
pip install tzdata
```

Если нет команды `python`, используйте `python3` для создания venv.

## Как обновиться с GitHub на сервере

```bash
cd /opt/bot_a-b
source .venv/bin/activate
git fetch --all
git checkout main
git pull --ff-only origin main
pip install -r requirements.txt
# если используете systemd
sudo systemctl restart easyway-bot
sudo systemctl status easyway-bot --no-pager
```
