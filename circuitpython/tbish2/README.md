# TBish2 synth

A TB-303 inspired monophonic bass synth — [`tbish/`](../tbish/) rebuilt on
[`synthtools`](https://github.com/todbot/CircuitPython_SynthTools)'
`BasslineSynth`.

Video demo of the original: https://www.youtube.com/watch?v=1AflpXbEIno

## Why this exists

`BasslineSynth` is a direct port of `tbish/tbish_synth.py` into the
library, and along the way it finished the four `# FIXME` items still
sitting in that file's `note_on_step()`. So `tbish2` is the same
instrument with:

- **accent → resonance** (`accent_q`) and **accent → cutoff**
  (`accent_cutoff`), not just accent → level
- **a real `slide_time`** instead of a hardcoded 0.1 s
- keyboard tracking, and the accent applied without contaminating the
  patch (it writes spare block inputs, so `filt_f`/`filt_q` still read
  back clean)

Four of tbish's eight files are gone into the library:

| `tbish/` | here |
|---|---|
| `tbish_synth.py` | `synthtools.BasslineSynth` |
| `tbish_sequencer.py` | `synthtools.step_sequencer.StepSequencer` |
| `paramset.py` | `synthtools.paramset` |
| `pitch_glider.py` | dropped — slide is `Synth.mono` + `glide_time` |
| `synth_setup_pts.py` | `pico_test_synth.Hardware`, shared |

`tbish/` is left exactly as it was.

## Controls

- **tap the button** — next pair of parameters (9 pages)
- **hold the button** — play / pause, and save the knobs to `/tbish2.json`
- **touch a pad** — transpose the sequence, −7..+8 semitones

The pots use `ParamSet`'s PICKUP mode: after a page change a pot does
nothing until it passes the value the parameter already has, so the sound
never jumps when you turn one.

## Install

Copy `code.py`, `tbish_ui.py` and `boot.py` to the CIRCUITPY root, then
install the libraries from `circuitpython/`:

```
circup install -r requirements.txt
```

That covers the local `lib/pico_test_synth` board package too — circup
installs from a path as readily as from the bundle.

`boot.py` is what makes the filesystem writable from the board's side.
Without it, saving the knobs on pause fails and the demo prints a note
saying so — everything else works fine.

```
circup install synthtools adafruit_display_text \
               adafruit_displayio_ssd1306 adafruit_debouncer
```

Needs a build with `audiofilters` and `audiodelays` for the 24 dB filter,
drive and delay. Without them it still runs on the voice's own 12 dB
Biquad and says so at boot. Distortion is enabled on RP2350 only —
`tbish/tbish_synth.py` found it too expensive for an RP2040.

## Two parameters changed units from `tbish`

Not renames — if you carry numbers over by hand, convert them:

- **`decay`** was a 0–1 fraction of the step time; it is now **seconds**,
  and it drives the *filter* fall only. The amp's decay is its own knob
  (`ampdec`) and wants to stay *longer*, or the note fades out at the same
  rate the cutoff falls and the sweep is masked.
- **`dtime`** was 0–1 seconds; `fx_delay_ms` is **milliseconds** (max
  1000).

## Notes

Same 303 research links as the original: see [`../tbish/README.md`](../tbish/README.md).
