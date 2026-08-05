#!/usr/bin/env bash
# Instalador remoto da distribuição Athena.

set -Eeuo pipefail

ATHENA_REPOSITORY="https://github.com/engsathiago/athena-agent.git"
ATHENA_BRANCH="${ATHENA_INSTALL_BRANCH:-main}"

command -v git >/dev/null 2>&1 || {
    echo "Erro: instale o Git antes de continuar." >&2
    exit 1
}

ATHENA_BOOTSTRAP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/athena-bootstrap.XXXXXX")"
trap 'rm -rf "$ATHENA_BOOTSTRAP_DIR" 2>/dev/null || true' EXIT

printf 'Baixando Athena de %s...\n' "$ATHENA_REPOSITORY"
git clone --depth 1 --branch "$ATHENA_BRANCH" "$ATHENA_REPOSITORY" "$ATHENA_BOOTSTRAP_DIR/athena"
"$ATHENA_BOOTSTRAP_DIR/athena/install.sh" "$@"
