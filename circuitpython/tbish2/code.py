# SPDX-FileCopyrightText: Copyright (c) 2025 Tod Kurt
# SPDX-License-Identifier: MIT
#
# tbish2 -- a TB-303-like acid bassline, on synthtools' BasslineSynth
#
# The tbish/ demo rebuilt on the library. BasslineSynth is a direct port of
# tbish/tbish_synth.py, so this is the same instrument with the four
# "# FIXME how to do this" items in that file's note_on_step() actually
# done: an accent now raises resonance (accent_q) and cutoff
# (accent_cutoff) as well as level, and a slide has a real slide_time.
#
# For a pico_test_synth / pico_test_synth2. Copy code.py, tbish_ui.py
# and boot.py onto the CIRCUITPY root, then, from circuitpython/:
#
#   circup install -r requirements.txt
#
# That pulls the synthtools package and the local lib/pico_test_synth
# board package -- circup installs from a path as readily as from the
# bundle. tbish2 draws its own screen (tbish_ui.py), so it never imports
# pico_test_synth.ui.
#
# NEEDS a build with audiofilters and audiodelays for the drive and delay
# knobs and the 24 dB filter. Without them the demo still runs -- the
# voice's own 12 dB Biquad only -- and says so at boot.
#
#   tap the button   -> next pair of parameters (9 pages)
#   hold the button  -> play / pause (and save the knobs to /tbish2.json)
#   touch a pad      -> transpose the sequence, -7..+8 semitones
#
# The pots use scaled ("catch-up") takeover: a turn ALWAYS moves the
# value, by an amount scaled so knob and value converge and reach the
# ends together. No dead travel after a page turn -- see
# ParamSet.update_knobs_scale() in synthtools.

import os
import time

import microcontroller

# Do this before any import that allocates. On the original tbish it took
# per-step latency from 10 ms down to 6 ms.
microcontroller.cpu.frequency = 200_000_000

from pico_test_synth import Hardware
from synthtools import BasslineSynth, Patch

# Only the 14 names in synthtools/__init__.py's _LAZY map can be imported
# from the package itself; everything else is a module-path import. The
# package is lazy on purpose (23 KB of rp2040 RAM against 52 KB eager) --
# don't "fix" that upstream.
from synthtools.paramset import Param, ParamSet
from synthtools.step_sequencer import StepSequencer
from tbish_ui import TBishUI

# tbish/tbish_synth.py:94 says outright "No distortion on rp2040 (not
# enough CPU)", while the extra filter stage it does afford ("but yes
# filter on rp2040 with custom compile"). Take it at its word rather than
# shipping a demo that stutters on half the boards this repo supports --
# the drive knobs simply do nothing on an rp2040. Same os.uname()[0] test
# tbish/synth_setup_pts.py:95 used.
IS_RP2350 = "rp2350" in os.uname()[0]

HOLD_SECS = 0.7  # button press longer than this is a hold, not a tap
UI_INTERVAL = 0.02  # seconds between UI passes
STEPS_PER_BEAT = 4  # 4 = 16th note, 2 = 8th, 1 = quarter
PARAMS_FILE = "/tbish2.json"

# Waveform names, from _builders in synthtools/waves.py. SAW and SQU are
# the 303's own two switch positions; the rest are here because they cost
# nothing. Indexed by a knob, so order is the UI.
WAVES = ("SAW", "SQU", "ASAW", "ASQU", "TRI", "SIN")

# --- the patterns --------------------------------------------------------
# (notes, velocities). A note of 0 is a rest. Velocity is overloaded as the
# per-step flag channel, exactly as in tbish: 1 = slide, 127 = accent.
# StepSequencer steps are [note, vel, gate, on], so this drops straight in.
# fmt: off
SEQS = [
    [[36, 36, 48, 36,  48, 55, 36, 48],
     [127, 80, 80, 80,  127, 1, 30, 1]],

    [[36, 48, 36, 48,  36, 48, 36, 48],
     [127, 80, 1, 1,  127, 1, 30, 1]],

    [[34, 36, 34, 36,  48, 48, 36, 48],
     [127, 80, 120, 80,  127, 11, 127, 80]],

    [[36, 24, 36, 48,  36, 0, 36, 0],
     [127, 1, 1, 80,  127, 80, 127, 80]],
]
# fmt: on
STEP_COUNT = len(SEQS[0][0])
GATE = 0.75  # traditional 303 gate length, as a fraction of a step

