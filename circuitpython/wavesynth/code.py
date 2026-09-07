# SPDX-FileCopyrightText: Copyright (c) 2024 Tod Kurt
# SPDX-License-Identifier: MIT
#
# wavesynth -- wavetable polysynth with saveable patches, for
# pico_test_synth / pico_test_synth2
#
# A wavetable synth on synthtools' WavetableSynth: WavePos moves within
# the wavetable and morphs live, WaveSel picks which of the .WAVs in
# wavetables/, and the two motion knobs (FiltLFO / FiltRate) drive the
# FILTER LFO.
#
# The UI (synthui.py, gauge_cluster.py, param_scaler.py, param.py) stays
# local to this folder.
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

import asyncio
import os
import sys
import time

import tmidi
import usb_midi

from param import ParamChoice, ParamRange
from pico_test_synth.hardware import Hardware
from synthtools import Patch, WavetableSynth, load_patches, save_patches
from synthui import SynthUI, splash_screen

if sys.platform == "RP2040":
    import microcontroller

    microcontroller.cpu.frequency = 250_000_000

PATCHES_FILE = "/wavesynth_patches.json"
WAVE_DIR = "/wavetables"
touch_midi_notes = list(range(45, 45 + 16))

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


def set_octave(v):
    global octave
    octave = int(v)


def wave_idx():
    try:
        return WAVES.index(synth.wave_file)
    except ValueError:
        return 0


# --- the 14 parameters, in gauge order -----------------------------------
# IMPORTANT: these setters and getters talk to the SYNTH, not the patch.
# synthtools keeps a Patch inert (a property setter never writes back to
# it) so reading the patch here would show stale values.
params = (
    # Pair 0
    ParamRange("FiltFreq", "filter frequency", synth.filt_f, "%4d", 60, 8000,
               setter=lambda x: setattr(synth, "filt_f", x),
               getter=lambda: synth.filt_f),
    ParamRange("FilterRes", "filter resonance", synth.filt_q, "%1.2f", 0.6, 6.0,
               setter=lambda x: setattr(synth, "filt_q", x),
               getter=lambda: synth.filt_q),

    # Pair 1
    ParamRange("WavePos", "wavetable position", synth.wave_pos, "%1.2f", 0, 8,
               setter=lambda x: setattr(synth, "wave_pos", x),
               getter=lambda: synth.wave_pos),
    ParamChoice("WaveSel", "wavetable file", wave_idx(),
                [w.split("/")[-1].replace(".WAV", "") for w in WAVES],
                setter=lambda x: setattr(synth, "wave_file", WAVES[int(x)]),
                getter=wave_idx),

    # Pair 2
    ParamRange("AmpAtk", "amp attack time", synth.attack_time, "%1.2f", 0.0, 3.0,
               setter=lambda x: setattr(synth, "attack_time", x),
               getter=lambda: synth.attack_time),
    ParamRange("AmpRls", "amp release time", synth.release_time, "%1.2f", 0.0, 3.0,
               setter=lambda x: setattr(synth, "release_time", x),
               getter=lambda: synth.release_time),

    # Pair 3
    ParamRange("FiltAtk", "filter env attack", synth.fenv_attack, "%1.2f", 0.01, 3.0,
               setter=lambda x: setattr(synth, "fenv_attack", x),
               getter=lambda: synth.fenv_attack),
    ParamRange("FiltRls", "filter env release", synth.fenv_release, "%1.2f", 0.01, 3.0,
               setter=lambda x: setattr(synth, "fenv_release", x),
               getter=lambda: synth.fenv_release),

    # Pair 4
    ParamRange("FiltEnv", "filter env amount", synth.fenv_amount, "%4d", -4000, 6000,
               setter=lambda x: setattr(synth, "fenv_amount", x),
               getter=lambda: synth.fenv_amount),
    ParamChoice("FiltType", "filter type", 0, FILTER_TYPES,
                setter=lambda x: setattr(synth, "filt_type", FILTER_TYPES[int(x)]),
                getter=lambda: FILTER_TYPES.index(synth.filt_type)),

    # Pair 5, the filter LFO
    ParamRange("FiltLFO", "filter lfo amount", synth.filt_lfo_amount, "%4d", 0, 4000,
               setter=lambda x: setattr(synth, "filt_lfo_amount", x),
               getter=lambda: synth.filt_lfo_amount),
    ParamRange("FiltRate", "filter lfo rate", synth.filt_lfo_rate, "%2.1f", 0.0, 8.0,
               setter=lambda x: setattr(synth, "filt_lfo_rate", x),
               getter=lambda: synth.filt_lfo_rate),

    # Pair 6, neither of these is a synth parameter
    ParamRange("Octave", "octave range", 0, "%d", -3, 2,
               setter=set_octave,
               getter=lambda: octave),
    ParamRange("Volume", "volume", hw.get_volume(), "%1.2f", 0.1, 1.0,
               setter=lambda x: hw.set_volume(min(max(x, 0), 1)),
               getter=hw.get_volume),
)


def update_params():
    """Pull every param's value back from what it represents."""
    for p in params:
        p.update()


def save_patches_action():
    v = hw.get_volume()
    hw.set_volume(0)
    time.sleep(0.2)
    synthui.set_patch_name("Saving...")
    hw.display.refresh()
    # the knobs wrote the SYNTH, not the patch, without this the file
    # gets the values the patch was loaded with
    synth.save_patch()
    try:
        save_patches(patches, PATCHES_FILE)
    except OSError:
        print("could not write", PATCHES_FILE, "-- is boot.py remounting /?")
    synthui.set_patch_name(patch.name)
    hw.set_volume(v)


def load_patches_action(patchidx):
    global patch
    patch = patches[patchidx]
    synth.all_notes_off()
    synth.load_patch(patch)
    update_params()  # read the new values back off the synth
    synthui.set_patch_name(patch.name)
    synthui.refresh_gauge_cluster()
    print("loaded patch #", patchidx)


update_params()
# read_pots() is 0.0-1.0; GaugeCluster and ParamScaler work in 0-255
knobA, knobB = (v * 255 for v in hw.read_pots())
synthui = SynthUI(hw.display, params, knobA, knobB)
synthui.set_patch_name(patch.name)


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
    p = 0  # which param pair we're looking at

    while True:
        hw.display.refresh()

        knobA, knobB = hw.read_pots()
        synthui.setA(knobA * 255)
        synthui.setB(knobB * 255)

        if button := hw.check_button():
            if button.pressed:
                button_held = True
            if button.released:
                # only advance the UI if not doing a patch-load gesture
                if not button_with_touch:
                    p = (p + 1) % (synthui.num_params // 2)
                    synthui.select_pair(p)
                    print("select param pair:", p)
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
        await asyncio.sleep(0.01)


print("--- pico_test_synth wavesynth ready ---")


async def main():
    await asyncio.gather(
        asyncio.create_task(ui_handler()),
        asyncio.create_task(midi_handler()),
    )


asyncio.run(main())
