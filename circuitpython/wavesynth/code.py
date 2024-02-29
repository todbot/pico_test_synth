import asyncio
import time
import usb_midi
import displayio, terminalio, vectorio

from pico_test_synth.hardware import Hardware

from synth_tools.patch import Patch
from synth_tools.instrument import WavePolyTwoOsc
from synth_tools.param import ParamRange, ParamChoice
import synth_tools.winterbloom_smolmidi as smolmidi

from synthui import SynthUI

import microcontroller
microcontroller.cpu.frequency = 250_000_000
time.sleep(2)

touch_midi_notes = list(range(45, 45+16))  # notes touch keyboard sends FIXME

print("hardware...")
hw = Hardware()

# let's get the midi going
midi_usb_in = smolmidi.MidiIn(usb_midi.ports[0])
midi_uart_in = smolmidi.MidiIn(hw.midi_uart)

# only using one patch for now, but let's pretend
patch1 = Patch('oneuno')
patch2 = Patch('twotoo')

patch1.amp_env_params.attack_time = 0.01
patch1.amp_env_params.release_time = 0.3
patch1.filt_env_params.attack_time = 1.1
patch1.filt_env_params.release_time = 0.8
patch1.filt_f = 2345
patch1.filt_q = 1.7
patch1.waveB = 'SQU'
patch1.wave_mix_lfo_amount = 0
patch1.detune = 1.01

patch2.filt_type = "HP"
patch2.wave = 'square'
patch2.detune = 1.01
patch2.filt_env_params.attack_time = 0.0  # turn off filter  FIXME
patch2.amp_env_params.release_time = 1.0

patch = patch1
inst = WavePolyTwoOsc(hw.synth, patch)

wave_selects = patch.generate_wave_selects()
filter_types = ("LP","BP","HP")

def update_wave_select(wave_select_idx):
    wave_select = wave_selects[wave_select_idx]
    #print("update_wave_select:",wave_select_idx, wave_select)
    inst.patch.set_by_wave_select(wave_select)
    inst.reload_patch()

# def update_octave(x):
#     global octave
#     octave = x
import math

params = (
    ParamRange("FiltFreq", "filter frequency", 1234, "%4d", 60, 8000,
               setter=lambda x: setattr(patch,"filt_f",x)),
    ParamRange("FilterRes", "filter resonance", 0.7, "%1.2f", 0.1, 2.5,
               setter=lambda x: setattr(patch,"filt_q",x)),
    
    ParamRange("WaveMix", "wave mix", 0.2, "%.2f", 0.0, 0.99,
               setter=lambda x: setattr(patch,"wave_mix",x)),
    ParamChoice("WaveSel", "wave select", 0, wave_selects,
                setter=lambda x: update_wave_select(x)),  # FIXME: requires reload patch
    
    ParamRange("WavLFO", "wave lfo amount", 0.3, "%2.1f", 0.0, 10,
               setter=lambda x: setattr(patch,"wave_mix_lfo_amount",x)),
    
    ParamRange("WavRate", "wave lfo rate", 0.3, "%2.1f", 0.0, 5,
               setter=lambda x: setattr(patch,"wave_mix_lfo_rate",x)),
    
    # ParamChoice("FiltType", "filter type", 0, filter_types,
    #             setter=lambda x: setattr(patch,"filt_type",filter_types[x])),
     
    ParamRange("AmpAtk", "attack time", 0.1, "%1.2f", 0.01, 3.0,
               setter=lambda x: setattr(patch.amp_env_params,"attack_time",x)),
    ParamRange("AmpRls", "release time", 0.3, "%1.2f", 0.1, 3.0,
               setter=lambda x: setattr(patch.amp_env_params,"release_time",x)),
    
    ParamRange("FiltAtk", "filter attack ", 1.1, "%1.2f", 0.01, 5.0,
               setter=lambda x: setattr(patch.filt_env_params,"attack_time",x)),
    ParamRange("FiltRls", "filter release", 0.8, "%1.2f", 0.1, 5.0,
               setter=lambda x: setattr(patch.filt_env_params,"release_time",x)),

    ParamRange("Octave", "octave range", 0, "%d", -3, 2,
               setter=lambda x: setattr(patch, "octave",int(x)) ),
    ParamRange("Volume", "volume", 1.0, "%1.2f", 0.1, 1.0,
               setter=lambda x: inst.set_volume(x)),
)

knobA, knobB = hw.read_pots()  # returns 0-255 values
synthui = SynthUI(hw.display, params, knobA, knobB)

async def instrument_updater():
    while True:
        inst.update()
        await asyncio.sleep(0.01)  # as fast as possible
        
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
        await asyncio.sleep(0.001)


async def ui_handler():
    notes_pressed = [None] * len(hw.touches)
    button_held = False
    button_with_touch = False
    p = 0
    
    while True:
        hw.display.refresh()
    
        knobA, knobB = hw.read_pots()
        synthui.setA( knobA )
        synthui.setB( knobB )
    
        if button := hw.check_button():
            if button.pressed:
                p = (p+1) % (synthui.num_params//2)
                synthui.select_pair(p)
                print("select_pair:", p)
                
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
                        midi_note = touch_midi_notes[touch.key_number]
                        midi_note += (inst.patch.octave*12)
                        notes_pressed[touch.key_number] = midi_note
                        inst.note_on(midi_note)
                        hw.set_led(0xff00ff)

                if touch.released:
                    if button_with_touch:
                        button_with_touch = False
                    else:
                        midi_note = notes_pressed[touch.key_number]
                        inst.note_off(midi_note)
                        hw.set_led(0)
        await asyncio.sleep(0.005)
    

print("--- pico_test_synth wavesynth ready ---")

async def main():
    task1 = asyncio.create_task(ui_handler())
    task2 = asyncio.create_task(midi_handler())
    task3 = asyncio.create_task(instrument_updater())
    await asyncio.gather(task1, task2, task3)
asyncio.run(main())