# --- the patch -----------------------------------------------------------
# The classic squelch is a big downward sweep from a bright start. envmod is
# a FRACTION of filt_f, not a number of Hz, so the sweep tracks the cutoff
# knob: 0.75 of 3000 Hz falls to 750, two octaves.
#
# The two numbers that decide whether you hear envmod at all are `decay`
# and the amp envelope's decay:
#
#   decay (the FILTER fall) must be SHORTER than the gate, or the sweep is
#   cut off partway and envmod does far less than its number suggests.
#   The gate here is 0.75 of a 125 ms step at 120 bpm = 94 ms.
#
#   The amp decay must be LONGER, so the note is still loud while the
#   cutoff falls. Equal times sound like one gesture -- a pluck -- because
#   loudness and brightness drop together and mask each other.
# fmt: off
patch = Patch(
    name="tbish2",
    synth_type="bassline",
    wave="SAW",
    filt_type="LPF",
    filt_f=3000,        # the PEAK the sweep starts from
    filt_q=1.8,         # squelch lives here; push it toward 3-4
    envmod=0.75,
    decay=0.09,         # FILTER fall time, seconds
    amp_env=[0.001, 0.25, 0.0, 0.02],   # sustain 0: every step plucks
    fenv_curve=3,       # fast drop, long tail -- reads as "analog"
    accent=0.5,
    accent_cutoff=4000,  # Hz added at full accent
    accent_q=0.8,        # resonance added at full accent
    amp_level=0.75,      # un-accented level, so accents have room
    slide_time=0.09,
    transpose=0,
    fx_filter_stages=1,  # a synthio.Note holds ONE Biquad, so the voice
                         # alone is 12 dB/oct; one extra stage makes 24,
                         # where the squelch really lives
    # The other two STRUCTURAL fx switches. They have to be on here for
    # the drive and delay knobs below to reach anything -- they build the
    # effects, and nothing in _PARAMS can turn them on later (a MIDI CC
    # that rebuilt the chain would silently mute it, since the mixer would
    # still be playing the old tail).
    fx_distortion_on=IS_RP2350,  # too expensive on an rp2040; see above
    fx_echo_on=True,
    fx_drive=0.0,
    fx_drive_mix=0.0,
    fx_delay_ms=250.0,
    fx_delay_mix=0.0,
    fx_delay_decay=0.3,
)
# fmt: on

# A Biquad above Nyquist is undefined, and Hardware runs at
# 22.05 kHz, so 9.9 kHz is the ceiling -- not the class default of 20 kHz.
# filt_f alone reaches 5000 and a full accent adds 4000 on top. Set on the
# SUBCLASS, and BEFORE construction: the clamp is baked into the block
# graph at build time.
hw = Hardware()
BasslineSynth.FILT_F_MAX = hw.sample_rate * 0.45

bass = BasslineSynth(hw.synth, patch)

# play() captures object identity at call time, so this has to happen after
# the fx chain exists -- and again after any STRUCTURAL fx change
# (fx_filter_stages, fx_distortion_on, fx_echo_on). None of the knobs below
# is structural, so once is enough here.
# Hardware.__init__ already played the bare synthesizer into voice 0;
# this REPLACES that with the effects chain's tail. Without it the whole
# chain is bypassed and nothing sounds wrong -- it just sounds thin.
try:
    hw.mixer.voice[0].play(bass.output)
    print("filter: 24 dB/octave (1 extra stage)")
except ImportError:
    print("no audiofilters in this build -- 12 dB/oct, no drive, no delay")
    hw.mixer.voice[0].play(bass.synthio)

