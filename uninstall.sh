#!/usr/bin/env bash
# ==============================================================================
#  WaleAttack - Desinstalador Universal para Linux
# ==============================================================================

set -e

BOLD='\033[1m'
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

PURGE=false

for arg in "$@"; do
    case "$arg" in
        --purge)
            PURGE=true
            ;;
        -h|--help)
            echo "Uso: $0 [OPÇÕES]"
            echo ""
            echo "Opções:"
            echo "  --purge      Remove também arquivos de configuração e perfis (~/.config/waleattack)"
            echo "  --help, -h   Exibe esta ajuda"
            exit 0
            ;;
    esac
done

echo -e "${CYAN}======================================================${NC}"
echo -e "${BOLD}       WaleAttack - Desinstalação para Linux          ${NC}"
echo -e "${CYAN}======================================================${NC}"

# 1. Remover instalação do sistema (se root ou sudo)
if [ "$EUID" -eq 0 ]; then
    echo -e "Removendo arquivos do sistema..."
    rm -f /usr/local/bin/waleattack
    rm -f /usr/local/bin/waleattack-cli
    rm -f /usr/local/bin/waleattack-uninstall
    rm -f /usr/share/applications/waleattack.desktop
    rm -f /usr/share/pixmaps/waleattack.png
    rm -f /usr/share/icons/hicolor/*/apps/waleattack.png
    rm -f /etc/udev/rules.d/70-waleattack.rules

    if command -v udevadm >/dev/null 2>&1; then
        udevadm control --reload-rules 2>/dev/null || true
        udevadm trigger --subsystem-match=hidraw 2>/dev/null || true
    fi

    if command -v gtk-update-icon-cache >/dev/null 2>&1; then
        gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor 2>/dev/null || true
    fi
    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database /usr/share/applications 2>/dev/null || true
    fi
    echo -e "${GREEN}✓ Arquivos do sistema removidos com sucesso!${NC}"
else
    # Se não for root, verifica se há arquivos de sistema instalados
    if [ -f "/usr/local/bin/waleattack" ] || [ -f "/etc/udev/rules.d/70-waleattack.rules" ]; then
        echo -e "${YELLOW}[!] Foram detectados arquivos instalados no sistema (/usr/local ou /etc/udev).${NC}"
        if command -v sudo >/dev/null 2>&1; then
            echo -e "${CYAN}--> Solicitando sudo para remover arquivos de sistema...${NC}"
            if [ "$PURGE" = true ]; then
                sudo bash "$0" --purge
            else
                sudo bash "$0"
            fi
        fi
    fi
fi

# 2. Remover instalação do usuário local
echo -e "Verificando arquivos locais do usuário ($HOME/.local)..."
rm -f "$HOME/.local/bin/waleattack"
rm -f "$HOME/.local/bin/waleattack-cli"
rm -f "$HOME/.local/bin/waleattack-uninstall"
rm -f "$HOME/.local/share/applications/waleattack.desktop"
rm -f "$HOME/.local/share/pixmaps/waleattack.png"
rm -f "$HOME/.local/share/icons/hicolor/"*"/apps/waleattack.png"

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -q -t -f "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
fi

# 3. Purge opcional
if [ "$PURGE" = true ]; then
    echo -e "Removendo configurações de usuário..."
    rm -rf "$HOME/.config/waleattack"
    echo -e "${GREEN}✓ Configurações e perfis removidos.${NC}"
else
    echo -e "Os arquivos de perfil e configurações em ${BOLD}~/.config/waleattack${NC} foram mantidos."
    echo -e "Para removê-los também, use: ${BOLD}$0 --purge${NC}"
fi

echo ""
echo -e "${GREEN}${BOLD}✓ Desinstalação concluída com sucesso!${NC}"
