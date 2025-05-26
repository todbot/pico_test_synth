# SPDX-FileCopyrightText: Copyright (c) 2023 Tod Kurt
# SPDX-License-Identifier: MIT
"""
`code.py`
================================================================================

This is the main code.py for a TB-like synth

14 May 2025 - @todbot / Tod Kurt

"""

import time, random
import ulab.numpy as np
import synthio
from synth_setup_pts import (mixer, knobA, knobB, keys,
                             setup_display, setup_touch, check_touch)

from param_set import ParamSet, Param

from tbish_synth import TBishSynth
from tbish_ui import TBishUI

display = setup_display()
touches = setup_touch()

playing = True
bpm = 120
steps_per_beat = 4
secs_per_step = 60 / bpm / steps_per_beat
glide_time = 0.25
midi_notes = [36, 36, 48+7, 36,  48, 0, 36, 48]
midi_vels = [127, 80, 127, 80,  127, 80, 127, 80]
midi_note = midi_notes[0]
next_midi_note = 0
gate_off_time = 0
gate_amount = 0.5
transpose = 0
i=0

params = [
    Param("cutoff", 8000, 0, 9000, "%4d", 'cutoff'),
    Param('envmod', 0.5,  0.0, 1.0, "%.2f",'envmod'), 
    
    Param("resQ",  1.0, 0.5, 3.5, "%.2f", 'resonance'),
    Param('decay', 0.9,  0.0, 1.0, "%.2f", 'decay'),
    
    Param('drive', 20, 5, 30, "%2d", 'drive'),
    Param('drivemix', 0.2, 0.0, 1.0, "%.2f", 'drive_mix'),
        
    Param('dely', 0.3, 0.0, 1.0, "%.2f"),
    Param('dtim', 0.25, 0.0, 1.0, "%.2f"),
]

touchpad_to_knobset = [1,3,6,8] #,10]
touchpad_to_transpose = [0,2,4,5,7,9,11,12,14]
    
tb = TBishSynth(mixer.sample_rate, mixer.channel_count)
tb_audio = tb.add_audioeffects()
mixer.voice[0].play(tb_audio)

param_set = ParamSet(params, num_knobs=2)
param_set.apply_params(tb)  # set up synth with param set

tb_disp = TBishUI(display, params)

print("="*80)
print("tbish synth! press button to start")
print("="*80)
print("secs_per_step:%.3f" % secs_per_step)

last_ui_time = time.monotonic()
def update_ui():
    global last_ui_time
    ki = tb_disp.curr_param_pair  # shorthand
    if time.monotonic() - last_ui_time > 0.1:
        last_ui_time = time.monotonic()

        param_set.update_knobs((knobA.value/65535, knobB.value/65535))

        param_set.apply_knobset(tb)  # set synth with params
        
        tb_disp.update_param_pairs()

next_step_time = time.monotonic()

while True:
    
    if key := keys.events.get():
        if key.pressed:
            playing = not playing
            if playing:
                next_step_time = time.monotonic()
            else:
                tb.note_off(midi_note)

    if touch_events := check_touch():
        for touch in touch_events:
            if touch.pressed:
                print("touchpad", touch.key_number)
                if touch.key_number in touchpad_to_knobset:
                    tb_disp.curr_param_pair = touchpad_to_knobset.index(touch.key_number)
                    param_set.idx = tb_disp.curr_param_pair
                if touch.key_number in touchpad_to_transpose:
                    transpose = touch.key_number   # chromatic
                    
    update_ui()

    if not playing:
        continue
    
    now = time.monotonic()
    if gate_off_time and gate_off_time - now <= 0:
        gate_off_time = 0
        if next_midi_note != 0:
            tb.note_off(midi_note)

    dt = (next_step_time - now)
    if dt <= 0:
        next_step_time = now + secs_per_step + dt  
        # add dt delta to attempt to make up for display hosing us
        
        #t = secs_per_step/2
        midi_note =  midi_notes[i]
        if midi_note != 0:   # 0 means slide
            midi_note += transpose
            vel = midi_vels[i] + random.randint(-30,0)
            tb.secs_per_step = secs_per_step * 1.0
            tb.note_on(midi_note, vel)
            gate_off_time = time.monotonic() + secs_per_step * gate_amount
        i = (i+1) % len(midi_notes)
        next_midi_note = midi_notes[i]
        #print("new: %d old: %d glide_time: %.2f vel:%3d" %
        #      (midi_note, tb.glider.midi_note, tb.glider.glide_time, vel),
        #      tb.filt_env.offset, tb.filt_env.scale)



