import time, random
import ulab.numpy as np
import synthio
from synth_setup_pts import mixer, knobA, knobB, keys, setup_display, setup_touch

from param_set import ParamSet, Param

from tbish_synth import TBishSynth
from tbish_ui import TBishUI

display = setup_display()
   
playing = True
bpm = 120
steps_per_beat = 4
secs_per_step = 60 / bpm / steps_per_beat
glide_time = 0.25
midi_notes = [36, 36, 48+7, 36,  48, 48, 36, 48]
midi_vels = [127, 80, 127, 80,  127, 80, 127, 80]
new_midi_note = midi_notes[0]
gate_off_time = 0 
i=0

params = [
    Param("cutoff", 8000, 0, 9000, "%4d", 'cutoff'),
    Param('envmod', 0.5,  0.0, 1.0, "%.2f",'envmod'), 
    
    Param('drive', 20, 5, 30, "%2d", 'drive'),
    Param('drivemix', 0.5, 0.0, 1.0, "%.2f", 'drive_mix'),
    
    Param("resQ",  1.0, 0.5, 3.5, "%.2f", 'resonance'),
    Param('decay', 0.5,  0.0, 1.0, "%.2f", ),    
    
    Param('root', 36, 12, 60, "%2d"),
    Param('bpm ', 120, 40, 200, "%3d"),
    
    Param('dely', 0.3, 0.0, 1.0, "%.2f"),
    Param('dtim', 0.25, 0.0, 1.0, "%.2f"),
]

tb = TBishSynth(mixer.sample_rate, mixer.channel_count)
tb_audio = tb.add_audioeffects()
mixer.voice[0].play(tb_audio)

param_set = ParamSet(params, num_knobs=2)

tb_disp = TBishUI(display, params)

last_ui_time = time.monotonic()
def update_ui():
    global last_ui_time
    ki = tb_disp.curr_param_pair  # shorthand
    if time.monotonic() - last_ui_time > 0.1:
        last_ui_time = time.monotonic()

        param_set.update_knobs((knobA.value/65535, knobB.value/65535))

        param_set.apply_knobset_to_obj(tb)
        
        tb_disp.update_param_pairs()
        
        #bpm = 40 + 200* (knobB.value/65535)


next_step_time = time.monotonic()

while True:
    update_ui()
    
    if key := keys.events.get():
        if key.pressed:
            tb_disp.next_param_pair()
            #tb_disp.update_param_pairs()
            param_set.idx = tb_disp.curr_param_pair

    if not playing:
        continue
    
    now = time.monotonic()
    if gate_off_time - now <=0:
        tb.note_off(new_midi_note)

    dt = (next_step_time - now)
    if dt <= 0:
        next_step_time = now + secs_per_step + dt  
        # add delta to attempt to make up for display hosing us
        
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
    



