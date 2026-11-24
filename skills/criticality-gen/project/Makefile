# Паспорта критичности ИС продукта E001 «Инструменты оператора»
# Инструмент: этот Makefile + skills/criticality-gen (скрипт, критерии, шаблоны).
# Данные проекта: is/, catalog.yaml, INDEX.md, docs/ — в ROOT.
#
# Запуск из корня проекта:  make <цель> [VAR=value]   (корневой Makefile — фасад)
# Запуск напрямую:          make -f .opencode/Makefile <цель> [ROOT=/путь]

.DEFAULT_GOAL := help

# ROOT — корень проекта с данными. По умолчанию — родитель каталога .opencode.
# Фасад из корня переопределяет: ROOT=$(CURDIR).
ROOT ?= $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/..)
SKILL_DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))skills/criticality-gen)
# Собственный файл целей: нужен рекурсивным вызовам (`make verify`), чтобы не
# зависеть от фасада в корне проекта и его переменной ROOT.
SELF_MAKEFILE := $(abspath $(lastword $(MAKEFILE_LIST)))

PYTHON ?= python3
CLI := $(PYTHON) $(SKILL_DIR)/scripts/criticality.py --root $(ROOT)

.PHONY: help help-fast info paths init prepare prepare-apply contacts validate index due show next-step reassess reassess-apply scaffold criteria criteria-check score check check-diag check-prepare selftest docs-sync docs-check verify-titles research verify start start-apply finalize handoff handoff-apply handoff-result publish publish-apply ssot ssot-apply ssot-mr ssot-mr-apply requirements collect collect-apply links links-apply sources sources-apply services services-apply ask ask-apply ask-answers enrich enrich-apply exclude include skill-install skill-uninstall skill-check

DRY ?= 1

help: ## Показать справку скилла с текущим состоянием ИС и список целей
	@$(CLI) help
	@echo ""
	@echo "Make-цели:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-18s %s\n", $$1, $$2}'
	@echo ""
	@echo "Примеры:"
	@echo "  make init"
	@echo "  make prepare"
	@echo "  make prepare-apply"
	@echo "  make contacts IS=erm.mm"
	@echo "  make contacts IS=erm.mm APPLY=1"
	@echo "  make validate"
	@echo "  make check"
	@echo "  make collect IS=erm.mm"
	@echo "  make collect-apply IS=erm.mm"
	@echo "  make services IS=erm.mm"
	@echo "  make services-apply IS=erm.mm"
	@echo "  make services-apply IS=erm.mm NO_CLONE=1"
	@echo "  make ask IS=erm.mm"
	@echo "  make ask IS=erm.mm JSON=1"
	@echo "  make ask-apply IS=erm.mm"
	@echo "  make ask-answers IS=erm.mm ANSWERS=is/erm.mm/ANSWERS.yaml"
	@echo "  make start"
	@echo "  make start IS=erm.mm DIFF=1"
	@echo "  make start-apply IS=erm.mm FORCE=1"
	@echo "  make publish IS=erm.mm TASK=E001-31245"
	@echo "  make publish-apply IS=erm.mm TASK=E001-31245"
	@echo "  make ssot IS=erm.mm TASK=E001-31245"
	@echo "  make ssot-apply IS=erm.mm TASK=E001-31245"
	@echo "  make handoff IS=erm.mm SEND=auto    (MCP, при отказе — REST API; SEND=manual — оставить вручную)"
	@echo "  make handoff IS=erm.mm DRY_RUN=1"
	@echo "  make handoff IS=erm.mm DRY_RUN=1 WRITE=1 ALLOW_INCOMPLETE=1"
	@echo "  make handoff-result IS=erm.mm MESSAGE_URL=<ссылка на сообщение>"
	@echo "  make handoff-apply IS=erm.mm CONFIRM=1"
	@echo "  make finalize IS=erm.mm"
	@echo "  make finalize IS=erm.mm APPROVE_LINK=<ссылка на тред> DRY_RUN=1"
	@echo "  make selftest"
	@echo "  make index"
	@echo "  make due"
	@echo "  make show IS=erm.mm"
	@echo "  make next-step IS=erm.mm"
	@echo "  make reassess IS=erm.mm"
	@echo "  make reassess-apply IS=erm.mm"
	@echo "  make scaffold CONTOUR=mm NAME=foo"
	@echo "  make exclude IS=ts.mm REASON='...' EXCLUDE_SCOPE=catalog"
	@echo "  make score AXES=legal=3,economic=2,reputational=1,client=4 TIME='<1h'"
	@echo "  make score ARGS=\"--cia c=high,i=medium,a=low\""
	@echo "  make docs-sync"
	@echo "  make docs-check"
	@echo "  make verify-titles"
	@echo "  make verify-titles IS=erm.mm FIX=1"
	@echo "  make research IS=erm.mm"
	@echo "  make verify"
	@echo "  make skill-install TARGET=/путь/к/проекту"
	@echo "  make skill-check"
	@echo "  make paths"
	@echo ""
	@echo "Документация инструмента: .opencode/skills/criticality-gen/references/commands.md"
	@echo "Канон флоу и гейты:      .opencode/skills/criticality-gen/references/workflow.md"

