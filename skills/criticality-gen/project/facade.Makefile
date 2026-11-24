# Точка входа. Инструмент живёт в .opencode/ (см. README.md).
# Все цели и переменные (IS=, FORCE=, DATE=, NO_CLONE=, DRY=, TARGET=...) —
# в .opencode/Makefile. ROOT фиксируется на корне проекта, из которого вызван make.
.DEFAULT_GOAL := help

# Цель `ssot` совпадает по имени с каталогом клона SSoT (`ssot/`): без явного
# правила и .PHONY make считает её «уже существующей» и ничего не запускает
# (для .PHONY неявный `%:` не применяется — поэтому правило задано явно).
.PHONY: ssot ssot-apply

ssot ssot-apply:
	@$(MAKE) --no-print-directory -f .opencode/Makefile $@ ROOT=$(CURDIR) $(filter-out $@,$(MAKECMDGOALS))

%:
	@$(MAKE) --no-print-directory -f .opencode/Makefile $@ ROOT=$(CURDIR) $(filter-out $@,$(MAKECMDGOALS))
