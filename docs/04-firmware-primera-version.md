# Firmware — primera versión (debug)

Primera versión funcional del firmware, en [`src/main.cpp`](../src/main.cpp).
Alcance: las 5 cuerdas láser disparan las 5 notas del **banco central**
(C4 D4 E4 G4 A4) por wavetable, y además cualquiera de las 15 notas del
catálogo completo se puede disparar por caracter recibido en **cualquiera
de dos UARTs**: `Serial2` (el enlace real con un Arduino Pro Micro externo)
o `Serial` (el mismo USB de programación/debug, útil para probar tipeando
en el Monitor Serie) — todo mezclado aditivamente y enviado por I2S al
PCM5102. Los 2
botones de banco (octava +/−) todavía no están cableados como entrada digital
directa en el ESP32 — con el UART ya disponible, esa lógica de banco puede
resolverse del lado del Pro Micro en vez de sumar más GPIO al ESP32.

## Framework y build

**Arduino sobre PlatformIO**, en vez de ESP-IDF nativo. Para una primera
versión de debug, la API de alto nivel (`driver/i2s.h`, `pinMode`/
`digitalRead`) permite iterar más rápido; no cierra la puerta a bajar a
ESP-IDF puro más adelante si hace falta más control (DMA, ISR a medida,
etc.).

`platformio.ini` fija `platform = espressif32 @ 6.9.0` (ESP-IDF 4.4 /
arduino-esp32 2.0.x) explícitamente en vez de dejarlo flotante, para que el
driver `driver/i2s.h` usado en el código (API "legacy", reemplazada por
`driver/i2s_std.h` en ESP-IDF 5 / arduino-esp32 3.x) tenga un target de
compilación estable y reproducible.

### Partition scheme

`notes_data.h` pesa ~1.54 MB de datos en flash (`.rodata`). El partition
table por defecto de Arduino/PlatformIO para ESP32 reserva ~1.31 MB por slot
de OTA (dos slots, A/B) — no alcanza para el binario resultante (código +
esos 1.54 MB). Se configuró `board_build.partitions = huge_app.csv`, que da
un único partition de aplicación de ~3 MB (sin soporte de OTA) — de sobra
para esta etapa. Si más adelante se necesita actualización OTA, hay que
revisar este trade-off (por ejemplo separando las muestras a un partition de
datos aparte, o subiendo a un módulo de más flash).

### Compilando con el Arduino IDE en vez de PlatformIO

El código también se puede compilar directo desde el **Arduino IDE**, como
sketch en `src/soundcard/soundcard.ino` (mismo contenido que `src/main.cpp`,
solo con la extensión que pide el IDE y viviendo en una carpeta con su mismo
nombre, como exige Arduino). Dos cosas de `platformio.ini` **no se heredan**
automáticamente ahí, porque son mecanismos exclusivos de PlatformIO:

- **Partition scheme**: el Arduino IDE no lee `board_build.partitions`. Hay
  que elegirlo a mano en **`Tools → Partition Scheme`**, seleccionando la
  opción "Huge APP (3MB No OTA/...)" (equivalente a `huge_app.csv`). Si se
  deja el default, el build falla con `Sketch too big` — el error apunta
  justo al techo de 1.310.720 bytes (1,3 MB) del slot OTA chico, que es
  exactamente el problema que este partition scheme evita. También conviene
  confirmar `Tools → Flash Size = 4MB`.
- **`-I tools`**: el Arduino IDE no soporta include paths custom sin tocar
  `platform.local.txt`. Por eso `tools/notes_data.h` está **copiado** a
  `src/soundcard/notes_data.h` — es una segunda copia, no un symlink. Si se
  regenera `tools/notes_data.h` (corriendo de nuevo
  `tools/generate_samples.py`), hay que volver a copiarlo manualmente a
  `src/soundcard/` para que el sketch de Arduino IDE quede sincronizado; si
  no, van a divergir en silencio.

`tools/notes_data.h` se referencia directo con `-I tools` en `build_flags`
de `platformio.ini` (para el build de PlatformIO), en vez de copiarlo a `src/`, para que siga habiendo una
única fuente generada por `tools/generate_samples.py`.

## Pinout

