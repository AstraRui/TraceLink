# Описание API

Каждый сервис на FastAPI отдаёт интерактивный Swagger UI на `/docs` и сырую
схему на `/openapi.json` (через шлюз — под префиксом `/api/<сервис>/`).

Публично через шлюз (`:8080`) доступны только две поверхности: UI админки и
редирект коротких ссылок. Эндпоинты управления ссылками и статистики доступны
лишь во внутренней docker-сети.

Каждый запрос несёт заголовок трассировки `X-Request-ID` (генерируется шлюзом и
возвращается в ответе).

---

## Шлюз (публично, `http://localhost:8080`)

| Метод | Путь | Доступ | Описание |
|---|---|---|---|
| GET | `/` | cookie | Дашборд (редирект на `/login`, если не авторизован) |
| GET | `/login` | – | Форма входа |
| POST | `/login` | – | Аутентификация, установка JWT-cookie, 303 → `/` |
| POST | `/logout` | – | Сброс cookie, 303 → `/login` |
| POST | `/links` | cookie | Создать ссылку (htmx), возвращает карточку |
| GET | `/links/{code}` | cookie | Детальная страница ссылки (статистика по коду) |
| DELETE | `/links/{code}` | cookie | **Каскадное удаление** ссылки и её кликов |
| GET | `/partials/stats.json` | cookie | JSON-статистика для живого поллинга |
| GET | `/partials/health` | cookie | Панель здоровья (htmx, каждые 10 c) |
| GET | `/logs` | cookie | Страница системных логов |
| GET | `/partials/logs` | cookie | Строки логов (фильтры `service`, `level`) |
| GET | `/static/*` | – | Статика админки (CSS/JS) |
| GET | `/{code}` | – | **302** редирект на оригинальный URL |
| GET | `/api/redirect/docs`, `/api/stats/docs` | – | Swagger UI сервисов |

---

## redirect-service (внутренний, `:8000`)

### `POST /api/links`  → `201`
Требует заголовок `X-Internal-Token: <INTERNAL_API_TOKEN>`.

```json
// запрос
{ "original_url": "https://example.com/page", "owner_id": 1,
  "is_private": false, "ttl_days": 30 }

// ответ
{ "id": 1, "short_code": "KyCThZW", "original_url": "https://example.com/page",
  "owner_id": 1, "is_private": false, "created_at": "...", "expires_at": "...",
  "short_url": "http://localhost:8080/KyCThZW" }
```

### `GET /api/links?owner_id=<id>`  → `200`
Требует `X-Internal-Token`. Возвращает список ссылок (с фильтром по владельцу).

### `DELETE /api/links/{code}`  → `204`
Требует `X-Internal-Token`. Удаляет ссылку из БД **и чистит кэш Redis**.
Идемпотентен (204 даже если кода не было).

### `GET /{code}`  → `302`
Публичный. Резолв через Redis → БД (с учётом срока жизни). `404`, если нет или
истёк. Планирует событие клика в stats-service фоновой задачей.

### `GET /health` → `{"status": "ok"}`

---

## stats-service (внутренний, `:8000`)

### `POST /api/events`  → `202`
Лёгкий приём. Разбирает user-agent и сохраняет одну строку клика.

```json
{ "short_code": "KyCThZW", "user_agent": "Mozilla/5.0 ...",
  "referer": "https://...", "ip_hash": "<sha256>", "timestamp": "..." }
```

### `GET /api/stats/summary?short_code=<code>&days=<n>`  → `200`
`short_code` и `days` необязательны (по умолчанию: все ссылки, 30 дней).

```json
{ "short_code": null, "days": 30, "total_clicks": 4,
  "clicks_by_day": [ { "day": "2026-06-29", "clicks": 4 } ],
  "top_links":     [ { "short_code": "KyCThZW", "clicks": 4 } ],
  "devices":       [ { "name": "pc", "clicks": 2 }, { "name": "mobile", "clicks": 1 } ],
  "browsers":      [ { "name": "Chrome", "clicks": 1 } ],
  "operating_systems": [ { "name": "Windows", "clicks": 2 } ] }
```

### `DELETE /api/clicks/{short_code}`  → `204`
Требует `X-Internal-Token`. Удаляет все клики короткого кода (каскад при удалении
ссылки).

### `GET /health` → `{"status": "ok"}`
