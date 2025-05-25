import time, random
import ulab.numpy as np
import synthio
from synth_setup_pts import  knobA, knobB, keys, mixer, setup_display, setup_touch

from param import Param
from knob_tracker import KnobTracker

from tbish_synth import TBishSynth
from tbish_ui import TBishUI

bpm = 120
steps_per_beat = 4
glide_time = 0.25
midi_notes = [36, 36, 48+7, 36,  48, 48, 36, 48]
midi_vels = [127, 80, 127, 80,  127, 80, 127, 80]
new_midi_note = midi_notes[0]
i=0

# this list of params, arranged in pairs (because there are two knobs)
params = [
    Param("cutoff", 8000, 0, 9000, "%4d", 'filt_frequency'),
    Param('envmod', 0.5,  0.0, 1.0, "%.2f", 'filt_env_depth'), 
    
    Param('resonance', 1.8, 0.5, 3.0, "%2.1f", 'resonance'),
    Param('drive', 0.1, 0.0, 1.0, "%.2f", 'drive'),
    
    Param('wave', 0, 0, 1, "%1d", 'wavenum'),
    Param('drive', 0.1, 0.0, 1.0, "%.2f", 'drive'),    
    
    Param('root', 36, 12, 60, "%2d"),
    Param('bpm ', 120, 40, 200, "%3d"),
    
    Param('dely', 0.3, 0.0, 1.0, "%.2f"),
    Param('dtim', 0.25, 0.0, 1.0, "%.2f"),
]

tb = TBishSynth(mixer.sample_rate, mixer.channel_count)
tb_audio = tb.add_audioeffects() 
mixer.voice[0].play(tb_audio)

display = setup_display()

tb_disp = TBishUI(display, params)

kt = KnobTracker(num_knobs=2, num_params=8, knob_change_min=0.1*65535)

last_ui_time = time.monotonic()
def update_ui():
    global last_ui_time
    if time.monotonic() - last_ui_time > 0.1:
        last_ui_time = time.monotonic()

        kt.update((knobA.value, knobB.value))  # update knobtracker
        knobAval, knobBval = kt.values
        
        ki = kt.idx  #  get which knobset we're on
        params[ki*2+0].update(knobAval)
        params[ki*2+1].update(knobBval)
        
        params[ki*2+0].apply_to_obj(tb)
        params[ki*2+1].apply_to_obj(tb)
        
        tb_disp.update()
        
        #bpm = 40 + 200* (knobB.value/65535)

# these normally live in the sequencer
secs_per_step = 60 / bpm / steps_per_beat
next_step_time = time.monotonic()
gate_off_time = 0 

while True:
    update_ui()
    
    if key := keys.events.get():
        if key.pressed:
            # go to next param set on button press
            kt.next_knobset()
            tb_disp.set_param_pair(kt.idx)
            tb_disp.update()

    # rudimentary sequencer
    now = time.monotonic()
    if gate_off_time - now <=0:
        tb.note_off(new_midi_note)
        
    if next_step_time - now <= 0:
        next_step_time = now + secs_per_step
        
        #t = secs_per_step/2
        new_midi_note =  midi_notes[i] # + int(24*(knobA.value/65535)) - 12  # new note to glide to
        vel = midi_vels[i] + random.randint(-30,0)
        tb.secs_per_step = secs_per_step * 1.0
        tb.note_on(new_midi_note, vel)
        gate_off_time = time.monotonic() + secs_per_step/2
        i = (i+1) % len(midi_notes)
        print("new: %d old: %d glide_time: %.2f vel:%3d" %
              (new_midi_note, tb.glider.midi_note, tb.glider.glide_time, vel),
              tb.filt_env.offset, tb.filt_env.scale)
    



