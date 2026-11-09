#!/usr/bin/env python3
# =============================================================================
# sloth-normalize.py — нормализация configs/slo-kit.yaml после slokit generate.
# -----------------------------------------------------------------------------
# Текущий slo-kit (v26.10.1) отклоняет некоторые rule type'ы для профиля
# ecomtech-letsgo, которые slokit может сгенерировать для external-адаптеров:
#   oif      -> 'oif is not supported for letsgo'
#   outgoing -> 'unknown rule type key outgoing'
#
# Нормализация преобразует такие группы в поддерживаемые формы:
#   oif: [...]  -> custom (error_ratio_query по http_outgoing_requests_*)
#                   + custom_latency (metric http_outgoing_requests_duration_seconds)
#
# Использование:
#   python3 sloth-normalize.py <configs/slo-kit.yaml>   # in-place
# =============================================================================
import sys

try:
    import yaml
except ImportError:
    print("PyYAML не установлен", file=sys.stderr)
    sys.exit(2)


def normalize(path):
    with open(path, "r", encoding="utf-8") as f:
        d = yaml.safe_load(f) or {}

    profile = d.get("profile", "")
    groups = d.get("groups") or {}
    changed = False

    for gname, g in groups.items():
        co = g.get("consists_of") or {}
        if "oif" in co:
            oifs = co.pop("oif")
            customs = []
            lat = []
            for o in oifs:
                name = o.get("name", "oif")
                desc = o.get("description", "External HTTP integration")
                customs.append({
                    "name": name,
                    "description": desc,
                    "error_ratio_query": (
                        'sum(rate(http_outgoing_requests_total{status!~"2..|3.."}'
                        '[{{.window}}])) / '
                        '(sum(rate(http_outgoing_requests_total[{{.window}}])) or vector(0))'
                    ),
                })
                lat.append({
                    "name": f"{name}-latency",
                    "description": f"Latency {desc}",
                    "metric_name": "http_outgoing_requests_duration_seconds",
                    "threshold": "0.5",
                })
            co["custom"] = customs
            co.setdefault("custom_latency", [])
            co["custom_latency"] += lat
            changed = True
            print(f"[normalize] group '{gname}': oif -> custom + custom_latency (profile={profile})")

        if "jobs" in co:
            jobs = co.pop("jobs")
            customs = []
            lat = []
            for j in jobs:
                q = j.get("queue", "?")
                name = j.get("name") or f"job-{q}"
                desc = j.get("description", f"Background job ({q})")
                customs.append({
                    "name": name,
                    "description": desc,
                    "error_ratio_query": (
                        'sum(rate(background_jobs_failure{queue="%s"}[{{.window}}])) / '
                        '(sum(rate(background_jobs_total{queue="%s"}[{{.window}}])) or vector(0))'
                        % (q, q)
                    ),
                })
                lat.append({
                    "name": f"{name}-latency",
                    "description": f"Latency {desc}",
                    "metric_name": "background_jobs_duration_seconds",
                    "threshold": "5",
                })
            co["custom"] = customs
            co.setdefault("custom_latency", [])
            co["custom_latency"] += lat
            changed = True
            print(f"[normalize] group '{gname}': jobs -> custom + custom_latency (profile={profile})")

    if changed:
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(d, f, allow_unicode=True, sort_keys=False)
    return 0


if __name__ == "__main__":
    sys.exit(normalize(sys.argv[1] if len(sys.argv) > 1 else "configs/slo-kit.yaml"))