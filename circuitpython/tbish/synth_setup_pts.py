# SPDX-FileCopyrightText: Copyright (c) 2025 Tod Kurt
# SPDX-License-Identifier: MIT
"""
`synth_setup_pts.py`

Getting synthio up and running on pico_touch_synth board
part of todbot circuitpython synthio tutorial
10 Feb 2025 - @todbot / Tod Kurt
"""

import board
import synthio
import audiobusio
import audiomixer
import keypad
import analogio

SAMPLE_RATE = 44100
CHANNEL_COUNT = 2
BUFFER_SIZE = 2048

# what we have plugged into the breadboard or pico_test_synth
button_pins = (board.GP28,)
knobA_pin = board.GP26
knobB_pin = board.GP27
i2s_bck_pin = board.GP20
i2s_lck_pin = board.GP21
i2s_dat_pin = board.GP22
i2c_scl_pin   = board.GP19
i2c_sda_pin   = board.GP18
uart_rx_pin   = board.GP17
uart_tx_pin   = board.GP16

touch_pins = (
    board.GP0, board.GP1, board.GP2, board.GP3, board.GP4, board.GP5,
    board.GP6, board.GP7 ,board.GP8, board.GP9, board.GP10, board.GP11,
    board.GP12, board.GP13, board.GP14, board.GP15 )

# hook up external stereo I2S audio DAC board
audio = audiobusio.I2SOut(bit_clock=i2s_bck_pin, word_select=i2s_lck_pin, data=i2s_dat_pin)

# add a mixer to give us a buffer
mixer = audiomixer.Mixer(sample_rate=SAMPLE_RATE,
                         channel_count=CHANNEL_COUNT,
                         buffer_size=BUFFER_SIZE)

# make the actual synthesizer
synth = synthio.Synthesizer(sample_rate=SAMPLE_RATE, channel_count=CHANNEL_COUNT)

# plug the mixer into the audio output
audio.play(mixer)

# plug the synth into the first 'voice' of the mixer
mixer.voice[0].play(synth)
mixer.voice[0].level = 0.25  # 0.25 usually better for headphones, 1.0 for line-in

# more on this later, but makes it sound nicer
synth.envelope = synthio.Envelope(attack_time=0.0, release_time=0.6)

# add key reading with debouncing
keys = keypad.Keys(button_pins, value_when_pressed=False, pull=True)

knobA = analogio.AnalogIn(knobA_pin)
knobB = analogio.AnalogIn(knobB_pin)

i2c = None
display_bus = None
display = None

def setup_display():
    global i2c, display_bus, display
    import busio
    import i2cdisplaybus
    import displayio
    import adafruit_displayio_ssd1306
    DW,DH = 128,64
    displayio.release_displays()
    i2c = busio.I2C(scl=i2c_scl_pin, sda=i2c_sda_pin, frequency=1_000_000)
    display_bus = i2cdisplaybus.I2CDisplayBus(i2c, device_address=0x3c)
    display = adafruit_displayio_ssd1306.SSD1306(display_bus, rotation=180,
                                                 width=DW, height=DH,
                                                 auto_refresh = False)
    display.refresh()
    return display

touchins = []
touches = []

def setup_touch():
    global touchins, touches
    import os
    import digitalio
    import touchio
    from adafruit_debouncer import Debouncer
    is_rp2350 = 'rp2350' in os.uname()[0]
    pull_type = None if not is_rp2350 else digitalio.Pull.UP
    for pin in touch_pins:
        touchin = touchio.TouchIn(pin, pull_type)
        touchin.threshold = int(touchin.threshold * 1.1)
        touchins.append(touchin)
        touches.append(Debouncer(touchin))
    return touches

def check_touch():
    """Check the touch inputs, return keypad-like Events"""
    events = []
    for i,touch in enumerate(touches):
        touch.update()
        if touch.rose:
            events.append(keypad.Event(i,True))
        elif touch.fell:
            events.append(keypad.Event(i,False))
    return events