help-fast: ## Справка без чтения состояния ИС (быстро): make help-fast
	@$(CLI) help --no-state
	@echo ""
	@echo "Список make-целей и примеры: make help"

info: ## Критерии оценки с пояснениями: make info [SECTION=levels] [JSON=1]
	@$(CLI) info $(if $(SECTION),--section $(SECTION),) $(if $(filter 1,$(JSON)),--json,)

paths: ## Показать ROOT (данные) и SKILL_DIR (инструмент)
	@echo "ROOT      = $(ROOT)"
	@echo "SKILL_DIR = $(SKILL_DIR)"

validate: ## Проверить паспорта и реестр (ненулевой код при ERROR)
	@$(CLI) validate

init: ## Создать каркас проекта: is.yaml, catalog.yaml, INDEX.md, is/ (FORCE=1 — перезаписать is.yaml)
	@$(CLI) init $(if $(filter 1,$(FORCE)),--force,)

prepare: ## Подготовка данных (dry-run): ssot -> INFORMATION.yaml, план клонирования
	@$(CLI) prepare $(if $(IS),--is $(IS),)

prepare-apply: ## Подготовка данных (apply): запись INFORMATION.yaml + git-операции
	@$(CLI) prepare --apply $(if $(IS),--is $(IS),) $(if $(filter 1,$(NO_CLONE)),--no-clone,) $(if $(filter 1,$(FORCE_OVERWRITE)),--force-overwrite,) $(if $(filter 1,$(ALLOW_EMPTY_SECTIONS)),--allow-empty-sections,) $(if $(filter 1,$(NO_BACKUP)),--no-backup,) $(if $(BACKUP_KEEP),--backup-keep $(BACKUP_KEEP),)

contacts: ## Собрать контакты TA/TL из SSoT team.yaml: make contacts IS=<код> [APPLY=1]
	@if [ -z "$(IS)" ]; then echo "ERROR: укажите IS=<код ИС>, например: make contacts IS=erm.mm"; exit 1; fi
	@$(CLI) contacts --is $(IS) $(if $(filter 1,$(APPLY)),--apply,) $(if $(filter 1,$(JSON)),--json,)

index: ## Перегенерировать INDEX.md: make index [DATE=YYYY-MM-DD]
	@$(CLI) index --write $(if $(DATE),--date $(DATE),)

due: ## Показать просроченные и ближайшие переоценки
	@$(CLI) due

show: ## Сводка по ИС: make show IS=erm.mm
	@if [ -z "$(IS)" ]; then echo "ERROR: укажите IS=<код ИС>, например: make show IS=erm.mm"; exit 1; fi
	@$(CLI) show --is $(IS)

next-step: ## Следующий шаг конвейера: make next-step [IS=erm.mm] [NO_CLONE=1]
	@$(CLI) next-step $(if $(IS),--is $(IS),) $(if $(filter 1,$(NO_CLONE)),--no-clone,)

reassess: ## План переоценки (dry-run): make reassess IS=erm.mm [DATE=YYYY-MM-DD]
	@if [ -z "$(IS)" ]; then echo "ERROR: укажите IS=<код ИС>, например: make reassess IS=erm.mm"; exit 1; fi
	@$(CLI) reassess --is $(IS) $(if $(DATE),--date $(DATE),)

