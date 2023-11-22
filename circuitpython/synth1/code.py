#
#
#
#

import asyncio
import time, random
import ulab.numpy as np
import synthio
import displayio, terminalio

from pico_test_synth import PicoTestSynthHardware

pts = PicoTestSynthHardware()

midi_notes = list(range(45,45+16))
filter_freq = 4000
filter_resonance = 1.2

# set up the synth
wave_saw = np.linspace(30000,-30000, num=256, dtype=np.int16)  # default squ is too clippy
amp_env = synthio.Envelope(sustain_level=0.8, release_time=0.4, attack_time=0.001)
synth.envelope = amp_env

# set up info to be displayed
maingroup = displayio.Group()
pts.display.show(maingroup)
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
            pts.synth.press( n )
            touch_notes[i] = n
        if touch.fell:
            print("touch release", i)
            pts.synth.release( touch_notes[i] )

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
