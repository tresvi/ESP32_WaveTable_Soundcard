# Obtención de las notas

## Escala elegida

El instrumento tiene 5 "cuerdas láser" y 2 botones que desplazan el banco de
notas una octava hacia arriba o hacia abajo. Eso da **15 notas** organizadas
en 3 bancos de 5.

Se eligió una **escala pentatónica** (Do-Re-Mi-Sol-La / C-D-E-G-A) porque
cualquier combinación simultánea de las 5 cuerdas suena consonante, sin
importar el orden en que se toquen — importante para un instrumento gestual
donde el usuario puede cruzar varios haces a la vez. Además, 5 notas por
octava coincide exactamente con las 5 cuerdas físicas: el patrón de
"dedos"/gestos es igual en los tres bancos, solo cambia el registro.

| Banco | Notas | Frecuencias (Hz) | MIDI |
|---|---|---|---|
| Graves (botón −) | C3 D3 E3 G3 A3 | 130.81 · 146.83 · 164.81 · 196.00 · 220.00 | 48 · 50 · 52 · 55 · 57 |
| Central (default) | C4 D4 E4 G4 A4 | 261.63 · 293.66 · 329.63 · 392.00 · 440.00 | 60 · 62 · 64 · 67 · 69 |
| Agudos (botón +) | C5 D5 E5 G5 A5 | 523.25 · 587.33 · 659.25 · 783.99 · 880.00 | 72 · 74 · 76 · 79 · 81 |

El banco central es el que suena sin presionar ningún botón, así que se
mapeó a las notas más "cómodas"/reconocibles al oído (registro medio,
alrededor del Do central).

## Fuente de audio

Se buscaron muestras reales de arpa/lira (no hay librerías libres de "lira"
específicamente — es un instrumento demasiado de nicho). Se evaluaron varias
opciones descargadas en `Downloads\Sonidos Lyra`:

- **KSHarp** — multisample de arpa (posiblemente síntesis Karplus-Strong),
  con el número de octava explícito en el nombre de archivo (`KSHarp_C3_mf.wav`).
  No se usó en la versión final, pero sirvió para calibrar el método de
  verificación de tono (ver más abajo).
- **256OrchestralSamples** (Versilian Studios / Sam Gossner) — pack
  orquestal, licencia explícita de dominio público, sin arpa/lira útil para
  este caso.
- **Cocoto_Harp.sf2** — SoundFont de arpa, no se llegó a usar.
- **Lyre Lyre** (instrumento Kontakt de Jordan Stevenson,
  `jscomposition.nz@gmail.com`) — **la fuente finalmente usada**. Son
  grabaciones reales de una lira griega tocada con los dedos, con 3 capas de
  intensidad (soft/medium/loud) y variaciones de round-robin por nota.

### ⚠️ Licencia pendiente de confirmar

El `README.txt` de "Lyre Lyre" no especifica términos de redistribución o de
uso fuera de Kontakt. A diferencia de `256OrchestralSamples` (explícitamente
de dominio público), acá no hay una licencia clara para **incrustar las
muestras crudas en el firmware de un producto físico**. Antes de distribuir
o vender el instrumento, hay que escribirle al autor para confirmar que este
uso está permitido, o reemplazar estas notas por una fuente con licencia
explícita (`256OrchestralSamples` o `KSHarp` son alternativas seguras).

## Cómo se identificó qué archivo corresponde a qué nota

Los archivos de "Lyre Lyre" **no traen el número de octava en el nombre**
(solo `<Nota> <intensidad>.<toma>.wav`, por ejemplo `C medium.9.wav`, y un
segundo grupo con prefijo `8 ` como `8 C medium.8.wav`). En vez de asumir la
octava por el nombre, se verificó el tono real de cada archivo con un
detector de pitch por autocorrelación (Python: `numpy` + `soundfile`, sobre
una ventana de ~0.4 s del sostenido de la nota, ignorando el ataque
inicial). El script está en el repo como
[`tools/detect_pitch.py`](../tools/detect_pitch.py):

```bash
python tools/detect_pitch.py "<carpeta o archivo.wav>" [--filter "*medium*"]
```

Resultado verificado:

| Letra | Archivo sin prefijo | Octava | Archivo con prefijo `8 ` | Octava |
|---|---|---|---|---|
| G | `G medium.12.wav` | 196.0 Hz ≈ **G3** | `8 G medium.11.wav` | 393.8 Hz ≈ **G4** |
| A | `A medium.9.wav` | 219.4 Hz ≈ **A3** | `8 A medium.9.wav` | 445.5 Hz ≈ **A4** |
| C | `C medium.9.wav` | 260.9 Hz ≈ **C4** | `8 C medium.8.wav` | 525.0 Hz ≈ **C5** |
| D | `D medium.9.wav` | 294.0 Hz ≈ **D4** | (no existe) | — |
| E | `E soft.2.wav` / `E medium.13.wav` | 329.1 Hz ≈ **E4** | (no existe) | — |

Es decir: el prefijo `8 ` significa "una octava arriba del archivo sin
prefijo del mismo nombre", pero **no está disponible para todas las
letras** (falta para D y E), y tampoco hay nada por debajo de la octava 3
ni por encima de la octava 5. De las 15 notas necesarias, la librería cubre
**8 directamente**; las otras 7 se derivan (ver abajo).

### Cobertura completa de la librería

