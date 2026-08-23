# ESP32 WaveTable Soundcard

Instrumento basado en ESP32 (I2S + PCM5102) que reproduce notas de
lira/arpa almacenadas en flash como wavetables, con 15 notas de polifonía.

## Documentación de generación de samples y síntesis polifónica

Este proyecto usa 15 notas de lira/arpa (5 cuerdas láser × 3 bancos de
octava, escala pentatónica C-D-E-G-A), procesadas a partir de grabaciones
reales. El proceso de **sintesis polifónica** es documentado en `docs/`:

- [01 - Obtención de las notas](docs/01-obtencion-de-notas.md): origen de
  los audios fuente, criterio de selección/verificación, resampling y
  cuantización.
- [02 - Recorte de las notas](docs/02-recorte-de-notas.md): recorte
  auditivo (duración final de cada nota) y recorte de cola residual sobre
  la señal ya cuantizada.
- [03 - notes_data.h](docs/03-notes_data-header.md): estructura del header
  C generado y cómo regenerarlo.
- [04 - Firmware, primera versión](docs/04-firmware-primera-version.md):
  framework, pinout, partition scheme y arquitectura de mezcla de la primera
  versión (debug) del firmware en `src/main.cpp`.
- [05 - Melodías de prueba](docs/05-melodias-de-prueba.md): qué melodías
  entran (y cuáles no) en la escala pentatónica, con las secuencias de
  caracteres para tocarlas por el puerto serie.

Todo lo descripto ahí lo produce un único script:
[`tools/generate_samples.py`](tools/generate_samples.py). La selección de duración
fue realizada y su edición fue realizada "manualmente" para mejor aprovechamiento de la memoria
(ver documento 02); todo el procesamiento numérico es reproducible
corriendo ese script.
