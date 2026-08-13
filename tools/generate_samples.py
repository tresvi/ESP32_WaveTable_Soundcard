"""
Pipeline de conversion de samples de lira/arpa para el ESP32 WaveTable Soundcard.

Toma las grabaciones reales de la libreria "Lyre Lyre" (8 de las 15 notas
necesarias) y deriva las 7 notas faltantes desplazando una octava (arriba o
abajo) las notas del registro central, usando resampleo polifasico (equivalente
a "Change Speed" de Audacity: cambia tono y duracion juntos, sin tocar la
tasa de muestreo nominal).

Cada nota se recorta a una duracion exacta (definida a oido, ver
TARGET_DURATIONS) y recibe una caida exponencial en el tramo final para que
el corte suene a apagado natural de cuerda, no a un tijeretazo.

Salida por cada una de las 15 notas:
  - tools/samples_wav/<NOTA>.wav   (22050 Hz, 16 bits, mono - para escuchar/verificar)
  - tools/notes_data.h              (arrays int16_t listos para el firmware)

Requiere: numpy, scipy, soundfile  (pip install numpy scipy soundfile)
"""

import os
from fractions import Fraction

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

# ---------------------------------------------------------------------------
# Configuracion
# ---------------------------------------------------------------------------

SRC_DIR = r"C:\Users\Basilio\Downloads\Sonidos Lyra\LyreLyre\Lyre Lyre\Lyre Lyre\Lyre Lyre Samples"
OUT_WAV_DIR = os.path.join(os.path.dirname(__file__), "samples_wav")
OUT_HEADER = os.path.join(os.path.dirname(__file__), "notes_data.h")

TARGET_SR = 22050
TARGET_PEAK = 2048          # +/-2048 segun lo definido para el proyecto

ONSET_THRESHOLD = 0.02      # fraccion del pico para detectar inicio del pulso
PRE_ROLL_MS = 3.0           # margen antes del onset detectado

RELEASE_FRACTION = 0.30     # fraccion final de la nota que recibe caida exponencial
RELEASE_TARGET_DB = -42.0   # nivel al que debe llegar el release al final de la nota
SAFETY_FADE_MS = 5.0        # fade lineal final corto, solo para evitar click residual

# Recorte de cola residual: aplica SOLO a los arrays de notes_data.h, nunca a
# los .wav (esos quedan como copia de referencia ya aprobada por el oido).
TAIL_TRIM_THRESHOLD = 5     # valores |x| <= 5 al final se consideran "apagado"
WRITE_WAV_FILES = False     # los .wav ya estan aprobados, no se regeneran

# Duracion final de cada nota, elegida de oido por el usuario (donde el
# sonido real termina, sin el silencio de cola que sobraba).
TARGET_DURATIONS = {
    "C3": 5.0, "D3": 5.0, "E3": 5.0, "G3": 3.6, "A3": 3.4,
    "C4": 2.6, "D4": 2.5, "E4": 2.5, "G4": 2.5, "A4": 2.45,
    "C5": 1.2, "D5": 1.25, "E5": 1.25, "G5": 1.3, "A5": 1.3,
}

NOTE_ORDER = [
    "C3", "D3", "E3", "G3", "A3",
    "C4", "D4", "E4", "G4", "A4",
    "C5", "D5", "E5", "G5", "A5",
]

# Notas centrales "reales" (registro 4), fuente directa de la libreria.
# A partir de estas se derivan las graves (octava 3) y agudas (octava 5).
CENTRAL_SOURCES = {
    "C": "C medium.9.wav",
    "D": "D medium.9.wav",
    "E": "E medium.13.wav",
    "G": "8 G medium.11.wav",
    "A": "8 A medium.9.wav",
}

# Notas grabadas directamente en otro registro (no se derivan por octava).
DIRECT_EXTRA = {
    "G3": "G medium.12.wav",
    "A3": "A medium.9.wav",
    "C5": "8 C medium.8.wav",
}

