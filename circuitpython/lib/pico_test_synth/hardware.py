# SPDX-FileCopyrightText: Copyright (c) 2023 Tod Kurt
# SPDX-License-Identifier: MIT
#
# pico_test_synth/hardware.py -- board I/O for pico_test_synth / pico_test_synth2
# 22 Jul 2023 - @todbot / Tod Kurt
# part of https://github.com/todbot/pico_test_synth
#
# One Hardware object owns the board: audio, the two pots, the button,
# the 16 touch pads, the OLED, the UART MIDI pins and the LED.
#
#     from pico_test_synth import Hardware
#     hw = Hardware()                 # audio is running after this
#     display = hw.setup_display()    # opt-in, see below
#     hw.setup_touch("up")
#
# The display, the touch pads and the MIDI UART are opt-in: each costs
# libraries, RAM and pins a given program may not want. Explicit calls
# rather than lazy properties, so the order stays visible at the call site:
# setup_display() takes the screen away from the REPL, so a program
# wants its startup prints to happen first.
#
# Libraries needed:
#   circup install adafruit_displayio_ssd1306   (only for setup_display)

import analogio
import audiobusio
import audiomixer
import board
import digitalio
import keypad
import pwmio
import synthio

# 22050 for a Pico (RP2040); a Pico 2 (RP2350) can do 44100.
#
# NOTE: Nyquist is 11 kHz here, and a synthio.Biquad cutoff above that is
# undefined. Cap it from hw.sample_rate, e.g.
#   SubtractiveSynth.FILT_F_MAX = hw.sample_rate * 0.45
SAMPLE_RATE = 22050
CHANNEL_COUNT = 2
# In BYTES: audiomixer splits it into two 1024-byte halves, 256 stereo
# frames each. One plays while the other refills, so one half (11.6 ms at
# 22.05 kHz, 5.8 at 44.1) is the deadline the main loop has to hit. More
# than 4096 adds too much lag.
BUFFER_SIZE = 2048

DW, DH = 128, 64  # display width/height

# pin definitions
# fmt: off
sw_pin        = board.GP28   # middle button
knobB_pin     = board.GP27   # right knob
knobA_pin     = board.GP26   # left knob
led_pin       = board.GP25   # regular LED, not neopixel
pico_pwr_pin  = board.GP23   # HIGH = less supply ripple, so less audio noise
i2s_data_pin  = board.GP22
i2s_lclk_pin  = board.GP21
i2s_bclk_pin  = board.GP20
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

# Knob filter, as a right-shift: the new reading gets 1/(2**KNOB_SHIFT) of
# the weight. Measured on device, read_pots() costs 0.23 ms and settles the
# pot to 0.13% of full scale, which ParamSet's deadband then swallows.
KNOB_SHIFT = 2
_KNOB_HALF = 1 << (KNOB_SHIFT - 1)  # rounds the shift to nearest

# AnalogIn.value is 0-65535; multiply rather than divide, cheaper on a
# soft-float target. 65535, not 65536, so full scale reads exactly 1.0.
_ADC_SCALE = 1.0 / 65535

TOUCH_PULLS = {"up": digitalio.Pull.UP, "down": digitalio.Pull.DOWN, None: None}


