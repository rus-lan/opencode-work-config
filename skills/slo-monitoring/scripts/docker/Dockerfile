# =============================================================================
# Dockerfile — изолированная среда для проверки генерации SLO (команда /sloth).
# Базовый образ — opencode (Alpine). Поверх доставляются только базовые
# зависимости; SLO-бинарники (slokit/slo-kit), проект и git-креды монтируются
# при запуске (см. docker/run.sh), чтобы не раздувать образ и не зашивать секреты.
#
# Сборка:
#   docker build -t sloth-verify -f docker/Dockerfile docker/
#
# Запуск (см. docker/run.sh):
#   docker run --rm -it \
#     -v "$PWD:/workspace" \
#     -v "$HOME/.local/bin/slokit:/usr/local/bin/slokit" \
#     -v "$HOME/.local/bin/slo-kit:/usr/local/bin/slo-kit" \
#     -v "$HOME/.netrc:/root/.netrc:ro" \
#     -v "$HOME/.ssh:/root/.ssh:ro" \
#     sloth-verify /workspace/docker/run-in-container.sh <name>
# =============================================================================
FROM ghcr.io/anomalyco/opencode:2.0.28

# git (клонирование), python3 + pyyaml (sloth-parse.py / services-slogen.yaml),
# bash (скрипты)
RUN apk add --no-cache git python3 py3-yaml bash ca-certificates \
    && python3 -c "import yaml; print('PyYAML', yaml.__version__)" \
    && opencode --version

WORKDIR /workspace
ENTRYPOINT ["/bin/bash"]