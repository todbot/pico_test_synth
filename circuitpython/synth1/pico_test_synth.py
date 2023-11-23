
# pico_test_synth.py -- hardware defines and setup for pico_test_synth board
# 22 Jul 2023 - @todbot / Tod Kurt
# part of https://github.com/todbot/pico_test_synth
#
# libraries needed:
#  circup install neopixel, adafruit_debouncer, adafruit_displayio_ssd1306
#
# UI fixme:
# knob "pickup" vs knob "catchup"  (maybe done in app instead)

import board, busio
import analogio, keypad
import touchio
from adafruit_debouncer import Debouncer
import neopixel
import audiopwmio, audiomixer, audiobusio
import synthio
import displayio
import adafruit_displayio_ssd1306

SAMPLE_RATE = 25600   # lets try powers of two
MIXER_BUFFER_SIZE = 4096
DW,DH = 128, 64  # display width/height

# pin definitions
sw_pin        = board.GP28
knobB_pin     = board.GP27
knobA_pin     = board.GP26
led_pin       = board.GP25
i2s_data_pin  = board.GP22
i2s_lclk_pin  = board.GP21
i2s_bclk_pin  = board.GP20
i2c_scl_pin   = board.GP19
i2c_sda_pin   = board.GP18
uart_rx_pin   = board.GP17
uart_tx_pin   = board.GP16

touch_pins = (
    board.GP0, board.GP1, board.GP2, board.GP3, board.GP4, board.GP5,
    board.GP6, board.GP7 ,board.GP8, board.GP9, board.GP10, board.GP11,
    board.GP12, board.GP13, board.GP14, board.GP15 )


class PicoTestSynthHardware():
    def __init__(self):
        self.led = neopixel.NeoPixel(led_pin, 1, brightness=0.1)
        self.keys = keypad.Keys( pins=(sw_pin,),  value_when_pressed=False )
        self._knobA = analogio.AnalogIn(knobA_pin)
        self._knobB = analogio.AnalogIn(knobB_pin)
        self.knobA = self._knobA.value
        self.knobB = self._knobB.value

        self.touchins = []  # for raw_value
        self.touches = []   # for debouncer
        for pin in touch_pins:
           touchin = touchio.TouchIn(pin)
           # touchin.threshold = int(touchin.threshold * 1.1) # noise protection
           self.touchins.append(touchin)
           self.touches.append( Debouncer(touchin) )

        self.midi_uart = busio.UART(rx=uart_rx_pin, tx=uart_tx_pin, baudrate=31250, timeout=0.001)

        displayio.release_displays()
        i2c = busio.I2C(scl=i2c_scl_pin, sda=i2c_sda_pin, frequency=400_000 )
        display_bus = displayio.I2CDisplay(i2c, device_address=0x3c )
        self.display = adafruit_displayio_ssd1306.SSD1306(display_bus,
                                                          width=DW, height=DH, rotation=180)

        # now do audio setup (after display) so we have minimal audible glitches
        self.audio = audiobusio.I2SOut(bit_clock=i2s_bclk_pin,
                                       word_select=i2s_lclk_pin,
                                       data=i2s_data_pin)
        self.mixer = audiomixer.Mixer(sample_rate=SAMPLE_RATE, voice_count=1, channel_count=1,
                                     bits_per_sample=16, samples_signed=True,
                                     buffer_size=MIXER_BUFFER_SIZE)
        self.synth = synthio.Synthesizer(sample_rate=SAMPLE_RATE)
        self.audio.play(self.mixer)
        self.mixer.voice[0].play(self.synth)

    def check_key(self):
        return self.keys.events.get()

    def check_touch(self):
        """Check the four touch inputs, return keypad-like Events"""
        events = []
        for i,touch in enumerate(self.touches):
            touch.update()
            if touch.rose:
                events.append(keypad.Event(i,True))
            elif touch.fell:
                events.append(keypad.Event(i,False))
        return events

    def read_pots(self):
        """Read the knobs, filter out their noise """
        filt = 0.5

        # avg_cnt = 5
        # knobA_vals = [self.knobA] * avg_cnt
        # knobB_vals = [self.knobB] * avg_cnt
        # for i in range(avg_cnt):
        #     knobA_vals[i] = self._knobA.value
        #     knobB_vals[i] = self._knobB.value

        # self.knobA = filt * self.knobA + (1-filt)*(sum(knobA_vals)/avg_cnt)  # filter noise
        # self.knobB = filt * self.knobB + (1-filt)*(sum(knobB_vals)/avg_cnt)  # filter noise

        self.knobA = filt * self.knobA + (1-filt)*(self._knobA.value)  # filter noise
        self.knobB = filt * self.knobB + (1-filt)*(self._knobB.value)  # filter noise
        return (int(self.knobA), int(self.knobB))
