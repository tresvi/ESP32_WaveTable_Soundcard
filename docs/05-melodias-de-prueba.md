# Melodías de prueba

Melodías que se pueden tocar mandando caracteres por el puerto serie (ver
"Entrada por UART" en [04](04-firmware-primera-version.md)). Sirven para
validar a oído el pipeline completo — afinación relativa entre notas, ataque,
duración, mezcla — con algo reconocible en vez de notas sueltas.

## Qué se puede y qué no

El instrumento usa una **escala pentatónica C-D-E-G-A** (ver
[01](01-obtencion-de-notas.md)). No tiene **F** ni **B**.

Esto descarta de entrada dos melodías que son las primeras que uno intenta:

| Melodía | Por qué no entra |
|---|---|
| Feliz Cumpleaños | Necesita el 4º grado (F en tonalidad de C). *(Arrancada en Sol es 100 % diatónica en Do mayor: `G G A G C B \| G G A G D C \| G G G' E C B A \| F F E C D C`; una versión anterior de esta tabla mencionaba también un B♭, pero eso sólo aplica si se arranca en Do, que la pone en Fa mayor.)* |
| Himno a la Alegría (Beethoven) | Necesita el 4º grado (F) |

**No se arregla transponiendo.** El Himno a la Alegría usa 5 grados
consecutivos de la escala (mi-fa-sol-la-si = grados 3-4-5 más vecinos), y en
una pentatónica los tramos consecutivos más largos son `C-D-E` (3 notas) y
`G-A` (2 notas). No existe tonalidad donde entre. Lo mismo aplica al Feliz
Cumpleaños.

Esto no es una limitación a corregir: es el trade-off deliberado documentado
en [01](01-obtencion-de-notas.md). Se eligió pentatónica para que **cualquier
combinación simultánea de las 5 cuerdas suene consonante** sin importar el
orden — determinante en un instrumento gestual donde el usuario puede cruzar
varios haces a la vez. El precio es no poder tocar melodías diatónicas
arbitrarias.

## Tabla de caracteres

Cada caracter dispara un índice de `notes[15]` (mismo orden fijo que en
[03](03-notes_data-header.md)):

| Nota | Char | | Nota | Char | | Nota | Char |
|---|---|---|---|---|---|---|---|
| C3 | `0` | | C4 | `5` | | C5 | `A` |
| D3 | `1` | | D4 | `6` | | D5 | `B` |
| E3 | `2` | | E4 | `7` | | E5 | `C` |
| G3 | `3` | | G4 | `8` | | G5 | `D` |
| A3 | `4` | | A4 | `9` | | A5 | `E` |

Las melodías de abajo están escritas en el **banco central** (registro 4).
Para subirlas una octava: `5→A, 6→B, 7→C, 8→D, 9→E`. Para bajarlas:
`5→0, 6→1, 7→2, 8→3, 9→4`.

## ⚠️ El firmware no maneja ritmo

Cada caracter dispara la nota **en el instante en que llega**. Si se pega una
cadena entera en el Monitor Serie, los caracteres llegan en pocos
milisegundos y suenan todos casi simultáneamente: se escucha un **acorde, no
una melodía** (y como cada nota tiene su voz dedicada con política de
retrigger, sólo suenan las notas *distintas*, no las repeticiones).

Para que suene como melodía hay que espaciar los caracteres en el tiempo:
mandándolos de a uno a mano, o desde el Pro Micro con `delay()` entre cada
uno. Las barras `|` en las transcripciones de abajo marcan divisiones de
frase, no se mandan.

## Melodías folk (pentatónicas puras)

### Mary tenía un corderito

Sólo usa C-D-E-G. La más simple para una primera prueba:

```
7656 777 666 788 7656 777 766765
```

| Frase | Notas | Chars |
|---|---|---|
| "Mary had a" | E D C D | `7656` |
| "little lamb" | E E E | `777` |
| "little lamb" | D D D | `666` |
| "little lamb" | E G G | `788` |
| "Mary had a" | E D C D | `7656` |
| "little lamb" | E E E | `777` |
| "its fleece was white as snow" | E D D E D C | `766765` |

### Viejo MacDonald / En la granja de mi tío

Usa las 5 notas de la escala, y cruza dos octavas (banco grave + central), así
que sirve para verificar que la transición entre bancos suena afinada:

```
5553443 | 77665
```

| Frase | Notas | Chars |
|---|---|---|
| "Old MacDonald had a farm" | C4 C4 C4 G3 A3 A3 G3 | `5553443` |
| "E-I-E-I-O" | E4 E4 D4 D4 C4 | `77665` |

## Melodías clásicas

### Dvořák — Sinfonía Nº 9 "Del Nuevo Mundo", Largo

