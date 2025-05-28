# SPDX-FileCopyrightText: Copyright (c) 2023 Tod Kurt
# SPDX-License-Identifier: MIT
"""
`code.py`
================================================================================

This is the main code.py for a TB-like synth

14 May 2025 - @todbot / Tod Kurt

"""
# this reduces some of per-step latency from 10ms down to 6ms
import microcontroller
microcontroller.cpu.frequency = 200_000_000

import time, random
import ulab.numpy as np
import synthio
from synth_setup_pts import (mixer, knobA, knobB, keys,
                             setup_display, setup_touch, check_touch)

from param_set import ParamSet, Param

from tbish_synth import TBishSynth
from tbish_sequencer import TBishSequencer
from tbish_ui import TBishUI

display = setup_display()
touches = setup_touch()

seqs = [
    [[36, 36, 48, 36,  48, 48+7, 36, 48],  # notes, 0 = rest
     [127, 80, 80, 80,  127, 1, 30, 1]],   # vels, 1=slide, 127=accent
    
    [[34, 36, 34, 36,  48, 48, 36, 48],    # notes, 0 = rest
     [127, 80, 120, 80,  127, 11, 127, 80]],  # vels 127=accent
    
    [[36, 36-12, 36, 36+12,  36, 0, 36, 0],    # notes, 0 = rest
     [127,  1,   1, 80,  127, 80, 127, 80]],  # vels 127=accent  
]
# future path
seqs_steps = [
    [[ ],  # notes,
     [ ],  # slide,
     [ ],],  # accent,
]    

params = [
    Param("cutoff", 4000, 200, 6000, "%4d", 'cutoff'),
    Param('envmod', 0.5,  0.0, 1.0, "%.2f",'envmod'), 
    
    Param("resQ",  1.0, 0.5, 4.0, "%.2f", 'resonance'),
    Param('decay', 0.5,  0.0, 1.0, "%.2f", 'decay'),
    
    Param('drive', 20, 5, 40, "%2d", 'drive'),
    Param('drivemix', 0.2, 0.0, 1.0, "%.2f", 'drive_mix'),
        
    Param('delay', 0.3, 0.0, 1.0, "%.2f"),
    Param('dtime', 0.25, 0.0, 1.0, "%.2f"),

    Param('seq', 0, 0, len(seqs), "%1d"),
    Param('bpm', 120, 40, 200, "%3d"),
]

touchpad_to_knobset = [1,3,6,8,10] # ,13]
touchpad_to_transpose = [0,2,4,5,7,9,11,12,14]
    
tb = TBishSynth(mixer.sample_rate, mixer.channel_count)
tb_audio = tb.add_audioeffects()
mixer.voice[0].play(tb_audio)

sequencer = TBishSequencer(tb, seqs)

param_set = ParamSet(params, num_knobs=2)
param_set.apply_params(tb)  # set up synth with param set

tb_disp = TBishUI(display, params)

print("="*80)
print("tbish synth! press button to play/pause")
print("="*80)
print("secs_per_step:%.3f" % sequencer._secs_per_step)
import gc
print("mem_free:", gc.mem_free())

last_ui_time = time.monotonic()
def update_ui():
    global last_ui_time
    ki = tb_disp.curr_param_pair  # shorthand
    if time.monotonic() - last_ui_time > 0.05:
        last_ui_time = time.monotonic()

        # bit-reduction filtering then normalize
        #knobvals = (knobA.value, knobB.value)
        #knobvals = [((k>>8)<<8)/65535 for k in knobvals]
        # just normalized
        knobvals = (knobA.value/65535, knobB.value/65535)
        param_set.update_knobs(knobvals)

        # set synth with params
        param_set.apply_knobset(tb) 
        
        # for non-tb params
        #gate_amount = param_set.param_for_name('gate').val
        bpm = param_set.param_for_name('bpm').val
        sequencer.bpm = bpm
        
        seq_num = int(param_set.param_for_name('seq').val)
        sequencer.seq_num = seq_num
        
        tb_disp.update_param_pairs()

sequencer.start()

while True:
    
    if key := keys.events.get():
        if key.pressed:
            if sequencer.playing:
                sequencer.stop()
            else:
                sequencer.start()

    if touch_events := check_touch():
        for touch in touch_events:
            if touch.pressed:
                print("touchpad", touch.key_number)
                if touch.key_number in touchpad_to_knobset:
                    tb_disp.curr_param_pair = touchpad_to_knobset.index(touch.key_number)
                    param_set.idx = tb_disp.curr_param_pair
                if touch.key_number in touchpad_to_transpose:
                    transpose = touch.key_number   # chromatic
                    sequencer.transpose = transpose
                    
    update_ui()

    sequencer.update()