# --- the 18 parameters, in knob-pair order -------------------------------
# Two pots, so params[0:2] are page 1, params[2:4] page 2, and so on.
# Adding two more gives a 10th page and nothing else changes.
#
# Two of these changed UNITS from tbish, not just name:
#   decay was a 0-1 fraction of the step; it is now seconds outright.
#   dtime was 0-1 seconds; fx_delay_ms is milliseconds (max 1000).
# fmt: off
PARAMS = [
    Param("cutoff",   patch.filt_f,        100,  5000,  "%4d",   "filt_f"),
    Param("envmod",   patch.envmod,        0.0,  1.0,   "%.2f",  "envmod"),

    # 4.0, not 6.0: an accent adds accent_q (up to 2.0) onto this same
    # shared block, so 4+2 is what actually reaches the filter. 0.6-6 is
    # the useful span -- see Synth.filt_q.
    Param("resQ",     patch.filt_q,        0.6,  4.0,   "%.2f",  "filt_q"),
    Param("decay",    patch.decay,         0.02, 0.40,  "%.2f",  "decay"),

    # the amp's decay, which wants to stay longer than the filter's
    Param("ampdec",   patch.amp_env[1],    0.02, 1.0,   "%.2f",  "decay_time"),
    Param("amplevel", patch.amp_level,     0.1,  1.0,   "%.2f",  "amp_level"),

    Param("accent",   patch.accent,        0.0,  1.0,   "%.2f",  "accent"),
    # tbish's "# FIXME: how to do" pair -- both real parameters now
    Param("acctcut",  patch.accent_cutoff, 0,    6000,  "%4d",   "accent_cutoff"),

    Param("acctQ",    patch.accent_q,      0.0,  2.0,   "%.2f",  "accent_q"),
    Param("slide",    patch.slide_time,    0.01, 0.25,  "%.2f",  "slide_time"),

    # wave has no objattr: it is an INDEX, not the string bass.wave wants.
    # vmax is len-1 so a pot at full scale truncates onto the last entry.
    Param("wave",     WAVES.index(patch.wave), 0, len(WAVES) - 1, "%.0f", None),
    Param("drive",    patch.fx_drive,      0.0,  1.0,   "%.2f",  "fx_drive"),

    Param("drivemix", patch.fx_drive_mix,  0.0,  1.0,   "%.2f",  "fx_drive_mix"),
    Param("dtime",    patch.fx_delay_ms,   0,    1000,  "%4d",   "fx_delay_ms"),

    Param("delaymix", patch.fx_delay_mix,  0.0,  1.0,   "%.2f",  "fx_delay_mix"),
    Param("dlyfeed",  patch.fx_delay_decay, 0.0, 0.9,   "%.2f",  "fx_delay_decay"),

    # the two sequencer knobs: no objattr, handled in apply_param
    Param("seq",      0,                   0,    len(SEQS) - 1, "%1d", None),
    Param("bpm",      120,                 40,   200,   "%3d",   None),
]
# fmt: on
# One odd param would silently drop off the last page (nknobsets floors),
# so say so here rather than wondering where "bpm" went.
assert len(PARAMS) % 2 == 0, "PARAMS must be even: two knobs per page"

# KNOB_SCALE, not the default KNOB_PICKUP: a turn always moves the
# value, scaled so knob and value converge and reach the ends
# together, instead of the pot being dead until it crosses.
param_set = ParamSet(PARAMS, num_knobs=2, knob_mode=ParamSet.KNOB_SCALE)


def apply_param(p):
    """Push one param onto the synth. Not everything is a plain setattr.

    A discrete parameter selects with round(), not int(). ParamSet
    deadbands: it stops updating once the knob is within
    0.1 * min_change * span of the value, so a pot at full scale leaves
    p.val a hair under vmax. int() truncates that to vmax - 1 and the last
    choice becomes unreachable; round() also gives every choice an equal
    band instead of a zero-width one at the top.
    """
    if p.name == "wave":
        bass.wave = WAVES[round(p.val)]  # index -> name string
    elif p.name == "seq":
        set_seq(round(p.val))
    elif p.name == "bpm":
        sequencer.bpm = p.val
    else:
        p.apply_to_obj(bass)  # plain setattr via p.objattr


def param_text(p):
    """Format one param for the screen. Wave shows its name, not its index."""
    # A discrete param must be FORMATTED the same way apply_param
    # SELECTS it. "%d" truncates, so a value of 2.99 would print 2
    # while round() applied 3 -- the screen disagreeing with the
    # sound, which reads as a synth bug rather than a display one.
    if p.name == "wave":
        return WAVES[round(p.val)]
    if p.name == "seq":
        return "%d" % round(p.val)
    return p.fmt % p.val


# --- the sequencer -------------------------------------------------------
# StepSequencer holds ONE steps list with step_count fixed at construction,
# so switching pattern means rewriting that list in place. All four
# patterns are the same length, which is what makes this work.


