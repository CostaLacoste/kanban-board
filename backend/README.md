# Flowboard API

FastAPI-бэкенд для Flowboard. Локально данные могут храниться в SQLite, а для
production поддерживается PostgreSQL через `DATABASE_URL`. API поддерживает
local-first режим, JWT, роли, комментарии и упоминания, realtime-присутствие,
совместные черновики, ревизии, поиск, уведомления, API-токены и webhooks.

## Запуск

```bash
cd backend
uv sync --dev
uv run fastapi dev app/main.py
```

После запуска:

- API: `http://127.0.0.1:8000/api/v1`;
- Swagger UI: `http://127.0.0.1:8000/docs`;
- OpenAPI JSON: `http://127.0.0.1:8000/openapi.json`.

## Основные маршруты

- `GET/POST /api/v1/boards`;
- `PATCH/DELETE /api/v1/boards/{id}`;
- `GET/POST/PATCH /api/v1/tasks`;
- `GET/PATCH/DELETE /api/v1/tasks/{id}`;
- `GET/POST /api/v1/tasks/{id}/comments`;
- `POST /api/v1/tasks/{id}/timer/start|stop`;
- `POST /api/v1/tasks/{id}/attachments`;
- `GET/DELETE /api/v1/attachments/{id}`;
- `GET/PUT /api/v1/automations`;
- `GET/PUT /api/v1/workspace`.
- `POST /api/v1/auth/register|login` и `GET /api/v1/auth/me`;
- `GET/PUT /api/v1/members` и управление API-токенами;
- `GET /api/v1/search/tasks` и `/api/v1/saved-filters`;
- `GET /api/v1/revisions` и восстановление версии;
- `GET /api/v1/notifications`;
- `GET/POST/DELETE /api/v1/webhooks`;
- `WS /api/v1/realtime` — присутствие и совместное редактирование черновика;
- `GET /api/v1/metrics` и `/api/v1/admin/backup`.

## Авторизация и синхронизация

По умолчанию API сохраняет совместимый локальный режим без обязательного входа.
Для защищённого режима задайте `FLOWBOARD_AUTH_REQUIRED=true` и длинный
`FLOWBOARD_AUTH_SECRET`. Изменения рабочего пространства принимают заголовок
`If-Match` с номером ревизии и возвращают `409` при конфликте.

Frontend использует API после явной настройки адреса. Это не позволяет
локальному серверу или тестам случайно подключиться к чужому экземпляру API.
Откройте кнопку «Аккаунт», укажите адрес FastAPI и зарегистрируйтесь или
войдите. Консольный вариант настройки также поддерживается:

```js
localStorage.setItem("flowboard-api-url", "http://127.0.0.1:8000/api/v1");
// Для защищённого режима вставьте accessToken из /auth/register или /auth/login:
localStorage.setItem("flowboard-api-token", "<accessToken>");
location.reload();
```

При недоступном API изменения остаются в `localStorage` и очереди. На
опубликованном домене API также отключён, пока адрес не будет настроен.

## Docker

```bash
cd backend
export FLOWBOARD_AUTH_SECRET="replace-with-a-long-random-secret"
export POSTGRES_PASSWORD="replace-with-a-strong-database-password"
docker compose up --build
```

Compose запускает отдельный PostgreSQL 17 и ожидает его readiness перед
стартом API. Для внешней управляемой базы задайте `DATABASE_URL` напрямую.

## Перенос SQLite в PostgreSQL

Перед переносом создайте резервную копию SQLite и остановите запись в старую
базу. Затем выполните:

```bash
cd backend
export DATABASE_URL="postgresql://user:password@host:5432/flowboard"
uv run python scripts/migrate_sqlite_to_postgres.py data/flowboard.db
```

Скрипт идемпотентно переносит пользователей, доски, задачи, комментарии,
вложения, ревизии, уведомления и настройки.

## Резервные копии

```bash
cd backend
uv run python scripts/backup.py
uv run python scripts/restore.py data/backups/flowboard-YYYYMMDDTHHMMSSZ.db
```

Эти два скрипта предназначены для SQLite. Для PostgreSQL используйте `pg_dump`
и `pg_restore` провайдера базы данных.

## Тесты

```bash
cd backend
uv run pytest
```

Публичное развёртывание этими командами не выполняется; они только запускают
локальную production-подобную конфигурацию.

