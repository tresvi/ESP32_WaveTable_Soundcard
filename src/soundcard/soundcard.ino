// Primera version (debug) del firmware del ESP32 WaveTable Soundcard.
//
// Alcance de esta version: las 5 cuerdas laser disparan las 5 notas del
// banco central (C4 D4 E4 G4 A4) por wavetable, mezcladas aditivamente y
// enviadas por I2S al PCM5102. Ademas, cada caracter recibido por UART0
// (Serial, USB) o UART2 (Serial2, enlace con el Pro Micro) dispara directo
// cualquiera de las 15 notas del catalogo completo (ver uart_poll()). Los 2
// botones de banco (octava +/-) todavia no estan cableados en esta version.
//
// Detalle de decisiones de diseno (pinout, partition scheme, politica de
// retrigger, etc.) en docs/04-firmware-primera-version.md.

#include <Arduino.h>
#include <driver/i2s.h>
#include "notes_data.h"

// ---------------------------------------------------------------------------
// Pinout
// ---------------------------------------------------------------------------

// Entradas de las 5 cuerdas laser, en el mismo orden que las notas dentro de
// un banco: C, D, E, G, A. Pull-up interna, activo en bajo (0 = pulsada).
static const gpio_num_t STRING_PIN[5] = {
    GPIO_NUM_4,   // C
    GPIO_NUM_13,  // D
    GPIO_NUM_14,  // E
    GPIO_NUM_32,  // G
    GPIO_NUM_33,  // A
};

static const gpio_num_t I2S_BCK_PIN  = GPIO_NUM_27;
static const gpio_num_t I2S_WS_PIN   = GPIO_NUM_25;
static const gpio_num_t I2S_DOUT_PIN = GPIO_NUM_26;

// UART hacia el Arduino Pro Micro (5V -> requiere divisor resistivo antes de
// este pin, ver docs/04). Solo RX: el ESP32 no le contesta nada al Pro Micro
// en esta version.
static const gpio_num_t UART_RX_PIN = GPIO_NUM_21;
static const uint32_t UART_BAUD = 115200;  // debe coincidir con Serial1.begin() del Pro Micro

// ---------------------------------------------------------------------------
// Audio / mezcla
// ---------------------------------------------------------------------------

static const uint32_t SAMPLE_RATE  = 22050;
static const i2s_port_t I2S_PORT   = I2S_NUM_0;
static const size_t BLOCK_FRAMES   = 256;

static const uint8_t NUM_STRINGS = 5;
static const uint8_t BANK_CENTRAL = 1;  // 0 = grave, 1 = central, 2 = agudo
static const uint8_t NOTE_COUNT = 15;   // ver notes[15] en notes_data.h

// Un slot de voz por nota del catalogo completo (3 bancos x 5 cuerdas),
// aunque esta version solo dispara las 5 del banco central. Mantiene la
// mezcla preparada para cuando se sumen los botones de octava.
struct Voice {
    const int16_t *data;
    uint32_t length;
    uint32_t pos;
    bool active;
};

static Voice voices[NOTE_COUNT];

static void trigger_note(uint8_t note_index) {
    const wavetable_note_t *n = &notes[note_index];
    Voice &v = voices[note_index];
    v.data = n->data;
    v.length = n->length;
    v.pos = 0;
    v.active = true;
    Serial.printf("trigger note_index=%u\n", note_index);
}

// Suma todas las voces activas en un acumulador de 32 bits y satura a 16
// antes de escribir el frame estereo (mismo dato en L y R).
static void mix_block(int16_t *stereo_out, size_t frames) {
    for (size_t i = 0; i < frames; i++) {
        int32_t acc = 0;
        for (uint8_t vi = 0; vi < NOTE_COUNT; vi++) {
            Voice &v = voices[vi];
            if (!v.active) {
                continue;
            }
            acc += v.data[v.pos];
            v.pos++;
            if (v.pos >= v.length) {
                v.active = false;
            }
        }
        if (acc > 32767) {
            acc = 32767;
        } else if (acc < -32768) {
            acc = -32768;
        }
        int16_t sample = (int16_t)acc;
        stereo_out[2 * i]     = sample;  // L
        stereo_out[2 * i + 1] = sample;  // R
    }
}

// ---------------------------------------------------------------------------
// Lectura de cuerdas (polling + debounce)
// ---------------------------------------------------------------------------

static const uint32_t DEBOUNCE_MS = 15;

static uint32_t last_change_ms[NUM_STRINGS];
static bool stable_state[NUM_STRINGS];    // ultimo estado confirmado
static bool raw_prev_state[NUM_STRINGS];  // ultima lectura cruda

