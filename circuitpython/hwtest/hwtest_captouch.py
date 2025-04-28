# pico_test_synth_hwtest_captouch.py -- test pico_test_synth captouch pads
# 15 Feb 2024 - @todbot / Tod Kurt
# Note: requires a wide terminal (110chars)
import time
import board
import touchio
import digitalio

pull_type = digitalio.Pull.UP

touch_pins = (
    board.GP0, board.GP1, board.GP2, board.GP3, board.GP4, board.GP5,
    board.GP6, board.GP7 ,board.GP8, board.GP9, board.GP10, board.GP11,
    board.GP12, board.GP13, board.GP14, board.GP15 )

touchins = []
for pin in touch_pins:
    print("touch pin:", pin)   # print here let's us diagnose if a pin is bad
    touchin = touchio.TouchIn(pin, pull=pull_type)
    touchin.threshold = int(touchin.threshold * 1.05)
    touchins.append(touchin)

while True:
    print("touch:","".join(['1' if t.value else '0' for t in touchins]), 
          "".join(["%4d " % t.raw_value for t in touchins]))
    time.sleep(0.05)
