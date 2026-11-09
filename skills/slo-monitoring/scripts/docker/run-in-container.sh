#!/usr/bin/env bash
# =============================================================================
# docker/run-in-container.sh — выполняется ВНУТРИ контейнера sloth-verify.
# Просто запускает generate-sloth.sh с переданными аргументами из /workspace.
# =============================================================================
set -euo pipefail

# Git (>=2.35.2, patched for CVE-2022-24765) refuses to operate on repositories
# owned by a user other than the current one ("detected dubious ownership").
# In this container git runs as root, but repos are cloned once and may later be
# chown'ed to the host uid by run.sh to fix ownership of generated files.
# Without this, every re-run of the skill hits "dubious ownership" and silently
# fails all git pull/checkout/branch operations. The container is used solely for
# this isolated /workspace, so a blanket safe.directory is appropriate here.
git config --global --add safe.directory '*'

cd /workspace

echo "[inside] opencode: $(opencode --version 2>/dev/null || echo n/a)"
echo "[inside] git:      $(git --version 2>/dev/null || echo 'NO git')"
echo "[inside] python3:  $(python3 --version 2>/dev/null || echo n/a)"
echo "[inside] slokit:   $(command -v slokit || echo NO)"
echo "[inside] slo-kit:  $(command -v slo-kit && slo-kit --version 2>/dev/null || echo NO)"
echo

ARGS=("$@")
if [[ ${#ARGS[@]} -eq 0 ]]; then
  echo "[inside] Полный прогон всех сервисов..."
  bash generate-sloth.sh
else
  echo "[inside] Прогон: generate-sloth.sh ${ARGS[*]}"
  bash generate-sloth.sh "${ARGS[@]}"
fi