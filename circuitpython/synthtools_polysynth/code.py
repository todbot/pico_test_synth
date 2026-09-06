# SPDX-FileCopyrightText: Copyright (c) 2025 Tod Kurt
# SPDX-License-Identifier: MIT
#
# synthtools_polysynth -- a playable SubtractiveSynth with a screen
#
# For a pico_test_synth2. Copy this code.py onto CIRCUITPY, plus the
# repo's circuitpython/lib/ (which carries the shared synth_setup_pts.py
# and synth_ui_pts.py this imports), plus the synthtools package.
#
# Those two modules used to live in this folder; they are now shared with
# tbish2/ and the other synthtools demos. CircuitPython puts lib/ on
# sys.path, so the import lines below are unchanged.
#
# 16 touch pads are a chromatic keyboard, two pots edit 14 synth
# parameters two at a time, and a 128x64 OLED shows which two.
#
#   tap the button   -> next pair of parameters (7 pages)
#   hold the button  -> next octave (C2 / C3 / C4)
#
# The pots use ParamSet's PICKUP mode: after changing page a pot does
# nothing until it passes the value the parameter already has, so the
# sound never jumps when you turn one. The footer shows "A*" once a pot
# has picked up, "A-" while it is still waiting.
#
# Libraries needed:
#   circup install synthtools adafruit_display_text \
#                  adafruit_displayio_ssd1306 adafruit_debouncer
#
# Polyphony: the patch has detune=1.0, so one synthio Note per pad. All
# sixteen pads down plus a few releasing still fits synthio's 24-note
# budget. Turning the detune knob (page 7) up spends TWO Notes per pad,
# which puts a full hand-spread over the ceiling -- audible as dropped
# notes, not a crash.
#
# --- why the display code looks paranoid -----------------------------
#
# A full 128x64 mono frame is 1024 bytes, ~9.5 ms on the wire at I2C
# 1 MHz. audiomixer splits its 2048-byte buffer in two, so the deadline to
# refill one half is 11.6 ms at this rig's 22.05 kHz (it would be 5.8 at
# 44.1). One careless refresh per loop pass is enough to starve it.
# Five things keep it quiet, in order of how much they matter:
#
#   1. Nothing is re-applied to the synth unless it actually changed.
#      This is the big one and it is not a display problem at all:
#      ParamSet.apply_knobset() setattrs every param every call, and
#      attack/decay/sustain/release each rebuild a synthio.Envelope and
#      push it to every sounding note. That is an allocation 20x a second
#      for a pot nobody is touching. See update_ui() below.
#   2. SynthUI.update() compares the raw float BEFORE formatting anything,
#      so an idle pass does no string work at all.
#   3. The whole UI pass is throttled to UI_INTERVAL.
#   4. One explicit display.refresh(), and only when something changed.
#   5. The refresh is skipped on any pass that handled a pad, so the I2C
#      burst never lands in the same iteration as a note_on() building a
#      voice. Costs at most one UI_INTERVAL of display lag.
#
# Measured on a pico_test_synth2 (rp2040 at 200 MHz), which is what those
# are worth in practice:
#
#   idle UI pass (update + clean refresh)   0.24 + 0.24 ms
#   one value+bar changes, update only      6.8 ms   (glyph re-render)
#   ...and its refresh()                    9.6 ms   (I2C, chunked)
#   a page change, all six elements         41 + 34 ms
#   check_touch(), all 16 pads              8.2 ms
#
# So the loop is dominated by the touch scan and runs near 80-100 Hz, an
# idle screen costs about 1% of it, and a page turn is a ~75 ms hiccup you
# can feel in touch latency. That last one is the honest weak spot: it is
# 8 label re-renders in one iteration. Audio survives it because displayio
# runs background tasks between I2C chunks and the VM yields between
# bytecodes -- but if it ever does click, spread the page repaint over
# several passes rather than making the whole thing cheaper.
#
# None of the above was the cause of the once-a-second glitch this rig had
# at 44.1 kHz, which is worth recording so nobody re-tunes the display
# chasing it. Measured with hands off the controls: the pots wrote a
# parameter 0 times in 100 passes, no single touch read exceeded 0.38 ms,
# and nothing in this loop has a 1 Hz period at all. It was render
# headroom, and the fix is the sample rate in synth_setup_pts.py.

import time

import microcontroller

# rp2040 boots at 125 MHz. Reading all 16 touch pads is the biggest thing
# in this loop, so overclock before anything else is set up. Measured on
# a pico_test_synth2: 10.89 ms per 16-pad scan at 125 MHz, 8.20 ms at 200.
# (Only part of the scan is CPU -- most of it is fixed RC settling time,
# which is why 1.6x the clock is nowhere near 1.6x the speed.)
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
from synthtools.paramset import Param, ParamSet

UI_INTERVAL = 0.05  # seconds between UI passes (20 Hz)
HOLD_SECS = 0.7  # button held longer than this = octave, not page
VELOCITY = 100  # touch pads have no velocity
# How the touch pads are wired. A pico_test_synth2 can go either way:
# "up" / "down" use the pin's internal resistor, None means the pads have
# their own (an rp2040 with neither raises "No pulldown on pin").
TOUCH_PULL = "up"
OCTAVES = (36, 48, 60)  # C2, C3, C4 -- pad 0's note
# A pot never reads exactly 0, so the detune knob's bottom end lands on
# 1.0000002 rather than 1.0 -- and SubtractiveSynth spends a SECOND Note
# per key for any detune that isn't exactly 1.0. Without this deadzone
# every patch would silently be dual-oscillator and 16 pads would want
# 32 Notes against a budget of 24.
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

