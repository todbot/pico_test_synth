# SPDX-FileCopyrightText: Copyright (c) 2024 Tod Kurt
# SPDX-License-Identifier: MIT
#
# wavesynth -- wavetable polysynth with saveable patches, for
# pico_test_synth / pico_test_synth2
#
# A wavetable synth on synthtools' WavetableSynth: WavePos moves within
# the wavetable and morphs live, WaveSel picks which of the .WAVs in
# wavetables/, and there are two LFOs with an amount and a rate each --
# FiltLFO/FiltRate over the filter cutoff, WaveLFO/WaveRate sweeping
# WavePos up through the table.
#
# The UI is lib/pico_test_synth's general two-pot SynthUI; the footer
# carries the patch name where it used to have its own header line.
#
# Patches live in PATCHES_FILE below. The old saved_patches.json uses an
# incompatible schema and is left on disk untouched.
#
# Copy the contents of this folder (including wavetables/) to the
# CIRCUITPY root, then, from circuitpython/:
#
#   circup install -r requirements.txt
#
# That pulls synthtools, tmidi, adafruit_wave and the local
# lib/pico_test_synth that Hardware comes from.

import sys
if sys.platform == "RP2040":
    import microcontroller
    microcontroller.cpu.frequency = 250_000_000

import asyncio
import os
import time

import tmidi
import usb_midi

from pico_test_synth.hardware import Hardware
from pico_test_synth.ui import SynthUI
from synthtools import Patch, WavetableSynth, load_patches, save_patches
from synthtools.paramset import Param, ParamSet

PATCHES_FILE = "/wavesynth_patches.json"
WAVE_DIR = "/wavetables"
touch_midi_notes = list(range(45, 45 + 16))


def splash_screen(display):
    """Boot screen, up until SynthUI takes the display over."""
    # imported here rather than at the top: nothing else in this program
    # draws, so the modules are only worth their RAM for this one call
    import displayio
    import terminalio
    from adafruit_display_text import bitmap_label as label

    g = displayio.Group()
    g.append(label.Label(terminalio.FONT, text="pico_test_synth", color=0xFFFFFF, x=1, y=10))
    g.append(label.Label(terminalio.FONT, text="wavesynth", color=0xFFFFFF, x=1, y=30, scale=2))
    g.append(label.Label(terminalio.FONT, text="@todbot", color=0xFFFFFF, x=1, y=50))
    display.root_group = g
    display.refresh()


print("hardware...")
# not Hardware's headphone-friendly 0.25 default; the Volume gauge
# would then read 0.25 at boot
hw = Hardware(volume=1.0)
splash_screen(hw.setup_display())
hw.setup_touch("up")        # "down" for a pico_test_synth1 with a Pico 1
hw.setup_midi_uart()
time.sleep(1)  # let USB quiet down (when debugging)

midi_usb = tmidi.MIDI(midi_in=usb_midi.ports[0])
midi_uart = tmidi.MIDI(midi_in=hw.midi_uart, midi_out=hw.midi_uart)


def wave_files():
    """The wavetable WAVs on the device, as full paths."""
    try:
        names = sorted(f for f in os.listdir(WAVE_DIR) if f.endswith(".WAV"))
    except OSError:
        names = []
    if not names:
        raise RuntimeError("no .WAV wavetables found in " + WAVE_DIR)
    return [WAVE_DIR + "/" + n for n in names]


WAVES = wave_files()
FILTER_TYPES = ("LPF", "HPF", "BPF", "NOTCH")


def default_patches():
    """Nine starting patches, spread across the wavetables on the card."""
    out = []
    for i in range(9):
        out.append(
            Patch(
                name="patch%d" % (i + 1),
                synth_type="wavetable",
                wave_file=WAVES[i % len(WAVES)],
                wave_pos=0,
                filt_type="LPF",
                filt_f=2345,
                filt_q=1.1,
                amp_env=[0.01, 0.1, 0.9, 0.5],
                fenv_amount=1500,
                fenv_attack=0.2,
                fenv_release=0.6,
            )
        )
    return out


