# pico_test_synth

Board support for the pico_test_synth / pico_test_synth2 boards.

Install with `circup install -r requirements.txt` from `circuitpython/`,
which picks this up as a local path.

- `hardware.py` -- the `Hardware` class: audio, pots, button, 16 touch
  pads, OLED, TRS MIDI UART, LED. Everything a program needs from the
  board.
- `ui.py` -- `SynthUI`, a general two-pot parameter display over a
  synthtools `ParamSet`. Optional, and not imported by the package;
  programs are free to draw their own screen instead.

```python
from pico_test_synth import Hardware

hw = Hardware()                  # audio running; 22050 stereo by default
display = hw.setup_display()     # opt-in
hw.setup_touch("up")             # opt-in: "down" for pico_test_synth1
```
