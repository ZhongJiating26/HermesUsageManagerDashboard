#!/usr/bin/env bash
# Run after `hermes plugins install`; no system Python or dependency upgrades.
set -euo pipefail
PLUGIN_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
HERMES_ROOT="${HERMES_HOME:-$HOME/.hermes}"
PYTHON=""

# Hermes' console-script shebang identifies its actual environment.
if HERMES_COMMAND="$(command -v hermes)" && [ -f "$HERMES_COMMAND" ]; then
  IFS= read -r FIRST_LINE < "$HERMES_COMMAND" || true
  CANDIDATE="${FIRST_LINE#\#!}"
  if [[ "$FIRST_LINE" == '#!'* && "${CANDIDATE##*/}" == python* && "$CANDIDATE" == /* && "$CANDIDATE" != *' '* && -x "$CANDIDATE" ]]; then
    PYTHON="$CANDIDATE"
  fi
fi
if [ -z "$PYTHON" ]; then
  for CANDIDATE in "$HERMES_ROOT/hermes-agent/venv/bin/python3" "$HERMES_ROOT/hermes-agent/.venv/bin/python3"; do
    if [ -x "$CANDIDATE" ]; then
      PYTHON="$CANDIDATE"
      break
    fi
  done
fi
if [ -z "$PYTHON" ]; then
  echo '未找到 Hermes 的 Python。请使用 Hermes 实际解释器执行 standalone.py setup --start-service。' >&2
  exit 1
fi
if [ -z "${HERMES_COMMAND:-}" ]; then
  echo '未找到 hermes 命令，请先激活 Hermes 的运行环境。' >&2
  exit 1
fi
USAGE_MANAGER_COLLECTION=0 "$HERMES_COMMAND" plugins doctor --ci "$PLUGIN_DIR"
"$PYTHON" "$PLUGIN_DIR/standalone.py" setup --start-service --host 0.0.0.0 --allow-http "$@"
echo '安装配置完成。请按原方式重启 Gateway，使采集配置生效。'
