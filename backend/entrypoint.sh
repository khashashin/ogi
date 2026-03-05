#!/bin/sh
set -eu

is_true() {
  case "$(printf '%s' "${1:-}" | tr '[:upper:]' '[:lower:]')" in
    1|true|yes|on) return 0 ;;
    *) return 1 ;;
  esac
}

BOOT_REQUIREMENTS_ENABLE="${OGI_BOOT_REQUIREMENTS_ENABLE:-true}"
BOOT_REQUIREMENTS_FILE="${OGI_BOOT_REQUIREMENTS_FILE:-/app/plugins/requirements.txt}"
BOOT_LOCK_FILE="${OGI_BOOT_LOCK_FILE:-/app/plugins/ogi-lock.json}"
BOOT_REQUIREMENTS_STRICT="${OGI_BOOT_REQUIREMENTS_STRICT:-false}"
BOOT_REQUIREMENTS_CACHE_DIR="${OGI_BOOT_REQUIREMENTS_CACHE_DIR:-/tmp/ogi-boot}"

if is_true "$BOOT_REQUIREMENTS_ENABLE"; then
  # Backward-compatibility: if requirements.txt is missing but lock metadata has
  # dependency entries, synthesize requirements.txt on boot.
  if [ ! -s "$BOOT_REQUIREMENTS_FILE" ] && [ -f "$BOOT_LOCK_FILE" ]; then
    python - "$BOOT_LOCK_FILE" "$BOOT_REQUIREMENTS_FILE" <<'PY'
import json
import sys
from pathlib import Path

lock_path = Path(sys.argv[1])
req_path = Path(sys.argv[2])
try:
    data = json.loads(lock_path.read_text(encoding="utf-8"))
except Exception:
    raise SystemExit(0)

deps: set[str] = set()
for entry in (data.get("transforms") or {}).values():
    raw = entry.get("python_dependencies", [])
    if isinstance(raw, list):
        for dep in raw:
            dep_text = str(dep).strip()
            if dep_text:
                deps.add(dep_text)

if deps:
    req_path.parent.mkdir(parents=True, exist_ok=True)
    req_path.write_text("".join(f"{d}\n" for d in sorted(deps)), encoding="utf-8")
PY
  fi

  if [ -f "$BOOT_REQUIREMENTS_FILE" ] && [ -s "$BOOT_REQUIREMENTS_FILE" ]; then
    mkdir -p "$BOOT_REQUIREMENTS_CACHE_DIR"
    MARKER_FILE="$BOOT_REQUIREMENTS_CACHE_DIR/requirements.sha256"
    CURRENT_HASH="$(sha256sum "$BOOT_REQUIREMENTS_FILE" | awk '{print $1}')"
    PREVIOUS_HASH=""
    if [ -f "$MARKER_FILE" ]; then
      PREVIOUS_HASH="$(cat "$MARKER_FILE")"
    fi

    if [ "$CURRENT_HASH" != "$PREVIOUS_HASH" ]; then
      echo "Installing boot requirements from $BOOT_REQUIREMENTS_FILE"
      uv pip install -r "$BOOT_REQUIREMENTS_FILE"
      printf '%s\n' "$CURRENT_HASH" > "$MARKER_FILE"
    else
      echo "Boot requirements unchanged, skipping install ($BOOT_REQUIREMENTS_FILE)"
    fi
  else
    if is_true "$BOOT_REQUIREMENTS_STRICT"; then
      echo "Boot requirements file missing or empty: $BOOT_REQUIREMENTS_FILE"
      exit 1
    fi
    echo "No boot requirements file found at $BOOT_REQUIREMENTS_FILE (continuing)"
  fi
fi

exec "$@"
