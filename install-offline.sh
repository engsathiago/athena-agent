#!/usr/bin/env sh
set -eu

BUNDLE_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ATHENA_TARGET=${ATHENA_OFFLINE_TARGET:-"$HOME/.local/share/athena"}
ATHENA_BIN_DIR=${ATHENA_OFFLINE_BIN_DIR:-"$HOME/.local/bin"}

if [ ! -d "$BUNDLE_DIR/athena-app" ]; then
  echo "Erro: pasta athena-app ausente no pacote offline." >&2
  exit 1
fi

mkdir -p "$ATHENA_TARGET" "$ATHENA_BIN_DIR"
cp -R "$BUNDLE_DIR/athena-app/." "$ATHENA_TARGET/"

PYTHON_BIN=${PYTHON_BIN:-python3}
if [ -d "$BUNDLE_DIR/wheels" ]; then
  "$PYTHON_BIN" -m venv "$ATHENA_TARGET/.venv"
  ATHENA_WHEEL=$(find "$BUNDLE_DIR/wheels" -maxdepth 1 -name 'athena_agent-*.whl' -print | head -n 1)
  if [ -n "$ATHENA_WHEEL" ]; then
    "$ATHENA_TARGET/.venv/bin/python" -m pip install --no-index --find-links "$BUNDLE_DIR/wheels" "$ATHENA_WHEEL"
  else
    "$ATHENA_TARGET/.venv/bin/python" -m pip install --no-index --find-links "$BUNDLE_DIR/wheels" "$ATHENA_TARGET/core"
  fi
  ATHENA_PYTHON="$ATHENA_TARGET/.venv/bin/python"
else
  ATHENA_PYTHON="$PYTHON_BIN"
  echo "Aviso: pacote sem wheelhouse; usando as dependencias Python ja instaladas na maquina."
fi

if [ -d "$BUNDLE_DIR/ollama-models" ]; then
  mkdir -p "$HOME/.ollama/models"
  cp -R "$BUNDLE_DIR/ollama-models/." "$HOME/.ollama/models/"
fi

if [ -f "$BUNDLE_DIR/bin/ollama" ]; then
  cp "$BUNDLE_DIR/bin/ollama" "$ATHENA_BIN_DIR/ollama"
  chmod +x "$ATHENA_BIN_DIR/ollama"
fi

cat > "$ATHENA_BIN_DIR/athena" <<EOF
#!/usr/bin/env sh
PYTHONPATH="$ATHENA_TARGET/core\${PYTHONPATH:+:\$PYTHONPATH}" exec "$ATHENA_PYTHON" -m athena "\$@"
EOF
chmod +x "$ATHENA_BIN_DIR/athena"

echo "Athena instalada sem acesso a internet."
echo "Use: $ATHENA_BIN_DIR/athena offline status"