# Notas derivadas de una central por desplazamiento de octava: (letra, +-1)
DERIVED = {
    "C3": ("C", -1), "D3": ("D", -1), "E3": ("E", -1),
    "D5": ("D", +1), "E5": ("E", +1), "G5": ("G", +1), "A5": ("A", +1),
}


# ---------------------------------------------------------------------------
# Utilidades de procesamiento
# ---------------------------------------------------------------------------

def load_mono(path):
    data, sr = sf.read(path, always_2d=True, dtype="float64")
    data = data.mean(axis=1)  # baja a mono promediando canales
    return data, sr


def resample_by_ratio(data, up, down):
    if up == down:
        return data
    return resample_poly(data, up, down)


def resample_to_rate(data, sr_in, sr_out):
    frac = Fraction(sr_out, sr_in).limit_denominator(1000)
    return resample_by_ratio(data, frac.numerator, frac.denominator)


def octave_shift(data, octaves):
    """octaves: +1 sube una octava (mas corto, mas agudo),
    -1 baja una octava (mas largo, mas grave)."""
    if octaves == 0:
        return data
    if octaves == 1:
        return resample_by_ratio(data, up=1, down=2)   # el doble de rapido
    if octaves == -1:
        return resample_by_ratio(data, up=2, down=1)   # la mitad de rapido
    raise ValueError("solo se soporta +-1 octava")


def find_onset_index(data, sr):
    peak = np.max(np.abs(data))
    if peak == 0:
        return 0
    above = np.abs(data) > ONSET_THRESHOLD * peak
    idx = int(np.argmax(above)) if above.any() else 0
    pre_roll = int(PRE_ROLL_MS * sr / 1000)
    return max(0, idx - pre_roll)


def slice_to_duration(data, sr, duration_s):
    n = int(duration_s * sr)
    if len(data) >= n:
        return data[:n]
    return np.concatenate([data, np.zeros(n - len(data))])


def apply_release_taper(data, sr):
    """Aplica una caida exponencial (release) sobre la fraccion final de la
    nota, simulando el apagado natural de una cuerda en vez de un corte
    abrupto. Termina con un fade lineal muy corto solo para eliminar
    cualquier click residual de discontinuidad."""
    n = len(data)
    n_release = int(n * RELEASE_FRACTION)
    if n_release > 1:
        target_amp = 10 ** (RELEASE_TARGET_DB / 20.0)
        alpha = -np.log(target_amp) / (n_release - 1)
        env = np.exp(-alpha * np.arange(n_release))
        data = data.copy()
        data[-n_release:] *= env

    n_safety = int(SAFETY_FADE_MS * sr / 1000)
    n_safety = min(n_safety, len(data))
    if n_safety > 0:
        fade = np.linspace(1.0, 0.0, n_safety)
        data = data.copy()
        data[-n_safety:] *= fade
    return data


def trim_tail_silence(data, threshold=TAIL_TRIM_THRESHOLD):
    """Recorta el final del array donde la intensidad cae a +/-threshold
    (inclusive) o menos, hasta apagarse. Solo se usa para notes_data.h."""
    above = np.where(np.abs(data) > threshold)[0]
    if len(above) == 0:
        return data[:0]
    return data[:above[-1] + 1]


def normalize_to_peak(data, target_peak):
    peak = np.max(np.abs(data))
    if peak == 0:
        return data
    return data * (target_peak / peak)


def finalize(data, sr, duration_s):
    """Recorta a la duracion exacta, aplica el release y convierte a
    22050 Hz / +-2048 / int16."""
    onset = find_onset_index(data, sr)
    data = data[onset:]
    data = slice_to_duration(data, sr, duration_s)
    data = apply_release_taper(data, sr)
    data = resample_to_rate(data, sr, TARGET_SR)
    data = normalize_to_peak(data, TARGET_PEAK)
    data = np.clip(data, -32768, 32767)
    return data.astype(np.int16)


# ---------------------------------------------------------------------------
# Pipeline principal
# ---------------------------------------------------------------------------