class Hardware:
    """The pico_test_synth board.

    :param int sample_rate: audio sample rate; see SAMPLE_RATE above
        before raising it.
    :param int channel_count: 2 for the stereo I2S DAC, 1 to halve the
        render cost if you don't need stereo.
    :param int buffer_size: mixer buffer in bytes; half of it is the
        refill deadline your main loop has to hit.
    :param float volume: initial mixer level. 0.25 suits headphones,
        1.0 a line input.
    """

    def __init__(
        self,
        sample_rate=SAMPLE_RATE,
        channel_count=CHANNEL_COUNT,
        buffer_size=BUFFER_SIZE,
        volume=0.25,
    ):
        self.sample_rate = sample_rate
        self.channel_count = channel_count
        self.buffer_size = buffer_size

        # regulator into PWM mode: lower ripple than the default PFM, so a
        # quieter noise floor on the DAC
        self.pwr_mode = digitalio.DigitalInOut(pico_pwr_pin)
        self.pwr_mode.switch_to_output(value=True)

        self.led = pwmio.PWMOut(led_pin)
        self.keys = keypad.Keys((sw_pin,), value_when_pressed=False, pull=True)

        self.knobA = analogio.AnalogIn(knobA_pin)
        self.knobB = analogio.AnalogIn(knobB_pin)
        # filter state, kept as ints, see read_pots()
        self._knobA_filt = self.knobA.value
        self._knobB_filt = self.knobB.value

        # opt-in, see the setup_* methods
        self.display = None
        self.midi_uart = None
        self.touchins = []
        self._touch_last = []

        # audio last, so the slow setup above is done before it starts
        self.audio = audiobusio.I2SOut(
            bit_clock=i2s_bclk_pin, word_select=i2s_lclk_pin, data=i2s_data_pin
        )
        self.mixer = audiomixer.Mixer(
            sample_rate=sample_rate,
            channel_count=channel_count,
            buffer_size=buffer_size,
        )
        self.synth = synthio.Synthesizer(
            sample_rate=sample_rate, channel_count=channel_count
        )
        self.audio.play(self.mixer)
        self.mixer.voice[0].play(self.synth)
        self.mixer.voice[0].level = volume

        # note: no synth.envelope here, synthtools' Synth gives every
        # Note its own, and a global one would override it

    # --- opt-in hardware --------------------------------------------------

    def setup_display(self):
        """Bring up the 128x64 SSD1306 OLED. Returns it, and sets .display.

        auto_refresh is OFF: a full frame is ~31 ms on the wire at I2C
        1 MHz, against an 11.6 ms mixer refill deadline. Refresh
        deliberately, and only when something actually changed. A partial
        redraw costs ~0.6 ms per dirty region plus ~0.03 ms per byte, so
        WIDTH is what a layout pays for, not how many elements moved;
        synthtools' tests/hw/test_display_cost.py measures all of it.
        """
        import adafruit_displayio_ssd1306
        import busio
        import displayio
        import i2cdisplaybus

        displayio.release_displays()
        self.i2c = busio.I2C(scl=i2c_scl_pin, sda=i2c_sda_pin, frequency=1_000_000)
        display_bus = i2cdisplaybus.I2CDisplayBus(self.i2c, device_address=0x3C)
        self.display = adafruit_displayio_ssd1306.SSD1306(
            display_bus, width=DW, height=DH, rotation=180, auto_refresh=False
        )
        self.display.refresh()
        return self.display

    def setup_touch(self, pull="up"):
        """Set up the 16 touch pads. Returns the list of TouchIns.

        ``pull`` picks the pin's internal resistor, which depends on how
        the pads are wired: a pico_test_synth2 can be either way:

        ``"up"``
            internal pull-up (the default, and the only one that works on
            an rp2040 with no external resistors)
        ``"down"``
            internal pull-down; pico_test_synth1 with a Pico 1
        ``None``
            no internal pull, for pads with their own resistor
        """
        import touchio

        pull_type = TOUCH_PULLS[pull]
        for pin in touch_pins:
            touchin = touchio.TouchIn(pin, pull_type)
            touchin.threshold = int(touchin.threshold * 1.1)  # noise protec
            self.touchins.append(touchin)
            self._touch_last.append(False)
        return self.touchins

    def setup_midi_uart(self, baudrate=31250):
        """Bring up the TRS MIDI UART. Returns it, and sets .midi_uart."""
        import busio

        self.midi_uart = busio.UART(
            rx=uart_rx_pin, tx=uart_tx_pin, baudrate=baudrate, timeout=0.001
        )
        return self.midi_uart

    # --- inputs -----------------------------------------------------------

    def read_pots(self):
        """Read both knobs, filtered. Returns a pair of 0.0-1.0 floats.

        An exponential moving average in INTEGER math on the raw 0-65535
        reading, with one float multiply at the end: the RP2040 is a
        Cortex-M0+ with no FPU, so every float operation is emulated.

        The last couple of counts are snapped rather than shifted. A
        right-shift floors, so on its own the average stalls short of the
        endpoints, and a pot at full scale reading 0.99998 puts
        ``int(knobval * vmax)`` on vmax - 1, making a DISCRETE parameter's
        top choice unreachable. Below a delta of 3 the shift cannot move a
        full count, so snap instead.

        Smoothing lives here because synthtools' ParamSet only deadbands.
        Anything wanting the raw value can read ``hw.knobA.value``.
        """
        d = self.knobA.value - self._knobA_filt
        self._knobA_filt += d if -3 < d < 3 else (d + _KNOB_HALF) >> KNOB_SHIFT
        d = self.knobB.value - self._knobB_filt
        self._knobB_filt += d if -3 < d < 3 else (d + _KNOB_HALF) >> KNOB_SHIFT
        return (self._knobA_filt * _ADC_SCALE, self._knobB_filt * _ADC_SCALE)

    def check_button(self):
        """The middle button's next event, or None.

        Sugar for ``hw.keys.events.get()``; use hw.keys directly if you
        want the queue itself.
        """
        return self.keys.events.get()

    def check_touch(self):
        """Scan the pads, return keypad-like Events for any that changed.

        Similar to what keys.events.get() gives: each Event has
        .key_number and .pressed.

        The most expensive thing in a typical main loop, and nearly all of
        it is the pads' RC settling time, which no code can remove. For 16
        pads, measured on a Pico on pico_test_synth2:

            via adafruit_debouncer      7.90 ms
            16 raw reads, nothing else  4.04 ms

        Returns an empty tuple, not None, when nothing changed.
        """
        events = None
        touchins = self.touchins
        last = self._touch_last
        for i in range(len(touchins)):
            pressed = touchins[i].value
            if pressed != last[i]:
                last[i] = pressed
                if events is None:
                    events = []
                events.append(keypad.Event(i, pressed))
        return events or ()

    def touch_hold(self, i):
        """How hard pad ``i`` is pressed, over its threshold.

        Takes its own reading, so it costs a full settling read per call:
        fine for the one pad you care about, not for polling all 16.
        Negative means not touched.
        """
        touchin = self.touchins[i]
        return touchin.raw_value - touchin.threshold

    # --- outputs ----------------------------------------------------------

    def set_volume(self, v):
        self.mixer.voice[0].level = v

    def get_volume(self):
        return self.mixer.voice[0].level

    def set_led(self, v):
        self.led.duty_cycle = (v & 255) * 255  # only use B of RGB, if RGB
