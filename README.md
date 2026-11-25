# Flowboard

Flowboard — local-first канбан-доска для личной работы и командного планирования. Приложение работает автономно в браузере, а при подключении FastAPI получает аккаунты, рабочие пространства, совместное редактирование, PostgreSQL, уведомления и серверные резервные копии.

Интерфейс выполнен в необруталистичном стиле и не зависит от frontend-фреймворков: используется нативный JavaScript, DOM API и CSS.

## Основные возможности

### Задачи и планирование

- несколько досок и настраиваемые колонки;
- Drag and Drop, мобильные жесты и пакетные операции;
- чек-листы, теги, приоритеты, исполнители и зависимости;
- дедлайны, повторяющиеся задачи, календарь и архив;
- цели, контрольные точки и дорожная карта;
- шаблоны, пользовательские поля, цвета и обложки;
- оценка времени, таймер и Pomodoro;
- импорт из Trello, Jira и Notion.

### Поиск, аналитика и автоматизации

- фильтры и расширенные поисковые запросы;
- статистика, отчёты по потоку и загрузке команды;
- настраиваемый дашборд;
- конструктор автоматических правил;
- командная палитра `⌘/Ctrl + K`;
- встроенный помощник для сводок, чек-листов и приоритизации.

### Командная работа

- аккаунты, приглашения и роли;
- изолированные рабочие пространства и права на доски;
- комментарии, ответы, реакции, упоминания и наблюдатели;
- realtime-присутствие и совместные черновики;
- журнал операций и аудит действий;
- публичные представления и формы сбора задач;
- интеграции, GitHub webhooks и календарь iCalendar.

### Надёжность и безопасность

- local-first хранение и офлайн-кэш PWA;
- очередь несинхронизированных изменений;
- интерфейс разрешения конфликтов синхронизации;
- серверные резервные копии и восстановление;
- история версий вложений;
- JWT, API-токены и активные сессии;
- TOTP/2FA, Passkeys и подтверждение email;
- OAuth через Google, GitHub и Microsoft;
- SQLite для локальной разработки и PostgreSQL для серверного режима.

## Интерфейс

Доступны семь тем: Classic, Dark, Sunset, Cyberpunk, Newspaper, Blueprint и Candy.

Поддерживаемые языки:

- русский;
- английский;
- игбо;
- узбекский;
- украинский;
- иврит;
- идиш.

Для иврита и идиша автоматически включается направление RTL. Также предусмотрены высокий контраст, изменение размера текста и уменьшение анимаций.

## Архитектура

```text
Browser UI
  ├── localStorage + Service Worker     локальная работа и офлайн-режим
  └── REST + WebSocket
        └── FastAPI
              ├── SQLite / PostgreSQL
              ├── фоновые задания и уведомления
              └── файловое хранилище
```

Frontend можно использовать без backend. После подключения API локальные изменения синхронизируются с выбранным рабочим пространством. При недоступном сервере они остаются в браузере и отправляются позже.

## Быстрый запуск frontend

Требуется Python 3 или любой другой статический HTTP-сервер.

```bash
python3 -m http.server 4173
```

