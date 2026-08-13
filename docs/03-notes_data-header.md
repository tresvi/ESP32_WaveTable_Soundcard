# `notes_data.h`

Header C con las 15 notas ya procesadas (ver
[01](01-obtencion-de-notas.md) y [02](02-recorte-de-notas.md)), listo para
incluir en el firmware del ESP32.

**Se genera automáticamente con `tools/generate_samples.py` — no se edita a
mano.** El propio archivo lo dice en su primera línea:

```c
// Generado automaticamente por tools/generate_samples.py
// No editar a mano.
```

Cualquier cambio (otra fuente de audio, otras duraciones, otro umbral de
recorte) se hace en el script y se corre de nuevo:

```bash
python tools/generate_samples.py
```

## Estructura del archivo

### 1. Un array `int16_t` por nota

```c
static const int16_t note_C3[101800] = {
    69,389,649,587,713,807,897,980,1042,1110,1151,1184,1194,1196,1180,1163,
    ...
};
```

Hay 15 arrays, uno por nota, nombrados `note_<NOTA>` (`note_C3`, `note_D3`,
`note_E3`, `note_G3`, `note_A3`, `note_C4`, ... `note_A5`). El largo de cada
uno es distinto porque cada nota tiene su propia duración (ver documento
02) — van desde 22 815 muestras (C5, ~1.03 s) hasta 101 800 muestras (C3,
~4.62 s).

Cada valor es una muestra de audio de 16 bits con signo, en un rango de
aproximadamente **±2048** (no ±32767 — ver "Formato de las muestras" en el
documento 01), pensado para dejar margen de suma al mezclar hasta 15 voces
en simultáneo antes de mandar el resultado al I2S.

**La tasa de muestreo (22050 Hz) no está guardada en el header** — es un
contrato implícito entre este generador y el firmware. El código que
reproduce estos arrays tiene que asumir 22050 muestras/segundo (o leerlo de
una constante compartida) para que la afinación y timing salgan correctos.

### 2. Struct y tabla de lookup

```c
typedef struct {
    const int16_t *data;
    uint32_t length;
} wavetable_note_t;

static const wavetable_note_t notes[15] = {
    { note_C3, 101800 },
    { note_D3, 102522 },
    { note_E3, 100503 },
    { note_G3, 64940 },
    { note_A3, 63012 },
    { note_C4, 52422 },
    { note_D4, 51261 },
    { note_E4, 50252 },
    { note_G4, 50027 },
    { note_A4, 47065 },
    { note_C5, 22815 },
    { note_D5, 25706 },
    { note_E5, 25160 },
    { note_G5, 25915 },
    { note_A5, 24787 },
};
```

`wavetable_note_t` empareja el puntero al array con su longitud (necesaria porque, a
diferencia de un array de tamaño fijo, cada nota mide distinto — el
firmware no puede asumir un largo común).

El nombre del tipo no es `note_t` a secas a propósito: el core `arduino-esp32`
ya define un `note_t` propio (un enum de notas musicales en
`esp32-hal-ledc.h`, usado por `ledcWriteNote()`) que entra en conflicto
directo si se compila como sketch de Arduino IDE (no aparece al compilar
con PlatformIO porque ese `.h` del core no se incluye salvo que algo lo
requiera, pero `Arduino.h` sí lo arrastra siempre). Por eso el generador
(`tools/generate_samples.py`) emite `wavetable_note_t`.

El array `notes[15]` sigue siempre el mismo orden fijo: **grave → central →
agudo, y dentro de cada registro, C, D, E, G, A** (el mismo orden de las 5
cuerdas). Es decir:

| Índice | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Nota | C3 | D3 | E3 | G3 | A3 | C4 | D4 | E4 | G4 | A4 | C5 | D5 | E5 | G5 | A5 |

Esto permite que el firmware calcule el índice de una nota como
`banco_octava * 5 + cuerda` (con `banco_octava` = 0 para graves, 1 para
central, 2 para agudos, y `cuerda` = 0..4 para C,D,E,G,A) en vez de tener
que buscar por nombre.

## Tamaño y ubicación en memoria

Al día de hoy el header pesa **~3.46 MB como archivo de texto**, pero lo
que importa es el tamaño de los datos ya compilados: ~1.54 MB de datos
`int16_t` (ver el detalle de bytes por nota en el documento 02). Al ser
`static const`, el compilador los coloca en flash (sección `.rodata` /
`DROM` en el ESP32), no en RAM — son datos de solo lectura que no necesitan
copiarse a RAM para usarse.

## Consumo desde el firmware (referencia)

```c
#include "notes_data.h"

const wavetable_note_t *n = &notes[indice];
int16_t muestra = n->data[posicion % n->length];
```

(El `% n->length` es solo ilustrativo de que hay que respetar el límite de
cada array — la lógica real de disparo/apagado de nota depende de cómo se
implemente la reproducción en el firmware, todavía no definida en este
documento.)