La tabla de arriba sólo lista las 5 letras de la pentatónica, porque era lo
único que se buscó en su momento. Un barrido posterior con
`detect_pitch.py` sobre toda la capa `medium` mostró que la librería es en
realidad **cromática y continua de G3 a C5** (18 semitonos, confianza 1.00
en todos, desviaciones dentro de ±16 cents):

| Sin prefijo | G3 G#3 A3 A#3 B3 C4 C#4 D4 D#4 E4 F4 F#4 |
|---|---|
| Con prefijo `8 ` | G4 G#4 A4 A#4 B4 C5 |

Consecuencia relevante: **F4 y B4 existen como grabaciones directas**, así
que si en algún momento se quisiera una escala diatónica de 7 notas en la
octava central (C4–B4), no haría falta ningún resampleo para ese banco —
sólo F3 y F5/B5 requerirían derivación por octava. Ver la discusión del
trade-off pentatónica vs. heptatónica en
[05](05-melodias-de-prueba.md).

El mismo método se usó primero sobre `KSHarp` para confirmar que su
numeración de octava sigue la convención estándar (A4 = 440 Hz), antes de
descartar esa librería.

## Notas directas vs. notas derivadas

| Nota | Origen | Archivo fuente |
|---|---|---|
| G3 | directa | `G medium.12.wav` |
| A3 | directa | `A medium.9.wav` |
| C4 | directa | `C medium.9.wav` |
| D4 | directa | `D medium.9.wav` |
| E4 | directa | `E medium.13.wav` |
| G4 | directa | `8 G medium.11.wav` |
| A4 | directa | `8 A medium.9.wav` |
| C5 | directa | `8 C medium.8.wav` |
| C3 | derivada −1 octava | de C4 |
| D3 | derivada −1 octava | de D4 |
| E3 | derivada −1 octava | de E4 |
| D5 | derivada +1 octava | de D4 |
| E5 | derivada +1 octava | de E4 |
| G5 | derivada +1 octava | de G4 |
| A5 | derivada +1 octava | de A4 |

Notar que el banco central completo (el más usado, sin botones) queda 100%
cubierto por grabaciones reales, sin ningún procesamiento de cambio de tono.

## Cómo se derivan las octavas faltantes

El desplazamiento de octava se implementa como **resampleo polifásico**
(`scipy.signal.resample_poly`), equivalente a la función "Change Speed" de
Audacity: cambia tono y duración juntos (como acelerar/frenar una cinta),
en vez de un time-stretch que intenta preservar la duración (eso suena más
artificial/"robótico" para un pulso de cuerda).

- **+1 octava** (más agudo, más corto): `resample_poly(datos, up=1, down=2)`
  → la mitad de muestras, el doble de velocidad.
- **−1 octava** (más grave, más largo): `resample_poly(datos, up=2, down=1)`
  → el doble de muestras, la mitad de velocidad.

Es exactamente ±12 semitonos, el tipo de transposición con menos artefactos
posible (no hay estimación de tono involucrada, es una relación matemática
exacta 2:1).

## Cuantización y formato final

Definido en conversaciones previas de diseño del firmware:

- **Tasa de muestreo: 22050 Hz.** Nyquist en 11.025 kHz, suficiente para los
  armónicos de una lira/arpa; reduce el almacenamiento a la mitad frente a
  44.1 kHz.
- **16 bits con signo (`int16_t`)** por muestra, formato nativo esperado por
  el I2S del ESP32 hacia el PCM5102.
- **Amplitud de pico ±2048** (no ±32767) por nota. Con hasta 15 voces
  sonando en simultáneo sumadas en un acumulador de 32 bits, el pico teórico
  es 15 × 2048 = 30 720, dentro del rango de 16 bits (±32767) sin necesidad
  de aplicar ganancia extra al mezclar.
- **Normalización de pico por nota, no ganancia común**: cada una de las 15
  notas se escala individualmente para que su propia muestra máxima llegue
  a ±2048. Esto garantiza que ninguna nota suene más floja que otra por
  diferencias de nivel entre tomas de grabación, a costa de aplanar
  cualquier diferencia de volumen "natural" que pudiera existir entre
  registros en la grabación original.
- El resampleo final a 22050 Hz (desde la tasa nativa del archivo fuente,
  44100 Hz) también se hace con `resample_poly`, calculando la fracción
  exacta `up/down` con `fractions.Fraction`.

## Scripts

Hay dos, con roles distintos:

- [`tools/generate_samples.py`](../tools/generate_samples.py) — **el
  pipeline**. Todo el procesamiento descripto en este documento (carga,
  recorte, resampleo, cuantización, emisión del header). Es lo que se corre
  cada vez que se regeneran las notas.
- [`tools/detect_pitch.py`](../tools/detect_pitch.py) — **calibración**. El
  detector de tono por autocorrelación con el que se mapea archivo → nota.
  No forma parte del pipeline (no hay que correrlo al regenerar), pero es
  el primer paso obligado si se cambia la fuente de muestras — por ejemplo
  si el pendiente de licencia obliga a reemplazar "Lyre Lyre" — porque los
  nombres de archivo de una librería nueva no son confiables hasta
  verificarlos. Originalmente fue un script ad-hoc que no se guardó; se
  reconstruyó y validó contra los 8 archivos de la tabla de arriba
  (coincidencia exacta de nota y octava en los 8) justamente para no
  tener que re-derivarlo cuando haga falta.

Dependencias de ambos: `numpy`, `scipy`, `soundfile`
(`pip install numpy scipy soundfile`).
