# ESP32 WaveTable Soundcard

Instrumento musical basado en ESP32: 5 "cuerdas láser" + 2 botones,
reproduce notas de lira/arpa pregrabadas como wavetables en flash, con
polifonía de 15 voces. Salida de audio vía I2S a un DAC PCM5102.

Este archivo resume las decisiones de diseño ya tomadas para que una
sesión futura no tenga que re-derivarlas. El detalle está en `docs/`
(índice en [README.md](README.md)) — no lo dupliques acá, referencialo.

## Estado actual

- **Hecho:** selección de escala/notas, obtención y procesamiento de las
  15 muestras de audio (`tools/generate_samples.py` → `tools/notes_data.h`).
  Firmware **funcionando y probado en hardware real** — ver
  [docs/04-firmware-primera-version.md](docs/04-firmware-primera-version.md):
  - I2S al PCM5102, mezcla aditiva de 15 voces, todo en una tarea de
    FreeRTOS fijada al core 0.
  - Disparo de notas por 3 vías: las 5 cuerdas láser (GPIO con pull-up
    interna, banco central), y cualquiera de las 15 notas por caracter
    recibido en UART0 (USB) o UART2 (enlace con un Arduino Pro Micro).
  - Melodía de prueba con ritmo al recibir `' '` (módulo aparte,
    `src/melody.h` — ver
    [docs/05-melodias-de-prueba.md](docs/05-melodias-de-prueba.md)).
  - Tono keep-alive de 20 Hz para parlantes amplificados con auto-standby.
- **Falta:** los 2 botones de banco (octava +/−) no están cableados como
  GPIO en el ESP32. Con el UART ya funcionando, esa lógica puede resolverse
  del lado del Pro Micro (que mandaría el índice absoluto 0-14) en vez de
  sumar entradas al ESP32.
- **Pendiente:** confirmar con el autor de la librería "Lyre Lyre"
  (`jscomposition.nz@gmail.com`) si su licencia permite incrustar las
  muestras en el firmware de un producto distribuido/vendido (ver
  [docs/01-obtencion-de-notas.md](docs/01-obtencion-de-notas.md)). Si no
  se consigue permiso, hay que resamplear las notas desde una fuente con
  licencia explícita (`256OrchestralSamples` o `KSHarp`, ambas ya
  evaluadas — ver mismo documento).

## Hardware

- **MCU:** ESP32-WROVER (D0WDQ6), 4 MB de flash.
- **DAC:** PCM5102, conectado por **I2S**. Ojo con el módulo: `SCK` va a
  **GND** (habilita el PLL interno; flotando causa errores de reloj) y
  `XSMT` en alto (si no, salida muteada). Pinout completo en
  [docs/04-firmware-primera-version.md](docs/04-firmware-primera-version.md).
- **Reproducción:** *(el diseño original preveía un timer por muestra; en la
  implementación real no hizo falta)*. Se mezcla por bloques de 256 frames y
  se escribe con `i2s_write()`, que bloquea hasta que la DMA tiene lugar —
  eso marca el ritmo real de 22050 sps sin ningún timer aparte.

## Formato de audio

- **Tasa de muestreo: 22050 Hz.** Nyquist en 11.025 kHz — de sobra para
  los armónicos de una lira/arpa; reduce el almacenamiento a la mitad
  frente a 44.1 kHz.
- **16 bits con signo (`int16_t`)** por muestra — formato nativo esperado
  por el I2S del ESP32 hacia el PCM5102.
- **Amplitud de pico ±2048 por nota** (no ±32767). Elegido así para dejar
  margen de suma: 15 voces × 2048 = 30 720, dentro de ±32767 sin necesidad
  de aplicar ganancia extra al mezclar.
- Cada nota se normaliza a su propio pico de ±2048 de forma independiente
  (no hay una ganancia común entre las 15 notas — ver
  [docs/01-obtencion-de-notas.md](docs/01-obtencion-de-notas.md)).

## Polifonía (implementado en `mix_block()`)

