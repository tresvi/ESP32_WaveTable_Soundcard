// Secuenciador de la melodia de prueba: Grieg, "Manana" (Peer Gynt).
// Transcripcion, ritmo y criterio musical en docs/05-melodias-de-prueba.md.
//
// El modulo es independiente del resto del firmware: no sabe nada del sistema
// de voces, del I2S ni de los UARTs. Recibe por callback la funcion que
// dispara una nota del catalogo, y lleva su propio reloj contando las muestras
// que consume cada bloque de audio.
//
// Header-only a proposito: hay dos copias del firmware (src/main.cpp para
// PlatformIO y src/soundcard/soundcard.ino para el Arduino IDE), y un solo
// archivo por copia es menos que mantener sincronizado. Esta pensado para
// incluirse una unica vez por firmware.

#pragma once

#include <stddef.h>
#include <stdint.h>

// ---------------------------------------------------------------------------
// Datos de la melodia
// ---------------------------------------------------------------------------

// delay_ms NO es la duracion audible de la nota: cada muestra se reproduce
// entera y decae sola (ver docs/02). Es el tiempo hasta disparar la SIGUIENTE
// nota, o sea el ritmo de la melodia. Por eso las notas se solapan, que es lo
// que da el sonido natural de un arpa/lira.
typedef struct {
    uint8_t note;        // indice en notes[], 0..14
    uint16_t delay_ms;
} melody_step_t;

// "Manana" esta en 6/8 con la corchea como pulso base. Valores ajustados a
// oido sobre el hardware: la primera version (200/300/400/1600) sonaba al
// doble de velocidad de lo que pide la pieza.
static const uint16_t T_8 = 400;    // corchea: pulso base (6/8)
static const uint16_t T_8P = 600;   // corchea con puntillo: enfasis
static const uint16_t T_4 = 800;    // negra: respiro de fin de frase
static const uint16_t T_FIN = 3200; // deja sonar la ultima nota

static const melody_step_t MELODY[] = {
    // Frase 1 - figura de apertura:  G4 E4 D4 C4 D4 E4
    {8, T_8}, {7, T_8}, {6, T_8}, {5, T_8}, {6, T_8}, {7, T_8},
    // Frase 2 - repeticion (en el original, la respuesta del oboe)
    {8, T_8}, {7, T_8}, {6, T_8}, {5, T_8}, {6, T_8}, {7, T_4},
    // Frase 3 - ascenso:             G4 E4 G4 A4 G4 E4
    {8, T_8}, {7, T_8}, {8, T_8}, {9, T_8}, {8, T_8}, {7, T_8},
    // Frase 4 - descenso/respuesta:  D4 C4 D4 E4 G4 E4
    {6, T_8}, {5, T_8}, {6, T_8}, {7, T_8}, {8, T_8}, {7, T_4},
    // Frase 5 - figura de apertura:  G4 E4 D4 C4 D4 E4
    {8, T_8}, {7, T_8}, {6, T_8}, {5, T_8}, {6, T_8}, {7, T_8},
    // Frase 6 - pico agudo:          G4 A4 C5 A4 G4 E4
    {8, T_8}, {9, T_8}, {10, T_8P}, {9, T_8}, {8, T_8}, {7, T_8},
    // Frase 7 - resolucion:          G4 E4 D4 C4
    {8, T_8}, {7, T_8}, {6, T_4}, {5, T_FIN},
};

static const uint16_t MELODY_LEN = sizeof(MELODY) / sizeof(MELODY[0]);

// ---------------------------------------------------------------------------
// Secuenciador
// ---------------------------------------------------------------------------

// Firma de la funcion que dispara una nota del catalogo (indice 0..14).
typedef void (*melody_trigger_fn)(uint8_t note_index);

static melody_trigger_fn melody_trigger = nullptr;
static uint32_t melody_sample_rate = 0;
static uint16_t melody_step = 0;
static uint32_t melody_samples_left = 0;
static bool melody_playing = false;

// trigger: como disparar cada nota. sample_rate: para convertir ms a muestras.
static void melody_init(melody_trigger_fn trigger, uint32_t sample_rate) {
    melody_trigger = trigger;
    melody_sample_rate = sample_rate;
}

// Arranca desde el principio. Si ya estaba sonando la reinicia, misma politica
// de retrigger que las notas sueltas.
static void melody_start() {
    melody_step = 0;
    melody_samples_left = 0;
    melody_playing = true;
}

// Avanza el secuenciador el equivalente a `frames` muestras y dispara las
// notas que correspondan. Llamar una vez por bloque de audio, ANTES de
// mezclar, para que las notas disparadas entren en ese mismo bloque.
//
// La base de tiempo es el propio reloj de audio (cuenta muestras consumidas),
// no millis(): como i2s_write() bloquea al ritmo real del DAC, contar bloques
// da un timing exacto y sin deriva respecto de lo que realmente se escucha.
// La resolucion es de un bloque (~11.6 ms), de sobra para ritmo musical.
static void melody_tick(size_t frames) {
    if (!melody_playing || melody_trigger == nullptr) {
        return;
    }
    while (melody_samples_left <= frames) {
        if (melody_step >= MELODY_LEN) {
            melody_playing = false;
            return;
        }
        melody_trigger(MELODY[melody_step].note);
        melody_samples_left +=
            (uint32_t)MELODY[melody_step].delay_ms * melody_sample_rate / 1000;
        melody_step++;
    }
    melody_samples_left -= frames;
}
