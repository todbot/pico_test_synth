# synth1 for pico_test_synth2/pico_test_synth
# 2023-2025 - @todbot / Tod Kurt
#
# synth1 is a simple demo synth showing off some CircuitPython synthio features.
#
# synth1 controls:
# - Left (A) knob controls filter cutoff
# - Right (B) knob controls filter attack envelope time
# - Tact button selects filter type: low-pass, high-pass, or band-pass
# - If button is held, knobA controls octave, knobB controls detune
# - Touch pads trigger notes
# - Send MIDI in to trigger notes
#
# To install, copy this 'code.py' and 'pico_test_synth.py' to CIRCUITPY
# and install needed third-party libraries with:
#  - circup install adafruit_display_text adafruit_displayio_ssd1306 tmidi
#

import asyncio
import time
import ulab.numpy as np
import synthio
import displayio, terminalio
from adafruit_display_text import bitmap_label as label
import tmidi

from pico_test_synth_hardware import PicoTestSynthHardware

hw = PicoTestSynthHardware()  # for pico_test_synth2
#hw = PicoTestSynthHardware(pull_type=digitalio.pull.DOWN)  # for pico_test_synth1

touch_notes = range(0,16)
octave = 3
filter_freq = 8000      # adjusted with knobA
filter_resonance = 2.0
detune = 1.008
filter_min_freq = 50
filter_env_time = 1.75

# set up the synth
# oscillator waveforms
wave_saw = np.linspace(30000,-30000, num=256, dtype=np.int16)  # default squ is too clippy
# LFO/envelope waveforms
lfo_saw_wave = np.array((0,32767), dtype=np.int16)
lfo_exp_wave = np.array(32767 * np.linspace(0, 1, num=64, endpoint=True)**2.8, dtype=np.int16)
# amplitude envelope
amp_env = synthio.Envelope(attack_level=0.5, sustain_level=0.5, release_time=0.4, attack_time=0.001)
hw.synth.envelope = amp_env

# set up midi ports
midi_uart = tmidi.MIDI(midi_in=hw.midi_uart, midi_out=hw.midi_uart)

# set up info to be displayed
maingroup = displayio.Group()
hw.display.root_group = maingroup
dy = 12
texts = [None] * 5
texts[0] = label.Label(terminalio.FONT, text="frq:1234 LPF 0.9:fatk", x=0, y=dy*1)
texts[1] = label.Label(terminalio.FONT, text="oct:2      0.000:detu", x=0, y=dy*2)
texts[2] = label.Label(terminalio.FONT, text="                     ", x=0, y=dy*3)
texts[3] = label.Label(terminalio.FONT, text="pico_test_synth      ", x=0, y=dy*4)
texts[4] = label.Label(terminalio.FONT, text="@todbot              ", x=0, y=dy*5-2)
#                                             012345678901234567890
for t in texts:
    maingroup.append(t)
time.sleep(1)
texts[4].text = "synth1"


filter_types = [('LPF', synthio.FilterMode.LOW_PASS),
                ('BPF', synthio.FilterMode.BAND_PASS),
                ('HPF', synthio.FilterMode.HIGH_PASS),]
filter_type_idx = 0
filter_type = filter_types[filter_type_idx][1]

notes_playing = {}  # dict of notes currently playing, value is ((note,note),env)

        
def note_on(notenum, vel=64):
    print("note_on", notenum, vel, time.monotonic())
    filter_env = synthio.LFO(once=True, rate=1/filter_env_time,
                             offset=filter_min_freq, scale=filter_freq,
                             waveform=lfo_exp_wave)
    f = synthio.midi_to_hz(notenum)
    filt = synthio.Biquad(filter_type, frequency=filter_env, Q=filter_resonance)
    notes = (synthio.Note(frequency=f, waveform=wave_saw, filter=filt),
             synthio.Note(frequency=f * detune, waveform=wave_saw, filter=filt))
    notes_playing[notenum] = notes #, filter_env)  # note info
    hw.synth.press(notes)
    filter_env.retrigger()
    hw.led.value = True

def note_off(notenum, vel=0):
    print("note_off", notenum, vel)
    if notes := notes_playing[notenum]:
        hw.synth.release(notes)  # releases all notes
    hw.led.value = False

#
# async tasks
#

async def input_handler():
    global filter_freq, filter_type_idx, filter_type, filter_env_time, octave, detune

    button_held = False
    knobA_last, knobB_last = hw.read_pots()
    
    while True:
        # read keyboard
        if touches := hw.check_touch():
            for touch in touches:
                if touch.pressed:
                    note_on( 12 + octave*12 + touch_notes[touch.key_number])
                if touch.released:
                    note_off(12 + octave*12 + touch_notes[touch.key_number])

        # read knobs
        knobA_val, knobB_val = hw.read_pots()
        knob_moved = abs(knobA_val - knobA_last) > 1000 or abs(knobB_val - knobB_last) > 1000
        
        if not button_held:
            filter_freq = knobA_val/65535 * 8000 + 10  # range 10-8010
            filter_env_time = knobB_val/65535 * 3 + 0.01  # range 0.1 to 3.01
        else:
            # only update if knob turned during button hold
            if knob_moved:
                octave = int(knobA_val/65535 * 5)
                detune = 1 + (knobB_val/65535) * 0.5

        # read tact button
        if button := hw.check_key():
            if button.pressed:
                print("BUTTON PRESS")
                button_held = True
                knobA_last, knobB_last = knobA_val, knobB_val
                
            if button.released:
                print("BUTTON RELEASE")
                button_held = False
                if not knob_moved:
                    filter_type_idx = (filter_type_idx+1) % len(filter_types)
                    filter_type = filter_types[filter_type_idx][1]

        await asyncio.sleep(0.005)

async def synth_updater():
    # for any notes playing, adjust its filter in realtime according to knobs
    while True:
        filt = None
        for notes in notes_playing.values():
            for n in notes:
                n.filter.frequency.scale = filter_freq
        await asyncio.sleep(0.01)

async def midi_handler():
    while True:
        while msg := midi_uart.receive():
            if msg.type == tmidi.NOTE_ON and msg.velocity > 0:
                note_on(msg.note, msg.velocity)
            if msg.type == tmidi.NOTE_OFF or msg.type == tmidi.NOTE_ON and msg.velocity ==0:
                note_off(msg.note, msg.velocity)
        await asyncio.sleep(0.001)

async def screen_updater():
    while True:
        new_text0 = "frq:%4d %3s %.1f:fatk" % (filter_freq,
                                              filter_types[filter_type_idx][0],
                                              filter_env_time) 
        new_text1 = "oct:%1d      %.3f:detu" % (octave, detune-1)
        if texts[0].text != new_text0:
            texts[0].text = new_text0
        texts[1].text = new_text1
        print(new_text0)
        await asyncio.sleep(0.1)

# main coroutine
async def main():  # Don't forget the async!
    await asyncio.gather(
        asyncio.create_task(screen_updater()),
        asyncio.create_task(input_handler()),
        asyncio.create_task(midi_handler()),
        asyncio.create_task(synth_updater()),
    )

print("hello pico_test_synth synth1")
asyncio.run(main())
