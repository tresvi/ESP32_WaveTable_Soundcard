"""Detector de tono por autocorrelacion para archivos WAV.

Herramienta de calibracion: dado un archivo o una carpeta de WAVs, estima la
frecuencia fundamental de cada uno y la traduce a nota + octava (convencion
A4 = 440 Hz, C4 = Do central, MIDI 60). Sirve para mapear archivo -> nota
cuando los nombres de archivo no son confiables (ej. la libreria "Lyre Lyre"
no trae la octava en el nombre; ver docs/01-obtencion-de-notas.md).

Es la reconstruccion del script ad-hoc con el que se hizo ese mapeo la
primera vez. Se guarda en el repo porque el mismo paso hay que repetirlo si
se cambia la fuente de muestras (ej. por el pendiente de licencia).

Uso:
    python tools/detect_pitch.py <archivo.wav | carpeta> [mas archivos/carpetas...]
    python tools/detect_pitch.py carpeta/ --filter "*medium*"

Metodo:
  1. Carga a mono (mismo criterio que generate_samples.py).
  2. Detecta el onset (2% del pico) y salta SKIP_ATTACK_MS para no medir
     sobre el transitorio del ataque, que es inarmonico.
  3. Toma una ventana de WINDOW_S segundos del sostenido y calcula la
     autocorrelacion via FFT.
  4. Busca picos en el rango de lags equivalente a [F_MIN, F_MAX] Hz y
     elige el de MENOR lag entre los que superan PEAK_RATIO veces el
     maximo: eso prefiere el periodo fundamental frente a sus multiplos
     (subarmonicos), que en una senal periodica dan picos casi iguales.
  5. Interpolacion parabolica alrededor del pico para precision sub-muestra.

La columna "conf" es el valor de autocorrelacion normalizada en el pico
(0..1): cerca de 1 = senal claramente periodica; bajo = ruidosa, inarmonica
o ventana mal ubicada. Desconfiar de resultados con conf < 0.5.

Dependencias: numpy, soundfile.
"""

import argparse
import glob
import math
import os
import sys

import numpy as np
import soundfile as sf

# --- Parametros de analisis ---------------------------------------------------

ONSET_THRESHOLD = 0.02   # fraccion del pico para detectar inicio del pulso
SKIP_ATTACK_MS = 80.0    # cuanto saltar despues del onset (transitorio inarmonico)
WINDOW_S = 0.4           # largo de la ventana de analisis sobre el sostenido
MIN_WINDOW_S = 0.1       # si el archivo es mas corto que esto, se descarta
F_MIN = 50.0             # rango de busqueda de la fundamental, en Hz
F_MAX = 2000.0
PEAK_RATIO = 0.9         # umbral relativo al maximo para aceptar un pico

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


# --- Audio --------------------------------------------------------------------

def load_mono(path):
    data, sr = sf.read(path, always_2d=True, dtype="float64")
    return data.mean(axis=1), sr


def find_onset_index(data):
    peak = np.max(np.abs(data))
    if peak == 0:
        return 0
    above = np.abs(data) > ONSET_THRESHOLD * peak
    return int(np.argmax(above)) if above.any() else 0


def analysis_window(data, sr):
    """Devuelve la porcion del sostenido sobre la que se mide, o None."""
    start = find_onset_index(data) + int(SKIP_ATTACK_MS * sr / 1000)
    end = min(len(data), start + int(WINDOW_S * sr))
    if end - start < int(MIN_WINDOW_S * sr):
        return None
    win = data[start:end]
    win = win - np.mean(win)          # quita DC
    return win * np.hanning(len(win))  # suaviza bordes


# --- Autocorrelacion ----------------------------------------------------------

def autocorrelation(x):
    n = len(x)
    size = 1 << (2 * n - 1).bit_length()  # padding a potencia de 2
    spec = np.fft.rfft(x, size)
    ac = np.fft.irfft(spec * np.conj(spec))[:n]
    if ac[0] <= 0:
        return None
    return ac / ac[0]  # normalizada: ac[0] = 1


def pick_fundamental_lag(ac, sr):
    lag_min = max(1, int(sr / F_MAX))
    lag_max = min(len(ac) - 2, int(sr / F_MIN))
    if lag_max <= lag_min:
        return None, 0.0

    seg = ac[lag_min:lag_max + 1]
    # maximos locales: mayor que ambos vecinos
    is_peak = (seg[1:-1] > seg[:-2]) & (seg[1:-1] > seg[2:])
    peak_idx = np.nonzero(is_peak)[0] + 1
    if len(peak_idx) == 0:
        return None, 0.0

    threshold = PEAK_RATIO * np.max(seg[peak_idx])
    candidates = [i for i in peak_idx if seg[i] >= threshold]
    i = candidates[0]  # el de menor lag: periodo fundamental
    lag = lag_min + i

    # interpolacion parabolica con los vecinos para precision sub-muestra
    y0, y1, y2 = ac[lag - 1], ac[lag], ac[lag + 1]
    denom = y0 - 2 * y1 + y2
    offset = 0.5 * (y0 - y2) / denom if denom != 0 else 0.0
    return lag + offset, float(y1)


# --- Conversion a nota --------------------------------------------------------

def freq_to_note(freq):
    midi = 69.0 + 12.0 * math.log2(freq / 440.0)
    nearest = int(round(midi))
    cents = 100.0 * (midi - nearest)
    name = NOTE_NAMES[nearest % 12] + str(nearest // 12 - 1)  # MIDI 60 -> C4
    return name, nearest, cents


def detect(path):
    data, sr = load_mono(path)
    win = analysis_window(data, sr)
    if win is None:
        return None
    ac = autocorrelation(win)
    if ac is None:
        return None
    lag, conf = pick_fundamental_lag(ac, sr)
    if lag is None:
        return None
    freq = sr / lag
    name, midi, cents = freq_to_note(freq)
    return {"freq": freq, "note": name, "midi": midi, "cents": cents, "conf": conf}


# --- CLI ----------------------------------------------------------------------

def collect_files(paths, pattern):
    files = []
    for p in paths:
        if os.path.isdir(p):
            files.extend(sorted(glob.glob(os.path.join(p, pattern))))
        elif os.path.isfile(p):
            files.append(p)
        else:
            print(f"aviso: no existe {p}", file=sys.stderr)
    return files


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("paths", nargs="+", help="archivos .wav y/o carpetas")
    ap.add_argument("--filter", default="*.wav",
                    help="patron glob dentro de carpetas (default: *.wav)")
    args = ap.parse_args()

    files = collect_files(args.paths, args.filter)
    if not files:
        print("no se encontraron archivos", file=sys.stderr)
        return 1

    width = max(len(os.path.basename(f)) for f in files)
    print(f"{'archivo':<{width}}  {'Hz':>8}  {'nota':<5} {'midi':>4}  {'cents':>6}  {'conf':>5}")
    print("-" * (width + 40))
    for f in files:
        base = os.path.basename(f)
        try:
            r = detect(f)
        except Exception as e:  # archivo corrupto, formato raro, etc.
            print(f"{base:<{width}}  error: {e}")
            continue
        if r is None:
            print(f"{base:<{width}}  (sin tono detectable / muy corto)")
            continue
        print(f"{base:<{width}}  {r['freq']:8.1f}  {r['note']:<5} {r['midi']:>4}  "
              f"{r['cents']:+6.0f}  {r['conf']:5.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
