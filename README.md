# EASY WAY Bot

Рабочий Telegram-бот для команды: активность по чатам, чек-ин, EOD, события продаж/логистики, отчёты и алерты по неактивности.

Если коротко: бот снимает рутину с ежедневных «кто на связи», «кто сдал отчёт», «кто пропал» и собирает это в понятные отчёты.

---

## Что умеет

### 1) Активность по рабочим чатам
- считает количество сообщений сотрудника за день;
- хранит первую и последнюю активность;
- отправляет дневной и недельный отчёты.

> Тексты сообщений не сохраняются — только метаданные активности.

### 2) Чек-ин и EOD
- утром отправляет кнопку чек-ина в общий чат;
- есть ручная команда `/checkin`;
- вечером присылает напоминание про EOD;
- EOD заполняется в личке с ботом (4 вопроса);
- через час после дедлайна отправляет список, кто не сдал EOD.

### 3) Sales / Logistics
- `/sale` — форма для отдела продаж;
- `/shipment` — форма для логистики;
- в недельном отчёте есть KPI-блок (сделки/суммы/отгрузки/задержки).

### 4) Контроль неактивности
- проверка каждые 10 минут в рабочем диапазоне времени;
- исключается роль `finance`;
- максимум 2 алерта в день на сотрудника;
- учитывается персональный график сотрудника (по дням недели или 2/2).

---

## Команды

### Базовые
- `/myid` — показать ваш `user_id`;
- `/chatinfo` — показать id и тип текущего чата.

### Для сотрудников
- `/checkin`
- `/eod`
- `/sale` (только sales + чат продаж)
- `/shipment` (только logistics + чат логистики)

### Для owner
- `/status`
- `/report today`
- `/week`
- `/add_employee role=sales|logistics|finance|general`
- `/set_checkin_time HH:MM`
- `/set_eod_time HH:MM`
- `/set_report_time HH:MM`
- `/export_csv`
- `/export csv` (старый формат, оставлен для совместимости)
- `/admin`
- `/admin_test` (алиас)

---

## Админ-меню (`/admin`)

Через меню можно управлять ботом без правок `.env`:

- отправить тестовые check-in / EOD / отчёты / проверку неактивности;
- настроить рабочие чаты и время задач;
- добавить сотрудника;
- удалить сотрудника (owner удалить нельзя);
- настроить график сотрудника:
  - по дням недели (кнопки с отметками ⚪/✅),
  - или режим 2/2 с датой старта;
- посмотреть хвост логов и скачать лог-файл.

---

## Быстрый запуск на сервере (Ubuntu)

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip tzdata

cd /opt
git clone https://github.com/middtho-dev/bot_a-b.git
cd /opt/bot_a-b

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt

cp .env.example .env
nano .env

python -m bot.main
```

Минимум в `.env`:

```env
BOT_TOKEN=...
OWNER_IDS=123456789
TIMEZONE=Asia/Dubai
DATABASE_PATH=bot_data.sqlite3
EMPLOYEES_JSON=[]
```

Остальное можно докрутить из `/admin`.

---

## Автозапуск (вариант 1: systemd)

В репозитории есть шаблон:

- `deploy/systemd/easyway-bot.service`

Установка:

```bash
sudo cp deploy/systemd/easyway-bot.service /etc/systemd/system/easyway-bot.service
sudo systemctl daemon-reload
sudo systemctl enable easyway-bot
sudo systemctl start easyway-bot
```

Проверка:

```bash
sudo systemctl status easyway-bot
journalctl -u easyway-bot -f
```

Если у вас другой путь проекта — поправьте `WorkingDirectory`, `EnvironmentFile` и `ExecStart` в unit-файле.

---

## Автозапуск (вариант 2: Docker)

Файлы уже добавлены:
- `Dockerfile`
- `docker-compose.yml`

Запуск:

```bash
docker compose up -d --build
```

Проверка:

```bash
docker compose ps
docker compose logs -f
```

Остановка:

```bash
docker compose down
```

В compose стоит `restart: unless-stopped`, поэтому контейнер поднимется после ребута.

---

## Обновление

```bash
cd /opt/bot_a-b
source .venv/bin/activate

git fetch --all
git checkout main
git pull --ff-only origin main
pip install -r requirements.txt

# если systemd
sudo systemctl restart easyway-bot

# если docker
# docker compose up -d --build
```

---

<<<<<<< codex/implement-telegram-bot-for-team-activities-rcw4lm

## Где лежат тексты и кнопки

Чтобы было удобнее поддерживать проект, основные пользовательские тексты и подписи кнопок вынесены в отдельный модуль:

- `bot/texts.py`

Если нужно поменять формулировки в меню, подсказках или help-блоках — обычно достаточно править только этот файл, без поиска строк по всему проекту.

---

=======
>>>>>>> main
## Структура проекта

```text
bot/
  config.py
  db.py
  handlers.py
  reports.py
  scheduler.py
  main.py

deploy/systemd/easyway-bot.service
Dockerfile
docker-compose.yml
.env.example
requirements.txt
README.md
<<<<<<< codex/implement-telegram-bot-for-team-activities-rcw4lm
  texts.py
=======
>>>>>>> main
```

---

## Важные замечания

- Для «чистого чата» боту нужны права удалять сообщения в группе.
- Если owner-команды не срабатывают в группе — проверьте, не включён ли у админа анонимный режим.
- Если бот «молчит» на `/sale` или `/shipment`, обычно причина одна из трёх:
  1) не тот чат,
  2) не та роль сотрудника,
  3) сотрудник не добавлен в систему.
