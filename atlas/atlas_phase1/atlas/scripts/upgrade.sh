#!/usr/bin/env bash
# Upgrade an existing Atlas checkout in place, keeping your data and your edits.
#
#   unzip atlas_phase1.zip -d ~/Downloads/atlas_phase1
#   bash ~/Downloads/atlas_phase1/atlas/scripts/upgrade.sh ~/Desktop/Notes/Notes/atlas
#
# What it does:
#   1. Backs up the target repo (code + configs + data) to <target>/../atlas-backup-<time>.tar.gz
#   2. Copies new code over it. NEVER touches: data/, .venv/, .git/, README.md, configs/*.local.yaml
#   3. configs/profile.yaml: kept if you already have one (new version saved as profile.yaml.new)
#      other configs/*.yaml: replaced; if yours differed, it is kept as <name>.yaml.bak-<time>
#   4. uv sync, run tests, atlas doctor
# Also works if you already unzipped over the repo: run it from inside the repo with no argument.
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="${1:-$SRC}"
TARGET="$(cd "$TARGET" && pwd)"
PROFILE="${ATLAS_PROFILE:-homepc}"
TS="$(date +%Y%m%d-%H%M%S)"
say() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }

[[ -f "$TARGET/pyproject.toml" && -d "$TARGET/src/atlas" ]] || { echo "Not an Atlas repo: $TARGET"; exit 1; }
say "Upgrading $TARGET  (from $SRC)"

# sha256 of configs shipped in earlier versions (unedited copies are replaced without a .bak)
PRISTINE="9faa355067c2e6fa2693b25f3d4f5394ded95a0861d548affc43c1a9351623e3 6ce6c87a16669f81ab70e936689b7979392d8795bda32cd5a3c6e68f811dedc1"

# 1) backup ------------------------------------------------------------------
BACKUP="$(dirname "$TARGET")/atlas-backup-$TS.tar.gz"
tar -C "$(dirname "$TARGET")" --exclude="$(basename "$TARGET")/.venv" -czf "$BACKUP" "$(basename "$TARGET")"
echo "   backup: $BACKUP"

# 2) code --------------------------------------------------------------------
if [[ "$SRC" != "$TARGET" ]]; then
  tar -C "$SRC" --exclude=./data --exclude=./.venv --exclude=./.git --exclude=./README.md \
      --exclude=./configs --exclude='*/__pycache__' --exclude=./.pytest_cache -cf - . | tar -C "$TARGET" -xf -
  echo "   code copied (data/, .venv/, .git/, README.md untouched)"

  # 3) configs -----------------------------------------------------------------
  mkdir -p "$TARGET/configs"
  for f in "$SRC"/configs/*.yaml; do
    name="$(basename "$f")"
    [[ "$name" == *.local.yaml ]] && continue
    dst="$TARGET/configs/$name"
    if [[ ! -f "$dst" ]]; then
      cp "$f" "$dst"; echo "   + configs/$name"
    elif cmp -s "$f" "$dst"; then
      :
    elif [[ " $PRISTINE " == *" $(sha256sum "$dst" | cut -c1-64) "* ]]; then
      cp "$f" "$dst"; echo "   ~ configs/$name updated (you had not edited it)"
    elif [[ "$name" == profile.yaml ]]; then
      cp "$f" "$dst.new"; echo "   = configs/profile.yaml kept (yours); new template at configs/profile.yaml.new"
    else
      cp "$dst" "$dst.bak-$TS"; cp "$f" "$dst"
      echo "   ~ configs/$name updated; your old copy is configs/$name.bak-$TS"
      echo "     (put personal tweaks in configs/${name%.yaml}.local.yaml so upgrades never touch them)"
    fi
  done
fi
mkdir -p "$TARGET/data/reports" "$TARGET/data/workspace"

# 4) deps + checks -----------------------------------------------------------
cd "$TARGET"
if [[ "${ATLAS_UPGRADE_SKIP_SYNC:-0}" != 1 ]]; then
  command -v uv >/dev/null || export PATH="$HOME/.local/bin:$PATH"
  say "uv sync"
  uv sync
  say "tests"
  uv run pytest -q || echo "   (tests failed; tell Atlas's builder what the output says)"
  say "doctor ($PROFILE)"
  uv run atlas doctor --profile "$PROFILE" || true
  command -v pandoc >/dev/null || echo "   tip: sudo dnf install -y pandoc   (for --docx/--pdf research exports)"
fi

cat <<DONE

Upgrade done. Your SQLite data in data/ was migrated automatically on first use (new columns/tables only).
Try:
  cd $TARGET
  uv run atlas chat --profile $PROFILE -v
  uv run atlas research "Voyager 1 spacecraft design and mission" --profile $PROFILE --docx
Optional GPU pinning (3060 = fast, 5070 Ti = reasoning):
  bash scripts/setup_gpu_pinning.sh          # dry run
  bash scripts/setup_gpu_pinning.sh --apply
DONE
