# SQL-запросы для отчёта по метрикам E001

Все запросы выполняются через `mcp-cedrus_execute_query`. Переменные `{START}` и `{END}` — границы периода: `resolved >= {START} AND resolved < {END}` (полуоткрытый диапазон).

Каталог/schema: `datalake_smkt.prsd_service_desk`.

## 1. Закрытые Done Epic по месяцам (LT/CR агрегат)

Используется для таблицы «Всего задач по месяцам».

```sql
SELECT
  date_trunc('month', resolved) AS m,
  count(*) FILTER (WHERE lower(statusname)='done') AS done_cnt,
  count(*) FILTER (WHERE lower(statusname)='cancelled') AS cancelled_cnt
FROM datalake_smkt.prsd_service_desk.jira_issue_4
WHERE projectkey='E001' AND lower(issuetypename)='epic'
  AND resolved >= TIMESTAMP '{START}' AND resolved < TIMESTAMP '{END}'
GROUP BY 1 ORDER BY 1
```

> ЛТ и CR по месяцам считаются детальными запросами с историей — см. ниже. Здесь — база по счётчикам Done/Cancelled.

## 2. Детализация закрытых Done Epic за период (с LT и CR)

Соединяет снимок с историей статусов. LT = сумма минут в рабочих статусах, округлёно к дням; диапазон 1–365 дн.

```sql
WITH hist AS (
  SELECT issuekey, changetime, lower(newvalue) AS st,
    LEAD(changetime) OVER (PARTITION BY issuekey ORDER BY changetime) AS next_ct
  FROM datalake_smkt.prsd_service_desk.jira_issue_history_hist
  WHERE lower(fieldname)='statusname'
),
issues AS (
  SELECT issuekey, CAST(resolved AS timestamp(3)) AS resolved,
    lower(statusname) AS st, assigneeusername, summary,
    CAST(enddate AS timestamp(3)) AS enddate,
    CAST(baselineenddate AS timestamp(3)) AS baselineenddate
  FROM datalake_smkt.prsd_service_desk.jira_issue_4
  WHERE projectkey='E001' AND lower(issuetypename)='epic'
    AND lower(statusname)='done'
    AND resolved >= TIMESTAMP '{START}' AND resolved < TIMESTAMP '{END}'
)
SELECT i.issuekey, i.st, i.assigneeusername, i.summary,
  round(COALESCE(sum(date_diff('minute', h.changetime, COALESCE(h.next_ct, i.resolved)))
    FILTER (WHERE h.st IN ('ba','ready for sa','sa','ready for dev','development','to test','testing')), 0)/1440.0) AS lt_days,
  CASE WHEN i.enddate IS NOT NULL AND i.baselineenddate IS NOT NULL
       AND i.enddate <= i.baselineenddate + INTERVAL '2' DAY THEN 'yes' ELSE 'over' END AS cr
FROM issues i
LEFT JOIN hist h ON h.issuekey = i.issuekey
GROUP BY i.issuekey, i.st, i.assigneeusername, i.summary, i.enddate, i.baselineenddate, i.resolved
ORDER BY 1
```

## 3. Сверка снимка vs истории (поиск «закрыт по истории, но не в снимке»)

В снимке `jira_issue_4` поле `statusname` может отставать (напр. `ready to deploy`, а по истории — `done`). Этот запрос находит такие задачи за период. Обязательно запускать и включать найденные `done`-по-истории задачи в отчёт.

```sql
WITH done_hist AS (
  SELECT issuekey, changetime,
    row_number() OVER (PARTITION BY issuekey ORDER BY changetime DESC) AS rn
  FROM datalake_smkt.prsd_service_desk.jira_issue_history_hist
  WHERE lower(fieldname)='statusname' AND lower(newvalue)='done'
)
SELECT i4.issuekey, lower(i4.issuetypename) AS itype,
  lower(i4.statusname) AS snap, (i4.resolved IS NOT NULL) AS has_resolved,
  substr(CAST(d.changetime AS VARCHAR),1,10) AS done_at,
  substr(CAST(i4.updated AS VARCHAR),1,10) AS updd
FROM datalake_smkt.prsd_service_desk.jira_issue_4 i4
JOIN done_hist d ON d.issuekey = i4.issuekey AND d.rn=1
WHERE i4.projectkey='E001'
  AND lower(i4.issuetypename) IN ('epic','initiative')
  AND d.changetime >= TIMESTAMP '{START}' AND d.changetime < TIMESTAMP '{END}'
  AND lower(i4.statusname) <> 'done'
  AND ( i4.resolved IS NULL OR i4.resolved < TIMESTAMP '{END}' )
ORDER BY 2,1
```

