# CircuitPython apps for pico_test_synth

CircuitPython demos for the pico_test_synth and pico_test_synth2 boards.

* [`hwtest`](hwtest/) - canonical hardware/pin reference for this board and a simple synth. Start here. 
* [`synthtools_polysynth`](synthtools_polysynth/) - 16-pad chromatic polysynth based on `SubtractiveSynth`, 18 parameters grouped into 6 named sections, two pots per pair, USB and TRS MIDI in/out
* [`synthtools_swarm`](synthtools_swarm/) - `SwarmSynth` drone — up to 8 detuned oscillators per note 
* [`synthtools_arp`](synthtools_arp/) - hold pads, `Arpeggiator` plays them back 
* [`wavesynth`](wavesynth/) - wavetable polysynth with 9 saveable patches 
* [`tbish`](tbish/) - TB-303-like monosynth with step-sequencer
* [`tbish2`](tbish2/) - TB-303-style acid bassline on `BasslineSynth`, with a step sequencer. Will try to use `audiofilters`/`audiodelays` for fatter sound
* [`synth1`](synth1/) - small demo synth: filter sweeps, detune, MIDI in 



## Install

You can use circup to install needed libraries:
```
circup install -r requirements.txt
```

For each demo, copy the contents of the directory flat onto the CIRCUITPY
root and reset.

The MIDI demos need tmidi 3.0 or later, which installs as a `lib/tmidi/`
folder. Delete an old `lib/tmidi.mpy` when upgrading.


## Building a UF2 for an app

`make_uf2.py` builds one UF2 holding both CircuitPython and an app's
CIRCUITPY drive. Flash it like any UF2 and the board boots straight
into the app, with no copying files or installing libraries.

    python3 make_uf2.py adafruit-circuitpython-...-en_US-11.0.0.uf2 wavesynth

It takes a CircuitPython firmware UF2 and an app folder, then:

- reads the board, CircuitPython version and drive address from the
  firmware with `picotool`
- copies the app folder to the drive root, skipping `README.md`,
  `__pycache__`, `.uf2` files and dot files
- copies the local entries in `requirements.txt` (`lib/pico_test_synth`)
  to `/lib`, or a single local `.py` to the drive root unless the app
  has its own copy
- installs the rest of `requirements.txt` into `/lib` with `circup`,
  matched to that board and CircuitPython version
- builds the drive and joins it to the firmware with `folder2uf2`,
  using the drive address and size from the firmware

The output is `<app>-<board>.uf2` unless `-o` names it. It writes the
firmware and only the used part of the drive, so it stays small; the
new drive replaces whatever was there. `--full` writes the whole drive
instead, wiping any leftover data.

Options:

- `-o FILE` - output UF2
- `-a PATH` - also put a file or folder at the drive root (repeatable)
- `-r FILE` - a different requirements file
- `--flash-size N` - flash size in bytes, if not 2MB (RP2040) or 4MB
  (RP2350)
- `--full` - write the whole drive, not just its used part
- `--keep` - keep the staged drive folder, to see what went in

Needs `picotool`, `circup` and `folder2uf2`. With Homebrew:

    brew install picotool && pip3 install circup folder2uf2

The GitHub Action in `.github/workflows/build-uf2.yml` runs this for
every app, for both Pico and Pico 2, against the latest CircuitPython
11.x when a release is published, and attaches the UF2s to the release.


## Notes

### Sample rate

These demos run at 22050 Hz sample rate in stereo, this works on RP2040 (Pico)
and RP2350 (Pico2). The Pico2 can do 44100 Hz sample rate. 

Every demo sets `FILT_F_MAX` on its synth subclass before constructing it to
be below the Nyquist frequency for the sample rate (e.g. 11 kHz for 22050 Hz),
since filter frequency above Nyquist is undefined. 
