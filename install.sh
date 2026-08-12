#!/usr/bin/env bash
# Athena independent installer for Linux and macOS.
# Installs the vendored core, a private Python runtime and the global `athena`
# command without requiring any other agent distribution.

set -Eeuo pipefail

ATHENA_INSTALL_VERSION="0.3.0"
ATHENA_PYTHON_VERSION="3.11"
ATHENA_ASSUME_YES=0
ATHENA_RUN_SETUP=0
ATHENA_INSTALL_GATEWAY=0
ATHENA_MINIMAL=0

ATHENA_SOURCE_ROOT="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ATHENA_SOURCE_CORE="$ATHENA_SOURCE_ROOT/core"
ATHENA_INSTALL_ROOT="${ATHENA_INSTALL_DIR:-$HOME/.local/share/athena}"
ATHENA_COMMAND_DIR="${ATHENA_BIN_DIR:-$HOME/.local/bin}"
ATHENA_STATE_ROOT="${ATHENA_HOME:-$HOME/.athena}"
ATHENA_PYTHON_OVERRIDE="${ATHENA_PYTHON:-}"

athena_usage() {
    cat <<'EOF'
Instalador da Athena

Uso: ./install.sh [opções]

Opções:
  --yes                 Instalação sem perguntas
  --setup               Abre a configuração da Athena após instalar
  --with-gateway        Configura, instala e inicia o gateway de mensagens
  --minimal             Instala o núcleo sem extras antecipados de mensagens
  --install-dir CAMINHO Diretório do aplicativo e runtime
  --bin-dir CAMINHO     Diretório que recebe o comando global athena
  --python CAMINHO      Usa um Python 3.11-3.13 específico
  -h, --help            Mostra esta ajuda
EOF
}

while (($#)); do
    case "$1" in
        --yes|-y)
            ATHENA_ASSUME_YES=1
            ;;
        --setup)
            ATHENA_RUN_SETUP=1
            ;;
        --with-gateway)
            ATHENA_INSTALL_GATEWAY=1
            ;;
        --minimal)
            ATHENA_MINIMAL=1
            ;;
        --install-dir)
            shift
            ATHENA_INSTALL_ROOT="${1:?--install-dir requires a path}"
            ;;
        --bin-dir)
            shift
            ATHENA_COMMAND_DIR="${1:?--bin-dir requires a path}"
            ;;
        --python)
            shift
            ATHENA_PYTHON_OVERRIDE="${1:?--python requires a path}"
            ;;
        -h|--help)
            athena_usage
            exit 0
            ;;
        *)
            echo "Opção desconhecida: $1" >&2
            athena_usage >&2
            exit 2
            ;;
    esac
    shift
done

athena_info() {
    printf '\033[1;36m→\033[0m %s\n' "$*"
}

athena_ok() {
    printf '\033[1;32m✓\033[0m %s\n' "$*"
}

athena_warn() {
    printf '\033[1;33m!\033[0m %s\n' "$*" >&2
}

athena_fail() {
    printf '\033[1;31m✗\033[0m %s\n' "$*" >&2
    exit 1
}

athena_python_supported() {
    "$1" -c 'import sys; raise SystemExit(0 if (3, 11) <= sys.version_info[:2] < (3, 14) else 1)' >/dev/null 2>&1
}

athena_prompt_yes() {
    local prompt="$1"
    if ((ATHENA_ASSUME_YES)); then
        return 0
    fi
    read -r -p "$prompt [Y/n] " answer
    [[ -z "$answer" || "$answer" =~ ^[Yy]$ ]]
}

athena_install_uv() {
    local uv_bin=""
    if command -v uv >/dev/null 2>&1; then
        uv_bin="$(command -v uv)"
    elif [[ -x "$HOME/.local/bin/uv" ]]; then
        uv_bin="$HOME/.local/bin/uv"
    elif [[ -x "$HOME/.cargo/bin/uv" ]]; then
        uv_bin="$HOME/.cargo/bin/uv"
    fi

    if [[ -n "$uv_bin" ]]; then
        printf '%s\n' "$uv_bin"
        return 0
    fi

    command -v curl >/dev/null 2>&1 || athena_fail "O curl é necessário para instalar o runtime Python da Athena."
    athena_info "Instalando o gerenciador privado do runtime Python" >&2
    local installer
    installer="$(mktemp "${TMPDIR:-/tmp}/athena-uv.XXXXXX")"
    if ! curl -LsSf https://astral.sh/uv/install.sh -o "$installer"; then
        rm -f "$installer"
        athena_fail "Não foi possível baixar o gerenciador do runtime Python."
    fi
    # athena_install_uv is evaluated in a command substitution. Keep the
    # third-party installer's progress output on stderr so the only stdout
    # value captured by ATHENA_UV_BIN is the executable path below.
    sh "$installer" >&2
    rm -f "$installer"

    for uv_bin in "$HOME/.local/bin/uv" "$HOME/.cargo/bin/uv"; do
        if [[ -x "$uv_bin" ]]; then
            printf '%s\n' "$uv_bin"
            return 0
        fi
    done
    athena_fail "A instalação do gerenciador terminou, mas o uv não foi encontrado."
}

