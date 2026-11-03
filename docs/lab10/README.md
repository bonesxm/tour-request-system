# ЛР №10: DORA — Tour Request System

Этот комплект **не подменяет реальную историю**. Гарантированно подтверждённая запись: первый деплой Render 03.11.2026 11:48:15 +05:00, коммит b2beb25 (создан 11:33:58). Тесты GitHub Actions не считаются деплоями.

## Запуск на Windows PowerShell

Откройте PowerShell внутри этой папки и выполните:

```powershell
py -m pip install -r requirements.txt
$env:GH_TOKEN = "ВАШ_FINE_GRAINED_READ_ONLY_TOKEN"
py scripts/dora.py --repo bonesxm/tour-request-system --window-start "2026-10-28T00:00:00+05:00"
py scripts/dashboard.py
```

**Токен не является обязательным** для публичного репозитория, однако без него лимит GitHub API ниже. Не отправляйте токен в чат или Git. Для быстрой офлайн-проверки, без API:

```powershell
py scripts/dora.py --offline --window-start "2026-10-28T00:00:00+05:00" --window-end "2026-11-04T00:00:00+05:00"
py scripts/dashboard.py
```

Результаты: `output/dora_metrics.json`, `output/deployments_analyzed.csv`, `output/dora_dashboard.png`. **Основной скрипт обращается к GitHub REST API**: `/deployments`, `/deployments/{id}/statuses`, `/actions/runs`, `/commits/{sha}`.

### Учет Render

Render может не создавать объекты GitHub Deployment API. Тогда новые подтверждённые развёртывания нужно добавлять в `data/deployments.csv`. Колонки:

- `id`: уникальный идентификатор на Render
- `sha`: хэш фактически развёрнутого коммита
- `source_commit_at`: время коммита ISO 8601 с часовым поясом, либо оставить пустым для получения через GitHub API
- `deployed_at`: **момент перехода в Live**, ISO 8601 с часовым поясом
- `result`: `success` или `failure`
- `incident_id`: ID связанного инцидента, если есть
- `note`: источник подтверждения

Если GitHub Deployments дублирует этот же запуск Render, уберите дубликат из CSV/настройте один авторитетный источник, иначе будет двойной счёт.

### Инциденты

При **фактическом** сбое заполняйте `data/incidents.csv`: `incident_id`, `deployment_id` (например, `render:first-render`), `started_at`, `restored_at`, `repair_hours`, `severity`, `description`, `corrective_action`. Восстановление считают только по инцидентам с датой начала и восстановления. Расход времени на исправления считается по `repair_hours` (трудозатраты), а не по длительности сбоя.

### Интерпретация

При единственном развёртывании **нельзя надёжно присвоить уровень DORA**. Не делайте вид, что `0 инцидентов = 0% CFR` при отсутствии регулярного журнала ошибок. `N/A` означает отсутствие измерений; это честнее, чем выдуманные цифры.

Время от merge-коммита `b2beb25` до состояния Live = **14 минут 17 секунд**. Это не обязательно полное *change lead time* от первого коммита изменения. Для последующих функций фиксируйте timestamp первого коммита каждого PR и момент доставки его изменений на стенд.

Окно по умолчанию начинается 28 октября 2026; конец = момент запуска скрипта. Меняйте оба параметра, если сравниваете разные недели.
