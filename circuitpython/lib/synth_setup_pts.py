# SPDX-FileCopyrightText: Copyright (c) 2025 Tod Kurt
# SPDX-License-Identifier: MIT
#
# synth_setup_pts.py -- board I/O for a pico_test_synth / breadboard rig
#
# The "pts" variant of synth_setup.py: same audio bring-up, plus the
# 16 touch pads, the I2C OLED and the UART MIDI pins.
#
# This is the CANONICAL copy, shared by every synthtools-based demo in
# this repo (synthtools_polysynth/, tbish2/, ...). It lives in lib/, which
# CircuitPython puts on sys.path, so demos still say
# `from synth_setup_pts import ...` with no path prefix. Edit it here, not
# in a demo folder.
#
# Imported, not run. Audio and inputs are set up at import; the display
# and touch pads are opt-in, since each pulls in libraries and RAM you
# may not want:
#
#     from synth_setup_pts import synth, mixer, keys, knobA, knobB
#     from synth_setup_pts import setup_display, setup_touch, check_touch
#     display = setup_display()
#     touches = setup_touch()

import analogio
import audiobusio
import audiomixer
import board
import keypad
import synthio

# 22050, not 44100. Measured on a pico_test_synth2: at 44.1 kHz this rig
# clicks about once a second no matter how many notes are held, and no
# buffer size fixes it -- past 4096 bytes the added lag is worse than the
# glitch. Halving the rate does fix it, and NOT merely by stretching the
# buffer: 4096 bytes at 44.1 kHz and 2048 at 22.05 kHz give the identical
# 11.6 ms deadline, yet only the latter is clean. The difference is render
# cost. A bigger buffer only postpones a stall; half the sample rate is
# half the samples to compute, so the renderer can catch up after one.
#
# NOTE: this halves Nyquist to 11 kHz, and a Biquad cutoff above that is
# undefined -- see how the demo caps Synth.FILT_F_MAX.
SAMPLE_RATE = 22050
CHANNEL_COUNT = 2
# In BYTES, and audiomixer splits it into TWO half-buffers: 2048 gives two
# 1024-byte halves = 256 stereo frames. One half plays while the other
# refills, so one half -- 11.6 ms at 22.05 kHz, 5.8 at 44.1 -- is the
# deadline the main loop has to hit.
BUFFER_SIZE = 2048

# what we have plugged into the breadboard or pico_test_synth
# fmt: off
button_pins   = (board.GP28,)
knobA_pin     = board.GP26
knobB_pin     = board.GP27
i2s_bck_pin   = board.GP20
i2s_lck_pin   = board.GP21
i2s_dat_pin   = board.GP22
i2c_scl_pin   = board.GP19
i2c_sda_pin   = board.GP18
uart_rx_pin   = board.GP17
uart_tx_pin   = board.GP16

touch_pins = (
    board.GP0,  board.GP1,  board.GP2,  board.GP3,
    board.GP4,  board.GP5,  board.GP6,  board.GP7,
    board.GP8,  board.GP9,  board.GP10, board.GP11,
    board.GP12, board.GP13, board.GP14, board.GP15,
)
# fmt: on

# hook up external stereo I2S audio DAC board
audio = audiobusio.I2SOut(bit_clock=i2s_bck_pin, word_select=i2s_lck_pin, data=i2s_dat_pin)

# add a mixer to give us a buffer
mixer = audiomixer.Mixer(
    sample_rate=SAMPLE_RATE, channel_count=CHANNEL_COUNT, buffer_size=BUFFER_SIZE
)

# make the actual synthesizer
synth = synthio.Synthesizer(sample_rate=SAMPLE_RATE, channel_count=CHANNEL_COUNT)

# plug the mixer into the audio output
audio.play(mixer)

# plug the synth into the first 'voice' of the mixer
mixer.voice[0].play(synth)
mixer.voice[0].level = 0.25  # 0.25 usually better for headphones, 1.0 for line-in

# note: no synth.envelope here -- synthtools' Synth gives every Note its own

# add key reading with debouncing
keys = keypad.Keys(button_pins, value_when_pressed=False, pull=True)

knobA = analogio.AnalogIn(knobA_pin)
knobB = analogio.AnalogIn(knobB_pin)

i2c = None
display_bus = None
display = None


def setup_display():
    """Bring up the 128x64 SSD1306 OLED. Returns the display.

    auto_refresh is OFF: a full frame is 1024 bytes, ~9.5 ms on the wire at
    1 MHz, against a ~5.8 ms audio refill deadline (see BUFFER_SIZE).
    displayio does break that into chunks and runs background tasks between
    them, but refresh deliberately anyway, and only when something changed.
    """
    global i2c, display_bus, display
    import adafruit_displayio_ssd1306
    import busio
    import displayio
    import i2cdisplaybus

    DW, DH = 128, 64
    displayio.release_displays()
    i2c = busio.I2C(scl=i2c_scl_pin, sda=i2c_sda_pin, frequency=1_000_000)
    display_bus = i2cdisplaybus.I2CDisplayBus(i2c, device_address=0x3C)
    display = adafruit_displayio_ssd1306.SSD1306(
        display_bus, rotation=180, width=DW, height=DH, auto_refresh=False
    )
    display.refresh()
    return display


touchins = []
touches = []


def setup_touch(pull="up"):
    """Set up the 16 touch pads. Returns a list of Debouncers.

    ``pull`` picks the pin's internal resistor, which depends on how the
    pads are wired -- a pico_test_synth2 can be either way, so choose:

    ``"up"``
        internal pull-up (the default)
    ``"down"``
        internal pull-down
    ``None``
        no internal pull: the pads must have their own resistor. On an
        rp2040 with nothing external this raises
        ``ValueError: No pulldown on pin; 1Mohm recommended``.
    """
    # no `global`: the lists are appended to, never rebound
    import digitalio
    import touchio
    from adafruit_debouncer import Debouncer

    # a string rather than a digitalio.Pull, so a caller picking one does
    # not have to import digitalio just to name it
    pull_type = {"up": digitalio.Pull.UP, "down": digitalio.Pull.DOWN, None: None}[pull]
    for pin in touch_pins:
        touchin = touchio.TouchIn(pin, pull_type)
        touchin.threshold = int(touchin.threshold * 1.1)
        touchins.append(touchin)
        touches.append(Debouncer(touchin))
    return touches


def check_touch():
    """Check the touch inputs, return keypad-like Events.

    Same shape as keys.events.get() gives, so pads and buttons can be
    handled by the same code: each Event has .key_number and .pressed.
    """
    events = []
    for i, touch in enumerate(touches):
        touch.update()
        if touch.rose:
            events.append(keypad.Event(i, True))
        elif touch.fell:
            events.append(keypad.Event(i, False))
    return events
