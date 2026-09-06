# SPDX-FileCopyrightText: Copyright (c) 2025 Tod Kurt
# SPDX-License-Identifier: MIT
#
# synthtools_arp -- hold pads, the arpeggiator plays them back
#
# For a pico_test_synth / pico_test_synth2. Copy this code.py onto
# CIRCUITPY, plus the repo's circuitpython/lib/ (for synth_setup_pts.py
# and synth_ui_pts.py) and the synthtools package.
#
# Libraries needed:
#   circup install synthtools adafruit_display_text \
#                  adafruit_displayio_ssd1306 adafruit_debouncer
#
# Each pad you hold is a ROOT note. The "chord" parameter picks a set of
# intervals from synthtools.arpeggiator.patterns, and every held root
# contributes those intervals to the arpeggio -- so one pad is an
# arpeggiated chord and three pads is a long melodic sequence.
#
#   tap the button   -> next pair of parameters (5 pages)
#   hold the button  -> next octave
#   hold a pad       -> add its root to the arpeggio
#
# The pots use ParamSet's PICKUP mode: after changing page a pot does
# nothing until it passes the value the parameter already has.

import time

import microcontroller

# rp2040 boots at 125 MHz, and reading all 16 touch pads is the biggest
# thing in the loop (10.9 ms at 125 MHz, 8.2 at 200).
microcontroller.cpu.frequency = 200_000_000

from synth_setup_pts import (
    SAMPLE_RATE,
    check_touch,
    keys,
    knobA,
    knobB,
    setup_display,
    setup_touch,
)
from synth_setup_pts import synth as engine
from synth_ui_pts import SynthUI
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

# A Biquad above Nyquist is undefined and synth_setup_pts runs at
# 22.05 kHz. Set on the SUBCLASS, BEFORE construction.
SubtractiveSynth.FILT_F_MAX = SAMPLE_RATE * 0.45

synth = SubtractiveSynth(engine, patch)

# --- the 10 parameters, in knob-pair order -------------------------------
# fmt: off
PARAMS = [
    Param("bpm",      120,                 40,   240,   "%3d",   None),
    Param("gate",     0.5,                 0.05, 0.95,  "%.2f",  None),

    Param("chord",    0,                   0,    len(patterns) - 1, "%1d", None),
    Param("octrange", 1,                   1,    3,     "%1d",   None),

    Param("cutoff",   patch.filt_f,        60,   4000,  "%4d",   "filt_f"),
    Param("reso",     patch.filt_q,        0.5,  8.0,   "%.1f",  "filt_q"),

    Param("envamt",   patch.fenv_amount,   0,    6000,  "%4d",   "fenv_amount"),
    Param("envrel",   patch.fenv_release,  0.01, 1.0,   "%.2f",  "fenv_release"),

    # wave has no objattr: it is an INDEX, not the string synth.wave wants
    Param("wave",     WAVES.index(patch.wave), 0, len(WAVES) - 1, "%.0f", None),
    Param("release",  patch.amp_env[3],    0.01, 1.5,   "%.2f",  "release_time"),
]
# fmt: on
assert len(PARAMS) % 2 == 0, "PARAMS must be even: two knobs per page"

param_set = ParamSet(PARAMS, num_knobs=2)

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
    shape = patterns[int(param_set.param_for_name("chord").val)]
    for root in held.values():
        for interval in shape:
            arp.add_note(root + interval)


def apply_param(p):
    """Push one param. Only some of these are synth attributes."""
    if p.name == "wave":
        synth.wave = WAVES[int(p.val)]  # index -> name string
    elif p.name == "bpm":
        arp.set_bpm(p.val, RATE)
    elif p.name == "gate":
        arp.gate = p.val
    elif p.name == "octrange":
        arp.oct_range = int(p.val)
    elif p.name == "chord":
        rebuild_arp()
    else:
        p.apply_to_obj(synth)


def param_text(p):
    """Format one param. Two of these are names, not numbers."""
    if p.name == "wave":
        return WAVES[int(p.val)]
    if p.name == "chord":
        return pattern_names[int(p.val)][:5]
    return p.fmt % p.val


# Catch a bad objattr or an over-wide name at boot, not at the page turn
# that would have shown it. Names are padded to 9 columns on screen.
for _p in PARAMS:
    if _p.objattr and _p.objattr not in synth._PARAMS:
        raise ValueError("no such synth parameter: '%s'" % _p.objattr)
    if len(_p.name) > 9:
        raise ValueError("param name too wide for the screen: '%s'" % _p.name)
    apply_param(_p)

print("synthtools arp: hold pads, tap button for page, hold for octave")

# setup_display() takes over the screen from the console, so print first.
display = setup_display()
setup_touch("up")
ui = SynthUI(display, param_set, param_text)

press_t = 0.0
last_ui = 0.0
arp.start()


def oct_name():
    return "C%d" % (base_note // 12 - 1)


def play_pads():
    """Held pads are arpeggio roots. Returns True if any pad changed."""
    events = check_touch()
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
    ev = keys.events.get()
    if not ev:
        return
    if ev.pressed:
        press_t = time.monotonic()
    elif time.monotonic() - press_t > HOLD_SECS:
        oct_i = (oct_i + 1) % len(OCTAVES)
        base_note = OCTAVES[oct_i]
        # roots already down keep the pitch they were pressed at, like a
        # keyboard; the new octave applies to the next pad pressed.
    else:
        param_set.next_knobset()


def update_ui():
    """Read the pots, push only what moved, redraw only what changed."""
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
