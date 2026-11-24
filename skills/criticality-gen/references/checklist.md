---
title: "Чеклист: criticality-gen"
purpose: "Приёмка цикла оценки: пункты до старта, во время работы и перед передачей."
audience: [ai-agent]
read_when: [закрываете цикл оценки, проверяете готовность к передаче]
updated: 2026-11-13
status: actual
related: [rules.md, workflow.md]
---

# Чеклист: criticality-gen

Проходится на каждую ИС и на каждый цикл оценки. Пункт считается закрытым
только по факту: команда вернула ожидаемое, файл существует, гейт зелёный.

## Перед запуском

- [ ] Каркас проекта создан: `make init` (в пустом проекте — `is.yaml`, `catalog.yaml`, `INDEX.md`, `is/`).
- [ ] Новая ИС заведена через `make scaffold IS=<код>` (папка `is/<код>/` и запись в `catalog.yaml`); существующая ИС не дублируется.
- [ ] `is.yaml` заполнен: список ИС; переопределения `product` / `teamName` — только там, где нужно (клон SSoT не нужен — данные из `ssot_get`).
- [ ] SSoT доступен: MCP `ssot-mcp` отвечает, `ssot_status` = `authorized` (сервер запущен, SSO-сессия активна).
- [ ] Зависимости проверены: [dependencies.md](dependencies.md) — ни одной строки `MISSING`.
- [ ] `make criteria-check` → `OK`; файл критериев не правился под конкретную ИС.
- [ ] `make docs-check` → `OK`: таблицы методики совпадают с критериями (нет `docs/02-methodology.md` — `WARN` и пропуск, код 0; это не блокер переносимого скилла).
- [ ] Для переоценки: `make due` просмотрен, `make reassess IS=erm.mm` создал файл переоценки.

## Во время

