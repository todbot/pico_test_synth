#include <Wire.h>
#include <Bounce2.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
//#include "fonts/Dialog_plain_12.h"
#include "fonts/Dialog_plain_10.h"
#include "fonts/Dialog_bold_12.h"
//#include "fonts/Dialog_bold_11.h"
#include "fonts/Dialog_plain_8.h"
#define myfont Dialog_plain_10
#define myfontB Dialog_bold_12
#define myfontSM Dialog_plain_8
#include <TouchyTouch.h>

#include "SynthPatch.h"
#include "SynthUI.h"

// PIN DEFINITIONS
const int sw_pin = 28;
const int knobB_pin = 27;
const int knobA_pin = 26;
const int led_pin = 25;       // regular LED, not neopixel
const int pico_pwr_pin = 23;  // HIGH = improved ripple (lower noise) but less efficient
const int i2s_data_pin = 22;
const int i2s_lclk_pin = 21;
const int i2s_bclk_pin = 20;
const int i2c_scl_pin = 19;
const int i2c_sda_pin = 18;
const int uart_rx_pin = 17;
const int uart_tx_pin = 16;

const int touch_pins[] = { 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15 };
const int touch_count = sizeof(touch_pins) / sizeof(int);
const int touch_threshold_adjust = 100;
const bool touch_black_keys[] = { 0, 1, 0, 1, 0, 0, 1, 0, 1, 0, 1, 0, 0, 1, 0, 1 }; // 1, 3, 6, 8, 10, 13, 14}

// DISPLAY PARAMTERS
const int oled_i2c_addr = 0x3C;
const int dw = 128;
const int dh = 64;

// GUI LAYOUT PARAMETERS
int num_disp_params = 3;
int hilite_param = 0;
int line_spacing = 12;  // depends on font
int param_offset = 0;

uint32_t last_status_time;

TouchyTouch touches[touch_count];
Bounce2::Button button;

Adafruit_SSD1306 display(dw, dh, &Wire1, -1);

SynthUI synthui(&display);

const char* wav_types[] = {"saw", "squ", "sin", "wv1", "wv2"};
const char* filt_types[] = {"lpf", "bpf", "hpf"};

// valid params for this synth
Param patch_params[] = {
  ParamChoice("Wave", "waveform type", 0, wav_types, 5),
  ParamChoice("Filter", "filter type", 0, filt_types, 3),
  ParamRange("fFreq", "filter frequency", 180.0),
  ParamRange("fReso", "filter resonance", 150),
  ParamRange("fAtk", "filter env attack", 0.2, 0, 10, "%0.2f"),
  ParamRange("aRel", "amp env release", 1.0, 0, 10, "%0.2f"),
  ParamRange("fAtk", "filter attack", 10),
};
//   ParamRange("fRel", 30),
//   ParamRange("fType", 0),
//   ParamRange("vMix", 0.01, /* min */ 0.0, /* max */ 1.0, "%.2f"),
//   ParamRange("Nois", 50),
//   ParamRange("fLfoR", 1.2, 0.1, 5.0, "%.2f"),
//   ParamRange("aLfoR", 1.2, 0.1, 5.0, "%.2f"),
//   ParamRange("LfoFr", 0.2, 0.1, 5.0, "%.2f"),
//   ParamRange("LfoAr", 0, 0.1, 5.0, "%.2f"),
//   ParamRange("tink", 420, /*min*/ 0, /*max*/ 1000),
//   ParamRange("foop", 123),
//   ParamRange("BONK", 1),
// };
const int num_patch_params = sizeof(patch_params) / sizeof(Param);

Patch patches[] = {
  Patch("onepatch", patch_params, num_patch_params),
  Patch("twopatch", patch_params, num_patch_params),
  Patch("threepatch", patch_params, num_patch_params),
};
int num_patches = sizeof(patches) / sizeof(Patch);
int patchi = 0;

/**
 */
void setup() {
  Serial.begin(115200);
  Serial.println("pico_test_synth hwtest2");

  // KNOBS & BUTTON & LED
  pinMode(led_pin, OUTPUT);
  button.attach(sw_pin, INPUT_PULLUP);
  button.setPressedState(LOW);

  // TOUCH
  for (int i = 0; i < touch_count; i++) {
    touches[i].begin(touch_pins[i]);
    touches[i].threshold += touch_threshold_adjust;  // make a bit more noise-proof
  }

  // DISPLAY
  Wire1.setSDA(i2c_sda_pin);
  Wire1.setSCL(i2c_scl_pin);
  Wire1.begin();

  if (!display.begin(SSD1306_SWITCHCAPVCC, oled_i2c_addr)) {
    Serial.println(F("SSD1306 allocation failed"));
    for (;;)
      ;  // Don't proceed, loop forever
  }

  display.setRotation(2);  // rotated 180
  display.clearDisplay();

  int16_t x1, y1;
  uint16_t w, h;
  display.setFont(&myfontB);
  display.getTextBounds("HELLO", 0, 20, &x1, &y1, &w, &h);
  line_spacing = h * 1.5;

  synthui.print_text(0, line_spacing * 1, "PICO_TEST_SYNTH", &myfont);
  display.display();
  delay(500);
  synthui.print_text(15, line_spacing * 2, "HWTEST2");
  synthui.print_textf(0, line_spacing * 4, "params:%d patches:%d", num_patch_params, num_patches);
  display.display();
  delay(2500);
}

/**
 *
 */
void updateInputs() {
  button.update();
  // knobA_update();
  // knobB_update();
  for (int i = 0; i < touch_count; i++) {
    touches[i].update();
  }
}

/**
 *
 */