Обратное направление (снимок = `done`, но история ≠ `done`) — проверять как «пересчёт», задачи вне периода исключать.

## 4. Done PI по кварталам (CR)

```sql
SELECT
  CASE WHEN resolved >= TIMESTAMP '{START}' AND resolved < TIMESTAMP '{START}' + INTERVAL '3' MONTH THEN 'Q_start'
       END AS q,  -- замените на фактические границы кварталов
  count(*) AS total_closed,
  sum(CASE WHEN lower(statusname)='done' THEN 1 ELSE 0 END) AS done_cnt,
  sum(CASE WHEN lower(statusname)='done' AND enddate IS NOT NULL AND baselineenddate IS NOT NULL THEN 1 ELSE 0 END) AS done_with_dates,
  sum(CASE WHEN lower(statusname)='done' AND enddate IS NOT NULL AND baselineenddate IS NOT NULL
           AND enddate <= baselineenddate + INTERVAL '2' DAY THEN 1 ELSE 0 END) AS done_on_time
FROM datalake_smkt.prsd_service_desk.jira_issue_4
WHERE projectkey='E001' AND lower(issuetypename)='initiative'
  AND resolved >= TIMESTAMP '{START}' AND resolved < TIMESTAMP '{END}'
GROUP BY 1 ORDER BY 1
```

> Кварталы задайте явно через `CASE WHEN` по дате `resolved` (3 квартала на календарный год). Пример границ для 2026: Q1 `[2026-01-01, 2026-04-01)`, Q2 `[2026-04-01, 2026-07-01)`, Q3 `[2026-07-01, 2026-10-01)`.

## 5. Одиночные (Single, без PRCON) PI по кварталам

PRCON-связь = в `linkedissues` есть задача с `projectkey='PRCON'`. Такие PI исключаются из ТТМ PI Single.

```sql
SELECT i1.issuekey,
  CASE WHEN i1.resolved >= TIMESTAMP '2026-01-01' AND i1.resolved < TIMESTAMP '2026-04-01' THEN 'Q1 2026'
       WHEN i1.resolved >= TIMESTAMP '2026-04-01' AND i1.resolved < TIMESTAMP '2026-07-01' THEN 'Q2 2026'
       WHEN i1.resolved >= TIMESTAMP '2026-07-01' AND i1.resolved < TIMESTAMP '2026-10-01' THEN 'Q3 2026'
       END AS q,
  count(i2.issuekey) FILTER (WHERE i2.projectkey='PRCON') AS prcon_cnt
FROM datalake_smkt.prsd_service_desk.jira_issue_4 i1
LEFT JOIN UNNEST(i1.linkedissues) AS l(lid, ltype) ON true
LEFT JOIN datalake_smkt.prsd_service_desk.jira_issue_4 i2 ON i2.id = CAST(l.lid AS VARCHAR)
WHERE i1.projectkey='E001' AND lower(i1.issuetypename)='initiative'
  AND lower(i1.statusname)='done'
  AND i1.resolved >= TIMESTAMP '{START}' AND i1.resolved < TIMESTAMP '{END}'
GROUP BY i1.issuekey, i1.resolved
ORDER BY 2,1
```

> `prcon_cnt = 0` → одиночный (входит в ТТМ PI Single). Квартальные границы в `CASE` замените под нужный период.
>
> ⚠️ **Удалённые связи (ловушка, 22.09.2026):** в changelog живого Jira `Link`-записи фиксируют и **добавленные, а потом удалённые** связи (при удалении заполнен `from_string`). Пример: E001-26330 имел связь `PRCON-4096` с 13.11.2025 по 31.03.2026, потом связь удалили — в текущем снимке `linkedissues` PRCON нет → PI **входит** в Single. Правило: PRCON-связь = только текущие `linkedissues` (снимок); changelog — лишь для аудита. Если в changelog была удалённая PRCON-связь — добавьте в отчёт оговорку и строгий срез (среднее без этой задачи) в скобках.

## 6. ТТМ PI Single по кварталам

ТТМ = сумма минут в рабочих статусах по истории, округлёно по итогу; диапазон 14–365 дн. Только Done PI без PRCON-связи.