- [ ] `make prepare-apply` выполнен; в `INFORMATION.yaml` заполнены автосекции, ручные секции не потеряны (повторный `prepare` не меняет `sha1sum`). `INFORMATION.yaml` добавлен в git (не остаётся неотслеживаемым).
- [ ] В таблице `prepare` колонка `unreadable` = 0; каждый `WARN <ref>: <ошибка>` разобран.
- [ ] Каждому непустому `criteria_inputs.*.value` сопоставлен `source: {type, ref}`.
- [ ] `status` у каждого входа ∈ `missing | derived | confirmed`; `derived` помечен как требующий подтверждения.
- [ ] `make check` пройден: все ИС `OK` (или `SKIPPED` для исключённых), код возврата 0. `BLOCKED` — стоп (strict по умолчанию; `make check-diag` — только для отладки).
- [ ] После каждого этапа проверена подсказка следующего шага (`Следующий шаг: ...` в конце вывода): команда и причина соответствуют состоянию ИС; если шага нет — напечатано `Все этапы пройдены`.
- [ ] Для каждой `BLOCKED` ИС существует `DATA-REQUIREMENTS.md`/`.yaml`; лист передан адресатам из колонки «у кого».
- [ ] В листе требований прочитано предупреждение: заполнение advisory detailed-входа (`axes_scores`, `cia`) переключает ИС на сложный сценарий и требует `time_to_impact` (пометка `switches_scenario: true`); заполнять его «для полноты паспорта» без `time_to_impact` нельзя — гейт станет `BLOCKED`.
- [ ] Для каждой `BLOCKED` ИС создан `RESEARCH-PLAN.md` (`make collect-apply IS=...`): в нём есть `page_id` страниц Confluence, дашборды Grafana и запросы, если вход измеряется в Grafana.
- [ ] `make services-apply IS=...` выполнен: `SERVICE-FINDINGS.md` создан, в §1 перечислены все сервисы из `components[]` (или они попали в §7), у цитат есть `файл:строка`.
- [ ] `SERVICE-FINDINGS.md` содержит раздел «Пропущенные сервисы» (§2): число пропущенных (`services_skipped` в frontmatter) совпадает с числом компонентов `lifecycle: closed`; закрытые сервисы не клонированы и не проанализированы (`criteria.service_lifecycle`).
- [ ] В клонах `apps/` ничего не собрано и не запущено: единственный процесс — `git`; `git -C apps/IS/COMPONENT status --porcelain` пуст (R12).
- [ ] Находки из кода не вписаны в `INFORMATION.yaml`: `sha1sum` файла после `make services-apply` не изменился (R14).
- [ ] Сценарий в таблице `make check` соответствует данным: заполнен любой вход только сложного набора → `сложный`; неполный сложный набор — `BLOCKED`, а не `простой` (R13).
- [ ] У каждого собранного значения проверен источник: `confluence` — `page_id` + раздел + дословная цитата; `grafana` — uid дашборда, панель, точный PromQL и окно; `manual` — кто подтвердил.
- [ ] `peak_hour_load` пересчитан по формуле `peak_rps × 3600`, а не скопирован как RPS; latency/errors/probe-метрики как нагрузка не использованы.
- [ ] `axes_scores` и `cia` не «выведены» из документов: это экспертное решение с адресатом в `source.ref`.
- [ ] Заполненный лист прогнан через `make enrich IS=...` (ошибок нет) и `make enrich-apply IS=...`; `INFORMATION.yaml` изменился только в `criteria_inputs`.
- [ ] Проверено, что заполненные значения листа не потеряны: `value`/`source.ref`/`status` на месте после `make check` (слияние), `check` не печатал `ОШИБКА: рендер листа потерял N заполненных значений`, файлов `DATA-REQUIREMENTS.yaml.new`/`.broken` не осталось без разбора.
- [ ] Если данных нет и взять их негде — ИС исключена (`excluded: true` + `reason` в `catalog.yaml` для общего решения или `is.yaml` локально, вердикт `SKIPPED`), а не заполнена догадкой; решение об исключении согласовано.
- [ ] Сценарий соответствует данным: непустой любой вход только сложного набора → `сложный`; неполный сложный набор — `BLOCKED`, а не `простой`; `простой` — только при пустом сложном наборе, со `status: preliminary`.
- [ ] Входы вне blocking-набора сценария либо заполнены, либо их отсутствие осознанно принято (`WARN`, не блокер).
- [ ] Все `kind: convention` перечислены в §7 `CRITICALITY.md` и в `GENERATION.md`, не выданы за документированные.
- [ ] `make score --is erm.mm` выполнен: уровень и `score_trace` совпадают с ожиданием, `status` не `incomplete` (сложный набор неполон — `BLOCKED`, а не простой сценарий).
- [ ] `make start IS=erm.mm DIFF=1` просмотрен: diff соответствует ожиданиям, лишних изменений нет.

## Перед сдачей

