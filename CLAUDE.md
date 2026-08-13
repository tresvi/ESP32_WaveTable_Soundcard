# ESP32 WaveTable Soundcard

Instrumento musical basado en ESP32: 5 "cuerdas láser" + 2 botones,
reproduce notas de lira/arpa pregrabadas como wavetables en flash, con
polifonía de 15 voces. Salida de audio vía I2S a un DAC PCM5102.

Este archivo resume las decisiones de diseño ya tomadas para que una
sesión futura no tenga que re-derivarlas. El detalle del pipeline que
genera las muestras de audio está en [docs/](docs/README.md) — no lo
dupliques acá, referencialo.

## Estado actual

- **Hecho:** selección de escala/notas, obtención y procesamiento de las
  15 muestras de audio (`tools/generate_samples.py` → `tools/notes_data.h`).
  Primera versión (debug) del firmware en `src/main.cpp` (PlatformIO +
  Arduino): I2S al PCM5102, lectura con pull-up interna y mezcla aditiva de
  las 5 cuerdas láser sobre el banco central de notas — ver
  [docs/04-firmware-primera-version.md](docs/04-firmware-primera-version.md).
- **Falta:** cablear los 2 botones de banco (octava +/−) en el firmware —
  el catálogo de 15 notas y el array de voces ya están preparados para
  eso, solo falta disparar los índices de los bancos grave/agudo.
- **Pendiente:** confirmar con el autor de la librería "Lyre Lyre"
  (`jscomposition.nz@gmail.com`) si su licencia permite incrustar las
  muestras en el firmware de un producto distribuido/vendido (ver
  [docs/01-obtencion-de-notas.md](docs/01-obtencion-de-notas.md)). Si no
  se consigue permiso, hay que resamplear las notas desde una fuente con
  licencia explícita (`256OrchestralSamples` o `KSHarp`, ambas ya
  evaluadas — ver mismo documento).

## Hardware

- **MCU:** ESP32, 4 MB de flash.
- **DAC:** PCM5102, conectado por **I2S**.
- **Reproducción:** un timer con período igual al intervalo de muestreo
  incrementa un puntero de posición por voz activa, lee la muestra
  correspondiente de flash y la escribe al registro de salida I2S.

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

## Polifonía (diseño, no implementado aún)

- **15 voces simultáneas.**
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