athena_copy_application() {
    local destination="$1"
    mkdir -p "$destination"
    tar -C "$ATHENA_SOURCE_CORE" \
        --exclude='./.git' \
        --exclude='./.pytest_cache' \
        --exclude='./test_durations.json' \
        --exclude='./log.txt' \
        --exclude='./tests' \
        --exclude='./apps' \
        --exclude='./website' \
        --exclude='./contributors' \
        --exclude='./docs' \
        --exclude='./nix' \
        --exclude='./docker' \
        --exclude='./README.*.md' \
        --exclude='./CONTRIBUTING*' \
        --exclude='./SECURITY*' \
        --exclude='./AGENTS.md' \
        --exclude='./athena-already-has-routines.md' \
        --exclude='./setup-athena.sh' \
        --exclude='./scripts/install.sh' \
        --exclude='./scripts/install.ps1' \
        --exclude='./scripts/install.cmd' \
        --exclude='./scripts/dev-sandbox.sh' \
        --exclude='./scripts/generate_conformance_vectors.py' \
        --exclude='./scripts/build_model_catalog.py' \
        --exclude='./scripts/contributor_audit.py' \
        --exclude='./scripts/sample_and_compress.py' \
        --exclude='./scripts/release.py' \
        --exclude='*/__pycache__' \
        --exclude='*.pyc' \
        --exclude='.DS_Store' \
        -cf - . | tar -C "$destination" -xf -
}

athena_add_path() {
    case ":$PATH:" in
        *":$ATHENA_COMMAND_DIR:"*) return 0 ;;
    esac

    if [[ "$ATHENA_COMMAND_DIR" != "$HOME/.local/bin" ]]; then
        athena_warn "$ATHENA_COMMAND_DIR não está no PATH. Adicione-o à configuração do shell."
        return 0
    fi

    local shell_file=""
    case "${SHELL:-}" in
        */zsh) shell_file="$HOME/.zshrc" ;;
        */bash) shell_file="$HOME/.bashrc" ;;
    esac
    if [[ -n "$shell_file" ]]; then
        touch "$shell_file"
        if ! grep -Fq 'export PATH="$HOME/.local/bin:$PATH"' "$shell_file"; then
            printf '\n# Athena command\nexport PATH="$HOME/.local/bin:$PATH"\n' >> "$shell_file"
            athena_ok "$ATHENA_COMMAND_DIR foi adicionado ao PATH em $shell_file"
        fi
    else
        athena_warn "$ATHENA_COMMAND_DIR não está no PATH. Adicione-o à configuração do shell."
    fi
}

[[ -f "$ATHENA_SOURCE_CORE/pyproject.toml" ]] || athena_fail \
    "Execute este instalador em uma cópia da Athena que contenha core/pyproject.toml."

case "$(uname -s)" in
    Linux|Darwin) ;;
    *) athena_fail "Este instalador oferece suporte a Linux e macOS." ;;
esac

printf '\n\033[1;38;2;255;191;0mATHENA\033[0m  instalador independente v%s\n\n' "$ATHENA_INSTALL_VERSION"
athena_info "Aplicativo: $ATHENA_INSTALL_ROOT"
athena_info "Dados:      $ATHENA_STATE_ROOT"
athena_info "Comando:    $ATHENA_COMMAND_DIR/athena"

mkdir -p "$ATHENA_INSTALL_ROOT" "$ATHENA_COMMAND_DIR" "$ATHENA_STATE_ROOT"
chmod 700 "$ATHENA_STATE_ROOT" 2>/dev/null || true

ATHENA_STAGE="$(mktemp -d "$ATHENA_INSTALL_ROOT/.stage.XXXXXX")"
trap 'rm -rf "$ATHENA_STAGE" 2>/dev/null || true' EXIT
athena_info "Copiando o aplicativo Athena"
athena_copy_application "$ATHENA_STAGE/app"

ATHENA_APP_DIR="$ATHENA_INSTALL_ROOT/app"
ATHENA_PREVIOUS_DIR=""
if [[ -d "$ATHENA_APP_DIR" ]]; then
    ATHENA_PREVIOUS_DIR="$ATHENA_INSTALL_ROOT/app.previous.$(date +%Y%m%d%H%M%S)"
    mv "$ATHENA_APP_DIR" "$ATHENA_PREVIOUS_DIR"