> ⚠️ **ВАЖНО (исправлено 21.09.2026):** у Initiative (PI) НЕ статусы Epic. У PI история имеет `business discovery, planning, concept design, analysis, implementing, ready to deploy, acceptance, pending, effects, cancelled, done, backlog, new`. Правило из docs/htc-cedrus.md: **ТТМ PI = все статусы, КРОМЕ** `new, backlog, business discovery, planning, pending, acceptance, effects, done, cancelled`. Ниже фильтр в SQL — по этому правилу (`NOT IN (...)`), НЕ по Epic-списку (`ba, ready for sa, ...`). Старый вариант давал ТТМ=0 для PI.

```sql
WITH prcon AS (
  SELECT DISTINCT i1.issuekey
  FROM datalake_smkt.prsd_service_desk.jira_issue_4 i1
  LEFT JOIN UNNEST(i1.linkedissues) AS l(lid, ltype) ON true
  LEFT JOIN datalake_smkt.prsd_service_desk.jira_issue_4 i2 ON i2.id = CAST(l.lid AS VARCHAR)
  WHERE i2.projectkey='PRCON'
),
hist AS (
  SELECT issuekey, changetime, lower(newvalue) AS st,
    LEAD(changetime) OVER (PARTITION BY issuekey ORDER BY changetime) AS next_ct
  FROM datalake_smkt.prsd_service_desk.jira_issue_history_hist
  WHERE lower(fieldname)='statusname'
),
pi AS (
  SELECT issuekey, CAST(resolved AS timestamp(3)) AS resolved
  FROM datalake_smkt.prsd_service_desk.jira_issue_4
  WHERE projectkey='E001' AND lower(issuetypename)='initiative'
    AND lower(statusname)='done'
    AND resolved >= TIMESTAMP '{START}' AND resolved < TIMESTAMP '{END}'
)
SELECT
  CASE WHEN p.resolved >= TIMESTAMP '{START}' AND p.resolved < TIMESTAMP '{START}' + INTERVAL '3' MONTH THEN 'Q1'
       ELSE 'Q2' END AS q,
  count(*) AS n,
  round(avg(mins)/1440.0,1) AS avg_days
FROM (
  SELECT p.issuekey, p.resolved, sum(
    date_diff('minute', h.changetime, COALESCE(h.next_ct, p.resolved))
  ) FILTER (WHERE h.st NOT IN ('new','backlog','business discovery','planning','pending','acceptance','effects','done','cancelled')) AS mins
  FROM pi p
  LEFT JOIN prcon pc ON pc.issuekey = p.issuekey
  LEFT JOIN hist h ON h.issuekey = p.issuekey
  WHERE pc.issuekey IS NULL
  GROUP BY p.issuekey, p.resolved
) t
WHERE mins BETWEEN 14*1440 AND 365*1440
GROUP BY 1 ORDER BY 1
```

## 7. Итоговые агрегаты за период

```sql
SELECT
  ( SELECT count(*) FROM datalake_smkt.prsd_service_desk.jira_issue_4
    WHERE projectkey='E001' AND lower(issuetypename)='epic'
      AND lower(statusname)='done' AND resolved >= TIMESTAMP '{START}' AND resolved < TIMESTAMP '{END}'
  ) AS epic_done_total,
  ( SELECT count(*) FROM datalake_smkt.prsd_service_desk.jira_issue_4
    WHERE projectkey='E001' AND lower(issuetypename)='initiative'
      AND lower(statusname)='done' AND resolved >= TIMESTAMP '{START}' AND resolved < TIMESTAMP '{END}'
  ) AS pi_done_total
```

## 8. Прогнозные ТТМ PI / LT Epic (незакрытые задачи в работе)

Метод «календарный калиброванный». Выборка: только E001, типы Initiative/Epic, статус не `done`/`cancelled`, `enddate` и `startdate` не NULL (задачи в работе). Backlog (startdate=NULL) исключается — время ожидания не входит в ТТМ/LT.

### 8a. Калибровка K по закрытым задачам

`K = медиана(фактический рабочий ТТМ/LT ÷ календарные дни)`. Факт — из истории (рабочие статусы, как в запросах 2/6), календарь — `startdate → enddate`. Для PI брать задачи без PRCON-связи и с фактическим ТТМ > 0 (у многих PI история пустая → сырой K=0 неприменим).