def on_step(note, vel, gate, on):
    """StepSequencer note-on. vel carries the 303's per-step flags."""
    if not on or note == 0:  # 0 is a rest
        return
    bass.note_on_step(note, slide=(vel == 1), accent=(vel == 127), velocity=vel)


def off_step(note, vel, gate, on):
    # `note` arrives already transposed: StepSequencer adds transpose
    # before it calls on_func, and hands off_func back the same tuple.
    if on and note != 0:
        bass.note_off(note)


sequencer = StepSequencer(STEP_COUNT, STEPS_PER_BEAT, on_func=on_step, off_func=off_step)


def set_seq(n):
    """Rewrite the pattern in place. StepSequencer has no seq bank."""
    notes, vels = SEQS[n]
    for i in range(STEP_COUNT):
        sequencer.steps[i] = [notes[i], vels[i], GATE, True]


# Catch a bad objattr or an over-wide name at boot rather than at the page
# turn that would have shown it. Names are padded to 8 columns on screen.
for _p in PARAMS:
    if _p.objattr and _p.objattr not in bass._PARAMS:
        raise ValueError("no such synth parameter: '%s'" % _p.objattr)
    if len(_p.name) > 8:
        raise ValueError("param name too wide for the screen: '%s'" % _p.name)
    apply_param(_p)

sequencer.bpm = param_set.param_for_name("bpm").val

print("tbish2: tap button for page, hold to play/pause, pads transpose")

# --- hardware ------------------------------------------------------------
# setup_display() takes over the screen from the console, so print first.
display = hw.setup_display()
hw.setup_touch("up")
ui = TBishUI(display, param_set, param_text)
display.root_group = ui

press_t = 0.0  # must exist: a release can arrive without its press
last_ui = 0.0

sequencer.start()


def save_params():
    """Persist the knobs. The only patch storage this demo has."""
    try:
        with open(PARAMS_FILE, "w") as f:
            f.write(ParamSet.dump(param_set))
    except OSError:
        # CIRCUITPY is read-only to the board unless a boot.py remounts it
        # writable; see wavesynth/boot.py for how.
        print("could not write", PARAMS_FILE, "-- need a boot.py remount")


def load_params():
    try:
        with open(PARAMS_FILE) as f:
            saved = ParamSet.load(f.read())
    except (OSError, ValueError):
        return  # no saved params yet, or they no longer parse
    # ParamSet.load() hands back a fresh list of Params rather than
    # mutating ours, and matches by position. Copy across by NAME instead,
    # so a saved file from an older PARAMS list restores what it can
    # rather than smearing values onto the wrong parameters.
    by_name = {p.name: p for p in saved}
    for p in PARAMS:
        was = by_name.get(p.name)
        if was is not None and p.vmin <= was.val <= p.vmax:
            p.val = was.val
        apply_param(p)


def check_button():
    """Tap = next page, hold = play/pause. Decided on release, no timer."""
    global press_t
    ev = hw.keys.events.get()
    if not ev:
        return
    if ev.pressed:
        press_t = time.monotonic()
    elif time.monotonic() - press_t > HOLD_SECS:
        if sequencer.playing:
            sequencer.stop()
            save_params()
        else:
            sequencer.start()
    else:
        param_set.next_knobset()


def play_pads():
    """Pads transpose the sequence. Returns True if any pad changed."""
    events = hw.check_touch()
    for ev in events:
        if ev.pressed:
            # centred on the middle of the strip, so the pads go DOWN as
            # well as up -- tbish mapped pad number straight to semitones,
            # which only ever transposed upward.
            sequencer.transpose = ev.key_number - 7
    return bool(events)


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
    # Only while running: StepSequencer.stop() resets .i to 0, which would
    # otherwise park the dot on the last step instead of leaving it where
    # playback actually stopped.
    if sequencer.playing:
        ui.show_beat((sequencer.i - 1) % STEP_COUNT)  # .i already advanced
    ui.update()


load_params()

while True:
    sequencer.update()
    touched = play_pads()
    check_button()

    now = time.monotonic()
    if now - last_ui > UI_INTERVAL:
        last_ui = now
        update_ui()
        # not on a pass that just built a voice -- a full frame is ~9.6 ms
        # of I2C against an 11.6 ms mixer refill deadline
        if ui.dirty and not touched:
            display.refresh()
            ui.dirty = False
