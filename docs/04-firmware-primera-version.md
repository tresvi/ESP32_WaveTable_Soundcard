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
  `src/soundcard/notes_data_greek_lyra.h` — es una segunda copia, no un
  symlink.

### ⚠️ Archivos duplicados que hay que mantener sincronizados

Como consecuencia de soportar los dos entornos de build, hay tres pares de
archivos duplicados. **No hay symlinks ni automatización: si se edita uno hay
que copiar el cambio al otro a mano, o divergen en silencio.**

| PlatformIO | Arduino IDE | Origen |
|---|---|---|
| `src/main.cpp` | `src/soundcard/soundcard.ino` | mismo código; difieren sólo en el `#include` de las muestras y en dos líneas de prueba en `setup()` |
| `src/melody.h` | `src/soundcard/melody.h` | copia idéntica |
| `tools/notes_data.h` | `src/soundcard/notes_data_greek_lyra.h` | generado por `tools/generate_samples.py`; **la copia del sketch lleva el nombre del set de muestras** |

Sobre el tercer par: el generador emite siempre `tools/notes_data.h` con
nombre genérico, pero en el sketch la copia se llama
`notes_data_greek_lyra.h` para identificar de qué instrumento son las
muestras (lira griega, librería "Lyre Lyre" — ver
[01](01-obtencion-de-notas.md)). Eso deja el nombre libre para eventuales
sets alternativos (por ejemplo si hubiera que reemplazar la fuente por una
con licencia explícita). Consecuencia práctica: al regenerar hay que copiar
**y renombrar**, no sólo copiar.

Para verificar que no divergieron:

```bash
diff src/main.cpp src/soundcard/soundcard.ino; diff src/melody.h src/soundcard/melody.h && diff tools/notes_data.h src/soundcard/notes_data_greek_lyra.h
```

El primer `diff` debe mostrar exactamente tres líneas distintas (el
`#include` y las dos de prueba); cualquier otra diferencia es una
desincronización real.

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

### Configuración del módulo PCM5102

El módulo usado es el breakout genérico (violeta, con jack de 3,5 mm) que
expone `SCK/BCK/DIN/LCK/GND/VIN` en un header y trae **cuatro jumpers de
soldadura** en la cara inferior (`H`/`L` por cada uno). Cableado hacia el
ESP32:

| Pin del módulo | Va a | Motivo |
|---|---|---|
| `BCK` | GPIO 27 | bit clock I2S |
| `LCK` | GPIO 25 | word select / LRCK |
| `DIN` | GPIO 26 | datos (el ESP32 transmite) |
| `VIN` | 3V3 | mismos niveles lógicos que el ESP32; no usar 5V |
| `GND` | GND | — |
| **`SCK`** | **GND** | *system clock*. El firmware **no genera MCLK**; con `SCK` a GND el chip usa su PLL interno derivando todo de `BCK`. **Flotando** el detector de reloj capta ruido y el chip entra/sale de error de reloj muteando la salida — se probó en hardware y es fuente real de fallas |

Jumpers de la cara inferior, con la posición que corresponde a este
firmware:

| Jumper | Posición | Por qué |
|---|---|---|
| **`FMT`** | **L** | `L` = I2S estándar, que es lo configurado (`I2S_COMM_FORMAT_STAND_I2S`). En `H` el chip espera Left-Justified y suena distorsionado/corrido |
| **`XSMT`** | **H** | Soft-mute. `L` = salida muteada, silencio total. Es **el primer sospechoso** ante un "no suena" con todo lo demás bien |
| **`DEMP`** | **L** | De-énfasis (para CDs con pre-énfasis a 44,1 kHz). Las muestras no lo tienen; en `H` colorea el sonido |
| **`FLT`** | **L** | Filtro digital de latencia normal. El más inofensivo; `L` es lo estándar |

Para verificar sin resoldar: multímetro en continuidad entre cada pin de
control y `A3V3` (→ está en `H`) o `AGND` (→ está en `L`).

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

