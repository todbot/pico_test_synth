
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
patch1.filt_env_params.attack_time = 1.1
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
    print("update_wave_select:",wave_select_idx, wave_select)
    inst.patch.set_by_wave_select(wave_select)
    inst.reload_patch()

    
params = (
    ParamRange("FiltFreq", "filter frequency", 1234, "%4d", 10, 8000,
               setter=lambda x: setattr(patch,"filt_f",x)),
    ParamRange("FilterRes", "filter resonance", 0.7, "%1.2f", 0.1, 2.5,
               setter=lambda x: setattr(patch,"filt_q",x)),
    
    ParamRange("WaveMix", "wave mix", 0.2, "%.2f", 0.0, 0.99,
               setter=lambda x: setattr(patch,"wave_mix",x)),
    ParamChoice("WaveSel", "wave select", 0, wave_selects,
                setter=lambda x: update_wave_select(x)),  # FIXME: requires reload patch
    
    ParamRange("WaveLFO", "wave lfo", 0.3, "%2.1f", 0.0, 10,
               setter=lambda x: setattr(patch,"wave_lfo",x)),
    ParamChoice("FiltType", "filter type", 0, filter_types,
                setter=lambda x: setattr(patch,"filt_type",filter_types[x])),
    
    
    ParamRange("AmpAtk", "attack time", 0.1, "%1.2f", 0.1, 3.0,
               setter=lambda x: setattr(patch.amp_env_params,"attack_time",x)),
    ParamRange("AmpRls", "release time", 0.3, "%1.2f", 0.3, 3.0,
               setter=lambda x: setattr(patch.amp_env_params,"release_time",x)),
    
    ParamRange("FiltAtk", "filter attack ", 2.0, "%1.2f", 0.1, 5.0,
               setter=lambda x: setattr(patch.filt_env_params,"attack_time",x)),
    ParamRange("FiltRls", "filter release", 0.3, "%1.2f", 0.0, 5.0,
               setter=lambda x: setattr(patch.filt_env_params,"release_time",x)),
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


knobA, knobB = hw.read_pots()  # returns 0-255 values
synthui = SynthUI(hw.display, params, knobA//2, knobB//2)

last_time = 0
p = 0
while True:
    hw.display.refresh()
    
    inst.update()
    
    handle_midi()
    handle_touch()
    
    if button := hw.check_button():
        if button.pressed:
            p = (p+1) % (synthui.num_params//2)
            synthui.select_pair(p)
            print("select_pair:", p)
            
    knobA, knobB = hw.read_pots()
    synthui.setA( knobA // 2 )
    synthui.setB( knobB // 2 )
    
    if time.monotonic() - last_time > 0.5:
       last_time = time.monotonic()
       print("patch:", inst.patch)