void updateDisplay() {
  delay(50);   // debug

  #define buflen 40
  char buf1[buflen], buf2[buflen];
  float xpos, ypos;

  Patch patch = patches[patchi];
  Param* params = patch.params;
  int num_params = patch.num_params;
  int hp = hilite_param + param_offset;

  byte key = uiGetKey(&xpos, &ypos);

  if (key == KEY_DOWN || key == KEY_UP) {
    Serial.printf("up/down!  ");
    param_offset = num_params * xpos;
  }
  if (key == KEY_RIGHT || key == KEY_LEFT) {
    Serial.printf("left/right!  ");
    params[hp].set_percent(ypos);
  }
  if (key == KEY_OK) {
    patchi = (patchi + 1) % num_patches;
    return;  // let it update
  }

  // Serial.printf("patch:'%s'\n", patch.name);
  // for( int i=0; i<num_params; i++ ) {
  //   Serial.printf("  param:'%s' = %.2f\n", params[i].name, params[i].val);
  // }

  display.clearDisplay();
  synthui.set_font(&myfont);
  synthui.print_textf(0, line_spacing * 0.75, "patch: %s", patch.name);
  //snprintf(buf1, buflen, "patch: %s", patch.name);
  //synthui.print_text(0, line_spacing / 2, buf1, &myfont);
  display.drawLine(0, line_spacing, 127, line_spacing, WHITE);

  synthui.draw_vertical_slider(122, line_spacing, (float)param_offset / num_params, 5, 50);

  for (int i = 0; i < num_disp_params; i++) {
    int io = i + param_offset;
    int yoff = line_spacing * 2 + i * line_spacing + line_spacing/4 - 2;
    if (io < num_params) {
      Param p = params[io];
      snprintf(buf1, buflen, "%s", p.name);
      p.val_to_str(buf2, buflen);
      synthui.print_text(3, yoff, buf1, i == hilite_param ? &myfontB : &myfont);
      // synthui.print_text(45, yoff, ":", &myfontSM);
      if( p.type == Range ) { 
        synthui.set_font(&myfontSM);
        synthui.print_text(50, yoff, buf2);
        synthui.draw_horizontal_slider(80, yoff, p.percent(), 35, 7, 7);
      }
      else { 
        synthui.print_text(50, yoff, buf2);
        synthui.draw_horizontal_slider(90, yoff, p.percent(), 25, 7, 7);
      }
    }
  }

  for( int i=0; i< touch_count; i++ ) { 
    bool black_key = touch_black_keys[i];
    if( touches[i].touched() ) { 
      display.fillRect(5 + (i*7), 58, 5,7, WHITE);
    } else { 
      display.drawRect(5 + (i*7), 58, 5, 7-2*black_key, WHITE);
    }
  } 

  // for (int i = 0; i < num_disp_params; i++) {
  //   int io = i + param_offset;
  //   int yoff = line_spacing * 2 + i * line_spacing;
  //   if (io < num_params) {
  //     snprintf(buf1, buflen, "%s", params[io].name);
  //     // snprintf(buf2, buflen, params[io].fmt, params[io].val);  // param value
  //     params[io].val_to_str(buf2, buflen);
  //     synthui.print_text(3, yoff, buf1, i == hilite_param ? &myfontB : &myfont);
  //     // synthui.print_text(45, yoff, ":", &myfontSM);
  //     synthui.set_font(&myfontSM);
  //     synthui.print_text(50, yoff, buf2);
  //     synthui.draw_horizontal_slider(80, yoff, params[io].percent(), 35, 7, 7);
  //   }
  // }
  display.display();
}

/**
 * Check to see if there's been any movement of the "X" and "Y" pots
 * and generate UI events for those. And if so, fill in the 
 * percentage absolute "position" in the passed in xpos & ypos
 */
int uiGetKey(float* xpos, float* ypos) {
  static int knobA_last;
  static int knobB_last;

  int knobA_val = analogRead(knobA_pin);  //knobA_update();
  int knobB_val = analogRead(knobB_pin);  //knobB_update();

  byte key = KEY_NONE;
  int knobA_diff = knobA_val - knobA_last;
  int knobB_diff = knobB_val - knobB_last;

  if (knobA_diff > 50) {
    key = KEY_DOWN;
    knobA_last = knobA_val;
  } else if (knobA_diff < -50) {
    key = KEY_UP;
    knobA_last = knobA_val;
  }

  if (knobB_diff > 50) {
    key = KEY_RIGHT;
    knobB_last = knobB_val;
  } else if (knobB_diff < -50) {
    key = KEY_LEFT;
    knobB_last = knobB_val;
  }

  if (button.pressed()) {
    key = KEY_OK;
  }

  // update the x & y percentage positions, if we've been asked
  if (xpos != NULL) { *xpos = knobA_val / 1024.0; }
  if (ypos != NULL) { *ypos = knobB_val / 1024.0; }

  return key;
}

/**
 *
 */
void loop() {
  updateInputs();
  updateDisplay();

  // if (button.pressed()) {
  //   Serial.println("           PRESS");
  // }
  // if (button.released()) {
  //   Serial.println("           RELEASE");
  // }

  uint32_t now = millis();
  if (now - last_status_time > 50) {
    last_status_time = now;
    for (int i = 0; i < touch_count; i++) {
      char t = touches[i].touched() ? '|' : ' ';  // indicates a touched value
      int touchval = touches[i].raw_value / 100;  // make a more printalbe value
      Serial.printf("%c%2d%c", t, touchval, t);
    }
    //Serial.printf(" knobs: %3d %3d", knobA_update(), knobB_update());
    Serial.println();
  }
}
