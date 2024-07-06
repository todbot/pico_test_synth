#ifndef SYNTHUI_H
#define SYNTHUI_H

#include <Adafruit_GFX.h>

#define KEY_NONE 0    // No key presses are detected
#define KEY_UP 1      // Up key is pressed (navigate up through the menu items list, select next value of the digit/char of editable variable, or previous option in select)
#define KEY_RIGHT 2   // Right key is pressed (navigate through the link to another (child) menu page, select next digit/char of editable variable, execute code associated with button)
#define KEY_DOWN 3    // Down key is pressed (navigate down through the menu items list, select previous value of the digit/char of editable variable, or next option in select)
#define KEY_LEFT 4    // Left key is pressed (navigate through the Back button to the previous menu page, select previous digit/char of editable variable)
#define KEY_CANCEL 5  // Cancel key is pressed (navigate to the previous (parent) menu page, exit edit mode without saving the variable, exit context loop if allowed within context's settings)
#define KEY_OK 6      // Ok/Apply key is pressed (toggle bool menu item, enter edit mode of the associated non-bool variable, exit edit mode with saving the variable, execute code associated with button)

class Param {
public:
  Param(const char* aname, float aval, float aminval = 0, float amaxval = 255, const char* afmt = "%.0f") {
    name = aname;
    val = aval;
    minval = aminval;
    maxval = amaxval;
    fmt = afmt;
  }
  float percent() {
    return (val - minval) / (maxval - minval);
  }
  void set_percent(float pct) {
    val = pct * (maxval - minval) + minval;
  }

  const char* name;
  float val;
  float minval;
  float maxval;
  const char* fmt;
};

class SynthUI {
public:
  SynthUI(Adafruit_GFX* adisplay) {
    display = adisplay;
  }


  void print_text(int x, int y, const char* str, const GFXfont *fnt = NULL) {
    if(fnt!=NULL) { display->setFont(fnt); } 
    display->setTextColor(WHITE, 0);
    display->setCursor(x, y);
    display->print(str);
  }

  /** 
   * Draw vertical slider with a "thumb" position identifying value
   * thumpos ranges 0.0-1.0
   */
  void draw_vertical_slider(int x, int y, float thumbpos, int w = 5, int h = 63, int thumbw = 5, int thumbh = 10) {
    int ypos = thumbpos * h;
    display->drawRect(x, y, w, h, WHITE);                   // right side scroll bar
    display->fillRect(x, y + ypos, thumbw, thumbh, WHITE);  // FIXME
  }


  Adafruit_GFX* display;
};

#endif