```sql
-- Epic: K_median, K_mean
WITH hist AS (
  SELECT issuekey, changetime, lower(newvalue) AS st,
    LEAD(changetime) OVER (PARTITION BY issuekey ORDER BY changetime) AS next_ct
  FROM datalake_smkt.prsd_service_desk.jira_issue_history_hist
  WHERE lower(fieldname)='statusname'
),
calc AS (
  SELECT i.issuekey,
    round(COALESCE(sum(date_diff('minute', h.changetime, COALESCE(h.next_ct, i.resolved)))
      FILTER (WHERE h.st IN ('ba','ready for sa','sa','ready for dev','development','to test','testing')), 0)/1440.0) AS actual_days,
    date_diff('day', CAST(i.startdate AS timestamp), CAST(i.enddate AS timestamp)) AS cal_days
  FROM datalake_smkt.prsd_service_desk.jira_issue_4 i
  LEFT JOIN hist h ON h.issuekey = i.issuekey
  WHERE i.projectkey='E001' AND lower(i.issuetypename)='epic'
    AND lower(i.statusname)='done' AND i.enddate IS NOT NULL AND i.startdate IS NOT NULL
  GROUP BY i.issuekey, i.startdate, i.enddate, i.resolved
)
SELECT count(*) AS n,
  round(approx_percentile(actual_days/cal_days, 0.5),3) AS k_median,
  round(avg(actual_days/cal_days),3) AS k_mean
FROM calc WHERE cal_days > 0
```

Для PI — повторить с `lower(i.issuetypename)='initiative'`, джойном к `prcon` (исключить связанные) и фильтром фактического ТТМ > 0. Репор K (снимок 07.08.2026): PI=0.31, Epic=0.58.

- **K_Median** (закрытые Epic): пересчёт 21.09.2026 — K_median = 0.587, K_mean = 0.649 (n=854). Для PI (без PRCON, факт>0): K_median = 0.674, K_mean = 0.658 (n=36). Репортовые ранее (снимок 07.08): PI=0.31, Epic=0.58 — устарели после исправления методики ТТМ PI.

### 8b. Агрегаты прогноза (медиана/среднее)

```sql
WITH base AS (
  SELECT lower(issuetypename) AS itype,
    date_diff('day', CAST(startdate AS timestamp), CAST(enddate AS timestamp)) AS cal_days
  FROM datalake_smkt.prsd_service_desk.jira_issue_4
  WHERE projectkey='E001' AND lower(issuetypename) IN ('initiative','epic')
    AND lower(statusname) NOT IN ('done','cancelled')
    AND startdate IS NOT NULL AND enddate IS NOT NULL
)
SELECT itype, count(*) AS n,
  round(approx_percentile(cal_days*CASE WHEN itype='initiative' THEN 0.674 ELSE 0.587 END,0.5),1) AS med_fc,
  round(avg(cal_days*CASE WHEN itype='initiative' THEN 0.674 ELSE 0.587 END),1) AS avg_fc
FROM base GROUP BY itype
```

### 8c. Список задач для таблицы прогноза

```sql
SELECT issuekey, summary, assigneeusername, lower(statusname) AS st,
  date_diff('day', CAST(startdate AS timestamp), CAST(enddate AS timestamp)) AS cal_days,
  substr(CAST(enddate AS VARCHAR),1,10) AS enddate
FROM datalake_smkt.prsd_service_desk.jira_issue_4
WHERE projectkey='E001' AND lower(issuetypename)='initiative'   -- или 'epic'
  AND lower(statusname) NOT IN ('done','cancelled')
  AND startdate IS NOT NULL AND enddate IS NOT NULL
ORDER BY cal_days DESC
```

Прогноз по строке = `round(cal_days * K)`. Обязательно исключать задачи, «закрытые по истории» (statusname не `done`, но история = `done`; напр. E001-29150) — проверять через запрос 3.

## Заметки по выполнению

- Все сравнения статусов — через `lower()`.
- История: последняя **непустая** запись `statusname` (`newvalue IS NOT NULL AND lower(newvalue)<>''`) — иначе попадётся `NULL`-запись и сверка сломается.
- `linkedissues.lid` — `bigint`, `jira_issue_4.id` — `varchar`: приводи типы (`CAST(l.lid AS VARCHAR)`).
- Квартальные границы в `CASE WHEN` в запросах 4/5/6 заменяй под фактический `{START}`–`{END}` (для года — Q1/Q2/Q3).