
import time
import usb_midi
import displayio, terminalio, vectorio

from pico_test_synth.hardware import Hardware

from synth_tools.patch import Patch
from synth_tools.instrument import WavePolyTwoOsc
from synth_tools.param import ParamRange, ParamChoice
import synth_tools.winterbloom_smolmidi as smolmidi

from synthui import SynthUI

time.sleep(2)

touch_midi_notes = list(range(45, 45+16))  # notes touch keyboard sends FIXME

print("hardware...")
hw = Hardware()

# let's get the midi going
midi_usb_in = smolmidi.MidiIn(usb_midi.ports[0])
midi_uart_in = smolmidi.MidiIn(hw.midi_uart)

patch1 = Patch('oneuno')
patch2 = Patch('twotoo')

patch1.filt_env_params.attack_time = 0.1
patch1.amp_env_params.attack_time = 0.01
patch1.filt_f = 1234

patch2.filt_type = "HP"
patch2.wave = 'square'
patch2.detune = 1.01
patch2.filt_env_params.attack_time = 0.0  # turn off filter  FIXME
patch2.amp_env_params.release_time = 1.0

patch = patch1
inst = WavePolyTwoOsc(hw.synth, patch)

wave_selects = patch.generate_wave_selects()
filter_types = ("LP","BP","HP")

def update_wave_select(x):
    print("update_wave_select:",x)
    pass

    
params = (
    ParamRange("FiltFreq", "filter frequency", 1234, "%4d", 10, 8000,
               setter=lambda x: setattr(patch,"filt_f",x)),
    ParamChoice("FiltType", "filter type", 0, filter_types,
                setter=lambda x: setattr(patch,"filt_type",filter_types[x])),
    
    ParamRange("FilterRes", "filter resonance", 0.7, "%1.2f", 0.1, 2.5,
               setter=lambda x: setattr(patch,"filt_q",x)),
    
    ParamChoice("WaveSel", "wave select", 0, wave_selects,
                setter=lambda x: update_wave_select(x)),  # FIXME: requires reload patch
    
    ParamRange("WaveMix", "wave mix", 1.2, "%.2f", 0.0, 0.99,
               setter=lambda x: setattr(patch,"wmix",x)),
    ParamRange("WaveLFO", "wave lfo", 0.3, "%2.1f", 0.0, 10,
               setter=lambda x: setattr(patch,"wave_lfo",x)),
    
    ParamRange("AmpAtk", "attack time", 0.1, "%1.2f", 0.1, 3.0,
               setter=lambda x: setattr(patch.amp_env_params,"attack_time",x)),
    ParamRange("AmpRls", "release time", 0.3, "%1.2f", 0.3, 3.0,
               setter=lambda x: setattr(patch.amp_env_params,"release_time",x)),
    
    ParamRange("FiltAtk", "filter attack ", 0.1, "%1.2f", 0.1, 5.0,
               setter=lambda x: setattr(patch.filt_env_params,"attack_time",x)),
    ParamRange("FiltRls", "filter release", 0.3, "%1.2f", 0.0, 5.0),
)

# from collections import OrderedDict
# params_ordered = OrderedDict((
#     ("freq", ParamRange("freq", "filter frequency", 1234, "%4d", 100, 8000)),
#     ("wsel", ParamChoice("wsel", "wave select", 0, wave_selects)),
#     ("wmix", ParamRange("wmix", "wave mix", 1.2, "%.2f", 0.0, 0.99)),
#     ("wlfo", ParamRange("wlfo", "wave lfo", 0.3, "%2.1f", 0.0, 10)),
# ))


# params = [
#     ParamRange(param_group[0], 0,
#                getter=lambda: patch.filt_f,
#                setter=lambda x: setattr(patch,"filt_f",x),
#                minval=100, maxval=8000,
#                fmt="%4d"),
#     ParamRange(param_group[1], 0,
#                getter=lambda: getattr(patch, "filt_q"),
#                setter=lambda x: setattr(patch,"filt_q",x),
#                minval=0.1, maxval=2.5,
#                fmt="%1.1f"),
#     ParamRange(param_group[2], 0,
#                getter=lambda: patch.wave_mix,
#                setter=lambda x: setattr(patch,"wave_mix",x),
#                minval=0.0, maxval=1.0,
#                fmt="%1.1f"),
#     ParamRange(param_group[3], 0,
#                getter=lambda: patch.wave_mix_lfo_amount,
#                setter=lambda x: setattr(patch,"wave_mix_lfo_amount",x),
#                minval=0.0, maxval=1.0,
#                fmt="%1.1f")
# ]