try:
    patches = load_patches(PATCHES_FILE)
except (OSError, ValueError):
    patches = []
if patches:
    print("loaded", len(patches), "patches")
else:
    print("no patches, making up some")
    patches = default_patches()

key_number_to_patch = (1, 0, 2, 0, 3, 4, 0, 5, 0, 6, 0, 7, 8, 0, 9, 0)

patch = patches[0]

# a Biquad above Nyquist is undefined; the clamp is baked into the block
# graph at build time, so this must be set before constructing
WavetableSynth.FILT_F_MAX = hw.sample_rate * 0.45

synth = WavetableSynth(hw.synth, patch)
octave = 0  # app state, not a synth parameter


def wave_idx():
    try:
        return WAVES.index(synth.wave_file)
    except ValueError:
        return 0


def wave_top():
    """Highest legal wave_pos in the file that is loaded right now.

    Read off the Wavetable because it is per-FILE: selecting a different
    .WAV changes how many waves there are to move between. There is no
    public accessor for it on the synth.
    """
    return max(synth._wavetable.num_waves - 1, 1)


def sync_wave_ranges():
    """Re-range the two params that index into the wavetable.

    Called when WaveSel loads a different file: their old maximum may now
    be off the end of it, and a param left above its own vmax would draw a
    bar past the end of the track.
    """
    top = wave_top()
    for name in ("WavePos", "WaveLFO"):
        q = param_set.param_for_name(name)
        q.vmax = top
        if q.val > top:
            q.val = top
            q.apply_to_obj(synth)


# --- the 16 parameters, in knob-pair order -------------------------------
# Two pots, so PARAMS[0:2] are pair 1, PARAMS[2:4] pair 2, and so on.
#
# IMPORTANT: these are seeded from, and written back to, the SYNTH, not the
# patch. synthtools keeps a Patch inert (a property setter never writes back
# to it) so reading the patch here would show stale values.
#
# Four of them cannot be a plain setattr and so carry no objattr: two are
# INDEXES into a list of names, and two are not synth parameters at all.
# apply_param() and read_param() below are the two halves of handling them.
# fmt: off
PARAMS = [
    # Pair 0
    Param("FiltFreq",  synth.filt_f,          60,   8000,  "%4d",   "filt_f"),
    Param("FilterRes", synth.filt_q,          0.6,    6.0, "%1.2f", "filt_q"),

    # Pair 1
    Param("WavePos",   synth.wave_pos,        0, wave_top(), "%1.2f", "wave_pos"),
    Param("WaveSel",   wave_idx(),            0, len(WAVES) - 1, "%.0f", None),

    # Pair 2, the wavetable LFO, the WavePos counterpart of pair 5: it
    # sweeps wave_pos up towards WaveLFO at WaveRate. A ceiling at or below
    # WavePos means no sweep at all, which is what 0 gives you.
    Param("WaveLFO",   synth.wave_pos_max,    0, wave_top(), "%1.2f", "wave_pos_max"),
    Param("WaveRate",  synth.wave_lfo_rate,   0.0,    8.0, "%2.1f", "wave_lfo_rate"),

    # Pair 3
    Param("AmpAtk",    synth.attack_time,     0.0,    3.0, "%1.2f", "attack_time"),
    Param("AmpRls",    synth.release_time,    0.0,    3.0, "%1.2f", "release_time"),

    # Pair 4
    Param("FiltAtk",   synth.fenv_attack,     0.01,   3.0, "%1.2f", "fenv_attack"),
    Param("FiltRls",   synth.fenv_release,    0.01,   3.0, "%1.2f", "fenv_release"),

    # Pair 5
    Param("FiltEnv",   synth.fenv_amount,  -4000,   6000,  "%4d",   "fenv_amount"),
    Param("FiltType",  FILTER_TYPES.index(synth.filt_type),
                                              0, len(FILTER_TYPES) - 1, "%.0f", None),
    # Pair 6, the filter LFO
    Param("FiltLFO",   synth.filt_lfo_amount, 0,   4000,   "%4d",   "filt_lfo_amount"),
    Param("FiltRate",  synth.filt_lfo_rate,   0.0,    8.0, "%2.1f", "filt_lfo_rate"),

    # Pair 7, neither of these is a synth parameter
    Param("Octave",    octave,               -2,      2,   "%d",    None),
    Param("Volume",    hw.get_volume(),       0.1,    1.0, "%1.2f", None),
]
# fmt: on

