"""Включает `python3 -m trr_impl <подкоманда> ...` (запуск из каталога
`scripts/`, где лежит пакет `trr_impl/`) как альтернативу исполняемому файлу
`scripts/trr` — обе точки входа вызывают `cli.main()`."""

import sys

# Та же причина, что и в `scripts/trr`: не оставлять `__pycache__` в каталоге
# скилла. Флаг работает для всех модулей, импортируемых после этой строки;
# байткод самого пакета (`__init__.py`) интерпретатор пишет до её выполнения —
# для полной чистоты запускайте через `scripts/trr` или с
# `PYTHONDONTWRITEBYTECODE=1`.
sys.dont_write_bytecode = True

from . import cli

if __name__ == "__main__":
    raise SystemExit(cli.main(sys.argv[1:], invocation="python3 -m trr_impl"))