def handle_midi():
    while msg := midi_usb_in.receive() or midi_uart_in.receive():
        if msg.type == smolmidi.NOTE_ON:
            inst.note_on(msg.data[0])
            hw.set_led(0xff00ff)
        elif msg.type == smolmidi.NOTE_OFF:
            inst.note_off(msg.data[0])
            hw.set_led(0x000000)
        elif msg.type == smolmidi.CC:
            ccnum = msg.data[0]
            ccval = msg.data[1]
            # hw.set_led(ccval)
            # if ccnum == 71:  # "sound controller 1"
            #     new_wave_mix = ccval/127
            #     print("wave_mix:", new_wave_mix)
            #     inst.patch.wave_mix = new_wave_mix
            # elif ccnum == 1:  # mod wheel
            #     inst.patch.wave_mix_lfo_amount = ccval/127 * 50
            #     # inst.patch.wave_mix_lfo_rate = msg.value/127 * 5
            # elif ccnum == 74:  # filter cutoff
            #     inst.patch.filt_f = ccval/127 * 8000

notes_pressed = [None] * len(hw.touches)
button_held = False
button_with_touch = False

def handle_touch():
    global button_held, button_with_touch
    if touches := hw.check_touch():
        for touch in touches:
            if touch.pressed:
                if button_held:  # load a patch
                    print("load patch", touch.key_number)
                    # disable this for now
                    #  inst.load_patch(patches[i])
                    #  hw.patch = patches[i]
                    #wavedisp.display_update()
                    #button_with_touch = True
                else:  # trigger a note
                    hw.set_led(0xff00ff)
                    midi_note = touch_midi_notes[touch.key_number]
                    midi_note += (inst.patch.octave*12)
                    notes_pressed[touch.key_number] = midi_note
                    inst.note_on(midi_note)

            if touch.released:
                if button_with_touch:
                    button_with_touch = False
                else:
                    hw.set_led(0)
                    midi_note = notes_pressed[touch.key_number]
                    inst.note_off(midi_note)