reassess-apply: ## Записать переоценку и обновить review_date: make reassess-apply IS=erm.mm [DATE=...]
	@if [ -z "$(IS)" ]; then echo "ERROR: укажите IS=<код ИС>, например: make reassess-apply IS=erm.mm"; exit 1; fi
	@$(CLI) reassess --is $(IS) $(if $(DATE),--date $(DATE),) --apply

scaffold: ## Создать ИС: make scaffold IS=foo.mm | CONTOUR=mm NAME=foo [ASSET=ММ] [PAGE_ID=...] [CRITICALITY_PAGE_ID=...]
	@name="$(NAME)"; contour="$(CONTOUR)"; \
	if [ -z "$$name" ] && [ -n "$(IS)" ]; then name="$${IS%.*}"; contour="$${IS##*.}"; fi; \
	if [ -z "$$name" ] || [ -z "$$contour" ]; then \
		echo "ERROR: укажите IS=<name_is>.<mm|smkt> или CONTOUR=<mm|smkt> NAME=<name_is>, например: make scaffold IS=foo.mm"; exit 1; \
	fi; \
	$(CLI) scaffold --contour "$$contour" --name "$$name" $(if $(ASSET),--asset "$(ASSET)",) $(if $(ARCH_CODE),--arch-code $(ARCH_CODE),) $(if $(TEAM),--team $(TEAM),) $(if $(PAGE_ID),--page-id $(PAGE_ID),) $(if $(CRITICALITY_PAGE_ID),--criticality-page-id $(CRITICALITY_PAGE_ID),)

criteria: ## Показать критерии расчёта (JSON: make criteria JSON=1)
	@$(CLI) criteria show $(if $(filter 1,$(JSON)),--json,)

criteria-check: ## Проверить целостность файла критериев
	@$(CLI) criteria check --no-next

score: ## Пример расчёта: make score AXES=... TIME='<1h' | make score ARGS="--cia c=high,i=medium,a=low"
	@if [ -n "$(ARGS)" ]; then \
		$(CLI) score $(ARGS); \
	else \
		$(CLI) score --axes "$${AXES:-legal=3,economic=2,reputational=1,client=4}" --time "$${TIME:-<1h}"; \
	fi

check: ## Гейт достаточности данных (strict по умолчанию): make check [IS=erm.mm] [NO_REQUIREMENTS=1]
	@$(CLI) check $(if $(IS),--is $(IS),) $(if $(filter 1,$(NO_REQUIREMENTS)),--no-requirements,)

check-diag: ## Гейт в диагностическом режиме (код 0 даже при BLOCKED): make check-diag [IS=...]
	@$(CLI) check --diagnostic $(if $(IS),--is $(IS),) $(if $(filter 1,$(NO_REQUIREMENTS)),--no-requirements,)

check-prepare: ## Подготовка данных + гейт: make check-prepare [IS=...] [NO_CLONE=1] [NO_REQUIREMENTS=1]
	@$(CLI) check --prepare $(if $(IS),--is $(IS),) $(if $(filter 1,$(NO_CLONE)),--no-clone,) $(if $(filter 1,$(NO_REQUIREMENTS)),--no-requirements,)

requirements: ## Лист недостающих данных (dry-run): make requirements [IS=...] [DATE=...] [APPLY=1]
	@$(CLI) requirements $(if $(IS),--is $(IS),) $(if $(DATE),--date $(DATE),) $(if $(filter 1,$(APPLY)),--apply,)

collect: ## План сбора данных по источникам (dry-run): make collect [IS=...] [DATE=...]
	@$(CLI) collect $(if $(IS),--is $(IS),) $(if $(DATE),--date $(DATE),)

collect-apply: ## Записать RESEARCH-PLAN.md: make collect-apply [IS=...] [DATE=...]
	@$(CLI) collect --apply $(if $(IS),--is $(IS),) $(if $(DATE),--date $(DATE),)

links: ## Карта обхода ссылок (dry-run): make links IS=... [DATE=...] [LIMIT=150]
	@if [ -z "$(IS)" ]; then echo "ERROR: укажите IS=<код ИС>, например: make links IS=opercrm.smkt"; exit 1; fi
	@$(CLI) links --is $(IS) $(if $(DATE),--date $(DATE),) $(if $(LIMIT),--limit $(LIMIT),)