static void strings_init() {
    for (uint8_t i = 0; i < NUM_STRINGS; i++) {
        pinMode(STRING_PIN[i], INPUT_PULLUP);
        stable_state[i] = true;    // HIGH = cuerda libre (pull-up)
        raw_prev_state[i] = true;
        last_change_ms[i] = 0;
    }
}

// Se llama periodicamente desde audio_task. En flanco de bajada confirmado
// (cuerda pulsada), retriggerea la nota del banco central correspondiente
// desde el principio, incluso si ya estaba sonando.
static void strings_poll() {
    uint32_t now = millis();
    for (uint8_t i = 0; i < NUM_STRINGS; i++) {
        bool raw = digitalRead(STRING_PIN[i]) != 0;
        if (raw != raw_prev_state[i]) {
            raw_prev_state[i] = raw;
            last_change_ms[i] = now;
        }
        if (raw != stable_state[i] && (now - last_change_ms[i]) >= DEBOUNCE_MS) {
            stable_state[i] = raw;
            if (!raw) {
                trigger_note(BANK_CENTRAL * NUM_STRINGS + i);
            }
        }
    }
}

// ---------------------------------------------------------------------------
// Lectura UART (comandos del Pro Micro)
// ---------------------------------------------------------------------------

// Cada caracter recibido dispara una nota, mapeo directo a notas[0..14]:
// '0'-'9' -> notas[0..9], 'A'-'E' -> notas[10..14]. Un byte = un trigger, sin
// framing de linea. Caracteres fuera de ese set se ignoran silenciosamente
// (protege contra basura electrica en la linea, ver docs/04).
static void process_uart_char(char c) {
    int8_t note_index = -1;
    if (c >= '0' && c <= '9') {
        note_index = c - '0';
    } else if (c >= 'A' && c <= 'E') {
        note_index = 10 + (c - 'A');
    }
    if (note_index >= 0) {
        trigger_note((uint8_t)note_index);
    }
}

// Acepta comandos tanto por UART0 (Serial, el USB de programacion/debug —
// util para probar tipeando en el Monitor Serie sin el Pro Micro conectado)
// como por UART2 (Serial2, el enlace real con el Pro Micro).
static void uart_poll() {
    while (Serial.available() > 0) {
        process_uart_char((char)Serial.read());
    }
    while (Serial2.available() > 0) {
        process_uart_char((char)Serial2.read());
    }
}

// ---------------------------------------------------------------------------
// I2S
// ---------------------------------------------------------------------------

static void i2s_setup() {
    i2s_config_t config = {
        .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX),
        .sample_rate = SAMPLE_RATE,
        .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
        .channel_format = I2S_CHANNEL_FMT_RIGHT_LEFT,
        .communication_format = I2S_COMM_FORMAT_STAND_I2S,
        .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
        .dma_buf_count = 4,
        .dma_buf_len = BLOCK_FRAMES,
        .use_apll = false,
        .tx_desc_auto_clear = true,
        .fixed_mclk = 0,
    };
    i2s_pin_config_t pins = {
        .bck_io_num = I2S_BCK_PIN,
        .ws_io_num = I2S_WS_PIN,
        .data_out_num = I2S_DOUT_PIN,
        .data_in_num = I2S_PIN_NO_CHANGE,
    };
    i2s_driver_install(I2S_PORT, &config, 0, NULL);
    i2s_set_pin(I2S_PORT, &pins);
}

// ---------------------------------------------------------------------------
// Tarea de audio
// ---------------------------------------------------------------------------

// i2s_write() bloquea hasta que la DMA tiene lugar libre, lo que marca el
// ritmo real de 22050 sps sin necesidad de un timer aparte. El polling de
// cuerdas se hace una vez por bloque (~11.6 ms a 256 frames).
//
// Se fija al core 0 (ver setup()) para separarla del core 1, donde
// arduino-esp32 corre setup()/loop() por defecto. No usamos WiFi/BT (que
// en ESP-IDF corren fijos en el core 0), asi que en este proyecto el core 0
// queda practicamente dedicado al audio.
static void audio_task(void *arg) {
    static int16_t block[BLOCK_FRAMES * 2];  // estereo intercalado
    for (;;) {
        strings_poll();
        uart_poll();
        mix_block(block, BLOCK_FRAMES);
        size_t written = 0;
        i2s_write(I2S_PORT, block, sizeof(block), &written, portMAX_DELAY);
    }
}

void setup() {
    Serial.begin(115200);
    strings_init();
    i2s_setup();
    Serial2.begin(UART_BAUD, SERIAL_8N1, UART_RX_PIN, -1);
    xTaskCreatePinnedToCore(audio_task, "audio_task", 4096, NULL, 2, NULL, 0);
    Serial.println("Soundcard initialized");
    trigger_note(10);
}

void loop() {
    vTaskDelay(pdMS_TO_TICKS(1000));
}