## Keep-alive del amplificador (tono de 20 Hz)

Síntoma observado en hardware: al disparar una nota **con el sistema en
silencio**, no se escuchaba el ataque — la nota parecía empezar por la mitad.
Con otra nota ya sonando, el ataque salía limpio.

**No era un problema del firmware ni del DAC.** Se descartaron por orden:

1. *Bug de reproducción*: `trigger_note()` siempre resetea `pos = 0` y ese
   mismo bloque ya contiene la nota desde la muestra 0. Además el reloj I2S
   nunca se detiene (`audio_task` escribe bloques de silencio
   continuamente), así que no hay "arranque en frío" del stream.
2. *Auto-mute del PCM5102A por ceros digitales*: se probó agregar un dither
   de ±1 LSB para que el stream nunca fuera cero puro. **No cambió nada**,
   lo que descartó esta hipótesis (y el dither se removió).
3. *`SCK` flotante* (fuera de spec, se corrigió igual atándolo a GND).
4. **Causa real**: el parlante amplificado usado para probar tiene
   **auto-standby** — corta su etapa de salida tras unos segundos de
   silencio y tarda 100-500 ms en despertar, comiéndose el transitorio de
   ataque. Confirmado escuchando con auriculares pasivos directo al jack del
   PCM5102: ahí el ataque aparece completo.

### Solución

Un tono senoidal continuo de **20 Hz** sumado a la mezcla (`keepalive_init()`
+ el término inicial de `acc` en `mix_block()`), que mantiene despierto al
detector de señal del amplificador.

La asimetría que hace que esto funcione sin ser molesto: el detector del
amplificador mide **amplitud eléctrica**, mientras que lo que molestaría es
el **sonido acústico** — y a 20 Hz (el borde inferior de la audición humana)
un parlante chico es muy ineficiente (no mueve aire suficiente) y el oído es
muchísimo menos sensible (curvas de Fletcher-Munson). El amplificador "ve" la
señal; el usuario casi no la escucha.

Detalles de la implementación:

- **Frecuencia baja, no alta**: a 22050 Hz de tasa de muestreo el máximo
  posible es ~11 kHz (Nyquist), que es claramente audible y molesto. Para
  que un tono agudo fuera inaudible haría falta 17-18 kHz, imposible sin
  rehacer todos los wavetables a mayor tasa de muestreo.
- **Suena siempre**, no solo durante los silencios, para no generar clicks
  al entrar/salir del tono.
- Tabla de 256 muestras generada en `setup()` + acumulador de fase de 32
  bits (los 8 bits altos indexan la tabla) — sin `sinf()` en el camino
  crítico de audio.
- `KEEPALIVE_AMPLITUDE` (sobre el pico de ±2048 por nota) es el valor a
  tunear: subirlo de a poco hasta que el amplificador deje de entrar en
  standby. **`0` desactiva el keep-alive por completo.**
- **Valores actuales: 20 Hz / amplitud 60**, ajustados a oído sobre el
  hardware real. La primera versión funcional fue 40 Hz / 120; bajar a la
  mitad ambos parámetros siguió manteniendo despierto al amplificador y
  redujo todavía más el riesgo de que el tono se perciba. Son específicos
  del parlante usado: con otro amplificador probablemente haya que
  recalibrarlos (o desactivarlo, ver abajo).

### Cuándo desactivarlo

Es un *workaround* para el parlante de prueba, no una necesidad del diseño.
Para el producto final conviene elegir un módulo amplificador **sin
auto-standby** (los class-D típicos tipo PAM8403 / TPA311x son always-on) y
poner `KEEPALIVE_AMPLITUDE = 0` — así no se gasta headroom de mezcla ni se
mete una señal que no aporta nada musicalmente.

## Entrada por UART (Pro Micro)