Es **el** ejemplo canónico de melodía pentatónica en el repertorio clásico
(el tema del corno inglés, conocido también con la letra "Goin' Home").
Dvořák la construyó deliberadamente sobre una escala pentatónica para evocar
el idioma de los espirituales/folk norteamericanos — el mismo tipo de escala
que este instrumento usa por un motivo distinto (consonancia entre cuerdas
simultáneas). Encaja completa, sin adaptar ninguna nota.

Frase de apertura, en C:

```
788765 | 67876 | 788765
```

| Notas | Chars |
|---|---|
| E G G E D C | `788765` |
| D E G E D | `67876` |
| E G G E D C | `788765` |

### Grieg — "Mañana" (Peer Gynt)

La melodía de flauta del comienzo también es pentatónica. Es una figura
mecedora que sube y baja, muy reconocible y cómoda para escuchar el
decaimiento de cada nota.

**Apertura** (la parte más reconocible):

```
876567 | 876567
```

**Versión extendida** — sigue la estructura real de la pieza: la figura de
apertura se repite (en el original la flauta la enuncia y el oboe la
responde), después sube hacia el agudo y vuelve a resolver:

```
876567 | 876567 | 878987 | 656787 | 876567 | 89A987 | 8765
```

| # | Frase | Notas | Chars |
|---|---|---|---|
| 1 | figura de apertura | G E D C D E | `876567` |
| 2 | repetición (respuesta) | G E D C D E | `876567` |
| 3 | ascenso | G E G A G E | `878987` |
| 4 | descenso / respuesta | D C D E G E | `656787` |
| 5 | figura de apertura | G E D C D E | `876567` |
| 6 | pico agudo (llega a C5) | G A C5 A G E | `89A987` |
| 7 | resolución | G E D C | `8765` |

La frase 6 es la única que sale del banco central (toca `A` = C5), así que de
paso sirve para verificar el salto al banco agudo.

> **Nota sobre las transcripciones clásicas**: las frases de apertura están
> transcritas con confianza; **el resto es una reconstrucción por contorno
> melódico hecha de memoria** — fiel en forma y carácter, aproximada en el
> detalle nota por nota. Son para tener algo reconocible con qué probar el
> instrumento, no transcripciones fieles de la partitura. Como ambos temas son
> pentatónicos, cualquier desvío cae igual dentro de las 15 notas disponibles
> y suena consonante. Las frases están numeradas justamente para poder
> corregirlas de a una al escucharlas.

## Pendientes del set ampliado (21 notas)

Si se agregan las 6 notas diatónicas faltantes como región 15–20
(`F3 B3 F4 B4 F5 B5`, sin tocar los índices 0–14 — ver la discusión en
[04](04-firmware-primera-version.md)), estas piezas pasan a ser codificables.
Chars propuestos para la región nueva: `'F'`–`'K'` (15–20), continuando la
secuencia actual.

### Grieg — "En la gruta del rey de la montaña" (Peer Gynt)

Tema principal transpuesto a **La menor natural** (mismas teclas blancas que
Do mayor). Hallazgo: de las notas que usa, **sólo B3 falta en el catálogo
actual** — A3, C4, D4, E4, G4 y A4 ya existen. Con B3 solo (índice 15,
grabación directa en Lyre Lyre) el tema se destraba.

| # | Frase | Notas | Chars (B3 = `F`) |
|---|---|---|---|
| 1 | tema | A3 B3 C4 D4 E4 C4 E4 | `4F56757` |
| 2 | respuesta cromática *(ver nota)* | E4 B3 E4 · D4 A3 D4 | `7F7646` |
| 3 | tema, cierre arriba | A3 B3 C4 D4 E4 C4 E4 A4 | `4F567579` |
| 4 | remate en la ♭7 | G4 E4 C4 E4 G4 | `87578` |

**Nota sobre la frase 2**: en el original las dos primeras notas son **E♭4**
(la ♭5, el tritono que da el carácter siniestro). Es una nota cromática y
no hay transposición que la ponga en tecla blanca — el único tritono
blanco-blanco es B–F, y Si menor tiene C# y F#. Se sustituye por E4 (la 5ª
justa): conserva el contorno, pierde la tensión.

**Accelerando**: es la seña de identidad de la pieza y el formato
`{nota, delay_ms}` lo permite directamente — repetir el tema bajando el
pulso en cada vuelta, las últimas una octava arriba:

| Vuelta | Negra (ms) | Octava | Necesita además |
|---|---|---|---|
| 1 | 400 | A3–A4 | B3 |
| 2 | 320 | A3–A4 | B3 |
| 3 | 250 | A4–A5 | B4 (índice 18) |
| 4 | 180 | A4–A5 | B4 |

**Crescendo: no codificable.** El mezclador no tiene velocidad por nota
(cada muestra suena a su pico fijo de ±2048). Es la otra mitad del drama de
esta pieza y se pierde. Agregar un campo de ganancia a `melody_step_t` y
un multiplicador en `mix_block()` sería barato en CPU, pero es una feature
nueva, no una transcripción.

