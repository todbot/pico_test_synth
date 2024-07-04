#include <Wire.h>
#include <Bounce2.h>
#include <U8g2lib.h>
// #include <Adafruit_GFX.h>
// #include <Adafruit_SSD1306.h>

#include <TouchyTouch.h>
#include <Smooth.h>

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
// display parameters
const int oled_i2c_addr = 0x3C;
const int dw = 128;
const int dh = 64;

TouchyTouch touches[touch_count];
Bounce2::Button button;
Smooth knobA_avg(10);
Smooth knobB_avg(10);

//Adafruit_SSD1306 display(dw, dh, &Wire1, -1);
U8G2_SSD1306_128X64_NONAME_F_2ND_HW_I2C  disp(U8G2_R2);


int knobA_update() {
  knobA_avg += analogRead(knobA_pin);
  return knobA_avg();
}
int knobB_update() {
  knobB_avg += analogRead(knobB_pin);
  return knobB_avg();
}

void setup() {
  Serial.begin(115200);
  Serial.println("pico_test_synth hwtest1");

  // KNOBS & BUTTON & LED
  pinMode(led_pin, OUTPUT);
  button.attach(sw_pin, INPUT_PULLUP);
  button.setPressedState(LOW);
  knobA_update();
  knobB_update();

  // TOUCH
  for (int i = 0; i < touch_count; i++) {
    touches[i].begin(touch_pins[i]);
    touches[i].threshold += touch_threshold_adjust;  // make a bit more noise-proof
  }

  // DISPLAY
  Wire1.setSDA(i2c_sda_pin);
  Wire1.setSCL(i2c_scl_pin);
  Wire1.begin();
  disp.begin();

  // Wire1.setSDA(i2c_sda_pin);
  // Wire1.setSCL(i2c_scl_pin);
  // Wire1.begin();

  // if (!display.begin(SSD1306_SWITCHCAPVCC, oled_i2c_addr)) {
  //   Serial.println(F("SSD1306 allocation failed"));
  //   for (;;)
  //     ;  // Don't proceed, loop forever
  // }

  // //display.clearDisplay();
  // display.display();  // must clear before display, otherwise shows adafruit logo
}

uint32_t last_status_time;

void updateInputs() {
  button.update();
  knobA_update();
  knobB_update();
  for (int i = 0; i < touch_count; i++) {
    touches[i].update();
  }
}

void updateDisplay() {
  disp.clearBuffer();					// clear the internal memory
  disp.setFont(u8g2_font_ncenB08_tr);	// choose a suitable font
  disp.drawStr(0,10,"Hello World!");	// write something to the internal memory
  char buf[20];
  snprintf(buf, 20, "m:%ld", millis());
  disp.drawStr(0,30,buf);	// write something to the internal memory
  disp.sendBuffer();					// transfer internal memory to the display
}

void loop() {
  updateInputs();
  updateDisplay();

  if (button.pressed()) {
    Serial.println("           PRESS");
  }
  if (button.released()) {
    Serial.println("           RELEASE");
  }

  uint32_t now = millis();
  if (now - last_status_time > 50) {
    last_status_time = now;
    for (int i = 0; i < touch_count; i++) {
      char t = touches[i].touched() ? '|' : ' ';  // indicates a touched value
      int touchval = touches[i].raw_value / 100;  // make a more printalbe value
      Serial.printf("%c%2d%c", t, touchval, t);
    }
    Serial.printf(" knobs: %3d %3d", knobA_update(), knobB_update());
    Serial.println();
  }

}