fi
mv "$ATHENA_STAGE/app" "$ATHENA_APP_DIR"

ATHENA_VENV_DIR="$ATHENA_INSTALL_ROOT/venv"
if [[ -n "$ATHENA_PYTHON_OVERRIDE" ]]; then
    [[ -x "$ATHENA_PYTHON_OVERRIDE" ]] || athena_fail "O Python não é executável: $ATHENA_PYTHON_OVERRIDE"
    athena_python_supported "$ATHENA_PYTHON_OVERRIDE" || athena_fail "A Athena exige Python 3.11-3.13."
    if [[ ! -x "$ATHENA_VENV_DIR/bin/python" ]]; then
        if [[ "${ATHENA_INSTALL_NO_DEPS:-0}" == "1" ]]; then
            "$ATHENA_PYTHON_OVERRIDE" -m venv --system-site-packages "$ATHENA_VENV_DIR"
        else
            "$ATHENA_PYTHON_OVERRIDE" -m venv "$ATHENA_VENV_DIR"
        fi
    fi
    ATHENA_INSTALL_PYTHON="$ATHENA_VENV_DIR/bin/python"
    athena_info "Instalando o pacote Athena e suas dependências"
    if [[ "${ATHENA_INSTALL_NO_DEPS:-0}" == "1" ]]; then
        "$ATHENA_INSTALL_PYTHON" -m pip install --no-build-isolation --no-deps -e "$ATHENA_APP_DIR"
    elif ((ATHENA_MINIMAL)); then
        "$ATHENA_INSTALL_PYTHON" -m pip install -e "$ATHENA_APP_DIR"
    else
        "$ATHENA_INSTALL_PYTHON" -m pip install -e "$ATHENA_APP_DIR[all,messaging]"
    fi
else
    ATHENA_UV_BIN="$(athena_install_uv)"
    if [[ ! -x "$ATHENA_VENV_DIR/bin/python" ]]; then
        athena_info "Preparando Python $ATHENA_PYTHON_VERSION"
        "$ATHENA_UV_BIN" python install "$ATHENA_PYTHON_VERSION"
        "$ATHENA_UV_BIN" venv "$ATHENA_VENV_DIR" --python "$ATHENA_PYTHON_VERSION"
    fi
    athena_info "Instalando o pacote Athena e suas dependências"
    if ((ATHENA_MINIMAL)); then
        UV_PROJECT_ENVIRONMENT="$ATHENA_VENV_DIR" "$ATHENA_UV_BIN" sync \
            --project "$ATHENA_APP_DIR" --locked
    else
        UV_PROJECT_ENVIRONMENT="$ATHENA_VENV_DIR" "$ATHENA_UV_BIN" sync \
            --project "$ATHENA_APP_DIR" --extra all --extra messaging --locked
    fi
fi

ln -sfn "$ATHENA_VENV_DIR/bin/athena" "$ATHENA_COMMAND_DIR/athena"
athena_add_path

ATHENA_HOME="$ATHENA_STATE_ROOT" "$ATHENA_COMMAND_DIR/athena" init
athena_ok "Athena $ATHENA_INSTALL_VERSION instalada"

if [[ -n "$ATHENA_PREVIOUS_DIR" ]]; then
    athena_warn "A cópia anterior do aplicativo foi preservada em $ATHENA_PREVIOUS_DIR"
fi

if ((ATHENA_RUN_SETUP)); then
    ATHENA_HOME="$ATHENA_STATE_ROOT" "$ATHENA_COMMAND_DIR/athena" setup
elif ((ATHENA_ASSUME_YES == 0)) && athena_prompt_yes "Configurar modelo e ferramentas agora?"; then
    ATHENA_HOME="$ATHENA_STATE_ROOT" "$ATHENA_COMMAND_DIR/athena" setup
fi

if ((ATHENA_INSTALL_GATEWAY)); then
    ATHENA_HOME="$ATHENA_STATE_ROOT" "$ATHENA_COMMAND_DIR/athena" gateway setup
    ATHENA_HOME="$ATHENA_STATE_ROOT" "$ATHENA_COMMAND_DIR/athena" gateway install
    ATHENA_HOME="$ATHENA_STATE_ROOT" "$ATHENA_COMMAND_DIR/athena" gateway start
fi

printf '\nInicie a Athena com:\n\n  %s\n\n' "$ATHENA_COMMAND_DIR/athena"
printf 'Telegram / gateway contínuo:\n\n  athena gateway setup\n  athena gateway install\n\n'
