# qtpy_synth_hwtest_code.py -- test hardware of qtpy_synth board
# 27 Jun 2023 - @todbot / Tod Kurt
#
# Functionality:
# - touch pads 1,2,3,4 trigger synth notes (defined in 'midi_notes')
# - middle button triggers random synth notes
# - left knob controls filter cutoff
# - right knob controls filter resonance
# - sending TRS UART MIDI will print out those bytes to the REPL
#
# Libaries needed:
# - asyncio
# - adafruit_debouncer
# - adafruit_displayio_ssd1306
# - adafruit_display_text
# Install them all with:
#   circup install asyncio adafruit_debouncer adafruit_displayio_ssd1306 adafruit_display_text
#
#
import asyncio
import time, random
import board, busio
import analogio, keypad
import audiopwmio, audiobusio, audiomixer, synthio
import ulab.numpy as np
import displayio, terminalio
import adafruit_displayio_ssd1306
from adafruit_display_text import bitmap_label as label
import touchio
from adafruit_debouncer import Debouncer

#midi_notes = (33, 45, 52, 57)
midi_notes = list(range(45,45+16))
filter_freq = 4000
filter_resonance = 1.2

# pin definitions
sw_pin        = board.GP28
knobB_pin     = board.GP27
knobA_pin     = board.GP26
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

# begin board setup
displayio.release_displays()

# set up our knobs and button
knobA = analogio.AnalogIn(knobA_pin)
knobB = analogio.AnalogIn(knobB_pin)
keys = keypad.Keys( pins=(sw_pin,),  value_when_pressed=False )

# set up touch pins using a debouncer
touchins = []
touchs = []
for pin in touch_pins:
    print("touch pin:", pin)
    touchin = touchio.TouchIn(pin)
    touchin.threshold = int(touchin.threshold * 1.05)
    touchins.append(touchin)
    touchs.append( Debouncer(touchin) )


uart = busio.UART(rx=uart_rx_pin, tx=uart_tx_pin, baudrate=31250, timeout=0.001)
i2c = busio.I2C(scl=i2c_scl_pin, sda=i2c_sda_pin, frequency=1_000_000 )

dw,dh = 128, 64
display_bus = displayio.I2CDisplay(i2c, device_address=0x3c )
display = adafruit_displayio_ssd1306.SSD1306(display_bus, width=dw, height=dh, rotation=180)

# set up the synth->audio system
audio = audiobusio.I2SOut(bit_clock=i2s_bclk_pin, word_select=i2s_lclk_pin, data=i2s_data_pin)
mixer = audiomixer.Mixer(voice_count=1, sample_rate=28000, channel_count=1,
                         bits_per_sample=16, samples_signed=True,
                         buffer_size=8192)  # buffer_size=4096)  # need a big buffer when screen updated
synth = synthio.Synthesizer(sample_rate=28000)
audio.play(mixer)
mixer.voice[0].level = 0.75 # turn down the volume a bit since this can get loud
mixer.voice[0].play(synth)

# set up the synth
wave_saw = np.linspace(30000,-30000, num=256, dtype=np.int16)  # default squ is too clippy
amp_env = synthio.Envelope(sustain_level=0.8, release_time=0.4, attack_time=0.001)
synth.envelope = amp_env

# set up info to be displayed
maingroup = displayio.Group()
display.show(maingroup)
text1 = label.Label(terminalio.FONT, text="helloworld...", x=0, y=10)
text2 = label.Label(terminalio.FONT, text="@todbot", x=0, y=25)
text3 = label.Label(terminalio.FONT, text="hwtest. press!", x=0, y=50)
for t in (text1, text2, text3):
    maingroup.append(t)

touch_notes = [None] * len(midi_notes)
sw_pressed = False

def check_touch():
    for i in range(len(touchs)):
        touch = touchs[i]
        touch.update()
        if touch.rose:
            print("touch press",i)
            f = synthio.midi_to_hz(midi_notes[i])
            filter = synth.low_pass_filter(filter_freq, filter_resonance)
            n = synthio.Note( frequency=f, waveform=wave_saw, filter=filter )
            synth.press( n )
            touch_notes[i] = n
        if touch.fell:
            print("touch release", i)
            synth.release( touch_notes[i] )

async def debug_printer():
    while True:
        text1.text = "K:%3d %3d S:%d" % (knobA.value//255, knobB.value//255, sw_pressed)
        text2.text = "T:" + ''.join(["%3d " % v for v in (touchins[0].raw_value//16, touchins[1].raw_value//16, touchins[2].raw_value//16, touchins[3].raw_value//16)])
        print(text1.text)
        print(text2.text)
        await asyncio.sleep(0.3)

async def input_handler():
    global sw_pressed
    global filter_freq, filter_resonance

    note = None

    while True:
        filter_freq = knobA.value/65535 * 8000 + 100  # range 100-8100
        filter_resonance = knobB.value/65535 * 3 + 0.2  # range 0.2-3.2

        for n in touch_notes:  # real-time adjustment of filter
            if n:
                n.filter = synth.low_pass_filter(filter_freq, filter_resonance)

        check_touch()

        if key := keys.events.get():
            if key.released:
                sw_pressed = False
                synth.release( note )
            if key.pressed:
                sw_pressed = True
                f = synthio.midi_to_hz(random.randint(32,60))
                note = synthio.Note(frequency=f, waveform=wave_saw) # , filter=filter)
                synth.press(note)
        await asyncio.sleep(0.005)

async def uart_handler():
    while True:
        while msg := uart.read(3):
            print("midi:", [hex(b) for b in msg])
        await asyncio.sleep(0)

# main coroutine
async def main():  # Don't forget the async!
    task1 = asyncio.create_task(debug_printer())
    task2 = asyncio.create_task(input_handler())
    task3 = asyncio.create_task(uart_handler())
    await asyncio.gather(task1,task2,task3)

print("hello pico_test_synth hwtest")
asyncio.run(main())