| Función | GPIO | Motivo |
|---|---|---|
| Cuerda C | 4 | GPIO común, soporta `INPUT_PULLUP` |
| Cuerda D | 13 | ídem |
| Cuerda E | 14 | ídem |
| Cuerda G | 32 | ídem |
| Cuerda A | 33 | ídem |
| I2S BCK | 27 | — |
| I2S WS (LRCK) | 25 | — |
| I2S DOUT | 26 | — |
| UART RX (Pro Micro) | 21 | GPIO común, soporta pull; usa `Serial2` |

Son valores por defecto propuestos, no un cableado ya definido por el
usuario — están como `static const gpio_num_t` al principio de
`src/main.cpp`, fáciles de cambiar si el hardware real usa otros pines.

Se evitó deliberadamente:

- **GPIO 6–11**: conectados internamente a la flash SPI en casi todos los
  módulos ESP32, no usables como GPIO de propósito general.
- **GPIO 16–17**: en el módulo **WROVER** (a diferencia del WROOM) están
  conectados a la PSRAM integrada.
- **GPIO 0, 2, 5, 12, 15** ("strapping pins"): fijan el modo de arranque
  (boot/flash) o el nivel de voltaje de flash; un pull externo o un estado
  incorrecto en el arranque puede impedir que el ESP32 bootee.
- **GPIO 34–39**: son solo de entrada y **no tienen pull-up/pull-down
  interna** — no sirven para las cuerdas, que necesitan `INPUT_PULLUP` por
  requisito del enunciado.

## Lectura de las cuerdas

Pull-up interna (`INPUT_PULLUP`), activo en bajo: cuerda libre = HIGH,
cuerda "pulsada" (haz cortado) = LOW.

Se hace polling (no interrupciones) una vez por bloque de audio (ver
"Tarea de audio" abajo, ~11.6 ms a 22050 Hz / 256 frames), con un debounce
simple de 15 ms por flanco: un cambio de nivel solo se confirma si se
mantiene estable ese tiempo. Esto evita falsos disparos por ruido eléctrico
o flicker en el borde del haz láser.

### Retrigger

Si una cuerda se "pulsa" de nuevo mientras su nota central sigue sonando,
**la nota se reinicia desde el principio** (se resetea la posición de esa
voz a 0), en vez de ignorarse o sumarse como una voz independiente. Cada
nota del catálogo completo tiene un slot de voz fijo y dedicado (`voices[]`,
indexado igual que `notes[]`), así que "reiniciar" es simplemente pisar
`pos = 0` sobre ese mismo slot — no hace falta lógica de asignación de
voces.

## Mezcla aditiva

`voices[15]` — un slot por nota del catálogo completo (3 bancos × 5
cuerdas), aunque en esta versión solo se disparan los 5 índices del banco
central (`índice = banco_octava * 5 + cuerda`, igual que en
[03](03-notes_data-header.md)). Se dimensiona a las 15 notas completas (no
solo 5) para que sumar los botones de octava en una próxima iteración sea
solo cuestión de llamar a `trigger_note()` con otro índice, sin tocar la
lógica de mezcla.

Por cada muestra de salida, `mix_block()` recorre las voces activas, suma
sus valores en un acumulador `int32_t`, y satura a `int16_t` antes de
escribirla al frame estéreo I2S (mismo valor en L y R) — exactamente el
esquema descripto en `CLAUDE.md` (acumulador de 32 bits, saturación a 16
antes de I2S).

## Entrada por UART (Pro Micro)

Además de las 5 cuerdas, cualquiera de las 15 notas del catálogo completo se
puede disparar por UART desde un Arduino Pro Micro externo (pensado para que
el Pro Micro sea el que lea los sensores láser/otros sensores y decida qué
nota mandar, incluyendo eventualmente los bancos de octava sin necesidad de
cablear botones físicos en el ESP32).

- **Protocolo**: un byte = un disparo, sin framing de línea. `'0'`-`'9'` →
  `notas[0..9]`, `'A'`-`'E'` → `notas[10..14]` — mapeo directo al mismo
  índice fijo de `notes[15]` (`banco_octava * 5 + cuerda`) que ya usan las
  cuerdas. Cualquier otro caracter se descarta en silencio (`uart_poll()`).
  No hace falta debounce del lado del ESP32: a diferencia de una entrada
  digital mecánica/óptica, UART no "rebota" — el único riesgo es basura
  eléctrica, y el filtro de caracteres válidos ya la absorbe (ver más abajo).
