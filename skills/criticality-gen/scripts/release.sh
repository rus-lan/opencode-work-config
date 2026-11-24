#!/usr/bin/env bash
# Build the source release bundle for criticality-gen into dist/release/:
#   criticality-gen.tar.gz  - runtime files only (what the skill needs)
#   install.sh              - copied in unmodified, downloaded by curl one-liner
#   checksums-sha256.txt    - sha256 over the two files above
#
# Usage: scripts/release.sh [VERSION] [--dry-run]
#   VERSION defaults to the contents of ./VERSION. If given, it must match
#   ./VERSION exactly -- this is the single source of truth for the project
#   version, and a mismatch (e.g. forgetting to bump VERSION before tagging)
#   hard-fails instead of silently releasing the wrong number.
#   --dry-run prints the plan (files, sizes, checks) and writes nothing.
set -euo pipefail

cd "$(dirname "$0")/.."

DRY_RUN=0
VERSION=""
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    -h|--help)
      sed -n '2,15p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    -*)
      echo "unknown flag: $arg" >&2
      exit 2
      ;;
    *)
      if [ -n "$VERSION" ]; then
        echo "unexpected extra argument: $arg" >&2
        exit 2
      fi
      VERSION="$arg"
      ;;
  esac
done

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

SKILL_NAME="criticality-gen"
OUT_DIR="dist/release"
STAGE_DIR="dist/stage/${SKILL_NAME}"
TARBALL_NAME="${SKILL_NAME}.tar.gz"
INSTALL_SCRIPT="install.sh"

# Runtime bundle -- must match install.sh's BUNDLE_ITEMS exactly, since the
# same directory is what LOCAL install.sh copies from a checkout and what
# REMOTE install.sh extracts and installs from. meta-templates/ is deliberately
# left out: it is authoring material for creating NEW skills, nothing at
# runtime reads it. commands/ and project/ are IN: the installed copy is
# self-contained (command /criticality_gen and the project payload travel with
# the skill). install.sh is also IN: `make selftest` (D6) reads it from the
# skill directory and the installed copy stays self-sufficient. It is copied
# into dist/release/ as a standalone asset as well.
BUNDLE_ITEMS="SKILL.md README.md VERSION CHANGELOG.md criteria templates references docs scripts commands project install.sh"

# BUNDLE_ITEMS в install.sh и release.sh обязаны совпадать побайтово: иначе
# локальная установка из клона и удалённая из архива дадут разные наборы
# файлов. Сверяем программно, а не глазами.
INSTALL_ITEMS="$(sed -n 's/^BUNDLE_ITEMS="\(.*\)"$/\1/p' "$INSTALL_SCRIPT" | head -1)"
if [ -z "$INSTALL_ITEMS" ]; then
  echo "could not read BUNDLE_ITEMS from $INSTALL_SCRIPT." >&2
  exit 1
fi
if [ "$INSTALL_ITEMS" != "$BUNDLE_ITEMS" ]; then
  echo "BUNDLE_ITEMS mismatch between $INSTALL_SCRIPT and scripts/release.sh:" >&2
  echo "  install.sh:   $INSTALL_ITEMS" >&2
  echo "  release.sh:   $BUNDLE_ITEMS" >&2
  exit 1
fi

if [ ! -f "$INSTALL_SCRIPT" ]; then
  echo "install script not found: $INSTALL_SCRIPT" >&2
  exit 1
fi

for item in $BUNDLE_ITEMS; do
  if [ ! -e "$item" ]; then
    echo "missing bundle item: $item" >&2
    exit 1
  fi
done

# Ничего лишнего в бандле: meta-templates не рантайм, python-артефакты и
# служебные файлы ОС -- мусор локальных прогонов.
case " $BUNDLE_ITEMS " in
  *" meta-templates "*)
    echo "meta-templates must not be part of the runtime bundle." >&2
    exit 1
    ;;
esac

if [ "$DRY_RUN" = "1" ]; then
  echo "dry-run: release ${TAG} of ${SKILL_NAME} (nothing is written)"
  echo "  version checks: VERSION=${PKG_VERSION} SKILL.md=${SKILL_VERSION} arg=${VERSION} -- OK"
  echo "  BUNDLE_ITEMS match install.sh -- OK"
  echo "  bundle:"
  for item in $BUNDLE_ITEMS; do
    printf '    %-16s %s\n' "$item" "$(du -sh "$item" | cut -f1)"
  done
  echo "  would build: ${OUT_DIR}/${TARBALL_NAME}"
  echo "  would copy:  ${OUT_DIR}/install.sh"
  echo "  would write: ${OUT_DIR}/checksums-sha256.txt"
  exit 0
fi

rm -rf "dist/stage" "$OUT_DIR"
mkdir -p "$STAGE_DIR" "$OUT_DIR"

echo "Staging ${SKILL_NAME} v${VERSION}..."
for item in $BUNDLE_ITEMS; do
  cp -R "$item" "$STAGE_DIR/$item"
done

# Чистка stage: python-артефакты и служебные файлы ОС в поставку не входят.
find "$STAGE_DIR" -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true
find "$STAGE_DIR" -name '*.pyc' -type f -exec rm -f {} + 2>/dev/null || true
find "$STAGE_DIR" -name '.pytest_cache' -type d -prune -exec rm -rf {} + 2>/dev/null || true
find "$STAGE_DIR" -name '.DS_Store' -type f -exec rm -f {} + 2>/dev/null || true

echo "Packing $TARBALL_NAME..."
( cd dist/stage && tar czf "$OLDPWD/$OUT_DIR/$TARBALL_NAME" --exclude='__pycache__' --exclude='*.pyc' --exclude='meta-templates' "$SKILL_NAME" )
rm -rf dist/stage

# Проверка содержимого архива: то, без чего установка не соберётся, должно быть
# внутри; мусора и authoring-шаблонов быть не должно.
TAR_LIST="$(tar tzf "$OUT_DIR/$TARBALL_NAME")"
for required in "SKILL.md" "VERSION" "scripts/criticality.py" "commands/criticality_gen.md" "project/Makefile" "criteria/" "templates/" "references/" "docs/"; do
  if ! printf '%s\n' "$TAR_LIST" | grep -q "^${SKILL_NAME}/${required}"; then
    echo "tarball is missing required entry: ${required}" >&2
    exit 1
  fi
done
if printf '%s\n' "$TAR_LIST" | grep -qE '(__pycache__|\.pyc$|meta-templates)'; then
  echo "tarball contains files that must not be shipped (__pycache__, *.pyc, meta-templates)." >&2
  exit 1
fi

echo "Copying $INSTALL_SCRIPT..."
cp "$INSTALL_SCRIPT" "$OUT_DIR/install.sh"

echo "Generating SHA256 checksums..."
( cd "$OUT_DIR" && sha256sum -- * > checksums-sha256.txt )

echo ""
echo "Built release ${TAG} in $OUT_DIR:"
ls -la "$OUT_DIR"