# KNOB_SCALE, not the default KNOB_PICKUP: a turn always moves the value,
# scaled so knob and value reach the ends together, instead of the pot being
# dead until it crosses. It also replaces the pre-fix ParamScaler this
# program used to vendor, which snapped unconditionally and had no deadband.
param_set = ParamSet(PARAMS, num_knobs=2, knob_mode=ParamSet.KNOB_SCALE)

# what the wavetable files are called, without the path or the extension
WAVE_NAMES = [w.split("/")[-1].replace(".WAV", "") for w in WAVES]


def apply_param(p):
    """Push one param onto whatever it represents.

    Discrete params select with round(), not int(): ParamSet's deadband
    leaves a full-scale knob a hair under vmax, which int() would truncate
    to vmax - 1, making the last choice unreachable.
    """
    global octave
    if p.name == "WaveSel":
        synth.wave_file = WAVES[round(p.val)]   # index -> full path
        sync_wave_ranges()                      # a new file, a new wave count
    elif p.name == "FiltType":
        synth.filt_type = FILTER_TYPES[round(p.val)]
    elif p.name == "Octave":
        octave = round(p.val)
    elif p.name == "Volume":
        hw.set_volume(min(max(p.val, 0), 1))
    else:
        p.apply_to_obj(synth)                   # plain setattr via p.objattr


def read_param(p):
    """The inverse of apply_param: what does this param represent right now?

    Only loading a patch needs it. The knobs write the synth, so after
    load_patch() every value has moved and the ParamSet has no idea.
    """
    if p.name == "WaveSel":
        p.val = wave_idx()
    elif p.name == "FiltType":
        p.val = FILTER_TYPES.index(synth.filt_type)
    elif p.name == "Octave":
        p.val = octave
    elif p.name == "Volume":
        p.val = hw.get_volume()
    elif p.objattr:
        p.val = getattr(synth, p.objattr)


def param_text(p):
    """Format one param for the screen. The two index params show a name.

    Wavetable names go out in full: SynthUI drops a value longer than five
    characters to scale 1, which is how the UI this replaced handled them.

    Octave rounds because apply_param does. "%d" truncates towards zero, so
    without this the number on screen changes at different knob positions
    from the octave you are actually playing in.
    """
    if p.name == "WaveSel":
        return WAVE_NAMES[round(p.val)]
    if p.name == "FiltType":
        return FILTER_TYPES[round(p.val)]
    if p.name == "Octave":
        return "%d" % round(p.val)
    return p.fmt % p.val


def update_params():
    """Pull every param's value back from what it represents."""
    for p in PARAMS:
        read_param(p)


# SynthUI's footer is "P<pair>/<pairs>  <text>", and this is the text: the
# patch name normally, a status line while saving.
foot = patch.name


def show_footer(text):
    """Put text in the footer and get it on screen now, not next pass."""
    global foot
    foot = text
    ui.update(foot)
    hw.display.refresh()
    ui.dirty = False


def save_patches_action():
    v = hw.get_volume()
    hw.set_volume(0)
    time.sleep(0.2)
    show_footer("Saving")
    # the knobs wrote the SYNTH, not the patch, without this the file
    # gets the values the patch was loaded with
    synth.save_patch()
    try:
        save_patches(patches, PATCHES_FILE)
    except OSError:
        print("could not write", PATCHES_FILE, "-- is boot.py remounting /?")
    show_footer(patch.name)
    hw.set_volume(v)


def load_patches_action(patchidx):
    global patch
    patch = patches[patchidx]
    synth.all_notes_off()
    synth.load_patch(patch)
    update_params()  # read the new values back off the synth
    # The pots have not moved but everything under them has. Without this
    # the next nudge of a knob would snap its param back to where the pot is
    # sitting and undo that much of the patch.
    param_set.is_tracking = [False] * param_set.nknobs
    show_footer(patch.name)
    print("loaded patch #", patchidx)


