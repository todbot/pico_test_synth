# synth1 for pico_test_synth2/pico_test_synth
# 2023 - @todbot / Tod Kurt
#
# To install, copy this 'code.py' and 'pico_test_synth.py' to CIRCUITPY
# and install needed third-party libraries with:
#  - circup install adafruit_display_text adafruit_displayio_ssd1306
#
#

import asyncio
import time
import ulab.numpy as np
import synthio
import displayio, terminalio
from adafruit_display_text import bitmap_label as label

from pico_test_synth import PicoTestSynthHardware

pts = PicoTestSynthHardware()  # this is for pico_test_synth2
#pts = PicoTestSynthHardware(pull_type=digitalio.pull.DOWN)  # pico_test_synth1

touch_midi_notes = list(range(48,48+16))
filter_freq = 4000
filter_resonance = 1.2
detune = 1.008

# set up the synth
wave_saw = np.linspace(30000,-30000, num=256, dtype=np.int16)  # default squ is too clippy
amp_env = synthio.Envelope(sustain_level=0.8, release_time=0.4, attack_time=0.001)
pts.synth.envelope = amp_env

# set up info to be displayed
maingroup = displayio.Group()
pts.display.root_group = maingroup
text1 = label.Label(terminalio.FONT, text="pico_test_synth...", x=0, y=10)
text2 = label.Label(terminalio.FONT, text="@todbot", x=0, y=25)
text3 = label.Label(terminalio.FONT, text="synth1. press!", x=0, y=50)
for t in (text1, text2, text3):
    maingroup.append(t)
time.sleep(1)
text2.text = "pico_test_synth"

notes_playing = {}  # dict of notes currently playing


filter_types = [('lpf', synthio.FilterMode.LOW_PASS),
                ('hpf', synthio.FilterMode.HIGH_PASS),
                ('bpf', synthio.FilterMode.BAND_PASS),]
filter_type_idx = 0
filter_type = filter_types[filter_type_idx][1]

def note_on( notenum, vel=64):
    print("note_on", notenum, vel)
    #cfg.filter_mod = (vel/127) * 1500
    f = synthio.midi_to_hz(notenum)
    filt = synthio.Biquad(filter_type, filter_freq, filter_resonance)
    notes = (
        synthio.Note( frequency=f, waveform=wave_saw, filter=filt),
        synthio.Note( frequency=f * detune, waveform=wave_saw, filter=filt))
    notes_playing[notenum] = notes
    pts.synth.press(notes)
    pts.led.value = True

def note_off( notenum, vel=0):
    print("note_off", notenum, vel)
    if notes := notes_playing[notenum]:
        pts.synth.release(notes)
    pts.led.value = False


async def input_handler():
    global filter_freq, filter_resonance, filter_type_idx, filter_type

    while True:
        knobA_val, knobB_val = pts.read_pots()
        filter_freq = knobA_val/65535 * 8000 + 10  # range 10-8010
        filter_resonance = knobB_val/65535 * 3.5 + 0.2  # range 0.2-3.2

        if touches := pts.check_touch():
            for touch in touches:
                if touch.pressed:
                    note_on( touch_midi_notes[touch.key_number] )
                if touch.released:
                    note_off( touch_midi_notes[touch.key_number] )

        if key := pts.check_key():
            if key.pressed:
                print("BUTTON PRESS")
                filter_type_idx = (filter_type_idx+1) % len(filter_types)
                filter_type = filter_types[filter_type_idx][1]

        await asyncio.sleep(0.005)

async def synth_updater():
    # for any notes playing, adjust its filter in realtime
    while True:
        filt = None
        for notes in notes_playing.values():
            for n in notes:
                if n:
                    if filt is None:
                        filt = synthio.Biquad(filter_type, filter_freq, filter_resonance)
                    n.filter = filt
        await asyncio.sleep(0.01)

async def uart_handler():
    while True:
        while msg := pts.midi_uart.read(3):
            print("midi:", [hex(b) for b in msg])
        await asyncio.sleep(0)

async def debug_printer():
    while True:
        text1.text = "K1:%3d  %s   %3d:K2" % (pts.knobA//255,
                                              filter_types[filter_type_idx][0],
                                              pts.knobB//255)
        print(text1.text)
        await asyncio.sleep(0.2)

# main coroutine
async def main():  # Don't forget the async!
    task1 = asyncio.create_task(debug_printer())
    task2 = asyncio.create_task(input_handler())
    task3 = asyncio.create_task(uart_handler())
    task4 = asyncio.create_task(synth_updater())
    await asyncio.gather(task1,task2,task3,task4)

print("hello pico_test_synth synth1")
asyncio.run(main())