links-apply: ## Записать LINK-MAP.md/.yaml: make links-apply IS=... [DATE=...] [LIMIT=150] [FORCE=1]
	@if [ -z "$(IS)" ]; then echo "ERROR: укажите IS=<код ИС>, например: make links-apply IS=opercrm.smkt"; exit 1; fi
	@$(CLI) links --is $(IS) --apply $(if $(DATE),--date $(DATE),) $(if $(LIMIT),--limit $(LIMIT),) $(if $(filter 1,$(FORCE)),--force,)

sources: ## Приём SOURCES-FINDINGS.yaml (dry-run): make sources IS=...
	@if [ -z "$(IS)" ]; then echo "ERROR: укажите IS=<код ИС>, например: make sources IS=opercrm.smkt"; exit 1; fi
	@$(CLI) sources --is $(IS) $(if $(DATE),--date $(DATE),)

sources-apply: ## Записать значения в INFORMATION.yaml: make sources-apply IS=...
	@if [ -z "$(IS)" ]; then echo "ERROR: укажите IS=<код ИС>, например: make sources-apply IS=opercrm.smkt"; exit 1; fi
	@$(CLI) sources --is $(IS) --apply $(if $(DATE),--date $(DATE),)


services: ## Клоны сервисов + docs/openspec (dry-run): make services [IS=...] [DATE=...] [NO_CLONE=1]
	@$(CLI) services $(if $(IS),--is $(IS),) $(if $(DATE),--date $(DATE),) $(if $(filter 1,$(NO_CLONE)),--no-clone,)

services-apply: ## Записать SERVICE-FINDINGS.md: make services-apply [IS=...] [DATE=...] [NO_CLONE=1]
	@$(CLI) services --apply $(if $(IS),--is $(IS),) $(if $(DATE),--date $(DATE),) $(if $(filter 1,$(NO_CLONE)),--no-clone,)

ask: ## План вопросов по недостающим входам: make ask IS=<код> [JSON=1]
	@if [ -z "$(IS)" ]; then echo "ERROR: укажите IS=<код ИС>, например: make ask IS=erm.mm"; exit 1; fi
	@$(CLI) ask --is $(IS) $(if $(filter 1,$(JSON)),--json,) $(if $(DATE),--date $(DATE),)

ask-apply: ## Записать ASK.md: make ask-apply IS=<код>
	@if [ -z "$(IS)" ]; then echo "ERROR: укажите IS=<код ИС>, например: make ask-apply IS=erm.mm"; exit 1; fi
	@$(CLI) ask --is $(IS) --apply $(if $(DATE),--date $(DATE),)

ask-answers: ## Принять ответы: make ask-answers IS=<код> ANSWERS=<файл>
	@if [ -z "$(IS)" ] || [ -z "$(ANSWERS)" ]; then echo "ERROR: укажите IS=<код> и ANSWERS=<файл>, например: make ask-answers IS=erm.mm ANSWERS=is/erm.mm/ANSWERS.yaml"; exit 1; fi
	@$(CLI) ask --is $(IS) --answers "$(ANSWERS)" $(if $(REASON),--reason "$(REASON)",) $(if $(EXCLUDE_SCOPE),--scope $(EXCLUDE_SCOPE),) $(if $(DATE),--date $(DATE),)

enrich: ## Приём DATA-REQUIREMENTS.yaml (dry-run): make enrich IS=erm.mm
	@if [ -z "$(IS)" ]; then echo "ERROR: укажите IS=<код ИС>, например: make enrich IS=erm.mm"; exit 1; fi
	@$(CLI) enrich --is $(IS)

enrich-apply: ## Принять лист и записать в INFORMATION.yaml: make enrich-apply IS=erm.mm
	@if [ -z "$(IS)" ]; then echo "ERROR: укажите IS=<код ИС>, например: make enrich-apply IS=erm.mm"; exit 1; fi
	@$(CLI) enrich --is $(IS) --apply

exclude: ## Исключить ИС из расчёта: make exclude IS=ts.mm REASON="..." [EXCLUDE_SCOPE=catalog]
	@if [ -z "$(IS)" ] || [ -z "$(REASON)" ]; then echo "ERROR: укажите IS=<код> и REASON=\"<причина>\""; exit 1; fi
	@$(CLI) exclude --is $(IS) --reason "$(REASON)" $(if $(EXCLUDE_SCOPE),--scope $(EXCLUDE_SCOPE),)

