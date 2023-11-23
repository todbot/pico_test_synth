#
#
#
#

import asyncio
import time, random
import ulab.numpy as np
import synthio
import displayio, terminalio
from adafruit_display_text import bitmap_label as label

from pico_test_synth import PicoTestSynthHardware

pts = PicoTestSynthHardware()

touch_midi_notes = list(range(45,45+16))
filter_freq = 4000
filter_resonance = 1.2

# set up the synth
wave_saw = np.linspace(30000,-30000, num=256, dtype=np.int16)  # default squ is too clippy
amp_env = synthio.Envelope(sustain_level=0.8, release_time=0.4, attack_time=0.001)
pts.synth.envelope = amp_env

# set up info to be displayed
maingroup = displayio.Group()
pts.display.show(maingroup)
text1 = label.Label(terminalio.FONT, text="helloworld...", x=0, y=10)
text2 = label.Label(terminalio.FONT, text="@todbot", x=0, y=25)
text3 = label.Label(terminalio.FONT, text="hwtest. press!", x=0, y=50)
for t in (text1, text2, text3):
    maingroup.append(t)


notes_playing = {}  # dict of notes currently playing

# filter_types = ['lpf', 'hpf', 'bpf']
# def make_filter():
#     freq = cfg.filter_f + cfg.filter_mod
#     if cfg.filter_type == 'lpf':
#         filter = qts.synth.low_pass_filter(freq, cfg.filter_q)
#     elif cfg.filter_type == 'hpf':
#         filter = qts.synth.high_pass_filter(freq, cfg.filter_q)
#     elif cfg.filter_type == 'bpf':
#         filter = qts.synth.band_pass_filter(freq, cfg.filter_q)
#     else:
#         print("unknown filter type", cfg.filter_type)
#     return filter

def note_on( notenum, vel=64):
    print("note_on", notenum, vel)
    #cfg.filter_mod = (vel/127) * 1500
    f = synthio.midi_to_hz(notenum)
    filt = pts.synth.low_pass_filter(filter_freq, filter_resonance)
    note = synthio.Note( frequency=f, waveform=wave_saw, filter=filt)
    notes_playing[notenum] = note
    pts.synth.press( note )
    pts.led.value = True

def note_off( notenum, vel=0):
    print("note_off", notenum, vel)
    if note := notes_playing[notenum]:
        pts.synth.release( note )
    pts.led.value = False


async def input_handler():
    global sw_pressed
    global filter_freq, filter_resonance

    note = None

    while True:
        knobA_val, knobB_val = pts.read_pots()
        filter_freq = knobA_val/65535 * 8000 + 100  # range 100-8100
        filter_resonance = knobB_val/65535 * 3 + 0.2  # range 0.2-3.2

        # for n in touch_notes:  # real-time adjustment of filter
        #     if n:
        #         n.filter = pts.synth.low_pass_filter(filter_freq, filter_resonance)

        if touches := pts.check_touch():
            for touch in touches:
                if touch.pressed: note_on( touch_midi_notes[touch.key_number] )
                if touch.released: note_off( touch_midi_notes[touch.key_number] )

        if key := pts.check_key():
            if key.pressed:
                print("KEY PRESS")
                #ftpos = (filter_types.index(cfg.filter_type)+1) % len(filter_types)
                #cfg.filter_type = filter_types[ ftpos ]

        await asyncio.sleep(0.005)

async def synth_updater():
    # for any notes playing, adjust its filter in realtime
    while True:
        filt = None
        for n in notes_playing.values():
            if n:
                if filt is None:
                    filt = pts.synth.low_pass_filter(filter_freq, filter_resonance)
                n.filter = filt
        await asyncio.sleep(0.01)

async def uart_handler():
    while True:
        while msg := pts.midi_uart.read(3):
            print("midi:", [hex(b) for b in msg])
        await asyncio.sleep(0)

async def debug_printer():
    while True:
        #text1.text = "K:%3d %3d S:%d" % (pts.knobA//255, pts.knobB//255, sw_pressed)
        text1.text = "K:%3d %3d S:%d" % (pts.knobA//255, pts.knobB//255, False)
        text2.text = "T:" + ''.join(["%3d " % v for v in (pts.touchins[0].raw_value//16, pts.touchins[1].raw_value//16, pts.touchins[2].raw_value//16, pts.touchins[3].raw_value//16)])
        print(text1.text)
        print(text2.text)
        await asyncio.sleep(0.3)

# main coroutine
async def main():  # Don't forget the async!
    task1 = asyncio.create_task(debug_printer())
    task2 = asyncio.create_task(input_handler())
    task3 = asyncio.create_task(uart_handler())
    task4 = asyncio.create_task(synth_updater())
    await asyncio.gather(task1,task2,task3,task4)

print("hello pico_test_synth hwtest")
asyncio.run(main())
