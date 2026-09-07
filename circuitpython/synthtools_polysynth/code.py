# SPDX-FileCopyrightText: Copyright (c) 2025 Tod Kurt
# SPDX-License-Identifier: MIT
#
# synthtools_polysynth -- a playable SubtractiveSynth on pico_test_synth
#
# 16 touch pads are a chromatic keyboard, two pots edit 14 synth
# parameters two at a time, and a 128x64 OLED shows which two.
#
#   tap the button   -> next pair of parameters (7 pages)
#   hold the button  -> next octave (C2 / C3 / C4)
#
# Polyphony: the patch has detune=1.0, so one synthio Note per pad, and all
# sixteen down still fit synthio's 24-note budget. Turning the detune knob
# (page 7) up spends TWO Notes per pad, which puts a full hand-spread over
# the ceiling -- audible as dropped notes, not a crash.

import time

import microcontroller
microcontroller.cpu.frequency = 200_000_000

from pico_test_synth import Hardware
from pico_test_synth.ui import SynthUI
from synthtools import Patch, SubtractiveSynth
from synthtools.paramset import Param, ParamSet

UI_INTERVAL = 0.05  # seconds between UI passes (20 Hz)
HOLD_SECS = 0.7  # button held longer than this = octave, not page
VELOCITY = 100  # touch pads have no velocity
# how the pads are wired; a pico_test_synth2 can go either way, see
# Hardware.setup_touch()
TOUCH_PULL = "up"
OCTAVES = (36, 48, 60)  # C2, C3, C4 -- pad 0's note
# A pot never reads exactly 0, and SubtractiveSynth spends a SECOND Note per
# key for any detune that isn't exactly 1.0. Without this deadzone every
# patch would silently be dual-oscillator, 32 Notes against a budget of 24.
DETUNE_OFF = 1.0005

# waveform names, from _builders in synthtools/waves.py
WAVES = ("SAW", "SQU", "TRI", "SIN", "ASAW", "ATRI", "ASQU", "SSQU")

# --- the synth -----------------------------------------------------------
# fmt: off
patch = Patch(name="touch lead", wave="ASAW", detune=1.0,
              filt_type="LPF", filt_f=1500, filt_q=1.4,
              amp_env=[0.02, 0.20, 0.7, 0.35],
              vib_rate=5.5, vib_depth=0.0,
              fenv_amount=2500, fenv_attack=0.06, fenv_release=0.35,
              filt_track=0.0)
# fmt: on

hw = Hardware()
SubtractiveSynth.FILT_F_MAX = hw.sample_rate * 0.45  # SUBCLASS, before constructing

synth = SubtractiveSynth(hw.synth, patch)

# --- the 14 parameters, in knob-pair order -------------------------------
# Two pots, so params[0:2] are page 1, params[2:4] page 2, and so on.
# Adding two more gives an 8th page and nothing else changes. Every one is
# seeded from the patch, so the screen matches what is sounding at boot.
# fmt: off
PARAMS = [
    # 60-4000, not the filter's full range: the pot is LINEAR, so a 20 kHz
    # top end would bury every useful bass cutoff in the first few percent
    # of travel. The envelope still reaches higher.
    Param("cutoff",   patch.filt_f,       60,    4000,  "%.0f",  "filt_f"),
    # 0.6-6 is the useful span: below it the filter is overdamped, above
    # it squeals.
    Param("reso",     patch.filt_q,       0.6,    6.0,  "%.1f",  "filt_q"),

    Param("attack",   patch.amp_env[0],   0.0,   2.0,   "%.2f",  "attack_time"),
    Param("release",  patch.amp_env[3],   0.01,  3.0,   "%.2f",  "release_time"),

    Param("decay",    patch.amp_env[1],   0.0,   2.0,   "%.2f",  "decay_time"),
    Param("sustain",  patch.amp_env[2],   0.0,   1.0,   "%.2f",  "sustain_level"),

    # bipolar on purpose: a NEGATIVE amount sweeps the cutoff DOWN while the
    # key is held, the 303-style squelch. Exactly 0 builds no envelope node
    # at all, which would make the knob next-note-on only.
    Param("envamt",   patch.fenv_amount, -4000,  6000,  "%.0f",  "fenv_amount"),
    Param("envatk",   patch.fenv_attack,  0.005, 1.0,   "%.3f",  "fenv_attack"),

    Param("envrel",   patch.fenv_release, 0.005, 2.0,   "%.2f",  "fenv_release"),
    # also bipolar: negative CLOSES the filter as you play higher
    Param("track",    patch.filt_track,  -1.0,   1.0,   "%+.2f", "filt_track"),

    Param("vibrate",  patch.vib_rate,     0.1,   12.0,  "%.1f",  "vib_rate"),
    Param("vibdepth", patch.vib_depth,    0.0,   0.05,  "%.3f",  "vib_depth"),

    # wave has no objattr: it is an INDEX, not the string synth.wave wants
    Param("wave",     WAVES.index(patch.wave), 0, len(WAVES) - 1, "%.0f", None),
    Param("detune",   patch.detune,       1.0,   1.01,  "%.3f",  "detune"),
]
# fmt: on