include: ## Вернуть ИС в расчёт: make include IS=ts.mm [EXCLUDE_SCOPE=catalog]
	@if [ -z "$(IS)" ]; then echo "ERROR: укажите IS=<код ИС>, например: make include IS=ts.mm"; exit 1; fi
	@$(CLI) include --is $(IS) $(if $(EXCLUDE_SCOPE),--scope $(EXCLUDE_SCOPE),)

selftest: ## Самопроверка расчёта + валидация критериев
	@$(CLI) criteria check --no-next
	@$(CLI) score --selftest --no-next

docs-sync: ## Перегенерировать таблицы docs/02 из критериев (ищется в проекте, затем в скилле)
	@$(CLI) criteria sync-docs --no-next

docs-check: ## Проверить таблицы docs/02 (ищется в проекте, затем в скилле; нигде нет — WARN, код 0)
	@$(CLI) criteria sync-docs --check --no-next

verify-titles: ## Сверить заголовки страниц Confluence с сохранёнными: make verify-titles [IS=...] [FIX=1]
	@$(CLI) verify-titles $(if $(IS),--is $(IS),) $(if $(filter 1,$(FIX)),--fix,)

research: ## Сбор доказательств по открытым входам (Confluence): make research [IS=...] [INPUT=e2e] [TIMEOUT=300] [ALLOW_PARTIAL=1]
	@$(CLI) research $(if $(IS),--is $(IS),) $(if $(INPUT),--input $(INPUT),) $(if $(TIMEOUT),--timeout $(TIMEOUT),) $(if $(filter 1,$(ALL)),--all,) $(if $(filter 1,$(ALLOW_PARTIAL)),--allow-partial,)

verify: ## Все гейты одним вызовом: criteria-check, selftest, validate, docs-check, verify-titles, skill-check
	@tmp=$$(mktemp -d); status=0; gates=0; errors=0; warns=0; failed=""; \
	for name in criteria-check selftest validate docs-check verify-titles skill-check; do \
		gates=$$((gates+1)); \
		$(MAKE) --no-print-directory -f $(SELF_MAKEFILE) $$name ROOT=$(ROOT) > "$$tmp/$$name.log" 2>&1; rc=$$?; \
		e=$$(grep -cE '^[[:space:]]*ERROR' "$$tmp/$$name.log"); w=$$(grep -cE '^[[:space:]]*WARN' "$$tmp/$$name.log"); \
		errors=$$((errors+e)); warns=$$((warns+w)); \
		if [ $$rc -eq 0 ]; then \
			printf '  %-16s OK   (ERROR %s, WARN %s)\n' "$$name" "$$e" "$$w"; \
		else \
			status=1; failed="$$failed $$name"; \
			printf '  %-16s FAIL (ERROR %s, WARN %s)\n' "$$name" "$$e" "$$w"; \
		fi; \
	done; \
	rm -rf "$$tmp"; \
	echo ""; \
	echo "ИТОГО: $$gates гейтов, $$errors ошибок, $$warns предупреждений"; \
	if [ $$status -eq 0 ]; then echo "Результат: OK"; else echo "Результат: FAIL — провалены:$$failed"; exit 1; fi

start: ## Генерация артефактов, dry-run по умолчанию: make start [IS=erm.mm] [DIFF=1] [DRY=0] [TASK=1]
	@$(CLI) start $(if $(IS),--is $(IS),) $(if $(DATE),--date $(DATE),) $(if $(filter 1,$(DIFF)),--diff,) $(if $(filter 1,$(REASSESSMENT)),--reassessment,) $(if $(filter 1,$(NO_REQUIREMENTS)),--no-requirements,) $(if $(filter 1,$(TASK)),--create-task,) $(if $(filter 1,$(DRY)),--dry-run,)

start-apply: ## Записать артефакты: make start-apply [IS=...] [FORCE=1] [REASSESSMENT=1] [TASK=1] [CONFLUENCE=1] [MESSAGE=1]
	@$(CLI) start $(if $(IS),--is $(IS),) $(if $(DATE),--date $(DATE),) $(if $(filter 1,$(FORCE)),--force,) $(if $(filter 1,$(REASSESSMENT)),--reassessment,) $(if $(filter 1,$(NO_REQUIREMENTS)),--no-requirements,) $(if $(filter 1,$(TASK)),--create-task,) $(if $(filter 1,$(CONFLUENCE)),--create-confluence,) $(if $(filter 1,$(MESSAGE)),--create-message,)