### Beethoven — Himno a la Alegría

Completo y sin sustituciones con el set de 21 (necesita F4, índice 17).
Rango C4–G4. Ver la tabla de "Qué se puede y qué no" arriba.

### Feliz Cumpleaños

Completo arrancando en G3 (necesita F4, índice 17). Rango G3–G4.

## Reproducción automática con ritmo (caracter `' '`)

Mandar un **espacio** por cualquiera de los dos UARTs reproduce "Mañana"
completa, con su ritmo — sin necesidad de espaciar los caracteres a mano.

Está implementado en un módulo aparte, **`src/melody.h`** (header-only), que
contiene tanto la tabla `MELODY[]` con las notas y sus tiempos como el
secuenciador. El firmware sólo lo usa a través de tres llamadas:

| Función | Dónde se llama |
|---|---|
| `melody_init(trigger_note, SAMPLE_RATE)` | una vez en `setup()` |
| `melody_start()` | al recibir `' '` en `process_uart_char()` |
| `melody_tick(BLOCK_FRAMES)` | una vez por bloque en `audio_task()` |

El módulo **no conoce el resto del firmware**: no sabe nada del sistema de
voces, del I2S ni de los UARTs. Recibe por callback la función que dispara
una nota (`melody_init`), así que para cambiar la melodía o agregar otra
alcanza con tocar ese archivo. Es header-only a propósito: hay dos copias del
firmware (PlatformIO y Arduino IDE), y un solo archivo por copia es menos que
mantener sincronizado — ver la tabla de archivos duplicados en
[04](04-firmware-primera-version.md).

Si se manda un espacio mientras la melodía ya está sonando, **reinicia desde
el principio** (misma política de retrigger que las notas sueltas). Las
cuerdas y los caracteres de nota siguen funcionando durante la reproducción y
se mezclan encima, así que también sirve para probar la mezcla aditiva contra
un fondo melódico.

### Base de tiempo

El secuenciador **no usa `millis()`**: cuenta las muestras consumidas por cada
bloque de audio. Como `i2s_write()` bloquea al ritmo real del DAC (ver
[04](04-firmware-primera-version.md)), contar bloques da una base de tiempo
atada al reloj de audio, exacta y sin deriva respecto de lo que realmente se
escucha. La resolución es de un bloque (~11,6 ms), de sobra para ritmo musical
(la figura más corta de esta melodía dura 400 ms).

### Ritmo

"Mañana" está en **6/8**, con la corchea como pulso base:

| Constante | Figura | ms | Uso |
|---|---|---|---|
| `T_8` | corchea | 400 | pulso base, casi toda la melodía |
| `T_8P` | corchea con puntillo | 600 | énfasis en el pico agudo (C5, frase 6) |
| `T_4` | negra | 800 | respiro al final de las frases 2, 4 y 7 |
| `T_FIN` | — | 3200 | deja sonar la última nota antes de terminar |

Con estos valores la melodía completa (40 notas) dura unos **18 segundos**
(corchea = 400 ms → negra con puntillo = 1,2 s, o sea unos 50 BPM por
compás de 6/8 — un *Allegretto pastorale* tranquilo, acorde a la pieza).

La primera versión usaba la mitad de estos valores (200/300/400/1600) y al
escucharla sonaba claramente apurada: con notas de lira que decaen lento, un
pulso rápido amontona las voces y se pierde la sensación de melodía. Para
acelerarla o frenarla toda junta, escalar los cuatro valores.

**Importante**: `delay_ms` no es la duración *audible* de la nota, sino el
tiempo hasta disparar la **siguiente**. Cada muestra se reproduce entera y
decae sola (ver [02](02-recorte-de-notas.md)) — una nota de 2,5 s sigue
sonando aunque la siguiente entre 200 ms después. Eso es justamente lo que da
el efecto de superposición natural de un arpa/lira, donde las notas se
solapan en vez de cortarse.

## Ideas de prueba adicionales

Más allá de las melodías, para ejercitar partes específicas del firmware:

- **Mezcla aditiva**: mandar varios caracteres distintos casi juntos (ej.
  `5`, `7`, `9` = C4-E4-A4) — debería sonar un acorde consonante, sin
  distorsión ni saturación audible.
- **Retrigger**: mandar el mismo caracter repetido rápido — cada repetición
  tiene que reiniciar la nota desde el ataque, no superponerse.
- **Barrido de todo el catálogo**: `0123456789ABCDE` de a uno, para verificar
  que las 15 notas suenan, están en orden ascendente de tono, y que las
  derivadas por resampleo (ver [01](01-obtencion-de-notas.md)) no desentonan
  contra las grabaciones directas.