# A Biquad above Nyquist is undefined, and synth_setup_pts runs at 22.05 kHz
# to stop this rig glitching -- so 11 kHz, not the class default of 20 kHz,
# is the ceiling. The cutoff bus can genuinely reach it: 4000 Hz of filt_f
# plus 6000 of envelope plus keyboard tracking sums well past 11 kHz on the
# top pads. Set on the SUBCLASS, so the library's Synth is left alone, and
# BEFORE construction -- the shared clamp bakes this in at graph-build time.
SubtractiveSynth.FILT_F_MAX = SAMPLE_RATE * 0.45

synth = SubtractiveSynth(engine, patch)

# --- the 14 parameters, in knob-pair order -------------------------------
# Two pots, so params[0:2] are page 1, params[2:4] page 2, and so on.
# Adding two more Params here gives an 8th page and nothing else changes:
# that is what ParamSet is for.
#
# Every one is seeded from the patch, so the screen matches what is
# actually sounding at boot and pickup starts from the right place.
# fmt: off
PARAMS = [
    # 60-4000 rather than the filter's full range: this is a LINEAR pot, so
    # a 20 kHz top end would bury every useful bass cutoff in the bottom
    # few percent of travel. 4000 puts 500 Hz at ~11% and the envelope
    # (up to +6000 Hz) still reaches the top of the audible range.
    Param("cutoff",   patch.filt_f,       60,    4000,  "%.0f",  "filt_f"),
    Param("reso",     patch.filt_q,       0.5,   14.0,  "%.1f",  "filt_q"),

    Param("attack",   patch.amp_env[0],   0.0,   2.0,   "%.2f",  "attack_time"),
    Param("release",  patch.amp_env[3],   0.01,  3.0,   "%.2f",  "release_time"),

    Param("decay",    patch.amp_env[1],   0.0,   2.0,   "%.2f",  "decay_time"),
    Param("sustain",  patch.amp_env[2],   0.0,   1.0,   "%.2f",  "sustain_level"),

    # bipolar on purpose: a NEGATIVE amount sweeps the cutoff DOWN while
    # the key is held, which is the 303-style squelch. Parking it at
    # EXACTLY 0 builds no envelope node at all, so the knob would then be
    # next-note-on only -- a pot never lands there, but that is why.
    Param("envamt",   patch.fenv_amount, -4000,  6000,  "%.0f",  "fenv_amount"),
    Param("envatk",   patch.fenv_attack,  0.005, 1.0,   "%.3f",  "fenv_attack"),

    Param("envrel",   patch.fenv_release, 0.005, 2.0,   "%.2f",  "fenv_release"),
    # also bipolar: negative CLOSES the filter as you play higher
    Param("track",    patch.filt_track,  -1.0,   1.0,   "%+.2f", "filt_track"),

    Param("vibrate",  patch.vib_rate,     0.1,   12.0,  "%.1f",  "vib_rate"),
    Param("vibdepth", patch.vib_depth,    0.0,   0.05,  "%.3f",  "vib_depth"),

    # wave has no objattr: it is an INDEX, not the string synth.wave wants.
    # vmax is len-1 so a pot at full scale truncates onto the last entry.
    Param("wave",     WAVES.index(patch.wave), 0, len(WAVES) - 1, "%.0f", None),
    Param("detune",   patch.detune,       1.0,   1.01,  "%.3f",  "detune"),
]
# fmt: on

param_set = ParamSet(PARAMS, num_knobs=2)


def apply_param(p):
    """Push one param onto the synth. Two knobs need more than a setattr."""
    if p.name == "wave":
        synth.wave = WAVES[int(p.val)]  # index -> name string
    elif p.name == "detune" and p.val < DETUNE_OFF:
        synth.detune = 1.0  # exactly 1.0 is what _make_notes tests for
    else:
        p.apply_to_obj(synth)  # plain setattr via p.objattr


def param_text(p):
    """Format one param for the screen. Wave shows its name, not its index."""
    return WAVES[int(p.val)] if p.name == "wave" else p.fmt % p.val


# Catch a bad objattr or an over-wide name at boot rather than at the page
# turn that would have shown it. Names are padded to 9 columns on screen.
for _p in PARAMS:
    if _p.objattr and _p.objattr not in synth._PARAMS:
        raise ValueError("no such synth parameter: '%s'" % _p.objattr)
    if len(_p.name) > 9:
        raise ValueError("param name too wide for the screen: '%s'" % _p.name)
    apply_param(_p)

print("synthtools touch demo: 16 pads, tap button for page, hold for octave")

# --- hardware ------------------------------------------------------------
# setup_display() takes over the screen from the console, so print first.
display = setup_display()
setup_touch(TOUCH_PULL)
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
    events = check_touch()
    for ev in events:
        if ev.pressed:
            # remember the note we actually played, so changing octave
            # while a pad is down still releases the right one. Notes
            # already sounding are not re-pitched -- like a keyboard,
            # they ring out where they were pressed.
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
    """Read the pots, push only what moved, redraw only what changed."""
    knobs = (knobA.value / 65535, knobB.value / 65535)
    i = param_set.idx * param_set.nknobs
    page = PARAMS[i : i + param_set.nknobs]
    before = [p.val for p in page]
    param_set.update_knobs(knobs)  # PICKUP mode + min_change deadband
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
        # not on a pass that just built a voice -- see the header
        if ui.dirty and not touched:
            display.refresh()
            ui.dirty = False