ssot: ## Обогащение SSoT критичностью (dry-run): make ssot IS=erm.mm TASK=E001-31245 [SSOT=путь] [BRANCH=имя] [PASSPORT_MR_URL=...]
	@if [ -z "$(IS)" ]; then echo "ERROR: укажите IS=<код ИС>, например: make ssot IS=erm.mm TASK=E001-31245"; exit 1; fi
	@$(CLI) ssot --is $(IS) $(if $(TASK),--task $(TASK),) $(if $(SSOT),--ssot $(SSOT),) $(if $(BRANCH),--branch $(BRANCH),) $(if $(PASSPORT_MR_URL),--passport-mr-url $(PASSPORT_MR_URL),)

ssot-apply: ## Ветка и коммит в клоне SSoT: make ssot-apply IS=... TASK=... [SSOT=...] [BRANCH=...] [PASSPORT_MR_URL=...] [PUSH=1]
	@if [ -z "$(IS)" ]; then echo "ERROR: укажите IS=<код ИС>, например: make ssot-apply IS=erm.mm TASK=E001-31245"; exit 1; fi
	@$(CLI) ssot --is $(IS) --apply $(if $(TASK),--task $(TASK),) $(if $(SSOT),--ssot $(SSOT),) $(if $(BRANCH),--branch $(BRANCH),) $(if $(PASSPORT_MR_URL),--passport-mr-url $(PASSPORT_MR_URL),) $(if $(filter 1,$(PUSH)),--push,)
	@echo "ВНИМАНИЕ: MR из ветки feature/<task> не пройдёт джоб codeowners для путей entities/**."
	@echo "Нужен @codeowners approve от maintainer'а проекта (access level >= 40), иначе MR останется красным."
	@echo "Для severity.* дополнительно требуется один апрув SRE/техархитектуры — см. references/data-sources.md."

ssot-mr: ## Обновить описание существующего SSoT-MR (dry-run): make ssot-mr IS=... TASK=... [PASSPORT_MR_URL=...]
	@if [ -z "$(IS)" ]; then echo "ERROR: укажите IS=<код ИС>, например: make ssot-mr IS=erm.mm TASK=E001-31245"; exit 1; fi
	@$(CLI) ssot --is $(IS) --update-mr $(if $(TASK),--task $(TASK),) $(if $(SSOT),--ssot $(SSOT),) $(if $(BRANCH),--branch $(BRANCH),) $(if $(PASSPORT_MR_URL),--passport-mr-url $(PASSPORT_MR_URL),)

handoff: ## Этап handoff: спросить и отправить тред в #Criticality_assessment: make handoff IS=... [SEND=auto|manual] [TRANSPORT=auto|mcp|api] [DRY_RUN=1] [WRITE=1] [ALLOW_INCOMPLETE=1] [FORCE_RESEND=1] [RESUME=1] [MCP_TIMEOUT=сек] [ALLOW_DUPLICATE_RISK=1]
	@if [ -n "$(ARGS)" ]; then \
		$(CLI) handoff $(if $(IS),--is $(IS),) $(ARGS); \
	else \
		if [ -z "$(IS)" ]; then echo "ERROR: укажите IS=<код ИС>, например: make handoff IS=erm.mm"; exit 1; fi; \
		$(CLI) handoff --is $(IS) $(if $(SEND),--send $(SEND),) $(if $(TRANSPORT),--transport $(TRANSPORT),) $(if $(filter 1,$(FORCE_RESEND)),--force-resend,) $(if $(filter 1,$(RESUME)),--resume,) $(if $(MCP_TIMEOUT),--mcp-timeout $(MCP_TIMEOUT),) $(if $(filter 1,$(ALLOW_DUPLICATE_RISK)),--allow-duplicate-risk,) $(if $(filter 1,$(ALLOW_INCOMPLETE)),--allow-incomplete,) $(if $(filter 1,$(WRITE)),--write,) $(if $(filter 1,$(DRY_RUN)),--dry-run,); \
	fi