Откройте [http://localhost:4173](http://localhost:4173).

Приложение сразу готово к работе: данные будут храниться в `localStorage`. Запуск FastAPI для этого режима не требуется.

## Запуск полного стека

### 1. Frontend

```bash
python3 -m http.server 4173
```

### 2. FastAPI

Требуются Python 3.11+ и [uv](https://docs.astral.sh/uv/).

```bash
cd backend
uv sync --dev
uv run fastapi dev app/main.py
```

После запуска доступны:

- API: [http://127.0.0.1:8000/api/v1](http://127.0.0.1:8000/api/v1);
- Swagger UI: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs);
- OpenAPI: [http://127.0.0.1:8000/openapi.json](http://127.0.0.1:8000/openapi.json).

### 3. Подключение интерфейса к API

В Flowboard откройте «Аккаунт», укажите адрес:

```text
http://127.0.0.1:8000/api/v1
```

После этого зарегистрируйте аккаунт или войдите. Адрес API сохраняется только в текущем браузере.

## Переменные окружения backend

Скопируйте пример конфигурации и измените нужные значения:

```bash
cd backend
cp .env.example .env
```

| Переменная | Назначение |
| --- | --- |
| `DATABASE_URL` | Подключение PostgreSQL. Если не задано, используется SQLite |
| `FLOWBOARD_DATABASE_PATH` | Путь к локальной базе SQLite |
| `FLOWBOARD_AUTH_SECRET` | Секрет подписи токенов; в production должен быть длинным и случайным |
| `FLOWBOARD_AUTH_REQUIRED` | Требовать авторизацию для API |
| `FLOWBOARD_CORS_ORIGINS` | Разрешённые адреса frontend |
| `FLOWBOARD_PUBLIC_APP_URL` | Публичный адрес интерфейса |
| `FLOWBOARD_API_PUBLIC_URL` | Публичный адрес API, используемый OAuth callback |
| `FLOWBOARD_OBJECT_STORAGE_PATH` | Каталог внешнего хранения вложений |
| `FLOWBOARD_SMTP_*` | Отправка писем и подтверждений |
| `FLOWBOARD_WEBAUTHN_*` | Настройка Passkeys |
| `FLOWBOARD_VAPID_*` | Web Push уведомления |
| `FLOWBOARD_GOOGLE_CLIENT_*` | OAuth Google |
| `FLOWBOARD_GITHUB_CLIENT_*` | OAuth GitHub |
| `FLOWBOARD_MICROSOFT_CLIENT_*` | OAuth Microsoft |

Базовый пример конфигурации находится в [`backend/.env.example`](backend/.env.example); дополнительные параметры описаны в [`backend/README.md`](backend/README.md).

### OAuth callback

Для каждого провайдера зарегистрируйте callback следующего вида:

```text
<FLOWBOARD_API_PUBLIC_URL>/auth/oauth/<provider>/callback
```

Примеры значений `<provider>`: `google`, `github`, `microsoft`. OAuth использует Authorization Code с PKCE; секреты провайдеров не передаются в браузер.

## PostgreSQL и Docker

Готовая конфигурация PostgreSQL находится в `backend/compose.yaml`.

```bash
cd backend
export FLOWBOARD_AUTH_SECRET="replace-with-a-long-random-secret"
export POSTGRES_PASSWORD="replace-with-a-strong-database-password"
docker compose up --build
```

Для подключения внешней базы задайте `DATABASE_URL`. Инструкции по переносу SQLite и резервному копированию PostgreSQL находятся в [`backend/README.md`](backend/README.md).

## Расширенный поиск

Операторы можно комбинировать с обычным текстом:

```text
status:progress priority:high tag:release
assignee:me due:overdue
due:this-week дизайн
board:default status:todo
```

Поддерживаются:

| Оператор | Пример |
| --- | --- |
| `status:` | `status:todo`, `status:progress`, `status:done` |
| `priority:` | `priority:low`, `priority:medium`, `priority:high` |
| `tag:` | `tag:design` |
| `assignee:` | `assignee:me` или имя исполнителя |
| `board:` | `board:default` |
| `due:` | `due:today`, `due:this-week`, `due:overdue` |

## Автотесты

Установите frontend-зависимости:

```bash
npm ci
```

Unit-тесты JavaScript:

```bash
npm test
```

Браузерные тесты Playwright:

```bash
npm run test:e2e
```

Тесты FastAPI:

```bash
cd backend
uv sync --dev
uv run pytest
```

Другие команды:

```bash
npm run test:watch
npm run test:coverage
npm run test:all
```

Текущий набор включает unit-, API- и E2E-проверки задач, синхронизации, импорта, автоматизаций, локализации, аккаунтов, резервных копий и версий вложений.

## Структура проекта

```text
.
├── assets/             иконки и изображения
├── backend/
│   ├── app/            FastAPI, модели, БД и сервисы
│   ├── scripts/        миграции и резервное копирование
│   └── tests/          backend-тесты
├── css/                дизайн-система и адаптивные стили
├── dist/               подготовленная статическая версия
├── js/
│   ├── api.js          API, realtime и синхронизация
│   ├── automations.js  автоматические правила
│   ├── importers.js    импорт Trello, Jira и Notion
│   ├── i18n.js         локализация
│   ├── main.js         состояние интерфейса и события
│   └── ...
├── tests/              unit-тесты JavaScript
├── tests-e2e/          сценарии Playwright
├── index.html          основной интерфейс
├── manifest.webmanifest
└── service-worker.js   PWA и офлайн-кэш
```

## Дополнительная документация

- [`backend/README.md`](backend/README.md) — маршруты API, авторизация, PostgreSQL, Docker и резервные копии;
- [`backend/.env.example`](backend/.env.example) — пример переменных окружения;
- Swagger UI — интерактивное описание API после локального запуска backend.

## Развёртывание

Репозиторий содержит frontend и backend, но команды из этого README выполняют только локальный запуск и тестирование. Автоматический деплой не выполняется.
