#!/usr/bin/env bash
# ==============================================================================
#  Build do WaleAttack para Windows (x64) via Wine + PyInstaller
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== 1. Gerando ícone .ico caso não exista ==="
python3 -c "
from PIL import Image
from pathlib import Path
base = Path('src/waleattack/assets/app_icon.png')
im = Image.open(base)
ico = Path('waleattack.ico')
im.save(ico, format='ICO', sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print('waleattack.ico pronto.')
"

echo "=== 2. Compilando WaleAttack.exe (GUI) ==="
wine "C:\\Program Files\\Python311\\Scripts\\pyinstaller.exe" --noconfirm --distpath dist_win --workpath build_win waleattack_win.spec

echo "=== 3. Compilando waleattack-cli.exe (CLI) ==="
wine "C:\\Program Files\\Python311\\Scripts\\pyinstaller.exe" --noconfirm --distpath dist_win --workpath build_win waleattack-cli_win.spec

echo "=== 4. Montando pacote de release para Windows ==="
RELEASE_NAME="WaleAttack-Windows-x64"
RELEASE_DIR="$SCRIPT_DIR/release/$RELEASE_NAME"

rm -rf "$RELEASE_DIR"
mkdir -p "$RELEASE_DIR"

# Copiar executáveis
cp -p dist_win/WaleAttack.exe "$RELEASE_DIR/"
cp -p dist_win/waleattack-cli.exe "$RELEASE_DIR/"
cp -p waleattack.ico "$RELEASE_DIR/"

# Script de criação de atalho na Área de Trabalho do Windows (.bat)
cat << "EOF" > "$RELEASE_DIR/Criar-Atalho-Desktop.bat"
@echo off
chcp 65001 >nul
echo Criando atalho na Área de Trabalho...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$WshShell = New-Object -comObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut(\"$([Environment]::GetFolderPath('Desktop'))\WaleAttack.lnk\"); $Shortcut.TargetPath = \"\"%~dp0WaleAttack.exe\"\"; $Shortcut.WorkingDirectory = \"\"%~dp0\"\"; $Shortcut.IconLocation = \"\"%~dp0WaleAttack.exe,0\"\"; $Shortcut.Description = \"WaleAttack - Gaming Mouse Manager\"; $Shortcut.Save()"
if exist "%USERPROFILE%\Desktop\WaleAttack.lnk" (
    echo [SUCESSO] Atalho criado na sua Área de Trabalho com sucesso!
) else (
    echo [AVISO] Não foi possível criar o atalho automaticamente. Você pode clicar com botão direito em WaleAttack.exe ^> Enviar para ^> Área de Trabalho.
)
echo.
pause
EOF

# README em português
cat << "EOF" > "$RELEASE_DIR/LEIA-ME.txt"
================================================================================
   WaleAttack - Gerenciador de Mouse Gaming para Windows (x64)
================================================================================

Este é o software completo e portátil para configuração do seu mouse gaming (PAW3311/Telink/Beken):
- Ajuste de DPI (1 a 8 estágios personalizáveis de 50 a 22.000 DPI com cores RGB)
- Polling Rate ajustável em tempo real (125Hz, 250Hz, 500Hz, 1000Hz)
- Monitoramento de bateria em tempo real e indicador fluido de carregamento
- Controle completo de iluminação RGB (efeitos, cores, velocidade e brilho)
- Ajustes de Angle Snap, Ripple Control e Key Debounce Time
- Editor completo de Macros e múltiplos Perfis independentes
- Funciona tanto via Conexão Sem Fio 2.4G (Dongle) quanto via Cabo USB-C

--------------------------------------------------------------------------------
COMO USAR:
--------------------------------------------------------------------------------
1. Interface Gráfica:
   - Dê dois cliques em "WaleAttack.exe". O programa é totalmente portátil,
     não precisa de instalador nem de direitos de administrador!
   - (Opcional) Dê dois cliques em "Criar-Atalho-Desktop.bat" para fixar um atalho
     com ícone na sua Área de Trabalho.

2. Interface de Linha de Comando (CLI):
   - Abra o Prompt de Comando (cmd) ou PowerShell nesta pasta e digite:
     .\waleattack-cli.exe --help
     .\waleattack-cli.exe show
     .\waleattack-cli.exe set-polling 1000

--------------------------------------------------------------------------------
CONFIGURAÇÕES E PERFIS:
--------------------------------------------------------------------------------
Os perfis e configurações são salvos automaticamente na pasta padrão do Windows:
%APPDATA%\WaleAttack\profiles.json
================================================================================
EOF

echo "=== 5. Compactando arquivo ZIP ==="
cd "$SCRIPT_DIR/release"
rm -f "${RELEASE_NAME}.zip" "${RELEASE_NAME}.zip.sha256"
zip -r "${RELEASE_NAME}.zip" "$RELEASE_NAME"
sha256sum "${RELEASE_NAME}.zip" > "${RELEASE_NAME}.zip.sha256"

# Copiar para a raiz do projeto para conveniência imediata
cp -p "${RELEASE_NAME}.zip" /home/ollems/Downloads/ATTACKSHARKX11/
cp -p "${RELEASE_NAME}.zip.sha256" /home/ollems/Downloads/ATTACKSHARKX11/
cp -p "$RELEASE_DIR/WaleAttack.exe" /home/ollems/Downloads/ATTACKSHARKX11/

echo "=== Concluído com Sucesso! ==="
ls -lh "$SCRIPT_DIR/release/${RELEASE_NAME}.zip"
ls -lh /home/ollems/Downloads/ATTACKSHARKX11/WaleAttack.exe