# KNOB_SCALE, not the default KNOB_PICKUP: a turn always moves the value,
# scaled so knob and value reach the ends together, instead of the pot
# being dead until it crosses.
param_set = ParamSet(PARAMS, num_knobs=2, knob_mode=ParamSet.KNOB_SCALE)


def apply_param(p):
    """Push one param onto the synth. Two knobs need more than a setattr.

    Discrete params select with round(), not int(): ParamSet's deadband
    leaves a full-scale knob a hair under vmax, which int() would truncate
    to vmax - 1, making the last choice unreachable.
    """
    if p.name == "wave":
        synth.wave = WAVES[round(p.val)]  # index -> name string
    elif p.name == "detune" and p.val < DETUNE_OFF:
        synth.detune = 1.0  # exactly 1.0 is what _make_notes tests for
    else:
        p.apply_to_obj(synth)  # plain setattr via p.objattr


def param_text(p):
    """Format one param for the screen. Wave shows its name, not its index."""
    return WAVES[round(p.val)] if p.name == "wave" else p.fmt % p.val


for _p in PARAMS:
    if _p.objattr and _p.objattr not in synth._PARAMS:
        raise ValueError("no such synth parameter: '%s'" % _p.objattr)
    if len(_p.name) > 9:
        raise ValueError("param name too wide for the screen: '%s'" % _p.name)
    apply_param(_p)

print("synthtools touch demo: 16 pads, tap button for page, hold for octave")

# --- hardware ------------------------------------------------------------
# setup_display() takes over the screen from the console, so print first.
display = hw.setup_display()
hw.setup_touch(TOUCH_PULL)
ui = SynthUI(display, param_set, param_text)

held = {}  # pad number -> the midi note actually pressed on it
oct_i = 1
base_note = OCTAVES[oct_i]
press_t = 0.0  # must exist: a release can arrive without its press
last_ui = 0.0


def oct_name():
    return "C%d" % (base_note // 12 - 1)


def play_pads():
    """Handle touch events. Returns True if any pad changed state."""
    events = hw.check_touch()
    for ev in events:
        if ev.pressed:
            # remember the note actually played, so changing octave while a
            # pad is down still releases the right one
            note = base_note + ev.key_number
            held[ev.key_number] = note
            synth.note_on(note, VELOCITY)
        else:
            note = held.pop(ev.key_number, None)
            if note is not None:
                synth.note_off(note)
    return bool(events)


def check_button():
    """Tap = next page, hold = next octave. Decided on release, so no timer."""
    global press_t, oct_i, base_note
    ev = hw.keys.events.get()
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
    """Read the pots, push only what moved, redraw only what changed."""
    knobs = hw.read_pots()  # filtered, 0.0-1.0
    i = param_set.idx * param_set.nknobs
    page = PARAMS[i : i + param_set.nknobs]
    before = [p.val for p in page]
    param_set.update_knobs(knobs)  # scaled takeover, always moves
    for p, was in zip(page, before):
        if p.val != was:  # only a real move gets applied
            apply_param(p)
    ui.update(oct_name())


while True:
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
