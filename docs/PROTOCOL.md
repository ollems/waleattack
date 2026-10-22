# Especificação do Protocolo HID (Hardware Wireless Gaming Mouse VID 1d57:fa60 / 1d57:fa55)

## Captura real de pacotes (Linux/Windows, `waleattack-cli probe`, mouse ligado)
```
0x0b: 0b 08 55 40 81 01 01 00
0x06: 06 09 01 01 fe 00 00 00 00
0x05: 05 0f 01 40 01 a8 00 ff 00 01 02 01 eb 00 00
0x04: 04 38 01 01 01 3f 20 20 12 23 2c 4b 75 81 00 00 00 00 00 00 00 01 00 00 03 ff 00 00 00 ff 00 00 00 ff ff ff 00 00 ff ff ff 00 ff ff 40 00 ff ff ff 02 0f 5c 00 00 00 00
```
Formato comum da resposta: `byte0 = report id`, `byte1 = tamanho total`. O app só aceita a resposta
se os dois baterem, e a biblioteca faz a mesma checagem.

## Validado contra o hardware (leitura e escrita)
* Handshake `SET 0xA0 [rid, len, 0, flag, 0, 0, 0]` -> `GET 0xA0` (`byte1 == 1`) -> `GET rid`.
* `flag = 0` para o report `0x0b` e `flag = 1` para `0x06`, `0x05`, `0x04`.
* Escrita (`0x4a1970`): `SetFeature(report)` com até 5 tentativas e `Sleep(200 ms)` após o envio.
* Teste real no hardware: escrita do estágio 2 (`1500 -> 1600 -> 1500 DPI`) gravou no mouse e leu de volta com checksum válido.

## Report `0x04` (56 bytes — parser `0x4993c0`, construtor `0x4a2050`, reset `0x49f36c`)

| Offset | Campo | Detalhe |
|---|---|---|
| 0..2 | cabeçalho | `04 38 01` |
| 3 | Angle Snap (`+0x944`) | `0` = off, `1` = on |
| 4 | Ripple Control (`+0x940`) | `0` = off, `1` = on |
| 5 | máscara de estágios habilitados | bit `i` = estágio `i+1` ativo (`0x3f` = estágios 1..6) |
| 6, 7 | máscara de faixa alta (`pos > 220`) | `0x4a21cd..0x4a21d2` grava o mesmo byte em `[6]` e `[7]` (`0x20` = estágio 6) |
| 8..15 | código de DPI por estágio (8 B) | traduzido pela tabela `0x4e50a8` / `0x4ec028` (220 entradas) |
| 16..23 | flag de faixa alta na tabela (8 B) | `1` quando `201 <= pos <= 220` ou `pos > 300`; `0` caso contrário |
| 24 | estágio de DPI atual (1-based) | `1..8` |
| 25..48 | cores dos 8 estágios | 8 × 3 bytes em ordem `(R, G, B)` |
| 49 | constante | `0x02` (`0x4a2378`) |
| 50..51 | checksum 16-bit big-endian | `sum(report[3:50]) & 0xFFFF` (`0x4a2370..0x4a2402`) |
| 52..55 | padding | `00 00 00 00` |

## Report `0x05` (15 bytes — parser `0x4996e0`, construtor `0x4a1e20`)

| Offset | Campo | Detalhe |
|---|---|---|
| 0..2 | cabeçalho | `05 0f 01` |
| 3 | modo de iluminação (`+0x94c`) | `(light_mode & 0x0F) << 4` (`0..6`) |
| 4 | deep sleep (alto) + velocidade LED (baixo) | `(deep_sleep & 0xF0) \| ((9 - light_speed) & 0x0F)` |
| 5 | deep sleep (baixo) + brilho LED (baixo) | `((deep_sleep & 0x0F) << 4) \| (brightness if mode in (1,5) else 8)` |
| 6..8 | cor da iluminação (`+0x95c`) | 3 bytes `(R, G, B)` |
| 9 | sleep / light-off timer (`+0x930`) | minutos |
| 10 | key debounce (`+0x958`) | valor × 2 ms (ex.: `0x02` = 4 ms) |
| 11..12 | checksum 16-bit big-endian | `sum(report[3:11]) & 0xFFFF` |
| 13..14 | padding | `00 00` |

## Report `0x06` (9 bytes — parser `0x4a3ab6`, construtor `0x4a1f1b`)
* Formato: `06 09 01 <rate_byte> <~rate_byte & 0xFF> 00 00 00 00`
* `rate_byte`: `8` = 125 Hz, `4` = 250 Hz, `2` = 500 Hz, `1` = 1000 Hz.
