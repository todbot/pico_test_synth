# pico_test_synth.hardware.py -- hardware defines and setup for pico_test_synth board
# 22 Jul 2023 - @todbot / Tod Kurt
# part of https://github.com/todbot/pico_test_synth
#
# libraries needed:
#  circup install adafruit_debouncer, adafruit_displayio_ssd1306
#
# UI fixme:
# knob "pickup" vs knob "catchup"  (maybe done in app instead)

import board, digitalio, pwmio, busio
import analogio, keypad
import touchio
from adafruit_debouncer import Debouncer
import audiobusio, audiomixer
import synthio
import displayio
import adafruit_displayio_ssd1306


SAMPLE_RATE = 25600   # lets try powers of two
MIXER_BUFFER_SIZE = 4096
CHANNEL_COUNT = 1
DW,DH = 128, 64  # display width/height

# pin definitions
sw_pin        = board.GP28
knobB_pin     = board.GP27
knobA_pin     = board.GP26
led_pin       = board.GP25  # regular LED, not neopixel
pico_pwr_pin  = board.GP23  # HIGH = improved ripple (lower noise) but less efficient
i2s_data_pin  = board.GP22
i2s_lclk_pin  = board.GP21
i2s_bclk_pin  = board.GP20
i2c_scl_pin   = board.GP19
i2c_sda_pin   = board.GP18
uart_rx_pin   = board.GP17
uart_tx_pin   = board.GP16
touch_pins = (board.GP0, board.GP1, board.GP2, board.GP3,
              board.GP4, board.GP5, board.GP6, board.GP7,
              board.GP8, board.GP9, board.GP10, board.GP11,
              board.GP12, board.GP13, board.GP14, board.GP15)

class Hardware():
    def __init__(self, sample_rate=SAMPLE_RATE, buffer_size=MIXER_BUFFER_SIZE):

        self.led = pwmio.PWMOut(led_pin)
        self.buttons = keypad.Keys( pins=(sw_pin,), value_when_pressed=False)
        self._knobA = analogio.AnalogIn(knobA_pin)
        self._knobB = analogio.AnalogIn(knobB_pin)
        self.knobA = self._knobA.value
        self.knobB = self._knobB.value

        self.touchins = []  # for raw_value
        self.touches = []   # for debouncer
        for pin in touch_pins:
            touchin = touchio.TouchIn(pin)
            touchin.threshold = int(touchin.threshold * 1.1)  # noise protec
            self.touchins.append(touchin)
            self.touches.append(Debouncer(touchin))

        # make power supply less noisy on real Picos
        self.pwr_mode = digitalio.DigitalInOut(pico_pwr_pin)
        self.pwr_mode.switch_to_output(value=True)

        self.midi_uart = busio.UART(rx=uart_rx_pin, tx=uart_tx_pin,
                                    baudrate=31250, timeout=0.001)

        displayio.release_displays()
        i2c = busio.I2C(scl=i2c_scl_pin, sda=i2c_sda_pin, frequency=1_000_000)
        display_bus = displayio.I2CDisplay(i2c, device_address=0x3c)
        self.display = adafruit_displayio_ssd1306.SSD1306(display_bus,
                                                          width=DW, height=DH,
                                                          rotation=180)

        # now do audio setup so we have minimal audible glitches
        self.audio = audiobusio.I2SOut(bit_clock=i2s_bclk_pin,
                                       word_select=i2s_lclk_pin,
                                       data=i2s_data_pin)
        self.mixer = audiomixer.Mixer(sample_rate=sample_rate, voice_count=1,
                                      channel_count=CHANNEL_COUNT,
                                      bits_per_sample=16, samples_signed=True,
                                      buffer_size=buffer_size)
        self.synth = synthio.Synthesizer(sample_rate=sample_rate,
                                         channel_count=CHANNEL_COUNT)
        self.audio.play(self.mixer)
        self.mixer.voice[0].play(self.synth)

    def set_volume(self,v):
        self.mixer.voice[0].level = v

    def check_button(self):
        return self.buttons.events.get()

    def set_led(self,v):
        self.led.duty_cycle = (v & 255) * 255  # only use B of RGB, if RGB

    def read_pots(self):
        """
        Read the knobs, filter out their noise,
        # Return pair of 0-255 values
        """
        valA, valB =  self._knobA.value, self._knobB.value
        self.knobA = valA if abs(valA-self.knobA) > 3 else self.knobA
        self.knobB = valB if abs(valB-self.knobB) > 3 else self.knobB
        return self.knobA//255, self.knobB//255
        #knobB = knobBnew if abs(knobBnew-knobB) > 3 else knobB
        
        #filt = 0.5  # filter amount, higher to filter more, more lag
        #self.knobA = filt * self.knobA + (1-filt)*(self._knobA.value)  # filter noise
        #self.knobB = filt * self.knobB + (1-filt)*(self._knobB.value)  # filter noise
        #return (self.knobA//255, self.knobB/255)  # admit knobs are only 8-bit

    def check_touch(self):
        """Check the four touch inputs, return keypad-like Events"""
        events = []
        for i, touch in enumerate(self.touches):
            touch.update()
            if touch.rose:
                events.append(keypad.Event(i,True))
            elif touch.fell:
                events.append(keypad.Event(i,False))
        return events

    def check_touch_hold(self, hold_func):
        for i in 0,1,2,3:
            if self.touches[i].value:  # pressed
                v = self.touchins[i].raw_value - self.touchins[i].threshold
                hold_func(i, v)