finalize: ## Финализация ИС одной командой (approve_link, даты, критичность, status=confirmed + гейты): make finalize IS=... [APPROVE_LINK=...] [ASSIGNED_DATE=YYYY-MM-DD] [REVIEW_DATE=YYYY-MM-DD] [DRY_RUN=1]
	@if [ -z "$(IS)" ]; then echo "ERROR: укажите IS=<код ИС>, например: make finalize IS=erm.mm"; exit 1; fi
	@$(CLI) finalize --is $(IS) $(if $(APPROVE_LINK),--approve-link "$(APPROVE_LINK)",) $(if $(ASSIGNED_DATE),--assigned-date $(ASSIGNED_DATE),) $(if $(REVIEW_DATE),--review-date $(REVIEW_DATE),) $(if $(filter 1,$(DRY_RUN)),--dry-run,)

handoff-result: ## Результат MCP-отправки: make handoff-result IS=... MESSAGE_URL=<ссылка> | FAILED="причина" [FORCE_RESEND=1] [ALLOW_DUPLICATE_RISK=1]
	@if [ -z "$(IS)" ]; then echo "ERROR: укажите IS=<код ИС>, например: make handoff-result IS=erm.mm MESSAGE_URL=..."; exit 1; fi
	@$(CLI) handoff-result --is $(IS) $(if $(MESSAGE_URL),--message-url "$(MESSAGE_URL)",) $(if $(FAILED),--failed "$(FAILED)",) $(if $(filter 1,$(FORCE_RESEND)),--force-resend,) $(if $(filter 1,$(ALLOW_DUPLICATE_RISK)),--allow-duplicate-risk,) $(if $(filter 1,$(DRY_RUN)),--dry-run,)

handoff-apply: ## Отправка в #Criticality_assessment (REST, необратимо): make handoff-apply IS=... CONFIRM=1 [DATE=...] [FORCE=1] [ALLOW_INCOMPLETE=1]
	@if [ -z "$(IS)" ]; then echo "ERROR: укажите IS=<код ИС>, например: make handoff-apply IS=erm.mm"; exit 1; fi
	@if [ "$(CONFIRM)" != "1" ]; then echo "ERROR: handoff-apply требует CONFIRM=1: отправка сообщения в канал необратима"; exit 1; fi
	@$(CLI) handoff-apply --is $(IS) $(if $(filter 1,$(CONFIRM)),--confirm,) $(if $(DATE),--date $(DATE),) $(if $(filter 1,$(FORCE)),--force-resend,) $(if $(filter 1,$(ALLOW_INCOMPLETE)),--allow-incomplete,)

ssot-mr-apply: ## Переписать описание SSoT-MR по шаблону (PUT): make ssot-mr-apply IS=... TASK=... [PASSPORT_MR_URL=...]
	@if [ -z "$(IS)" ]; then echo "ERROR: укажите IS=<код ИС>, например: make ssot-mr-apply IS=erm.mm TASK=E001-31245"; exit 1; fi
	@$(CLI) ssot --is $(IS) --update-mr --apply $(if $(TASK),--task $(TASK),) $(if $(SSOT),--ssot $(SSOT),) $(if $(BRANCH),--branch $(BRANCH),) $(if $(PASSPORT_MR_URL),--passport-mr-url $(PASSPORT_MR_URL),)

publish: ## Публикация паспорта в dochub (dry-run): make publish IS=erm.mm TASK=E001-31245 [DOCHUB=путь] [BRANCH=имя]
	@if [ -z "$(IS)" ]; then echo "ERROR: укажите IS=<код ИС>, например: make publish IS=erm.mm TASK=E001-31245"; exit 1; fi
	@$(CLI) publish --is $(IS) $(if $(TASK),--task $(TASK),) $(if $(DOCHUB),--dochub $(DOCHUB),) $(if $(BRANCH),--branch $(BRANCH),)

publish-apply: ## Ветка и коммит в клоне dochub: make publish-apply IS=... TASK=... [DOCHUB=...] [BRANCH=...] [UPDATE=1] [REUSE=1] [PUSH=1]
	@if [ -z "$(IS)" ]; then echo "ERROR: укажите IS=<код ИС>, например: make publish-apply IS=erm.mm TASK=E001-31245"; exit 1; fi
	@$(CLI) publish --is $(IS) --apply $(if $(TASK),--task $(TASK),) $(if $(DOCHUB),--dochub $(DOCHUB),) $(if $(BRANCH),--branch $(BRANCH),) $(if $(filter 1,$(UPDATE)),--update,) $(if $(filter 1,$(REUSE)),--reuse-local,) $(if $(filter 1,$(PUSH)),--push,)

