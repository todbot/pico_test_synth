# SPDX-FileCopyrightText: Copyright (c) 2025 Tod Kurt
# SPDX-License-Identifier: MIT
#
# tbish_ui.py -- two-knob parameter display plus a step dot, 128x64 OLED
#
# The step dot is why this is not just pico_test_synth.ui: a sequencer
# wants a beat readout across the bottom of the screen, which SynthUI's
# single-line footer has no room for. Same display economy as that file:
#
#   * update() does NOT refresh. The caller picks the moment, so the
#     ~9.6 ms I2C burst never lands in the same pass that built a voice.
#   * Compare the raw value BEFORE formatting: measured at 2.9 ms per
#     idle pass, against 0.24 ms for the float compare.
#   * `dirty` is sticky: set here, cleared by whoever refreshes.

import displayio
import terminalio
import vectorio
from adafruit_display_text import bitmap_label as label

FNT = terminalio.FONT
WHITE = 0xFFFFFF

COL_X = (1, 75)  # left and right column origins
NAME_Y = 8  # scale 1
VALUE_Y = 24  # scale 2
PAGE_Y = 5  # page dot
STEP_Y = 60  # step dot
STEP_X0, STEP_DX = 5, 6


class TBishUI(displayio.Group):
    """Two-parameter knob display over a ``synthtools.paramset.ParamSet``.

    Holds the ParamSet rather than copies of its values, so there is
    nothing to keep in sync: whatever the pots wrote is what gets drawn.

    ``text_func(param)`` formats one param's value, so a caller can
    special-case one whose value is not really a number (the waveform
    index). Defaults to ``param.fmt % param.val``.
    """

    def __init__(self, display, param_set, text_func=None):
        super().__init__()
        self.display = display
        self.param_set = param_set
        self.text_func = text_func or (lambda p: p.fmt % p.val)
        #: sticky: set by update()/show_beat(), cleared by the refresher
        self.dirty = True
        self._seen = [None] * len(COL_X)
        self._seen_page = None
        self._step = -1

        palette = displayio.Palette(1)
        palette[0] = WHITE

        self.page_dot = vectorio.Rectangle(
            pixel_shader=palette, width=4, height=4, x=45, y=PAGE_Y
        )
        self.step_dot = vectorio.Rectangle(
            pixel_shader=palette, width=5, height=5, x=STEP_X0, y=STEP_Y
        )
        self.append(self.page_dot)
        self.append(self.step_dot)

        self.names = []
        self.values = []
        for x in COL_X:
            name = label.Label(FNT, text=" " * 8, color=WHITE, x=x, y=NAME_Y)
            val = label.Label(FNT, text=" " * 4, color=WHITE, x=x, y=VALUE_Y, scale=2)
            self.append(name)
            self.append(val)
            self.names.append(name)
            self.values.append(val)

        self.logo = label.Label(FNT, text="TBishBassSynth", color=WHITE, x=20, y=45)
        self.append(self.logo)

    def _set_text(self, lbl, text):
        """Write only on a real change. Returns True if it wrote."""
        if lbl.text == text:
            return False
        lbl.text = text
        return True

    def show_beat(self, step):
        """Move the step dot. Cheap enough to call every pass."""
        if step == self._step:
            return
        self._step = step
        self.step_dot.x = STEP_X0 + step * STEP_DX
        self.dirty = True

    def update(self):
        """Redraw from the ParamSet. Returns True if anything changed."""
        ps = self.param_set
        changed = False
        for i in range(len(COL_X)):
            p = ps.params[ps.idx * ps.nknobs + i]
            # Identity catches a page turn, the float compare catches a
            # knob move. Anything else stops here, with no formatting.
            seen = self._seen[i]
            if seen is not None and seen[0] is p and seen[1] == p.val:
                continue
            self._seen[i] = (p, p.val)
            # Fixed-width text keeps each bitmap the same size from one
            # write to the next, so the dirty region never grows.
            changed |= self._set_text(self.names[i], "%-8s" % p.name)
            changed |= self._set_text(self.values[i], "%4s" % self.text_func(p))

        if ps.idx != self._seen_page:
            self._seen_page = ps.idx
            self.page_dot.x = 45 + 4 * ps.idx
            changed = True

        self.dirty = self.dirty or changed
        return changed
