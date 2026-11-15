# Flowboard API

Локальный FastAPI-бэкенд для Flowboard. Данные хранятся в SQLite, бинарные
вложения — в отдельной таблице той же базы.

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
- `POST /api/v1/tasks/{id}/timer/start|stop`;
- `POST /api/v1/tasks/{id}/attachments`;
- `GET/DELETE /api/v1/attachments/{id}`;
- `GET/PUT /api/v1/automations`;
- `GET/PUT /api/v1/workspace`.

## Тесты

```bash
cd backend
uv run pytest
```

Бэкенд рассчитан на локальный single-user режим. Перед публичным размещением
следует добавить аутентификацию, авторизацию и внешнее хранилище файлов.

