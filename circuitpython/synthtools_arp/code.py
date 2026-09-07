# SPDX-FileCopyrightText: Copyright (c) 2025 Tod Kurt
# SPDX-License-Identifier: MIT
#
# synthtools_arp -- hold pads, the arpeggiator plays them back
#
# For a pico_test_synth / pico_test_synth2. Copy this code.py onto the
# CIRCUITPY root, then, from circuitpython/:
#
#   circup install -r requirements.txt
#
# That pulls synthtools and the local lib/pico_test_synth board package,
# whose optional ui module draws the screen here.
#
# Each pad you hold is a ROOT note. The "chord" parameter picks a set of
# intervals from synthtools.arpeggiator.patterns, and every held root
# contributes those intervals to the arpeggio -- so one pad is an
# arpeggiated chord and three pads is a long melodic sequence.
#
#   tap the button   -> next pair of parameters (5 pages)
#   hold the button  -> next octave
#   hold a pad       -> add its root to the arpeggio

import time

import microcontroller

# rp2040 boots at 125 MHz, and reading all 16 touch pads is the biggest
# thing in the loop (10.9 ms at 125 MHz, 8.2 at 200).
microcontroller.cpu.frequency = 200_000_000

from pico_test_synth import Hardware
from pico_test_synth.ui import SynthUI
from synthtools import Patch, SubtractiveSynth

# Only the 14 names in synthtools/__init__.py's _LAZY map come from the
# package itself; the rest are module-path imports.
from synthtools.arpeggiator import Arpeggiator, pattern_names, patterns
from synthtools.paramset import Param, ParamSet

HOLD_SECS = 0.7
UI_INTERVAL = 0.02
OCTAVES = (24, 36, 48)  # C1, C2, C3
VELOCITY = 100
RATE = 4  # arp steps per beat: 4 = sixteenths

WAVES = ("SAW", "SQU", "TRI", "SIN", "ASAW", "ASQU")

# fmt: off
patch = Patch(name="arp", wave="SAW", detune=1.0,
              filt_type="LPF", filt_f=1800, filt_q=1.2,
              amp_env=[0.005, 0.12, 0.0, 0.15],   # plucky: sustain 0
              fenv_amount=2000, fenv_attack=0.02, fenv_release=0.15,
              fenv_curve=2)
# fmt: on

hw = Hardware()
SubtractiveSynth.FILT_F_MAX = hw.sample_rate * 0.45  # SUBCLASS, before constructing

synth = SubtractiveSynth(hw.synth, patch)

# --- the 10 parameters, in knob-pair order -------------------------------
# fmt: off
PARAMS = [
    Param("bpm",      120,                 40,   240,   "%3d",   None),
    Param("gate",     0.5,                 0.05, 0.95,  "%.2f",  None),

    Param("chord",    0,                   0,    len(patterns) - 1, "%1d", None),
    Param("octrange", 1,                   1,    3,     "%1d",   None),

    Param("cutoff",   patch.filt_f,        60,   4000,  "%4d",   "filt_f"),
    Param("reso",     patch.filt_q,        0.6,  6.0,   "%.1f",  "filt_q"),

    Param("envamt",   patch.fenv_amount,   0,    6000,  "%4d",   "fenv_amount"),
    Param("envrel",   patch.fenv_release,  0.01, 1.0,   "%.2f",  "fenv_release"),

    # wave has no objattr: it is an INDEX, not the string synth.wave wants
    Param("wave",     WAVES.index(patch.wave), 0, len(WAVES) - 1, "%.0f", None),
    Param("release",  patch.amp_env[3],    0.01, 1.5,   "%.2f",  "release_time"),
]
# fmt: on
assert len(PARAMS) % 2 == 0, "PARAMS must be even: two knobs per page"

# KNOB_SCALE, not the default KNOB_PICKUP: a turn always moves the value,
# scaled so knob and value reach the ends together, instead of the pot
# being dead until it crosses.
param_set = ParamSet(PARAMS, num_knobs=2, knob_mode=ParamSet.KNOB_SCALE)