- [ ] `make start-apply IS=erm.mm FORCE=1` выполнен; паспорт и `CRITICALITY.md` обновлены осознанно, а не «на всякий случай».
- [ ] `make validate` → 0 ERROR. WARN разобраны и объяснены (обычно это незаполненные `object_sla`, `object_workload`, `assigned_date`).
- [ ] Детерминизм проверен: два прогона с одной `DATE` дают одинаковый `sha1sum` / пустой `git diff` для всех артефактов, включая `actions/*` (признак переоценки не зависит от уже созданного паспорта).
- [ ] Расхождения зафиксированы в `conflicts` и в `GENERATION.md`, оба значения сохранены — оба вида: `calculation vs ssot` (расчёт ≠ `identity.criticality_ssot`) и `ssot vs catalog` (`catalog.criticality` ≠ SSoT).
- [ ] `make criteria-check`, `make docs-check`, `make selftest` → `OK`.
- [ ] Action-пакеты на месте: `actions/jira-task.md`, `actions/confluence-page.md`, `actions/rocketchat-message.md`.
- [ ] Внешние действия либо выполнены по флагу и с подтверждением, либо оформлены как action-пакеты.
- [ ] `INDEX.md` перегенерирован (`make index`), если менялся состав ИС или уровни.
- [ ] `make publish IS=<код> TASK=<key>` просмотрен (этап 8, **первым**): путь `architecture/app/<контур>/<сущность>/criticality_passport.yaml`, ключ `sber.ecom.<контур>.criticality_passport.<сущность>`, уровень в верхнем регистре совпадают с ожиданием; `_root.yaml` — импорт добавляется один раз.
- [ ] `make publish-apply IS=<код> TASK=<key>` выполнен: ветка `feature/<task>` (или `feature/<task>-<контур>`) от `origin/master`, коммит `<task>: feat(criticality): паспорт критичности <код> — <уровень>` из ровно двух файлов, описание MR в `.publish/<код>-MR.md`.
- [ ] `make ssot-plan IS=<код>` просмотрен (этап 9, **после** `publish`): в `.ssot/<код>-apply-plan.json` меняются только `severity.type` (из `levels.ssot_enum`) и `severity.confirmation` (= `approve_link`), `status` — `changed`/`no_change`/`blocked`, перечислены шаги MCP.
- [ ] MCP-форма выполнена: `ssot_entity_open` → `ssot_form_fields` → `ssot_ui_select`/`ssot_ui_fill` → `ssot_form_save`; ответ содержит `mrUrl`.
- [ ] `make ssot-record IS=<код> MR_URL=<mrUrl>` выполнен: `.ssot/<код>-MR.url` и `.ssot/<код>-MR.md` на месте, поля `ssot_mr_url`/`ssot_version`/`ssot_status` записаны в `INFORMATION.yaml`. Повторный `ssot-plan` на применённой ИС печатает `status: no_change`.
- [ ] Применение MR подтверждено человеком: `ssot_mr_approve(confirm: true)` → `ssot_apply_changes(confirm: true)` → `ssot_wait_master`; `make ssot-verify` записал `ssot_snapshot.verified.matched: true`.
- [ ] Для ИС с зелёным гейтом `DATA-REQUIREMENTS.md`/`.yaml` отсутствуют (лист удаляется, когда незакрытых входов нет).

## После сдачи

- [ ] MR с `criticality_passport.yaml` открыт в dochub и смержен; ссылка на MR вписана в action-пакет и `GENERATION.md`. Ветку и коммит создал `make publish-apply`; пуш и MR — по подтверждению.
- [ ] SSoT-MR (только `severity.type`/`severity.confirmation`) создан через `ssot_form_save`, смержен и применён до публикации в `#Criticality_assessment`. `severity.type` в SSoT совпадает с уровнем паспорта, `severity.confirmation` — с `approve_link` (`ssot-verify` подтвердил).
- [ ] SRE подтвердил оценку; `approve_link` заполнен, `review_date` назначен.
- [ ] Карточка SSoT обновлена: `criticality_ssot` совпадает с паспортом, расхождений нет.
- [ ] Jira-задача на переоценку создана (или создана вручную по action-пакету), ключ вписан.
- [ ] Сообщение в `#Criticality_assessment` отправлено человеком; ссылки и поля заполнены.
- [ ] Дата следующей переоценки видна в `make due`; `reassessment-YYYY-MM-DD.md` создан при старте нового цикла.

## Что считается провалом приёмки

| Симптом | Почему это провал |
|---------|-------------------|
| `validate` с ERROR | паспорт не соответствует схеме — в dochub его нельзя считать оценкой |
| Паспорт без `approve_link` | нет подтверждения SRE: это черновик, а не критичность |
| Значение без `source` | провенанс потерян, переоценка невозможна (R4) |
| `express` без пометки `preliminary` | предварительная оценка выдана за полную |
| Ручная правка сгенерированного файла | следующий прогон затрёт правку (R2) |
| Расхождение, разрешённое молча | потерян след решения (R6) |
| Два прогона дают разный результат | нарушен детерминизм, diff перестаёт быть сигналом (R7) |
| Значение вписано в обход `enrich` | источник не проверен, гейт обойдён (R1, R11) |
| `BLOCKED` без `DATA-REQUIREMENTS.*` | адресат не знает, что и где взять; работа встала молча (R11) |
| Публикация из черновика или из ветки не от `origin/master` | в dochub попадёт неоценённый/устаревший паспорт; гейт `publish` это ловит |