- **Puerto**: los comandos se aceptan por **dos** UARTs a la vez —
  `Serial2` (UART2, RX en **GPIO 21**, el enlace real con el Pro Micro) y
  también `Serial` (UART0, el mismo puerto USB que ya se usa para
  programar/debuggear). Esto último es a propósito: permite tipear
  directo en el Monitor Serie (`'0'`-`'9'`, `'A'`-`'E'`) para probar el
  disparo de cualquier nota sin tener el Pro Micro conectado. `process_uart_char()`
  centraliza el mapeo caracter→nota para no duplicar lógica entre ambos
  puertos. `Serial2.begin(UART_BAUD, SERIAL_8N1, UART_RX_PIN, -1)` — el
  `-1` en TX significa que el ESP32 no maneja esa línea, no hace falta por
  ahora porque el enlace con el Pro Micro es unidireccional.
- **Nivel lógico**: el Pro Micro (variante de 5V) no es compatible directo
  con la entrada de 3,3V del ESP32 — **hace falta un divisor resistivo**
  (1kΩ serie + 2kΩ a GND, ≈3,33V) entre el `TX1` del Pro Micro y este pin.
  Nunca conectar el `TX` de 5V directo: el máximo absoluto del GPIO del
  ESP32 es 3,6V.
- **Por qué no hace falta preocuparse por la programación del Pro Micro**:
  el Pro Micro (ATmega32u4) tiene USB nativo — programar el sketch pasa por
  el periférico USB (`Serial`), un hardware completamente separado del UART
  físico (`Serial1`, pines `D0`/`D1`) que se usa para hablar con el ESP32.
  Subir un sketch nuevo no mueve un solo bit por `TX1`. El riesgo residual
  (un glitch brevísimo al resetear el Pro Micro, o la línea flotando si se
  desconecta) se mitiga con el filtro de caracteres válidos de `uart_poll()`
  y, opcionalmente, una pull-up en el `RX` del ESP32 para que la línea
  quede en estado alto definido cuando nadie la maneja.

## I2S

Configuración estándar maestro/TX, 16 bits, estéreo, 22050 Hz,
`dma_buf_count = 4` / `dma_buf_len = 256` frames (~46 ms de buffer total).
No hay timer de hardware dedicado: `i2s_write()` bloquea hasta que hay lugar
en la cola DMA, lo que en la práctica marca el ritmo real de reproducción a
22050 muestras/segundo sin necesidad de un timer aparte — el mismo
comportamiento de bloqueo evaluado al diseñar el pipeline de audio.

Todo corre en una tarea de FreeRTOS (`audio_task`) fijada al **core 0**, que
en cada vuelta: hace polling de las 5 cuerdas, hace polling del UART del Pro
Micro, mezcla un bloque de 256 frames, y lo escribe por I2S. Se eligió el
core 0 a propósito: en
arduino-esp32, `setup()`/`loop()` corren por defecto en el core 1, y en
ESP-IDF las tareas del driver de WiFi/Bluetooth (que acá no usamos) están
fijas al core 0. Como no hay radios inicializadas, el core 0 queda
prácticamente dedicado al audio, separado por completo de `loop()` — que en
esta versión no hace nada, pero que a futuro puede usarse para trabajo no
crítico (por ejemplo, si se agregan los botones de octava con otra
estrategia) sin riesgo de interferir con la mezcla/I2S.

## Limitaciones conocidas de esta versión

- **Sin botones de octava como GPIO directo**: los bancos grave/agudo se
  pueden disparar ya mismo por UART (cualquier índice 0-14), pero no hay
  entradas físicas dedicadas en el ESP32 para ellos — la decisión de qué
  banco corresponde queda del lado del Pro Micro.
- **Latencia no optimizada**: ~46 ms de buffer DMA más el polling por
  bloque (~12 ms) dan un margen pulsación→sonido notable para un
  instrumento gestual. Aceptable para esta etapa de debug; si se percibe
  lento al probar en hardware, ajustar `dma_buf_count`/`dma_buf_len` es el
  primer lugar para mirar.
- **Debounce simple por polling**, no por interrupción — suficiente para
  validar el instrumento en el banco, a revisar si en la placa final los
  sensores láser resultan más ruidosos de lo esperado.