knobA, knobB = hw.read_pots()  # returns 0-255 values
synthui = SynthUI(hw.display, params, knobA//2, knobB//2)

last_time = 0
p = 0
while True:
    hw.display.refresh()
    
    inst.update()
    handle_midi()
    handle_touch()
    
    knobA, knobB = hw.read_pots()
    if button := hw.check_button():
        if button.pressed:
            p = (p+1) % (synthui.num_params//2)
            synthui.select_pair(p)
            print("select_pair:", p)
            
    synthui.setA( knobA // 2 )
    synthui.setB( knobB // 2 )
    #time.sleep(0.05)
    
    if time.monotonic() - last_time > 0.5:
        last_time = time.monotonic()
        print("patch:", inst.patch)







###########################################################################

# wavesynth_code.py -- wavesynth for pico_test_synth, ported from qtpy_synth
# 15 Feb 2024 - @todbot / Tod Kurt
# part of https://github.com/todbot/pico_test_synth
#
# To install:
#  - Copy files in 'pico_test_synth/circuitpython/wavesynth' dir to CIRCUITPY
#  - Copy files in 'pico_test-synth/circuitpython/lib' to CIRCUITPY/lib
#  - Install third-party libraries with circup
#  - See https://github.com/todbot/pico_test_synth/blob/main/circuitpython/README.md
#
#  UI:
#  - Display shows four lines of two parameters each
#  - The current editable parameter pair is underlined, adjustable by the knobs
#  - The knobs have "catchup" logic  (
#      (knob must pass through the displayed value before value can be changed)
#
#  - Key tap (press & release) == change what editable line (what knobs are editing)
#  - Key hold + touch press = load patch 1,2,3,4  (turned off currently)
#  - Touch press/release == play note / release note
#

import asyncio
import time
import usb_midi

from pico_test_synth.hardware import Hardware
from pico_test_synth.synthio_instrument import WavePolyTwoOsc, Patch, FiltType
import pico_test_synth.winterbloom_smolmidi as smolmidi

from wavesynth_display import WavesynthDisplay

import microcontroller
microcontroller.cpu.frequency = 250_000_000

time.sleep(2)  # let USB settle down

touch_midi_notes = list(range(45, 45+16))

patch1 = Patch('oneuno')
patch2 = Patch('twotoo')
patch3 = Patch('three')
patch4 = Patch('fourfor')
patches = (patch1, patch2, patch3, patch4)

patch1.filt_env_params.attack_time = 0.1
patch1.amp_env_params.attack_time = 0.01

patch2.filt_type = FiltType.HP
patch2.wave = 'square'
patch2.detune = 1.01
patch2.filt_env_params.attack_time = 0.0  # turn off filter  FIXME
patch2.amp_env_params.release_time = 1.0

patch3.waveformB = 'square'  # show off wavemixing
patch3.filt_type = FiltType.BP

patch4.wave_type = 'wtb'
patch4.wave = 'PLAITS02'  # 'MICROW02' 'BRAIDS04'
patch4.wave_mix_lfo_amount = 0.23
# patch4.detune = 0  # disable 2nd oscillator
patch4.amp_env_params.release_time = 0.5

print("--- pico_test_synth wavesynth starting up ---")

hw = Hardware()
inst = WavePolyTwoOsc(hw.synth, patch4)
wavedisp = WavesynthDisplay(hw.display, inst.patch)

# let's get the midi going
midi_usb_in = smolmidi.MidiIn(usb_midi.ports[0])
midi_uart_in = smolmidi.MidiIn(hw.midi_uart)


def map_range(s, a1, a2, b1, b2):
    return b1 + ((s - a1) * (b2 - b1) / (a2 - a1))


async def instrument_updater():
    while True:
        inst.update()
        await asyncio.sleep(0.01)  # as fast as possible


async def display_updater():
    while True:
        wavedisp.display_update()
        await asyncio.sleep(0.1)


async def midi_handler():
    while True:
        while msg := midi_usb_in.receive() or midi_uart_in.receive():
            if msg.type == smolmidi.NOTE_ON:
                inst.note_on(msg.data[0])
                hw.set_led(0xff00ff)
            elif msg.type == smolmidi.NOTE_OFF:
                inst.note_off(msg.data[0])
                hw.set_led(0x000000)
            elif msg.type == smolmidi.CC:
                ccnum = msg.data[0]
                ccval = msg.data[1]
                hw.set_led(ccval)
                if ccnum == 71:  # "sound controller 1"
                    new_wave_mix = ccval/127
                    print("wave_mix:", new_wave_mix)
                    inst.patch.wave_mix = new_wave_mix
                elif ccnum == 1:  # mod wheel
                    inst.patch.wave_mix_lfo_amount = ccval/127 * 50
                    # inst.patch.wave_mix_lfo_rate = msg.value/127 * 5
                elif ccnum == 74:  # filter cutoff
                    inst.patch.filt_f = ccval/127 * 8000

        await asyncio.sleep(0.001)


async def input_handler():

    # fixme: put these in hardware.py? no I think they are part of this "app"
    # also this 'knob_saves' business is kludgey and gross
    knob_mode = 0  # 0=frequency, 1=wavemix, 2=, 3=
    button_held = False
    button_with_touch = False
    max_lines = wavedisp.max_lines
    knob_saves = [(0, 0) for _ in range(max_lines)]  # list of knob state pairs
    param_saves = [(0, 0) for _ in range(max_lines)]  # list of param pairs for knobs
    knobA_pickup, knobB_pickup = False, False
    # index is touch keynumber, value is midi note
    notes_pressed = [None] * len(hw.touches)

    def reload_patch(wave_select):
        print("reload patch!", wave_select)
        # the below is the wrong way to do this, needlessly complex
        inst.patch.set_by_wave_select(wave_select)
        inst.reload_patch()
        param_saves[0] = wavedisp.wave_select_pos(), inst.patch.wave_mix
        param_saves[1] = inst.patch.detune, inst.patch.wave_mix_lfo_amount
        param_saves[2] = inst.patch.filt_type, inst.patch.filt_f
        param_saves[3] = inst.patch.filt_q, inst.patch.filt_env_params.attack_time
        param_saves[4] = inst.patch.octave, inst.patch.volume

    knobA, knobB = hw.read_pots()
    for i in range(max_lines):
        knob_saves[i] = knobA, knobB

    reload_patch(wavedisp.wave_selects[0])  # to set param_saves
    
    while True:
        # KNOB input
        (knobA_new, knobB_new) = hw.read_pots()

        # # simple knob pickup logic: if the real knob is close enough 
        if abs(knobA - knobA_new) < 5:  # knobs range 0-255
            knobA_pickup = True
        if abs(knobB - knobB_new) < 5:
            knobB_pickup = True

        knobA = knobA_new if knobA_pickup else knobA
        knobB = knobB_new if knobB_pickup else knobB

        # TOUCH input
        if touches := hw.check_touch():
            for touch in touches:

                if touch.pressed:
                    if button_held:  # load a patch
                        print("load patch", touch.key_number)
                        # disable this for now
                        #  inst.load_patch(patches[i])
                        #  hw.patch = patches[i]
                        wavedisp.display_update()
                        button_with_touch = True
                    else:  # trigger a note
                        hw.set_led(0xff00ff)
                        midi_note = touch_midi_notes[touch.key_number]
                        midi_note += (inst.patch.octave*12)
                        notes_pressed[touch.key_number] = midi_note
                        inst.note_on(midi_note)

                if touch.released:
                    if button_with_touch:
                        button_with_touch = False
                    else:
                        hw.set_led(0)
                        midi_note = notes_pressed[touch.key_number]
                        inst.note_off(midi_note)

        # BUTTON input
        if button := hw.check_button():
            if button.pressed:
                button_held = True
            if button.released:
                button_held = False
                if not button_with_touch:  
                    # turn off pickup mode since we change what knobs do
                    knobA_pickup, knobB_pickup = False, False
                    knob_saves[knob_mode] = knobA, knobB  # save knob positions
                    knob_mode = (knob_mode + 1) % 5  # FIXME: make max_knob_mode
                    knobA, knobB = knob_saves[knob_mode]  # retrieve saved pos
                    print("knob mode:",knob_mode, knobA, knobB)
                    wavedisp.selected_info = knob_mode  # FIXME

        # Handle parameter changes depending on knob mode
        # this is such a mess
        if knob_mode == 0:  # wave selection & wave_mix
            wave_select_pos, wave_mix = param_saves[knob_mode]

            if knobA_pickup: 
                wave_select_pos = map_range(knobA, 0, 255, 0, len(wavedisp.wave_selects)-1)
            if knobB_pickup:
                wave_mix = map_range(knobB, 0,  255, 0, 1)

            param_saves[knob_mode] = wave_select_pos, wave_mix
            wave_select = wavedisp.wave_selects[int(wave_select_pos)]
            if inst.patch.wave_select() != wave_select:
                reload_patch(wave_select)
            inst.patch.wave_mix = wave_mix

        elif knob_mode == 1:  # osc detune & wave_mix lfo
            detune, wave_lfo = param_saves[knob_mode]

            # 300-65300 because RP2040 has bad ADC
            if knobA_pickup:
                detune = map_range(knobA, 300, 65300, 1, 1.1)
            if knobB_pickup:
                wave_lfo = map_range(knobB, 0, 65535, 0, 1)

            param_saves[knob_mode] = detune, wave_lfo
            inst.patch.wave_mix_lfo_amount = wave_lfo
            inst.patch.detune = detune

        elif knob_mode == 2:  # filter type and filter freq
            filt_type, filt_f = param_saves[knob_mode]

            if knobA_pickup:
                filt_type = int(map_range(knobA, 0, 65535, 0, 3))
            if knobB_pickup:
                filt_f = map_range(knobB, 300, 65300, 100, 8000)

            param_saves[knob_mode] = filt_type, filt_f
            inst.patch.filt_type = filt_type
            inst.patch.filt_f = filt_f

        elif knob_mode == 3:
            filt_q, filt_env = param_saves[knob_mode]

            if knobA_pickup:
                filt_q = map_range(knobA, 0, 65535, 0.5, 2.5)
            if knobB_pickup:
                filt_env = map_range(knobB, 300, 65300, 1, 0.01)

            param_saves[knob_mode] = filt_q, filt_env
            inst.patch.filt_q = filt_q
            inst.patch.filt_env_params.attack_time = filt_env

        elif knob_mode == 4:
            octave, volume = param_saves[knob_mode]

            if knobA_pickup:
                octave = int(map_range(knobA, 0, 65535, -3, 3))
            if knobB_pickup:
                volume = map_range(knobB, 300, 65300, 0.1, 1)

            param_saves[knob_mode] = octave, volume
            inst.patch.octave = octave
            inst.patch.volume = volume
            hw.set_volume(volume)
        else:
            pass

        
        await asyncio.sleep(0.005)

    
        
print("--- pico_test_synth wavesynth ready ---")

async def main():
    task1 = asyncio.create_task(display_updater())
    task2 = asyncio.create_task(input_handler())
    task3 = asyncio.create_task(midi_handler())
    task4 = asyncio.create_task(instrument_updater())
    await asyncio.gather(task1, task2, task3, task4)

asyncio.run(main())