held = {}  # pad number -> the root note it added
oct_i = 1
base_note = OCTAVES[oct_i]


def note_on(note):
    synth.note_on(note, VELOCITY)


def note_off(note):
    if note is not None:  # Arpeggiator.stop() passes None if nothing is held
        synth.note_off(note)


arp = Arpeggiator(RATE, on_func=note_on, off_func=note_off)


def rebuild_arp():
    """Re-derive the arpeggio from the held roots and the chord shape.

    Called on a pad change AND on a chord/octrange change, so turning the
    chord knob with pads down re-voices what is already playing.
    """
    arp.notes = []
    shape = patterns[round(param_set.param_for_name("chord").val)]
    for root in held.values():
        for interval in shape:
            arp.add_note(root + interval)


def apply_param(p):
    """Push one param. Only some of these are synth attributes.

    Discrete params select with round(), not int(): ParamSet's deadband
    leaves a full-scale knob a hair under vmax, which int() would truncate
    to vmax - 1, making the last choice unreachable.
    """
    if p.name == "wave":
        synth.wave = WAVES[round(p.val)]  # index -> name string
    elif p.name == "bpm":
        arp.set_bpm(p.val, RATE)
    elif p.name == "gate":
        arp.gate = p.val
    elif p.name == "octrange":
        arp.oct_range = round(p.val)
    elif p.name == "chord":
        rebuild_arp()
    else:
        p.apply_to_obj(synth)


def param_text(p):
    """Format one param. Two of these are names, not numbers."""
    # round() to match how apply_param selects, or the screen disagrees
    # with the sound
    if p.name == "wave":
        return WAVES[round(p.val)]
    if p.name == "chord":
        return pattern_names[round(p.val)][:5]
    if p.name == "octrange":
        return "%d" % round(p.val)
    return p.fmt % p.val


for _p in PARAMS:
    if _p.objattr and _p.objattr not in synth._PARAMS:
        raise ValueError("no such synth parameter: '%s'" % _p.objattr)
    if len(_p.name) > 9:
        raise ValueError("param name too wide for the screen: '%s'" % _p.name)
    apply_param(_p)

print("synthtools arp: hold pads, tap button for page, hold for octave")

# setup_display() takes over the screen from the console, so print first.
display = hw.setup_display()
hw.setup_touch("up")
ui = SynthUI(display, param_set, param_text)

press_t = 0.0
last_ui = 0.0
arp.start()


def oct_name():
    return "C%d" % (base_note // 12 - 1)


def play_pads():
    """Held pads are arpeggio roots. Returns True if any pad changed."""
    events = hw.check_touch()
    for ev in events:
        if ev.pressed:
            held[ev.key_number] = base_note + ev.key_number
        else:
            held.pop(ev.key_number, None)
    if events:
        rebuild_arp()
    return bool(events)


def check_button():
    """Tap = next page, hold = next octave. Decided on release."""
    global press_t, oct_i, base_note
    ev = hw.keys.events.get()
    if not ev:
        return
    if ev.pressed:
        press_t = time.monotonic()
    elif time.monotonic() - press_t > HOLD_SECS:
        oct_i = (oct_i + 1) % len(OCTAVES)
        base_note = OCTAVES[oct_i]
        # roots already down keep their pitch; this applies to the next pad
    else:
        param_set.next_knobset()


def update_ui():
    """Read the pots, push only what moved, redraw only what changed."""
    knobs = hw.read_pots()  # filtered, 0.0-1.0
    i = param_set.idx * param_set.nknobs
    page = PARAMS[i : i + param_set.nknobs]
    before = [p.val for p in page]
    param_set.update_knobs(knobs)  # scaled takeover, always moves
    for p, was in zip(page, before):
        if p.val != was:
            apply_param(p)
    ui.update(oct_name())


while True:
    arp.update()
    touched = play_pads()
    check_button()

    now = time.monotonic()
    if now - last_ui > UI_INTERVAL:
        last_ui = now
        update_ui()
        # not on a pass that just built a voice
        if ui.dirty and not touched:
            display.refresh()
            ui.dirty = False
