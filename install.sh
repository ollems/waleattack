#!/usr/bin/env bash
# ==============================================================================
#  WaleAttack - Instalador Universal para Linux (x86_64)
#  Compatível com todas as distribuições: Ubuntu, Debian, Fedora, Arch,
#  Manjaro, openSUSE, Gentoo, Void, Alpine, Pop!_OS, Linux Mint, etc.
# ==============================================================================

set -e

# Cores e Formatação
BOLD='\033[1m'
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

show_banner() {
    cat << "EOF"
  __        __    _        _   _   _             _    
  \ \      / /_ _| | ___  / \ | |_| |_ __ _  ___| | __
   \ \ /\ / / _` | |/ _ \/ _ \| __| __/ _` |/ __| |/ /
    \ V  V / (_| | |  __/ ___ \ |_| || (_| | (__|   < 
     \_/\_/ \__,_|_|\___/_/   \_\__|\__\__,_|\___|_|\_\
      Gerenciador de Mouse Gaming para Linux e Windows
EOF
    echo -e "${CYAN}======================================================${NC}"
}

print_help() {
    echo "Uso: $0 [OPÇÕES]"
    echo ""
    echo "Opções:"
    echo "  --system         Instala em todo o sistema (/usr/local, requer root/sudo - Padrão)"
    echo "  --user           Instala apenas no diretório do usuário local (~/.local)"
    echo "  --help, -h       Exibe esta ajuda"
    echo ""
    echo "Exemplos:"
    echo "  sudo ./install.sh        # Instalação recomendada com regras udev automáticas"
    echo "  ./install.sh --user      # Instalação sem privilégios de root"
    exit 0
}

# Resolve caminhos dos arquivos fonte
resolve_sources() {
    # Binário da GUI
    if [ -f "$SCRIPT_DIR/bin/waleattack" ]; then
        GUI_BIN="$SCRIPT_DIR/bin/waleattack"
    elif [ -f "$SCRIPT_DIR/dist/waleattack" ]; then
        GUI_BIN="$SCRIPT_DIR/dist/waleattack"
    elif [ -f "$SCRIPT_DIR/waleattack" ]; then
        GUI_BIN="$SCRIPT_DIR/waleattack"
    else
        echo -e "${RED}[ERRO] Binário 'waleattack' não encontrado!${NC}"
        exit 1
    fi

    # Binário do CLI
    if [ -f "$SCRIPT_DIR/bin/waleattack-cli" ]; then
        CLI_BIN="$SCRIPT_DIR/bin/waleattack-cli"
    elif [ -f "$SCRIPT_DIR/dist/waleattack-cli" ]; then
        CLI_BIN="$SCRIPT_DIR/dist/waleattack-cli"
    elif [ -f "$SCRIPT_DIR/waleattack-cli" ]; then
        CLI_BIN="$SCRIPT_DIR/waleattack-cli"
    else
        echo -e "${YELLOW}[AVISO] Binário 'waleattack-cli' (CLI) não encontrado; continuando apenas com GUI.${NC}"
        CLI_BIN=""
    fi

    # Desktop entry
    if [ -f "$SCRIPT_DIR/desktop/waleattack.desktop" ]; then
        DESKTOP_SRC="$SCRIPT_DIR/desktop/waleattack.desktop"
    elif [ -f "$SCRIPT_DIR/assets/waleattack.desktop" ]; then
        DESKTOP_SRC="$SCRIPT_DIR/assets/waleattack.desktop"
    elif [ -f "$SCRIPT_DIR/waleattack.desktop" ]; then
        DESKTOP_SRC="$SCRIPT_DIR/waleattack.desktop"
    else
        echo -e "${RED}[ERRO] Arquivo 'waleattack.desktop' não encontrado!${NC}"
        exit 1
    fi

    # Regras udev
    if [ -f "$SCRIPT_DIR/udev/70-waleattack.rules" ]; then
        UDEV_SRC="$SCRIPT_DIR/udev/70-waleattack.rules"
    elif [ -f "$SCRIPT_DIR/assets/70-waleattack.rules" ]; then
        UDEV_SRC="$SCRIPT_DIR/assets/70-waleattack.rules"
    elif [ -f "$SCRIPT_DIR/70-waleattack.rules" ]; then
        UDEV_SRC="$SCRIPT_DIR/70-waleattack.rules"
    else
        UDEV_SRC=""
    fi

    # Script uninstaller
    if [ -f "$SCRIPT_DIR/uninstall.sh" ]; then
        UNINSTALL_SRC="$SCRIPT_DIR/uninstall.sh"
    else
        UNINSTALL_SRC=""
    fi
}

install_system() {
    echo -e "${CYAN}--> Modo de Instalação: Sistema Inteiro (/usr/local)${NC}"

    if [ "$EUID" -ne 0 ]; then
        echo -e "${YELLOW}[!] Privilégios de superusuário necessários para instalação no sistema.${NC}"
        if command -v sudo >/dev/null 2>&1; then
            echo -e "${CYAN}--> Solicitando sudo...${NC}"
            exec sudo bash "$0" --system "$@"
        else
            echo -e "${RED}[ERRO] Comando 'sudo' não encontrado. Execute como root: su -c '$0 --system'${NC}"
            exit 1
        fi
    fi

    # Diretórios de destino
    BIN_DIR="/usr/local/bin"
    APP_DIR="/usr/share/applications"
    ICON_BASE="/usr/share/icons/hicolor"
    PIXMAPS_DIR="/usr/share/pixmaps"
    UDEV_DIR="/etc/udev/rules.d"

    mkdir -p "$BIN_DIR" "$APP_DIR" "$PIXMAPS_DIR"

    # 1. Instalar Binários
    echo -e "  [+] Instalando executável ${BOLD}waleattack${NC} em $BIN_DIR..."
    install -m 755 "$GUI_BIN" "$BIN_DIR/waleattack"

    if [ -n "$CLI_BIN" ]; then
        echo -e "  [+] Instalando executável CLI ${BOLD}waleattack-cli${NC} em $BIN_DIR..."
        install -m 755 "$CLI_BIN" "$BIN_DIR/waleattack-cli"
    fi

    # 2. Instalar Uninstaller
    if [ -n "$UNINSTALL_SRC" ]; then
        echo -e "  [+] Instalando comando de desinstalação ${BOLD}waleattack-uninstall${NC}..."
        install -m 755 "$UNINSTALL_SRC" "$BIN_DIR/waleattack-uninstall"
    fi

    # 3. Instalar Atalho Desktop
    echo -e "  [+] Instalando atalho de menu em $APP_DIR..."
    install -m 644 "$DESKTOP_SRC" "$APP_DIR/waleattack.desktop"

    # 4. Instalar Ícones
    echo -e "  [+] Instalando ícones do aplicativo..."
    for sz in 16 24 32 48 64 128 256; do
        icon_file="$SCRIPT_DIR/icons/waleattack_${sz}x${sz}.png"
        target_dir="$ICON_BASE/${sz}x${sz}/apps"
        if [ -f "$icon_file" ]; then
            mkdir -p "$target_dir"
            install -m 644 "$icon_file" "$target_dir/waleattack.png"
        fi
    done

    # Ícone fallback em pixmaps e ícone 256x256
    if [ -f "$SCRIPT_DIR/icons/waleattack_256x256.png" ]; then
        install -m 644 "$SCRIPT_DIR/icons/waleattack_256x256.png" "$PIXMAPS_DIR/waleattack.png"
    elif [ -f "$SCRIPT_DIR/src/waleattack/assets/app_icon.png" ]; then
        install -m 644 "$SCRIPT_DIR/src/waleattack/assets/app_icon.png" "$PIXMAPS_DIR/waleattack.png"
        mkdir -p "$ICON_BASE/256x256/apps"
        install -m 644 "$SCRIPT_DIR/src/waleattack/assets/app_icon.png" "$ICON_BASE/256x256/apps/waleattack.png"
    fi

    # 5. Instalar Regras Udev
    if [ -n "$UDEV_SRC" ]; then
        echo -e "  [+] Instalando regras de permissão udev em $UDEV_DIR..."
        mkdir -p "$UDEV_DIR"
        install -m 644 "$UDEV_SRC" "$UDEV_DIR/70-waleattack.rules"

        echo -e "  [+] Recarregando regras udev e aplicando permissões..."
        if command -v udevadm >/dev/null 2>&1; then
            udevadm control --reload-rules 2>/dev/null || true
            udevadm trigger --subsystem-match=hidraw 2>/dev/null || true
        fi
    fi

    # 6. Atualizar Caches do Sistema
    if command -v gtk-update-icon-cache >/dev/null 2>&1; then
        gtk-update-icon-cache -q -t -f "$ICON_BASE" 2>/dev/null || true
    fi
    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database "$APP_DIR" 2>/dev/null || true
    fi

    echo ""
    echo -e "${GREEN}${BOLD}✓ WaleAttack instalado com sucesso no sistema!${NC}"
    echo -e "  • Para abrir a interface gráfica: digite ${BOLD}waleattack${NC} no terminal ou abra pelo Menu de Aplicativos."
    if [ -n "$CLI_BIN" ]; then
        echo -e "  • Para usar o CLI: digite ${BOLD}waleattack-cli --help${NC}"
    fi
    echo -e "  • Para desinstalar no futuro: execute ${BOLD}sudo waleattack-uninstall${NC}"
    echo ""
}

install_user() {
    echo -e "${CYAN}--> Modo de Instalação: Usuário Local ($HOME/.local)${NC}"

    BIN_DIR="$HOME/.local/bin"
    APP_DIR="$HOME/.local/share/applications"
    ICON_BASE="$HOME/.local/share/icons/hicolor"
    PIXMAPS_DIR="$HOME/.local/share/pixmaps"

    mkdir -p "$BIN_DIR" "$APP_DIR" "$PIXMAPS_DIR"

    # 1. Instalar Binários
    echo -e "  [+] Instalando executável ${BOLD}waleattack${NC} em $BIN_DIR..."
    install -m 755 "$GUI_BIN" "$BIN_DIR/waleattack"

    if [ -n "$CLI_BIN" ]; then
        echo -e "  [+] Instalando executável CLI ${BOLD}waleattack-cli${NC} em $BIN_DIR..."
        install -m 755 "$CLI_BIN" "$BIN_DIR/waleattack-cli"
    fi

    # 2. Instalar Uninstaller
    if [ -n "$UNINSTALL_SRC" ]; then
        echo -e "  [+] Instalando desinstalador em $BIN_DIR/waleattack-uninstall..."
        install -m 755 "$UNINSTALL_SRC" "$BIN_DIR/waleattack-uninstall"
    fi

    # 3. Instalar Atalho Desktop
    echo -e "  [+] Instalando atalho de menu em $APP_DIR..."
    install -m 644 "$DESKTOP_SRC" "$APP_DIR/waleattack.desktop"

    # 4. Instalar Ícones
    echo -e "  [+] Instalando ícones do aplicativo..."
    for sz in 16 24 32 48 64 128 256; do
        icon_file="$SCRIPT_DIR/icons/waleattack_${sz}x${sz}.png"
        target_dir="$ICON_BASE/${sz}x${sz}/apps"
        if [ -f "$icon_file" ]; then
            mkdir -p "$target_dir"
            install -m 644 "$icon_file" "$target_dir/waleattack.png"
        fi
    done

    if [ -f "$SCRIPT_DIR/icons/waleattack_256x256.png" ]; then
        install -m 644 "$SCRIPT_DIR/icons/waleattack_256x256.png" "$PIXMAPS_DIR/waleattack.png"
    elif [ -f "$SCRIPT_DIR/src/waleattack/assets/app_icon.png" ]; then
        install -m 644 "$SCRIPT_DIR/src/waleattack/assets/app_icon.png" "$PIXMAPS_DIR/waleattack.png"
        mkdir -p "$ICON_BASE/256x256/apps"
        install -m 644 "$SCRIPT_DIR/src/waleattack/assets/app_icon.png" "$ICON_BASE/256x256/apps/waleattack.png"
    fi

    # Atualizar Caches
    if command -v gtk-update-icon-cache >/dev/null 2>&1; then
        gtk-update-icon-cache -q -t -f "$ICON_BASE" 2>/dev/null || true
    fi
    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database "$APP_DIR" 2>/dev/null || true
    fi

    # Verificar PATH
    case ":$PATH:" in
        *":$BIN_DIR:"*) ;;
        *)
            echo -e "${YELLOW}[!] Dica: Adicione '$BIN_DIR' ao seu PATH em ~/.bashrc ou ~/.zshrc:${NC}"
            echo -e "    export PATH=\"\$HOME/.local/bin:\$PATH\""
            ;;
    esac

    # Aviso sobre UDEV
    if [ ! -f "/etc/udev/rules.d/70-waleattack.rules" ]; then
        echo ""
        echo -e "${YELLOW}----------------------------------------------------------------------${NC}"
        echo -e "${YELLOW}[IMPORTANTE] Regras udev de permissão do mouse:${NC}"
        echo -e "Para acessar o mouse sem ser root, instale a regra udev executando:"
        if [ -n "$UDEV_SRC" ]; then
            echo -e "  ${BOLD}sudo cp \"$UDEV_SRC\" /etc/udev/rules.d/70-waleattack.rules && sudo udevadm control --reload-rules && sudo udevadm trigger${NC}"
        else
            echo -e "  ${BOLD}sudo udevadm control --reload-rules && sudo udevadm trigger${NC}"
        fi
        echo -e "${YELLOW}----------------------------------------------------------------------${NC}"
    fi

    echo ""
    echo -e "${GREEN}${BOLD}✓ WaleAttack instalado com sucesso para seu usuário!${NC}"
    echo -e "  • Para abrir a interface gráfica: execute ${BOLD}$BIN_DIR/waleattack${NC} ou use o menu."
    echo ""
}

# --- Ponto de Entrada Principal ---
show_banner

case "$1" in
    -h|--help)
        print_help
        ;;
    --user)
        resolve_sources
        install_user
        ;;
    --system)
        resolve_sources
        install_system
        ;;
    *)
        resolve_sources
        # Se for root, instala system-wide diretamente
        if [ "$EUID" -eq 0 ]; then
            install_system
        else
            # Pergunta amigável ou tenta system-wide se sudo disponível
            echo -e "${CYAN}Escolha o modo de instalação desejado:${NC}"
            echo -e "  ${BOLD}1)${NC} Instalação Completa do Sistema (${GREEN}Recomendado${NC} - configura udev automaticamente, requer sudo)"
            echo -e "  ${BOLD}2)${NC} Instalação Local do Usuário (instala apenas em ~/.local/bin)"
            echo ""
            read -r -p "Opção [1/2, padrão: 1]: " CHOICE || CHOICE="1"
            case "$CHOICE" in
                2|user)
                    install_user
                    ;;
                *)
                    install_system
                    ;;
            esac
        fi
        ;;
esac