# Установка инструмента в ДРУГОЙ проект: TARGET=/путь, по умолчанию — текущий каталог.
skill-install: ## Установить скилл в другой проект: make skill-install TARGET=/путь [FORCE=1]
	@bash $(SKILL_DIR)/install.sh --project "$(if $(TARGET),$(TARGET),$(ROOT))" $(if $(filter 1,$(FORCE)),--force,)

skill-uninstall: ## Удалить установленный скилл из другого проекта: make skill-uninstall TARGET=/путь
	@bash $(SKILL_DIR)/install.sh --uninstall --project "$(if $(TARGET),$(TARGET),$(ROOT))"

skill-check: ## Проверить структуру скилла: frontmatter, references, отсутствие плейсхолдеров
	@set -e; \
	skill=$(SKILL_DIR); \
	test -f $$skill/SKILL.md || { echo "ERROR: нет $$skill/SKILL.md"; exit 1; }; \
	[ "$$(head -1 $$skill/SKILL.md)" = "---" ] || { echo "ERROR: SKILL.md не начинается с frontmatter (---)"; exit 1; }; \
	grep -qx 'name: criticality-gen' $$skill/SKILL.md || { echo "ERROR: name в frontmatter не совпадает с каталогом criticality-gen"; exit 1; }; \
	for key in version description user-invocable compatibility allowed-tools; do \
		grep -q "^$$key:" $$skill/SKILL.md || { echo "ERROR: нет поля $$key в frontmatter"; exit 1; }; \
	done; \
	refs=$$(ls $$skill/references/*.md 2>/dev/null | wc -l); \
	test $$refs -gt 0 || { echo "ERROR: в $$skill/references нет ни одного *.md"; exit 1; }; \
	for p in $$skill/references/*.md; do \
		f=$$(basename $$p .md); \
		test -f $$skill/references/$$f.md || { echo "ERROR: нет $$skill/references/$$f.md"; exit 1; }; \
		grep -q "references/$$f.md" $$skill/SKILL.md || { echo "ERROR: references/$$f.md не упомянут в SKILL.md"; exit 1; }; \
	done; \
	refs_list=$$(ls $$skill/references/*.md | xargs -n1 basename | sed 's/\.md$$//' | sort | paste -sd, - | sed 's/,/, /g'); \
	if grep -rn '{{' $$skill/SKILL.md $$skill/references 2>/dev/null; then \
		echo "ERROR: в SKILL.md/references остались незаполненные плейсхолдеры {{ }}"; exit 1; \
	fi; \
	missing=0; \
	for ref in $$(grep -oE 'references/[a-z-]+\.md' $$skill/SKILL.md | sort -u); do \
		test -f $$skill/$$ref || { echo "ERROR: ссылка $$ref из SKILL.md не существует"; missing=1; }; \
	done; \
	test $$missing -eq 0 || exit 1; \
	test -f $(abspath $(dir $(lastword $(MAKEFILE_LIST)))commands/criticality_gen.md) || { echo "ERROR: нет .opencode/commands/criticality_gen.md"; exit 1; }; \
	test -f $$skill/scripts/criticality.py || { echo "ERROR: нет $$skill/scripts/criticality.py"; exit 1; }; \
	test -f $$skill/criteria/criticality-criteria.yaml || { echo "ERROR: нет $$skill/criteria/criticality-criteria.yaml"; exit 1; }; \
	for t in criticality-passport.yaml CRITICALITY.md GENERATION.md publication.md MR-dochub.md MR-ssot.md INFORMATION.yaml ASK.md CANDIDATES.yaml ANSWERS.yaml actions/jira-task.md actions/confluence-page.md actions/rocketchat-message.md; do \
		test -f $$skill/templates/$$t || { echo "ERROR: нет $$skill/templates/$$t"; exit 1; }; \
	done; \
	echo "OK: frontmatter корректен (name, version, description, user-invocable, compatibility, allowed-tools)"; \
	echo "OK: $$refs references на месте ($$refs_list)"; \
	echo "OK: ссылки из SKILL.md на references существуют"; \
	echo "OK: scripts/, criteria/, templates/ внутри скилла на месте"; \
	echo "OK: .opencode/commands/criticality_gen.md на месте"; \
	echo "OK: плейсхолдеров {{ }} в SKILL.md/references нет"
