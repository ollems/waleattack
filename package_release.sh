#!/usr/bin/env bash
# ==============================================================================
#  Gera o pacote de distribuição final do WaleAttack para Linux (tar.gz)
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== 1. Verificando/Compilando binários com PyInstaller ==="
if [ ! -f "dist/waleattack" ]; then
    echo "Compilando dist/waleattack..."
    pyinstaller --noconfirm waleattack.spec
fi

if [ ! -f "dist/waleattack-cli" ]; then
    echo "Compilando dist/waleattack-cli..."
    pyinstaller --noconfirm waleattack-cli.spec
fi

echo "=== 2. Gerando ícones multi-resolução ==="
python3 -c "
from PIL import Image
from pathlib import Path
base = Path('src/waleattack/assets/app_icon.png')
im = Image.open(base)
icons = Path('icons')
icons.mkdir(exist_ok=True)
for sz in (16, 24, 32, 48, 64, 128, 256):
    im.resize((sz, sz), Image.Resampling.LANCZOS).save(icons / f'waleattack_{sz}x{sz}.png')
print('Ícones gerados com sucesso.')
"

echo "=== 3. Montando estrutura do pacote de release ==="
RELEASE_NAME="WaleAttack-Linux-x86_64"
RELEASE_DIR="$SCRIPT_DIR/release/$RELEASE_NAME"

rm -rf "$SCRIPT_DIR/release"
mkdir -p "$RELEASE_DIR/bin"
mkdir -p "$RELEASE_DIR/desktop"
mkdir -p "$RELEASE_DIR/udev"
mkdir -p "$RELEASE_DIR/icons"

# Copiar arquivos
cp -p dist/waleattack "$RELEASE_DIR/bin/"
cp -p dist/waleattack-cli "$RELEASE_DIR/bin/"
cp -p waleattack.desktop "$RELEASE_DIR/desktop/"
cp -p udev/70-waleattack.rules "$RELEASE_DIR/udev/"
cp -p icons/*.png "$RELEASE_DIR/icons/"
cp -p install.sh "$RELEASE_DIR/"
cp -p uninstall.sh "$RELEASE_DIR/"
chmod +x "$RELEASE_DIR/install.sh" "$RELEASE_DIR/uninstall.sh"
chmod +x "$RELEASE_DIR/bin/waleattack" "$RELEASE_DIR/bin/waleattack-cli"

# Gerar README de instalação para o usuário final
cat << "EOF" > "$RELEASE_DIR/README.md"
# WaleAttack - Gerenciador de Mouse Gaming para Linux

Software completo e universal para configuração de mouses gaming sem fio (PAW3311/Telink/Beken) no Linux:
- Ajuste de DPI (1..8 estágios customizáveis e cores RGB)
- Polling Rate em tempo real (125Hz, 250Hz, 500Hz, 1000Hz)
- Monitoramento de bateria em tempo real e indicador animado de carregamento
- Iluminação RGB (efeitos, velocidade, brilho, cores)
- Key debounce, Angle Snap, Ripple Control e Sensor LOD
- Editor visual de macros e perfis independentes
- Compatível com conexões Wireless 2.4G (Dongle) e Cabo USB-C

---

## Como Instalar (Qualquer Distribuição Linux)

Abra o terminal na pasta extraída e execute:

```bash
sudo ./install.sh
```

O instalador irá:
1. Copiar os binários portáteis para `/usr/local/bin` (`waleattack` e `waleattack-cli`).
2. Instalar o lançador gráfico `.desktop` no menu de aplicativos do seu sistema.
3. Instalar os ícones de alta resolução.
4. Configurar as regras `udev` em `/etc/udev/rules.d/70-waleattack.rules` para permitir acesso direto ao mouse sem precisar de root na execução.
5. Recarregar as regras do udev e caches do sistema.

### Instalação sem Root (Apenas para o Usuário Local)

Se preferir não usar `sudo`, instale localmente com:

```bash
./install.sh --user
```

*(Nota: o acesso ao hardware via `/dev/hidraw*` sem root requer a regra de udev configurada pelo menos uma vez pelo administrador).*

---

## Como Usar

- **Interface Gráfica**:
  - Pelo menu de aplicativos procurando por **WaleAttack**, ou
  - Digitando `waleattack` no terminal.

- **Interface de Linha de Comando (CLI)**:
  - `waleattack-cli --help`
  - `waleattack-cli show`
  - `waleattack-cli set-stage 2`
  - `waleattack-cli set-polling 1000`

---

## Como Desinstalar

Basta executar no terminal:

```bash
sudo waleattack-uninstall
```

Ou dentro desta pasta:
```bash
sudo ./uninstall.sh
```
Para remover também as configurações salvas em `~/.config/waleattack`, adicione a flag `--purge`:
```bash
sudo waleattack-uninstall --purge
```
EOF

echo "=== 4. Compactando tar.gz ==="
cd "$SCRIPT_DIR/release"
tar -czvf "${RELEASE_NAME}.tar.gz" "$RELEASE_NAME"
sha256sum "${RELEASE_NAME}.tar.gz" > "${RELEASE_NAME}.tar.gz.sha256"

echo "=== Release criado com sucesso! ==="
echo "Arquivo: $SCRIPT_DIR/release/${RELEASE_NAME}.tar.gz"
ls -lh "$SCRIPT_DIR/release/${RELEASE_NAME}.tar.gz"
cat "$SCRIPT_DIR/release/${RELEASE_NAME}.tar.gz.sha256"
