#!/usr/bin/env bash
# =============================================================================
# docker/run.sh — запуск сценария генерации SLO в изолированном контейнере.
# -----------------------------------------------------------------------------
# Собирает контейнер sloth-verify (opencode base + git/python3/yaml) и запускает
# внутри него generate-sloth.sh для проверки полного сценария в чистой среде.
#
# Проект (./ = workspace), SLO-бинарники и git-креды (./.netrc, ./.ssh)
# монтируются как тома — ничего не копируется внутрь образа и ничего не
# зашивается в него.
#
# Использование (из корня набора):
#   ./docker/run.sh                 # сборка + прогон всех сервисов
#   ./docker/run.sh <service>       # прогон одного сервиса
#   ./docker/run.sh --skip-git      # не трогать git-ветки
#   ./docker/run.sh --no-clone      # не клонировать (использовать ./apps/*)
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
IMAGE="sloth-verify"
CONTAINER_NAME="sloth-verify-run"

cd "$ROOT"

# --- сборка образа ---
echo "[docker] Сборка образа $IMAGE ..."
docker build -t "$IMAGE" -f docker/Dockerfile docker/

# helm-репо теперь клонируется из git.ecom.tech/ecom/cicd/<company>/helm внутри
# контейнера в ./helm/<company> (см. generate-sloth.sh), отдельные тома не нужны.

# Внутренний DNS корпоративной сети: контейнер по умолчанию не видит его.
# Пробрасываем nameserver'ы из resolv.conf host'а, чтобы git.ecom.tech резолвился.
DNS_ARGS=()
while read -r ns; do
  DNS_ARGS+=("--dns" "$ns")
done < <(awk '/^nameserver/{print $2}' /etc/resolv.conf)
if [[ ${#DNS_ARGS[@]} -gt 0 ]]; then
  echo "[docker] пробрасываю DNS: ${DNS_ARGS[*]}"
fi

# --- аргументы для generate-sloth.sh, переданные скрипту ---
ARGS=("$@")

# --- передаём host UID/GID, чтобы контейнер вернул владельца файлов ---
HOST_UID="$(id -u)"
HOST_GID="$(id -g)"
echo "[docker] host uid/gid: $HOST_UID/$HOST_GID"

# --- удостоверяемся, что бинарники на host есть ---
[[ -f "$HOME/.local/bin/slokit" ]] || { echo "[docker] нет slokit ($HOME/.local/bin/slokit)"; exit 1; }
[[ -f "$HOME/.local/bin/slo-kit" ]] || { echo "[docker] нет slo-kit ($HOME/.local/bin/slo-kit)"; exit 1; }

echo "[docker] Запуск изолированного прогона в $IMAGE ..."
echo "[docker] Команда: generate-sloth.sh ${ARGS[*]:-<all>}"

# docker cleanup на выходе
cleanup() { docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true; }
trap cleanup EXIT

docker run --rm --name "$CONTAINER_NAME" \
  -e HOST_UID="$HOST_UID" -e HOST_GID="$HOST_GID" \
  -v "$ROOT:/workspace" \
  -v "$HOME/.local/bin/slokit:/usr/local/bin/slokit" \
  -v "$HOME/.local/bin/slo-kit:/usr/local/bin/slo-kit" \
  -v "$HOME/.netrc:/root/.netrc:ro" \
  -v "$HOME/.ssh:/root/.ssh:ro" \
  "${DNS_ARGS[@]+"${DNS_ARGS[@]}"}" \
  "$IMAGE" /workspace/docker/run-in-container.sh "${ARGS[@]:-}"

echo "[docker] восстановление владельца сгенерированных файлов -> host uid/gid..."
docker run --rm --entrypoint "" \
  -v "$ROOT:/workspace" \
  -e HOST_UID="$HOST_UID" -e HOST_GID="$HOST_GID" \
  "$IMAGE" sh -c 'for d in /workspace/apps /workspace/.sloth-logs /workspace/helm; do [ -d "$d" ] && chown -R "$HOST_UID:$HOST_GID" "$d"; done' 2>/dev/null || true

echo "[docker] Готово. apps/ и helm/ обновлены в изолированной среде; см. .sloth-logs/."