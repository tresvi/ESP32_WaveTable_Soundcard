# Recorte de las notas

Hay dos recortes distintos e independientes aplicados a cada nota:

1. **Recorte auditivo**: decide *cuánto dura* la nota (dónde termina
   musicalmente). Se definió escuchando en Audacity.
2. **Recorte de cola residual**: elimina, dentro de esa duración ya
   aprobada, los últimos samples que quedaron en un nivel inaudible después
   de cuantizar a ±2048. Es puramente un ahorro de espacio en flash, no
   cambia la duración audible de la nota.

## 1. Recorte auditivo (duración final de cada nota)

Este recorte se hizo por iteración, escuchando los resultados en Audacity:

### Intento 1 — corte automático por umbral de silencio

Primera versión: un tope de duración fijo por registro (graves 4.0 s /
central 2.0 s / agudos 1.0 s), un detector de decaimiento por RMS a -35 dB
relativo al pico, y un fade lineal de solo 30 ms al final.

**Resultado:** casi todas las notas llegaban al tope sin haber decaído
realmente (seguían sonando fuerte), y el fade de 30 ms sobre una señal
todavía fuerte se escuchaba como un corte abrupto ("robótico"). Solo G3
sonó bien; A3 necesitaba un poco más; C3 sonaba cortada incluso en su
duración máxima.

### Intento 2 — topes más generosos + release exponencial

Se subieron los topes (graves 6.0 s / central 3.0 s / agudos 1.5 s), se
relajó el umbral de silencio a -50 dB (para no cortar temprano como le
pasaba a A3), y se reemplazó el fade lineal de 30 ms por una **caída
exponencial** sobre el último 30% de la duración de la nota (bajando hasta
-42 dB), más un fade lineal de seguridad de 5 ms al final para eliminar
cualquier click residual. Esto imita el apagado físico de una cuerda en vez
de un corte en seco.

**Resultado:** el usuario aprobó que sonaba natural, pero notó que **todas
las notas tenían de más** — quedaba mucho silencio de cola después de que
el sonido real ya había terminado.

### Intento 3 (versión final) — duración exacta definida a oído

El usuario escuchó los 15 `.wav` resultantes del intento 2 en Audacity y
determinó, nota por nota, el punto exacto donde el sonido real termina
(antes del silencio de más). Esos valores reemplazan por completo la lógica
de topes automáticos + detección de decaimiento:

| Nota | Duración | Nota | Duración | Nota | Duración |
|---|---|---|---|---|---|
| C3 | 5.00 s | C4 | 2.60 s | C5 | 1.20 s |
| D3 | 5.00 s | D4 | 2.50 s | D5 | 1.25 s |
| E3 | 5.00 s | E4 | 2.50 s | E5 | 1.25 s |
| G3 | 3.60 s | G4 | 2.50 s | G5 | 1.30 s |
| A3 | 3.40 s | A4 | 2.45 s | A5 | 1.30 s |

Estos valores están hardcodeados en `TARGET_DURATIONS` en
`tools/generate_samples.py`. El release exponencial del intento 2 se
conserva, pero ahora se calcula sobre el último 30% de **esta** duración
exacta, no de la señal larga sin recortar.

Con estas duraciones, el total de las 15 notas bajó de ~2.09 MB a **~1.72 MB**.

El usuario guardó una copia de este estado (los `.wav` de 22050 Hz ya
recortados a oído, antes del paso 2) en
`tools/samples_wav/OriginalesSinCortar/`. **Esa carpeta es un respaldo
manual y no debe borrarse ni regenerarse** — el pipeline no la toca.

## 2. Recorte de cola residual (sobre la señal ya cuantizada)

Después del recorte auditivo, al inspeccionar los arrays de
`notes_data.h` se notó que el final de cada uno tenía muchos valores en 0 o
oscilando en un rango muy chico (±1 a ±5). Esto **no es un error**: es el
piso de ruido de la grabación original (ruido de sala/micrófono), que
sigue presente incluso después de que el pulso de la cuerda terminó, y que
al escalar la nota a su pico de ±2048 queda representado como números muy
pequeños — inaudible, pero ocupando 2 bytes por muestra igual que cualquier
otro dato.

### Criterio de corte

Se definió el umbral en **±5 inclusive**: cualquier muestra final cuyo valor
absoluto sea ≤ 5 se considera parte del "apagado" y se recorta. La
implementación busca, desde el final del array, la **última muestra cuyo
valor absoluto sea mayor a 5**, y corta todo lo que queda después de esa
posición:

```python
def trim_tail_silence(data, threshold=5):
    above = np.where(np.abs(data) > threshold)[0]
    return data[:above[-1] + 1]
```

Al tomar la *última* ocurrencia por encima del umbral (no la primera vez
que la señal baja de ±5), un pico aislado de ruido cerca del final no
genera un corte prematuro en medio de la nota.

### Dónde se aplica (y dónde no)

Este recorte se aplica **únicamente a los arrays que se escriben en
`notes_data.h`**. Los archivos `.wav` en `tools/samples_wav/` se dejan
intactos a propósito: son la referencia ya escuchada y aprobada por el
usuario (recorte auditivo), y sirven como control de calidad — si en algún
momento el header y los `.wav` "más largos" no coinciden en duración, la
diferencia son exactamente estos últimos milisegundos de silencio inaudible
recortados.

### Resultado

| Nota | Duración en `.wav` | Duración en header | Ahorro |
|---|---|---|---|
| C3 | 5.000 s | 4.617 s | 16 900 B |
| D3 | 5.000 s | 4.650 s | 15 456 B |
| E3 | 5.000 s | 4.558 s | 19 494 B |
| G3 | 3.600 s | 2.945 s | 28 880 B |
| A3 | 3.400 s | 2.858 s | 23 916 B |
| C4 | 2.600 s | 2.377 s | 9 816 B |
| D4 | 2.500 s | 2.325 s | 7 728 B |
| E4 | 2.500 s | 2.279 s | 9 746 B |
| G4 | 2.500 s | 2.269 s | 10 196 B |
| A4 | 2.450 s | 2.134 s | 13 916 B |
| C5 | 1.200 s | 1.035 s | 7 290 B |
| D5 | 1.250 s | 1.166 s | 3 714 B |
| E5 | 1.250 s | 1.141 s | 4 806 B |
| G5 | 1.300 s | 1.175 s | 5 500 B |
| A5 | 1.300 s | 1.124 s | 7 756 B |

**Total: 1 801 488 B → 1 616 374 B, ahorro de 185 114 B (~181 KB)**, sin
ningún cambio perceptible al oído (la duración *auditiva* real de cada nota
no cambió — solo se eliminó lo que ya era inaudible).
