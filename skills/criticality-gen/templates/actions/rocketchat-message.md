# Action-пакет: сообщение в `#Criticality_assessment`

> Сгенерировано `criticality.py start` из `templates/actions/rocketchat-message.md`.
> Руками не править — правки перезапишутся. Меняйте `INFORMATION.yaml`.
> **Статус:** `{{ actions.message.status }}`.
> Текст ниже — ПРЕДПРОСМОТР на момент `start`: ссылки на MR и `approve_link`
> появляются позже. Финальное сообщение собирает `make handoff IS=<код>` из
> текущего состояния и печатает целиком; отправка — только
> `make handoff-apply IS=<код> CONFIRM=1` после явного подтверждения человеком,
> ОДНИМ сообщением.

{{#if actions.message.blocked}}
> **⛔ Отправка заблокирована — незаполненных полей: {{ actions.message.blocked_count }}.**
> В тексте сообщения остались `⛔ не заполнено`, поэтому статус остаётся
> `pending_manual`: `--create-message` не переводит пакет в `requested`, пока
> дыры не закрыты. Незаполненные поля:
{{#each actions.message.blocked_fields}}
> - {{ . }}
{{/each}}
{{/if}}

## 1. Параметры

| Параметр | Значение |
|----------|----------|
| Канал | {{ actions.message.channel }} |
| Код ИС | `{{ identity.code }}` |
| Новая критичность | {{ passport.object_criticality_estimation | or_missing }} |
| Критичность SSoT | {{ identity.criticality_ssot | or_missing }} |
| Номер задачи Jira | {{ actions.jira.task_key | or_missing }} |
| Ссылка на задачу Jira | {{ actions.jira.task_link | or_missing }} |
| Ссылка на MR (паспорт в dochub) | {{ actions.mr_link | or_missing }} |
| Ссылка на MR (критичность в SSoT) | {{ actions.ssot_mr_text | or_missing }} |
| Ссылка на карточку ИС в SSoT | {{ actions.ssot_card_link | or_missing }} |
| Ссылка на процесс D6.1.1 | {{ actions.process_link | or_missing }} |

## 2. Предпросмотр сообщения

```text
{{ actions.message.text }}
```

## 3. Как отправить

Три пути — выберите один; после отправки ссылка на сообщение попадает в
`catalog.yaml → systems.{{ identity.code }}.thread_link`, а `approve_link`
(ссылка на тред согласования) проставляется тем же значением автоматически.

| Путь | Команда | Что делает |
|------|---------|------------|
| Авто (MCP → API) | `make handoff IS={{ identity.code }} SEND=auto` | пишет запрос для MCP (`.handoff-request.json`); при отказе MCP или отсутствии MCP-сервера Rocket.Chat отправляет через REST API |
| Только MCP | `make handoff IS={{ identity.code }} SEND=auto TRANSPORT=mcp` | пишет `.handoff-request.json` и ждёт `make handoff-result IS={{ identity.code }} MESSAGE_URL=<ссылка>` |
| Только API | `make handoff IS={{ identity.code }} SEND=auto TRANSPORT=api` | `POST /api/v1/chat.postMessage` с `ROCKETCHAT_TOKEN` + `ROCKETCHAT_USER_ID` |
| Вручную | `make handoff IS={{ identity.code }} SEND=manual` | ничего не отправляет: пакет остаётся `pending_manual`, сообщение копируется из блока 2 вручную |

Предпросмотр без отправки — `make handoff IS={{ identity.code }} DRY_RUN=1`.
Отправка запрещена, пока в тексте есть `⛔` или `validate` даёт ERROR; повтор
после `published` запрещён (`FORCE_RESEND=1` — осознанный обход).

## 4. Чеклист перед отправкой

- [ ] Задача в Jira создана, её номер подставлен выше (сейчас: {{ actions.jira.task_key | or_missing }}).
- [ ] MR в dochub создан, метка `criticality` проставлена (сейчас: {{ actions.mr_link | or_missing }}).
- [ ] MR в SSoT создан, в «Основании» — ссылка на dochub-MR (сейчас: {{ actions.ssot_mr_text | or_missing }}).
- [ ] Ссылка на карточку ИС в SSoT указана (сейчас: {{ actions.ssot_card_link | or_missing }}).
- [ ] `make validate` проходит без ERROR.
- [ ] В сообщении заполнены обязательные поля: технический архитектор, MR паспорта (dochub), ссылка на SSOT (в тексте нет `⛔` в этих строках).
- [ ] E2E-процессы перечислены или дана ссылка на неформальное описание.
- [ ] Тег технического архитектора актуален.
- [ ] Пользователь ответил «Публиковать» на вопрос «Публиковать это сообщение в треде или что-то нужно исправить?».

## 5. После отправки

1. Записать ссылку на сообщение: `make handoff-result IS={{ identity.code }} MESSAGE_URL=<ссылка>` (для транспорта MCP) — она ляжет в `catalog.yaml → thread_link`, а `approve_link` будет проставлен тем же значением автоматически.
2. Выполнить `make finalize IS={{ identity.code }}`:
   команда берёт `approve_link` из `thread_link` (флаг `--approve-link` —
   только явный override), проставляет `assigned_date`, `review_date`,
   `criticality`, `criticality_ssot`, `status: confirmed` и прогоняет
   `start-apply` → `validate` → `index` → `verify` (ERROR в `validate` —
   откат записанных полей).
3. Подтверждение фиксируется **мержем MR**: без аппрува MR не смержится,
   поэтому отдельного ожидания ответа SRE в треде нет.
4. `assigned_date` = дата генерации паспорта (`generated_at`),
   `review_date` = она же + период переоценки из критериев
   (`staleness.review_period_months`); `--assigned-date`/`--review-date` —
   явный override (при расхождении с датой генерации печатается WARN).

## 6. Чего в этом пакете нет

- **Ссылки на MR** — появляются только после создания обоих MR: паспорт в
  dochub (`make publish-apply … PUSH=1`) и критичность в SSoT
  (`make ssot-apply … PUSH=1`). В сообщении их **две**; пока их нет, в тексте
  стоит `⛔ не заполнено` — отправлять такое сообщение нельзя.
  Исключение — `catalog.yaml → systems.<код>.ssot_status: no_change`: severity
  в SSoT уже соответствует расчёту, MR не требуется, и в тексте стоит
  «не требуется: severity уже соответствует (…)» — это заполненное поле.
- **Номер задачи Jira** — появляется только после создания задачи.
- **`approve_link`** — не ждёт ответа: это ссылка на тред согласования,
  проставляется автоматически после публикации треда.
