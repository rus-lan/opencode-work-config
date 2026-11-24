"""Реализация диспетчера скилла task-readiness-review (stdlib, без сети).

Python 3.9+. Две точки входа, обе ведут в `trr_impl.cli.main()`:

    <skill>/scripts/trr <подкоманда> ...        # исполняемый файл
    python3 -m trr_impl <подкоманда> ...        # из каталога scripts/

Карта модулей:
    cli           разбор подкоманд, коды выхода, печать диагностики
    config        чтение, нормализация и валидация task-readiness-review.yaml
    state         .task-readiness/state.json
    doctor        диагностика окружения и артефактов (`trr doctor`)
    schema_lite   валидатор подмножества JSON Schema + канонический JSON
    yamlmini      минимальный YAML-парсер

Модули дорожек (`stats`, `calibrate`, `check`, `estimate`, `report`) подключаются
лениво: пока их нет, подкоманда печатает `[BLOCKED]` и выходит с кодом 2.
"""

__all__ = ["cli", "config", "doctor", "schema_lite", "state", "yamlmini"]