- **15 voces simultáneas**, un slot fijo por nota del catálogo. Como el slot
  es fijo, volver a disparar una nota que ya suena la **reinicia desde el
  ataque** (política de retrigger) en vez de superponerla.
- **Acumulador de mezcla: 32 bits con signo**, no 16. En el ESP32 (Xtensa,
  registros de 32 bits) leer un `int16_t` y sumarlo a un acumulador de
  32 bits no cuesta ciclos extra frente a usar un acumulador de 16 bits
  (el hardware tiene carga con extensión de signo en 1 ciclo), así que no
  hay motivo para arriesgarse con 16 bits solo por "ahorrar".
- El resultado de la suma se satura (clamp) a 16 bits antes de escribirlo
  al registro I2S.

## Instrumento / escala musical

- **5 cuerdas láser**, cada una dispara una nota al "pulsarla" (cortar el
  haz).
- **2 botones** desplazan el banco activo una octava arriba o abajo.
- **15 notas = 3 bancos de 5**, escala **pentatónica C-D-E-G-A** (Do-Re-Mi-Sol-La).
  Se eligió pentatónica porque cualquier combinación simultánea de las 5
  cuerdas suena consonante, sin importar el orden — clave para un
  instrumento gestual donde el usuario puede activar varios haces a la vez.
  El banco central (sin botones) es el más "usado"/reconocible al oído
  (registro medio, alrededor del Do central).

| Banco | Notas |
|---|---|
| Graves (botón −) | C3 D3 E3 G3 A3 |
| Central (default) | C4 D4 E4 G4 A4 |
| Agudos (botón +) | C5 D5 E5 G5 A5 |

Detalle de frecuencias/MIDI en
[docs/01-obtencion-de-notas.md](docs/01-obtencion-de-notas.md).

## Datos de audio

Las 15 notas están en `tools/notes_data.h` (autogenerado, no editar a
mano — ver [docs/03-notes_data-header.md](docs/03-notes_data-header.md)).
Índice fijo: `banco_octava * 5 + cuerda` (banco 0=grave/1=central/2=agudo,
cuerda 0..4 = C,D,E,G,A).

Para regenerar tras cambiar fuente/duraciones/umbrales:

```bash
python tools/generate_samples.py
```

## ⚠️ Archivos duplicados

El proyecto soporta **dos entornos de build** (PlatformIO y Arduino IDE), y
eso obliga a mantener tres pares de archivos duplicados **a mano** — no hay
symlinks ni automatización, si se edita uno hay que copiar el cambio al otro:

| PlatformIO | Arduino IDE |
|---|---|
| `src/main.cpp` | `src/soundcard/soundcard.ino` |
| `src/melody.h` | `src/soundcard/melody.h` |
| `tools/notes_data.h` | `src/soundcard/notes_data_greek_lyra.h` |

Ojo con el tercer par: el generador emite `tools/notes_data.h` con nombre
genérico, pero la copia del sketch se llama **`notes_data_greek_lyra.h`**
(el nombre identifica el set de muestras — lira griega de "Lyre Lyre"). Al
regenerar hay que copiar **y renombrar**. Los dos `.ino`/`.cpp` incluyen
nombres distintos por eso mismo.

Verificar con:

```bash
diff src/main.cpp src/soundcard/soundcard.ino; diff src/melody.h src/soundcard/melody.h && diff tools/notes_data.h src/soundcard/notes_data_greek_lyra.h
```

(el primer `diff` va a mostrar exactamente una línea distinta — el
`#include` — y las dos líneas de prueba en `setup()`; eso es lo esperado.)

El build real que viene usando el autor es el del **Arduino IDE**, con
`Tools → Partition Scheme = Huge APP (3MB No OTA)` — sin eso falla con
`Sketch too big` (el binario pesa ~1.9 MB por los datos de audio).

Detalle de por qué existe esta duplicación en
[docs/04-firmware-primera-version.md](docs/04-firmware-primera-version.md).
