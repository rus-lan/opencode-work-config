#!/usr/bin/env python3
# =============================================================================
# sloth-parse.py — чтение services-slogen.yaml и вывод списка сервисов TSV.
# -----------------------------------------------------------------------------
# Вывод (одна строка на сервис, поля разделены табом):
#   <name>\t<namespace>\t<company>\t<repo>\t<profile>\t<team>\t<cost_centre>\t<helm|...>
#
# Используется generate-sloth.sh вместо парсинга services-md-файла.
# =============================================================================
import sys

try:
    import yaml
except ImportError:
    print("PyYAML не установлен (pip install pyyaml)", file=sys.stderr)
    sys.exit(2)


def main(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except FileNotFoundError:
        print(f"Нет файла {path}", file=sys.stderr)
        sys.exit(2)

    services = data.get("services", []) if isinstance(data, dict) else []
    for svc in services:
        name = svc.get("name", "")
        ns = svc.get("namespace", "")
        company = svc.get("company", "")
        repo = svc.get("repo", "")
        profile = svc.get("profile", "")
        team = svc.get("team", "")
        cc = svc.get("cost_centre", "")
        helm = svc.get("helm") or []
        helm_cell = "|".join(h for h in helm if h)
        print(f"{name}\t{ns}\t{company}\t{repo}\t{profile}\t{team}\t{cc}\t{helm_cell}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "services-slogen.yaml")