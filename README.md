# WaleAttack

<p align="center">
  <img src="src/waleattack/assets/app_icon.png" alt="WaleAttack Logo" width="128" height="128">
</p>

<p align="center">
  <strong>Software moderno, aberto e multiplataforma (Linux & Windows) para gerenciamento e configuração de mouses gaming sem fio.</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Plataformas-Linux%20%7C%20Windows-blue" alt="Platforms">
  <img src="https://img.shields.io/badge/Python-3.10%2B-brightgreen" alt="Python Version">
  <img src="https://img.shields.io/badge/Licen%C3%A7a-MIT-orange" alt="License">
  <img src="https://img.shields.io/badge/GUI-Tkinter%20Nativo-blueviolet" alt="GUI">
  <img src="https://img.shields.io/badge/Hardware-VID%201d57%20%2F%20248a-informational" alt="Hardware">
</p>

---

## 📌 Visão Geral

O **WaleAttack** é uma suíte completa, leve e de código aberto criada para fornecer controle total sobre mouses gaming baseados nos sensores ópticos **PixArt PAW3311 / PAW3395** e chipsets Telink/Beken (identificados pelos Vendor IDs `0x1D57` e `0x248A`).

Ao contrário dos softwares proprietários que frequentemente são pesados ou restritos a versões antigas do Windows, o WaleAttack foi projetado do zero com foco em **eficiência**, **privacidade (100% offline, sem telemetria)** e **verdadeira portabilidade** no Linux e no Windows.

---

## ✨ Recursos

- 🎯 **Ajuste de DPI Preciso**:
  - Configuração de 1 até 8 estágios personalizáveis (de 50 a 22.000 DPI).
  - Seleção de cor RGB independente para cada estágio.
  - Alternância de estágio em tempo real (inclusive pelo botão físico no mouse).
- ⚡ **Polling Rate em Tempo Real**:
  - 125 Hz, 250 Hz, 500 Hz e 1.000 Hz com aplicação instantânea no hardware.
- 🔋 **Monitoramento de Bateria & Indicador de Carregamento**:
  - Máquina de estados precisa para leitura em tempo real via Input Reports HID.
  - Indicador animado e fluido quando o cabo USB-C está conectado carregando o mouse.
  - Detecção imediata de conexão e desconexão do cabo / dongle sem travamentos.
- 💡 **Controle de Iluminação RGB**:
  - Efeitos: Estático, Respiração, Neon, Onda de Cores, Desligado.
  - Ajuste fino de velocidade, brilho e seletor de cores RGB.
- ⚙️ **Ajustes de Sensor e Desempenho**:
  - **Angle Snap** (ligado/desligado).
  - **Ripple Control** (suavização em altas sensibilidades).
  - **Key Debounce Time** configurável de 2 ms a 30 ms (tempo de resposta dos botões).
  - Temporizadores de **Sleep Mode** e **Deep Sleep**.
- 🖲️ **Remapeamento de Botões**:
  - Configuração completa dos botões 1 a 5 (Cliques, DPI+/-, Botão de Fogo, Easy Aim, Navegador e Mídia).
- 📝 **Gerenciador de Macros**:
  - Editor visual para gravação e edição de sequências de teclas, delays e repetições.
- 📁 **Perfis Independentes**:
  - Crie, renomeie, exporte e importe perfis em formato `.json`.
- 🔌 **Conectividade Dupla**:
  - Suporte completo tanto via Receptor Sem Fio 2.4G (Dongle) quanto via Cabo USB direto.
- 🖥️ **Duas Interfaces**:
  - Interface Gráfica nativa e moderna (`waleattack`).
  - Utilitário de Linha de Comando rápido para scripts e automações (`waleattack-cli`).

---

## 🚀 Instalação e Execução

### 🐧 No Linux (Qualquer Distribuição)

O WaleAttack possui um instalador universal testado em Ubuntu, Debian, Fedora, Arch Linux, Manjaro, openSUSE, Void, Alpine, etc.

#### Opção A: Usando o Pacote Pré-compilado (Recomendado)
Baixe o arquivo `WaleAttack-Linux-x86_64.tar.gz` nas [Releases](../../releases), extraia e execute:

```bash
sudo ./install.sh
```