update_params()
for _p in PARAMS:
    if _p.objattr and _p.objattr not in synth._PARAMS:
        raise ValueError("no such synth parameter: '%s'" % _p.objattr)
    if len(_p.name) > 9:
        raise ValueError("param name too wide for the screen: '%s'" % _p.name)
ui = SynthUI(hw.display, param_set, param_text)


def draw(touched):
    """Redraw, and put it on the wire only if that changed anything.

    A full frame is ~31 ms against the mixer's 11.6 ms refill deadline, so
    never on a pass that just built a voice, and never when nothing moved.
    This program used to refresh unconditionally, every time round the loop.
    """
    ui.update(foot)
    if ui.dirty and not touched:
        hw.display.refresh()
        ui.dirty = False


def read_knobs():
    """Read the pots, push only what actually moved onto the synth."""
    knobs = hw.read_pots()  # filtered, 0.0-1.0
    i = param_set.idx * param_set.nknobs
    pair = PARAMS[i : i + param_set.nknobs]
    before = [p.val for p in pair]
    param_set.update_knobs(knobs)  # scaled takeover, always moves
    for p, was in zip(pair, before):
        if p.val != was:  # only a real move gets applied
            apply_param(p)


async def midi_handler():
    while True:
        while msg := (midi_usb.receive() or midi_uart.receive()):
            if msg.type == tmidi.NOTE_ON and msg.velocity:
                synth.note_on(msg.note, msg.velocity)
                hw.set_led(0xFF00FF)
            elif msg.type in (tmidi.NOTE_OFF, tmidi.NOTE_ON):
                synth.note_off(msg.note)
                hw.set_led(0x000000)
            elif msg.type == tmidi.CC:
                # tmidi names the note bytes but not the CC ones
                if msg.data0 == 74:  # filter cutoff
                    synth.filt_f = 60 + msg.data1 / 127 * 7940
                elif msg.data0 == 1:  # mod wheel -> wavetable position
                    synth.wave_pos = msg.data1 / 127 * 8
                elif msg.data0 in (120, 123):
                    synth.all_notes_off()
        await asyncio.sleep(0.01)


async def ui_handler():
    notes_pressed = [None] * len(hw.touchins)
    button_held = False
    button_with_touch = False

    while True:
        read_knobs()

        if button := hw.check_button():
            if button.pressed:
                button_held = True
            if button.released:
                # only advance the UI if not doing a patch-load gesture
                if not button_with_touch:
                    param_set.next_knobset()
                button_held = False
                button_with_touch = False

        if touches := hw.check_touch():
            for touch in touches:
                if touch.pressed:
                    if button_held:  # load or save a patch
                        button_with_touch = True
                        patchidx = key_number_to_patch[touch.key_number]
                        if touch.key_number == 15:  # save key
                            save_patches_action()
                        elif patchidx > 0:
                            load_patches_action(patchidx - 1)
                    else:  # trigger a note
                        button_with_touch = False
                        midi_note = touch_midi_notes[touch.key_number] + octave * 12
                        notes_pressed[touch.key_number] = midi_note
                        synth.note_on(midi_note)
                        hw.set_led(0xFF00FF)

                if touch.released and not button_with_touch:
                    midi_note = notes_pressed[touch.key_number]
                    if midi_note is not None:
                        synth.note_off(midi_note)
                        notes_pressed[touch.key_number] = None
                    hw.set_led(0)

        draw(touched=bool(touches))
        await asyncio.sleep(0.01)

async def synth_handler():
    while True:
        synth.update()
        await asyncio.sleep(0.01)
        
print("--- pico_test_synth wavesynth ready ---")


async def main():
    await asyncio.gather(
        asyncio.create_task(ui_handler()),
        asyncio.create_task(midi_handler()),
        asyncio.create_task(synth_handler()),
    )


asyncio.run(main())
