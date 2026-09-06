# SPDX-FileCopyrightText: Copyright (c) 2025 Tod Kurt
# SPDX-License-Identifier: MIT
#
# synthtools_swarm -- a supersaw drone, on synthtools' SwarmSynth
#
# For a pico_test_synth / pico_test_synth2. Copy this code.py onto
# CIRCUITPY, plus the repo's circuitpython/lib/ (for synth_setup_pts.py
# and synth_ui_pts.py) and the synthtools package.
#
# Libraries needed:
#   circup install synthtools adafruit_display_text \
#                  adafruit_displayio_ssd1306 adafruit_debouncer
#
# SwarmSynth stacks up to 8 detuned oscillators on ONE note. It is
# mono = True, so the 16 pads behave like a pitch ribbon: touching a new
# one steals the sounding voice and glides to it rather than stacking a
# chord. That is what keeps it inside synthio's 24-note budget -- eight
# oscillators is eight Notes, and there is only ever one key down.
#
#   tap the button   -> next pair of parameters (4 pages)
#   hold the button  -> next octave
#   touch a pad      -> play / glide to that note
#
# `spread` and `drift` are the two knobs worth turning. Both are in bend
# units, where 1.0 is an octave -- so 0.01 is about +/-12 cents, and the
# useful range is small. Drift at 0 is a static chorus; wind it up and the
# oscillators wander against each other.

import time

import microcontroller

microcontroller.cpu.frequency = 200_000_000

from synth_setup_pts import (
    SAMPLE_RATE,
    check_touch,
    keys,
    knobA,
    knobB,
    mixer,
    setup_display,
    setup_touch,
)
from synth_setup_pts import synth as engine
from synth_ui_pts import SynthUI
from synthtools import Patch, SwarmSynth
from synthtools.paramset import Param, ParamSet

HOLD_SECS = 0.7
UI_INTERVAL = 0.02
OCTAVES = (24, 36, 48)  # C1, C2, C3
VELOCITY = 120

WAVES = ("SAW", "ASAW", "SQU", "TRI", "SIN")

# fmt: off
patch = Patch(name="swarm", synth_type="swarm", wave="SAW",
              swarm_count=7, swarm_spread=0.008, swarm_drift=0.003,
              filt_type="LPF", filt_f=2200, filt_q=0.7,
              amp_env=[0.6, 0.2, 0.9, 1.2],       # slow pad attack/release
              vib_rate=0.0, vib_depth=0.0)
# fmt: on

SwarmSynth.FILT_F_MAX = SAMPLE_RATE * 0.45  # SUBCLASS, before constructing

synth = SwarmSynth(engine, patch)
synth.glide_time = 0.25  # the ribbon glissando; mono makes this audible

# SwarmSynth divides each note's amplitude by swarm_count so the stack does
# not clip, which leaves the whole instrument quiet. Make it back up here
# rather than in the patch -- the mixer is the one gain that does not have
# to be shared with anything.
mixer.voice[0].level = 0.9

# --- the 8 parameters, in knob-pair order --------------------------------
# fmt: off
PARAMS = [
    # both in BEND units: 1.0 = one octave, so these ranges are narrow on
    # purpose. Past ~0.03 of spread it stops being a chorus and starts
    # being a chord.
    Param("spread",   patch.swarm_spread,  0.0,  0.03,  "%.3f",  "swarm_spread"),
    Param("drift",    patch.swarm_drift,   0.0,  0.02,  "%.3f",  "swarm_drift"),

    # applies at the NEXT note-on: the fan of oscillators is built there
    Param("count",    patch.swarm_count,   1,    SwarmSynth.MAX_OSCS, "%1d", "swarm_count"),
    Param("glide",    synth.glide_time,    0.0,  1.5,   "%.2f",  "glide_time"),

    Param("cutoff",   patch.filt_f,        60,   4000,  "%4d",   "filt_f"),
    Param("reso",     patch.filt_q,        0.5,  8.0,   "%.1f",  "filt_q"),

    # wave has no objattr: it is an INDEX, not the string synth.wave wants
    Param("wave",     WAVES.index(patch.wave), 0, len(WAVES) - 1, "%.0f", None),
    Param("release",  patch.amp_env[3],    0.05, 3.0,   "%.2f",  "release_time"),
]
# fmt: on
assert len(PARAMS) % 2 == 0, "PARAMS must be even: two knobs per page"

param_set = ParamSet(PARAMS, num_knobs=2)


def apply_param(p):
    if p.name == "wave":
        synth.wave = WAVES[int(p.val)]  # index -> name string
    elif p.name == "count":
        synth.swarm_count = int(p.val)  # the setter clamps to 1..MAX_OSCS
    else:
        p.apply_to_obj(synth)


def param_text(p):
    return WAVES[int(p.val)] if p.name == "wave" else p.fmt % p.val


for _p in PARAMS:
    if _p.objattr and _p.objattr not in synth._PARAMS:
        raise ValueError("no such synth parameter: '%s'" % _p.objattr)
    if len(_p.name) > 9:
        raise ValueError("param name too wide for the screen: '%s'" % _p.name)
    apply_param(_p)

print("synthtools swarm: %d oscs, mono=%s" % (synth.swarm_count, synth.mono))

display = setup_display()
setup_touch("up")
ui = SynthUI(display, param_set, param_text)

held = {}  # pad -> the note it played
oct_i = 1
base_note = OCTAVES[oct_i]
press_t = 0.0
last_ui = 0.0


def oct_name():
    return "C%d" % (base_note // 12 - 1)


def play_pads():
    """Mono ribbon: a new pad steals the voice, the last release ends it."""
    events = check_touch()
    for ev in events:
        if ev.pressed:
            note = base_note + ev.key_number
            held[ev.key_number] = note
            synth.note_on(note, VELOCITY)
        else:
            note = held.pop(ev.key_number, None)
            # Only release for real when nothing else is still down --
            # mono stole the voice, so an earlier pad lifting must not cut
            # off the note a later one is holding.
            if note is not None and not held:
                synth.note_off(note)
    return bool(events)


def check_button():
    global press_t, oct_i, base_note
    ev = keys.events.get()
    if not ev:
        return
    if ev.pressed:
        press_t = time.monotonic()
    elif time.monotonic() - press_t > HOLD_SECS:
        oct_i = (oct_i + 1) % len(OCTAVES)
        base_note = OCTAVES[oct_i]
    else:
        param_set.next_knobset()


def update_ui():
    knobs = (knobA.value / 65535, knobB.value / 65535)
    i = param_set.idx * param_set.nknobs
    page = PARAMS[i : i + param_set.nknobs]
    before = [p.val for p in page]
    param_set.update_knobs(knobs)
    for p, was in zip(page, before):
        if p.val != was:
            apply_param(p)
    ui.update(oct_name())


while True:
    touched = play_pads()
    check_button()

    now = time.monotonic()
    if now - last_ui > UI_INTERVAL:
        last_ui = now
        update_ui()
        if ui.dirty and not touched:
            display.refresh()
            ui.dirty = False