def main():
    os.makedirs(OUT_WAV_DIR, exist_ok=True)
    results = {}

    # 1) Cargar las 5 fuentes centrales "en crudo" (solo recorte de onset,
    #    sin limite de duracion todavia) para poder derivar octavas de ellas.
    central_raw = {}
    central_sr = {}
    for letter, fname in CENTRAL_SOURCES.items():
        data, sr = load_mono(os.path.join(SRC_DIR, fname))
        onset = find_onset_index(data, sr)
        central_raw[letter] = data[onset:]
        central_sr[letter] = sr

    # 2) Notas centrales directas (register 4)
    for letter in CENTRAL_SOURCES:
        note = f"{letter}4"
        results[note] = finalize(central_raw[letter], central_sr[letter], TARGET_DURATIONS[note])

    # 3) Notas derivadas por desplazamiento de octava
    for note, (letter, octaves) in DERIVED.items():
        shifted = octave_shift(central_raw[letter], octaves)
        results[note] = finalize(shifted, central_sr[letter], TARGET_DURATIONS[note])

    # 4) Notas grabadas directamente en otro registro (G3, A3, C5)
    for note, fname in DIRECT_EXTRA.items():
        data, sr = load_mono(os.path.join(SRC_DIR, fname))
        results[note] = finalize(data, sr, TARGET_DURATIONS[note])

    # 5) Recorte de cola residual, solo para el header (los .wav no se tocan)
    header_results = {note: trim_tail_silence(arr) for note, arr in results.items()}

    # 6) Reporte + export
    total_bytes = 0
    total_bytes_trimmed = 0
    print(f"{'Nota':6}{'Dur. wav (s)':>14}{'Dur. header (s)':>18}{'Bytes header':>14}{'Ahorro':>10}")
    for note in NOTE_ORDER:
        arr = results[note]
        trimmed = header_results[note]
        dur = len(arr) / TARGET_SR
        dur_trim = len(trimmed) / TARGET_SR
        nbytes = arr.nbytes
        nbytes_trim = trimmed.nbytes
        total_bytes += nbytes
        total_bytes_trimmed += nbytes_trim
        print(f"{note:6}{dur:14.3f}{dur_trim:18.3f}{nbytes_trim:14d}{nbytes - nbytes_trim:10d}")
        if WRITE_WAV_FILES:
            sf.write(os.path.join(OUT_WAV_DIR, f"{note}.wav"), arr, TARGET_SR, subtype="PCM_16")

    print(f"\nTotal sin recortar: {total_bytes} bytes (~{total_bytes/1024/1024:.3f} MB)")
    print(f"Total en header:    {total_bytes_trimmed} bytes (~{total_bytes_trimmed/1024/1024:.3f} MB)")
    print(f"Ahorro:             {total_bytes - total_bytes_trimmed} bytes")

    # 7) Header C con los 15 arrays (recortados) + tabla de lookup
    with open(OUT_HEADER, "w") as f:
        f.write("// Generado automaticamente por tools/generate_samples.py\n")
        f.write("// No editar a mano.\n\n")
        f.write("#pragma once\n#include <stdint.h>\n\n")
        for note in NOTE_ORDER:
            arr = header_results[note]
            f.write(f"static const int16_t note_{note}[{len(arr)}] = {{\n")
            line = "    "
            for i, v in enumerate(arr):
                line += f"{v},"
                if (i + 1) % 16 == 0:
                    f.write(line + "\n")
                    line = "    "
            if line.strip():
                f.write(line + "\n")
            f.write("};\n\n")

        f.write("typedef struct {\n    const int16_t *data;\n    uint32_t length;\n} wavetable_note_t;\n\n")
        f.write(f"static const wavetable_note_t notes[{len(NOTE_ORDER)}] = {{\n")
        for note in NOTE_ORDER:
            f.write(f"    {{ note_{note}, {len(header_results[note])} }},\n")
        f.write("};\n")

    if WRITE_WAV_FILES:
        print(f"\nWAVs de verificacion: {OUT_WAV_DIR}")
    print(f"Header C generado:    {OUT_HEADER}")


if __name__ == "__main__":
    main()
