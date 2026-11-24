#!/usr/bin/env bash
# Сборка релизного бандла task-readiness-review в dist/release/:
#   task-readiness-review-<ver>.tar.gz - рантайм-файлы скилла (внутри каталог
#                                        task-readiness-review/)
#   task-readiness-review.tar.gz       - тот же архив под стабильным именем:
#                                        по нему install.sh в удалённом режиме
#                                        скачивает пакет из Registry, а
#                                        components.yaml объявляет asset
#   install.sh                         - копируется без изменений, скачивается
#                                        curl-однострочником
#   checksums-sha256.txt               - sha256 по всем файлам выше
#
# Usage: scripts/release.sh [VERSION]
#   VERSION по умолчанию берётся из ./VERSION. Если аргумент задан, он должен
#   совпадать с ./VERSION точно -- это единственный источник версии проекта, и
#   расхождение (например, забыли поднять VERSION перед тегом) жёстко падает,
#   а не выпускает «не то» число.
#
# Требования к бандлу: templates/, schemas/, commands/ и пример конфига
# обязательны. Без них установленный скилл не работает (нет шаблонов, схем и
# слэш-команд), поэтому отсутствие любого элемента -- ошибка сборки, а не
# молчаливый пропуск.
set -euo pipefail

cd "$(dirname "$0")/.."

VERSION="${1:-}"
PKG_VERSION="$(tr -d '[:space:]' < VERSION)"
if [ -z "$VERSION" ]; then
  VERSION="$PKG_VERSION"
elif [ "$VERSION" != "$PKG_VERSION" ]; then
  echo "VERSION argument ($VERSION) does not match the VERSION file ($PKG_VERSION)." >&2
  echo "Bump the VERSION file to $VERSION first, or pass no argument to release the current version." >&2
  exit 1
fi
TAG="v${VERSION}"

SKILL_VERSION="$(sed -n 's/^version: *//p' SKILL.md | head -1 | tr -d '[:space:]')"
if [ "$SKILL_VERSION" != "$PKG_VERSION" ]; then
  echo "SKILL.md frontmatter version ($SKILL_VERSION) does not match the VERSION file ($PKG_VERSION)." >&2
  echo "Update SKILL.md's 'version:' field to $PKG_VERSION first." >&2
  exit 1
fi

SKILL_NAME="task-readiness-review"
OUT_DIR="dist/release"
STAGE_DIR="dist/stage/${SKILL_NAME}"
TARBALL_NAME="${SKILL_NAME}-${VERSION}.tar.gz"
STABLE_TARBALL_NAME="${SKILL_NAME}.tar.gz"
INSTALL_SCRIPT="install.sh"

# Рантайм-бандл -- должен совпадать с install.sh's BUNDLE_ITEMS: один и тот же
# каталог копируется при локальной установке из клона и распаковывается из
# архива релиза. tests/ и evals/ в бандл не входят: рантайм их не читает.
# install.sh кладётся отдельно (не внутрь архива).
BUNDLE_ITEMS="SKILL.md README.md VERSION references scripts templates schemas commands task-readiness-review.example.yaml"

if [ ! -f "$INSTALL_SCRIPT" ]; then
  echo "install script not found: $INSTALL_SCRIPT" >&2
  exit 1
fi

rm -rf "dist/stage" "$OUT_DIR"
mkdir -p "$STAGE_DIR" "$OUT_DIR"

echo "Staging ${SKILL_NAME} v${VERSION}..."
for item in $BUNDLE_ITEMS; do
  if [ ! -e "$item" ]; then
    echo "missing bundle item: $item" >&2
    exit 1
  fi
  cp -R "$item" "$STAGE_DIR/$item"
done

# Байткод Python не входит в релиз: он не нужен рантайму, ломает
# воспроизводимость сборки и тянет пути машины, где её делали.
find "$STAGE_DIR" -type d -name '__pycache__' -prune -exec rm -rf {} + 2>/dev/null || true
find "$STAGE_DIR" -type f -name '*.pyc' -delete 2>/dev/null || true

# Исполняемость сохраняется в архиве: диспетчер запускают напрямую.
chmod 0755 "$STAGE_DIR/scripts/trr"

echo "Packing $TARBALL_NAME..."
( cd dist/stage && tar czf "$OLDPWD/$OUT_DIR/$TARBALL_NAME" \
    --exclude='__pycache__' --exclude='*.pyc' "$SKILL_NAME" )
rm -rf dist/stage

# Стабильное имя: по нему удалённая установка и Registry находят пакет,
# не завися от номера версии в имени файла.
cp "$OUT_DIR/$TARBALL_NAME" "$OUT_DIR/$STABLE_TARBALL_NAME"

echo "Copying $INSTALL_SCRIPT..."
cp "$INSTALL_SCRIPT" "$OUT_DIR/install.sh"
chmod 0755 "$OUT_DIR/install.sh"

echo "Generating SHA256 checksums..."
( cd "$OUT_DIR" && sha256sum -- * > checksums-sha256.txt )

echo ""
echo "Built release ${TAG} in $OUT_DIR:"
ls -la "$OUT_DIR"