Además de las 5 cuerdas, cualquiera de las 15 notas del catálogo completo se
puede disparar por UART desde un Arduino Pro Micro externo (pensado para que
el Pro Micro sea el que lea los sensores láser/otros sensores y decida qué
nota mandar, incluyendo eventualmente los bancos de octava sin necesidad de
cablear botones físicos en el ESP32).

- **Protocolo**: un byte = un disparo, sin framing de línea. `'0'`-`'9'` →
  `notas[0..9]`, `'A'`-`'E'` → `notas[10..14]` — mapeo directo al mismo
  índice fijo de `notes[15]` (`banco_octava * 5 + cuerda`) que ya usan las
  cuerdas. El **espacio** `' '` reproduce una melodía de prueba completa con
  su ritmo (ver [05](05-melodias-de-prueba.md)). Cualquier otro caracter se
  descarta en silencio (`uart_poll()`).
  No hace falta debounce del lado del ESP32: a diferencia de una entrada
  digital mecánica/óptica, UART no "rebota" — el único riesgo es basura
  eléctrica, y el filtro de caracteres válidos ya la absorbe (ver más abajo).
- **Baudrate: 57600** (`UART_BAUD`), y tiene que coincidir con el
  `Serial1.begin()` del Pro Micro. La primera versión usaba 115200; se bajó
  a 57600 en el commit `ecb8d3d` **por robustez**: la línea de transmisión
  es muy básica (cables sueltos + divisor resistivo, sin blindaje ni
  impedancia controlada), y a menor baudrate cada bit dura el doble, lo
  que da más margen frente al redondeo de flancos que introduce el RC del
  divisor con la capacidad del pin, y frente al ruido acoplado. No es que
  115200 fallara de forma demostrada — es una decisión de margen. El
  protocolo es de un byte por evento, así que 57600 (~5.760 bytes/s) sigue
  siendo miles de veces más de lo necesario. Si en algún momento hiciera
  falta más velocidad, antes de subir el baudrate conviene mejorar la línea
  (cable corto, par trenzado con GND, o un level-shifter activo en vez del
  divisor).
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
- **Latencia no optimizada: hasta ~70 ms** entre pulsar una cuerda y que
  suene, en el peor caso. No es "un bloque" (11,6 ms) — hay dos factores
  que lo multiplican, cada uno hasta 3 bloques:
  1. *Detección + debounce (hasta 3 × 11,6 ≈ 35 ms)*. `strings_poll()`
     corre una vez por bloque, y el debounce de 15 ms se evalúa en esos
     chequeos discretos. Peor caso: el pulso cae justo después de un
     chequeo (+1 bloque hasta detectarlo), el siguiente chequeo lleva
     11,6 ms de estable (< 15, no confirma), y recién el tercero llega a
     23,2 ms ≥ 15 y dispara. Este multiplicador depende de la relación
     `DEBOUNCE_MS` / período de bloque: con 15 ms y 11,6 ms son 3 bloques.
  2. *Cola DMA (hasta 3 × 11,6 ≈ 35 ms)*. `i2s_write()` no espera a que el
     bloque *suene*, sólo a que haya un slot libre. Como `mix_block()`
     calcula en microsegundos, en régimen la cola de `dma_buf_count = 4`
     está siempre llena: el bloque recién calculado entra **detrás de 3
     bloques ya encolados** que tienen que sonar primero.

  Las notas por UART se ahorran el factor 1 (no hay debounce) y quedan en
  ~35 ms. Para bajar la latencia real, las palancas son `DEBOUNCE_MS`
  (menos → más sensible a ruido), `BLOCK_FRAMES` (menos → períodos más
  cortos pero más overhead de CPU) y `dma_buf_count` (menos → menos colchón,
  más riesgo de underrun). Aceptable para esta etapa; a revisar si al tocar
  se percibe lento.
- **Debounce simple por polling**, no por interrupción — suficiente para
  validar el instrumento en el banco, a revisar si en la placa final los
  sensores láser resultan más ruidosos de lo esperado.
