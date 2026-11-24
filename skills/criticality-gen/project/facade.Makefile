# Точка входа. Инструмент живёт в .opencode/ (см. README.md).
# Все цели и переменные (IS=, FORCE=, DATE=, NO_CLONE=, DRY=, TARGET=...) —
# в .opencode/Makefile. ROOT фиксируется на корне проекта, из которого вызван make.
.DEFAULT_GOAL := help

%:
	@$(MAKE) --no-print-directory -f .opencode/Makefile $@ ROOT=$(CURDIR) $(filter-out $@,$(MAKECMDGOALS))