O instalador automático:
1. Copia os binários portáteis para `/usr/local/bin` (`waleattack` e `waleattack-cli`).
2. Adiciona o atalho no menu de aplicativos (`waleattack.desktop`) com ícone em alta resolução.
3. Instala as regras de permissão udev em `/etc/udev/rules.d/70-waleattack.rules` para acesso ao mouse sem precisar de root.
4. Recarrega as regras do sistema.

#### Opção B: Instalação apenas para o Usuário Local (sem root)
```bash
./install.sh --user
```

#### Para Desinstalar no Linux
Basta rodar no terminal:
```bash
sudo waleattack-uninstall
```
*(Adicione `--purge` se quiser excluir também as configurações salvas em `~/.config/waleattack`).*

---

### 🪟 No Windows (10 / 11)

1. Baixe o arquivo `WaleAttack.exe` ou `WaleAttack-Windows-x64.zip` nas [Releases](../../releases).
2. **Execução Direta**: Dê dois cliques em `WaleAttack.exe`. O software é **100% portátil** (não requer instalação nem privilégios de administrador).
3. **Atalho Opcional**: Dentro do `.zip`, dê dois cliques em `Criar-Atalho-Desktop.bat` para criar automaticamente um atalho com ícone na sua Área de Trabalho.

---

## 💻 Interface de Linha de Comando (CLI)

O WaleAttack disponibiliza o utilitário `waleattack-cli` (Linux) e `waleattack-cli.exe` (Windows):

```bash
# Ajuda geral
waleattack-cli --help

# Listar dispositivos compatíveis detectados
waleattack-cli list

# Exibir status completo (DPI, polling, bateria, debounce, iluminação)
waleattack-cli show

# Alterar Polling Rate para 1000 Hz
waleattack-cli set-polling 1000

# Alterar DPI do estágio 2 para 1600 DPI
waleattack-cli set-dpi 2 1600

# Selecionar estágio de DPI ativo (ex: estágio 3)
waleattack-cli set-stage 3

# Configurar sensor (Angle Snap desligado, Ripple Control ligado)
waleattack-cli set-sensor --angle-snap off --ripple-control on

# Configurar iluminação (Modo 4, brilho 8, velocidade 8, cor verde)
waleattack-cli set-light --mode 4 --brightness 8 --speed 8 --color 00ff00

# Observar mudanças de estado em tempo real no hardware
waleattack-cli watch --seconds 30
```

---

## 🛠️ Executando a Partir do Código-Fonte

Requisitos: **Python 3.10 ou superior**.

1. Clone o repositório:
```bash
git clone https://github.com/OLLEMS/waleattack.git
cd waleattack
```

2. Instale as dependências:
```bash
pip install -r requirements.txt
```

3. Execute a interface gráfica:
```bash
python3 run_gui.py
```

4. Execute a interface CLI:
```bash
python3 run_cli.py show
```

5. Executar os testes automatizados:
```bash
python3 -m pytest
```

---

## 📦 Como Compilar os Executáveis Standalone

O projeto inclui scripts automatizados de empacotamento com PyInstaller:

- **Linux (gera binários e tarball universal)**:
  ```bash
  ./package_release.sh
  ```
- **Windows (gera executável .exe e zip via Wine ou nativamente no Windows)**:
  ```bash
  ./build_win_release.sh
  ```

---

## 🔒 Privacidade e Segurança

- **Zero Telemetria**: Nenhuma conexão com a internet é feita pelo aplicativo em momento algum.
- **Acesso Direto ao Hardware**: Comunicação direta via nós HID padronizados (`/dev/hidraw*` no Linux e `hid.dll` no Windows).
- **Armazenamento Local**: Perfis e preferências são mantidos exclusivamente em sua máquina local (`~/.config/waleattack` ou `%APPDATA%\WaleAttack`).

---

## 📜 Licença e Isenção de Responsabilidade

Este projeto é distribuído sob a licença [MIT](LICENSE).

> **Aviso Legal**: WaleAttack é um projeto independente de código aberto desenvolvido para fins de interoperabilidade de hardware. Todos os nomes de marcas e modelos de terceiros pertencem aos seus respectivos proprietários e são citados apenas para fins de identificação de compatibilidade.
