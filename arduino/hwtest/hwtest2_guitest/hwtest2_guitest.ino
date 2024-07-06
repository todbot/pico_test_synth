#include <Wire.h>
#include <Bounce2.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include "fonts/Dialog_plain_10.h"
#include "fonts/Dialog_bold_11.h"
#include "fonts/Dialog_plain_8.h"
#define myfont Dialog_plain_10
#define myfontB Dialog_bold_11
#define myfontSM Dialog_plain_8
#include <TouchyTouch.h>

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

// DISPLAY PARAMTERS
const int oled_i2c_addr = 0x3C;
const int dw = 128;
const int dh = 64;

// GUI LAYOUT PARAMETERS
const int num_disp_params = 5;
const int hilite_param = 0;
const int line_spacing = 12;  // depends on font
const int line_offset = 12; // how much to move down from top
int param_offset = 0;

uint32_t last_status_time;

TouchyTouch touches[touch_count];
Bounce2::Button button;

Adafruit_SSD1306 display(dw, dh, &Wire1, -1);

SynthUI synthui(&display);

Param params[] = {
  Param("FREQ", 180.0), 
  Param("ATCK", 10 ),
  Param("RELS", 30),
  Param("RESQ", 150),
  Param("DTUN", 0.01, /* min */ 0.0, /* max */ 1.0, "%.2f"),
  Param("NOIS", 50),
  Param("VMIX", 50),
  Param("LFOr", 1.2, 0.1, 5.0, "%.2f"),
  Param("tink", 420, /*min*/ 0, /*max*/ 1000),
  Param("foop", 123),
  Param("BONK", 1),
};
const int num_params = sizeof(params) / sizeof(Param);

/**
 */
void setup() {
  Serial.begin(115200);
  Serial.println("pico_test_synth hwtest1");

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
  // display.display();       // must clear before display, otherwise shows adafruit logo
  // delay(500);
  display.clearDisplay();
  display.setFont(&myfont);

  synthui.print_text(10,10, "PICO_TEST_SYNTH", &myfont);
  display.display();  
  delay(500);
  synthui.print_text(10,20, "HWTEST2");
  display.display();
  delay(500);
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
 * Draw vertical slider with a "thumb" position identifying value
 * thumpos ranges 0.0-1.0
 */
void draw_vertical_slider(int x, int y, float thumbpos, int w=5, int h=63, int thumbw=5, int thumbh=10 ) { 
  int ypos = thumbpos * h;
  display.drawRect( x, y, w, h, WHITE ); // right side scroll bar
  display.fillRect( x, y + ypos, thumbw, thumbh, WHITE ); // FIXME
}
/** 
 * Draw horizontal slider with a "thumb" position identifying value
 * thumpos ranges 0.0-1.0
 */
void draw_horizontal_slider(int x, int y, float thumbpos, int w=127, int h=5, int thumbw=10, int thumbh=5) { 
  int xpos = thumbpos * (w-thumbw);
  display.drawRect( x, y-h, w, h, WHITE ); // right side scroll bar
  display.fillRect( x+xpos, y-h, thumbw, thumbh, WHITE ); // FIXME
}

/**
 *
 */
void updateDisplay() {
  // delay(50);
  char buf[20];
  float xpos, ypos;
  int hp = hilite_param + param_offset;
 
  byte key = uiGetKey(&xpos, &ypos);

  if( key == KEY_DOWN || key == KEY_UP ) {
    Serial.printf("up/down!  ");
    param_offset =  num_params * xpos; 
  }
  if( key == KEY_RIGHT || key == KEY_LEFT ) { 
    Serial.printf("left/right!  ");
    params[hp].set_percent( ypos );
  }

  display.clearDisplay();
  display.setFont(&myfont);
  display.setTextColor(WHITE, 0);
  
  draw_vertical_slider( 122, 0, (float)param_offset / (num_params-num_disp_params+1));

  for (int i = 0; i < num_disp_params; i++) {
    display.setFont( i==hilite_param ? &myfontB : &myfont);
    int io = i + param_offset;
    int loff = line_offset + i * line_spacing;
    if (io < num_params) {
      snprintf(buf, 20, "%s", params[io].name);
      display.setCursor(5, loff); // param name
      display.print(buf);
      display.setFont(&myfontSM);
      snprintf(buf, 20, params[io].fmt, params[io].val);  // param value
      // display.setFont( i==hilite_param ? &myfontB : &myfont);
      display.setCursor(45, loff);
      display.print(": ");
      display.print(buf);
      draw_horizontal_slider( 80, loff, params[io].percent(), 30, 5 );
    }
  }
  
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

  button.update();
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
  if( xpos!=NULL ) { *xpos = knobA_val / 1024.0; }
  if( ypos!=NULL ) { *ypos = knobB_val / 1024.0; }

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