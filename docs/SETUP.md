# Установка и разработка

## Требования

- [Docker](https://docs.docker.com/get-docker/) + Docker Compose v2
- Для локальной разработки (без Docker): [uv](https://docs.astral.sh/uv/) и Python 3.12

## Запуск всего стека (одна команда)

```bash
cp .env.example .env     # затем поправьте значения-заглушки
docker compose up -d --build
```

Откройте <http://localhost:8080>. Остановить — `docker compose down` (с флагом
`-v` ещё и удалит том базы данных).

Пользователь-админ создаётся автоматически при первом старте из `ADMIN_USERNAME` /
`ADMIN_PASSWORD`.

## Переменные окружения

Все сервисы читают один общий `.env` (через `env_file` в `docker-compose.yml`).
Каждый сервис игнорирует переменные, которые ему не нужны.

| Переменная | Кто использует | Назначение |
|---|---|---|
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | все | Доступ к БД |
| `POSTGRES_HOST` / `POSTGRES_PORT` | все | Адрес БД (`postgres:5432`) |
| `REDIS_HOST` / `REDIS_PORT` / `REDIS_PASSWORD` | redirect, admin | Подключение к Redis |
| `CACHE_TTL_SECONDS` | redirect | Максимальное время жизни горячей ссылки в кэше |
| `SHORT_CODE_LENGTH` | redirect | Длина кода (6–8) |
| `DEFAULT_LINK_TTL_DAYS` | redirect | Срок жизни ссылки по умолчанию (0 = бессрочно) |
| `BASE_URL` | redirect, admin | Публичный URL для коротких ссылок / QR |
| `REDIRECT_SERVICE_URL` / `STATS_SERVICE_URL` | admin, redirect | Внутренние адреса сервисов |
| `INTERNAL_API_TOKEN` | admin, redirect, stats | Общий секрет для управляющих/разрушающих вызовов |
| `STATS_DEFAULT_DAYS` / `TOP_LINKS_LIMIT` | stats | Параметры агрегации по умолчанию |
| `JWT_SECRET` / `JWT_ALGORITHM` / `JWT_EXPIRE_MINUTES` | admin | Подпись токенов |
| `COOKIE_NAME` / `COOKIE_SECURE` | admin | Cookie сессии (`COOKIE_SECURE=true` за HTTPS) |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | admin | Первый пользователь-админ |

Полный шаблон с комментариями — в [`.env.example`](../.env.example).

> `DOCS_PREFIX` (для Swagger за шлюзом) задаётся **по сервису** в
> `docker-compose.yml` (а не в общем `.env`): `/api/redirect` и `/api/stats`.

## Локальная разработка (по сервисам)

Каждый сервис — независимый uv-проект.

```bash
cd redirect-service          # или stats-service / admin-panel
uv sync                      # создать venv + установить зависимости (с dev)
uv run pytest                # тесты
uvx ruff@0.8.4 check app     # линт
uvx ruff@0.8.4 format app    # форматирование
uv run --with mypy mypy --config-file ../pyproject.toml app   # типизация
```

Конфигурация `ruff` и `mypy` — общая, в корне ([`pyproject.toml`](../pyproject.toml)).

### pre-commit (необязательно)

```bash
pip install pre-commit
pre-commit install           # ruff + проверка секретов перед коммитом
```

## Миграции БД (Alembic)

Миграции применяются автоматически при старте контейнера (entrypoint выполняет
`alembic upgrade head` перед запуском сервера). Создать новую миграцию при
разработке:

```bash
cd redirect-service
uv run alembic revision -m "describe change"   # отредактируйте сгенерированный файл
uv run alembic upgrade head
```

У каждого сервиса своя история миграций и своя таблица версий
(`alembic_version_{service}`), поэтому они спокойно живут в общей БД. Таблица
`system_logs` создаётся идемпотентно при старте каждого сервиса.

## Замечания по админке / Tailwind

CSS админки собирается из `static/src/input.css` в `static/css/output.css`. В
Docker это делается в отдельном слое-сборщике. Пересобрать локально (нужен
автономный бинарник Tailwind CLI):

```bash
cd admin-panel
./tailwindcss -i static/src/input.css -o static/css/output.css --minify
```

(`htmx` и `Chart.js` лежат локально в `static/js/` — без CDN и без npm.)
