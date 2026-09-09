# SPDX-FileCopyrightText: Copyright (c) 2025 Tod Kurt
# SPDX-License-Identifier: MIT
#
# pico_test_synth/ui.py -- two-knob parameter display for a 128x64 OLED
#
# A general two-pot UI over a synthtools ParamSet. OPTIONAL: the package
# does not import it, so a program that draws its own screen pays nothing
# for this one.
#
#     from pico_test_synth.ui import SynthUI
#
#     ui = SynthUI(display, param_set, param_text)
#     if ui.update("C3"):        # True if anything on screen changed
#         display.refresh()
#
# Shows the two params the pots are currently editing, as name + value +
# bar, plus a footer with the page number and the octave.
#
# Everything is built once, and update() compares before assigning: doing
# so re-renders the glyph bitmap and dirties the region even when the
# string is identical, so an unchanging screen sends no bytes at all.
#
# Two layout rules keep the cost down when something DOES change:
#
#   * The SSD1306 is addressed in 8-row pages and displayio rounds every
#     dirty rectangle out to a page boundary, so each element is aligned to
#     one; a label straddling three pages costs 50% more than one fitting
#     in two. terminalio.FONT is 6x12 with ascent 10, so a Label's top row
#     is `y - 5*scale`; the y values below come from that.
#   * Nothing is wider than one 64px column, so the biggest single transfer
#     is one scale-2 value label: 60px x 24 rows = 180 bytes, ~6 ms measured.
#     A value too long for that slot drops to scale 1 rather than growing;
#     see _set_value().

import displayio
import terminalio
import vectorio
from adafruit_display_text import bitmap_label as label

# x/y are label BASELINE-ish anchors; the comments give the rows each
# element actually paints, and which 8-row page(s) that lands in.
BAR_W = 58  # bar width in px
COL_X = (2, 66)  # left and right column origins
NAME_Y = 5  # scale 1 -> rows  0..11, pages 0-1
VALUE_Y = 26  # scale 2 -> rows 16..39, pages 2-4; 12px/char, 5 chars/column
BAR_Y = 40  # h=5     -> rows 40..44, page 5
TRACK_Y = 46  # h=1     -> row  46,     page 5 (under the bar, not behind it)
FOOTER_Y = 53  # scale 1 -> rows 48..59, pages 6-7


class SynthUI(displayio.Group):
    """Two-parameter knob display over a ``paramset.ParamSet``.

    Holds the ParamSet itself rather than copies, so there is nothing to
    keep in sync: whatever the pots wrote is what gets drawn.

    ``text_func(param)`` formats one param's value; it exists so a caller
    can special-case a param whose value is not really a number (the
    waveform index in the touch demo). Defaults to ``param.fmt % val``.
    """

    def __init__(self, display, param_set, text_func=None):
        super().__init__()
        self.display = display
        self.param_set = param_set
        self.text_func = text_func or (lambda p: p.fmt % p.val)
        #: sticky: set by update(), cleared by whoever calls display.refresh()
        self.dirty = True
        # Last (param, value) drawn per column, and the state behind the
        # footer. Compared BEFORE formatting anything: measured on an
        # rp2040 at 200 MHz, formatting unconditionally cost 2.9 ms on
        # every idle pass.
        self._seen = [None] * len(COL_X)
        self._seen_foot = None

        white = displayio.Palette(1)
        white[0] = 0xFFFFFF

        self.names = []
        self.values = []
        self.bars = []
        for x in COL_X:
            # the rail under each bar, so an empty bar still shows its range
            self.append(
                vectorio.Rectangle(pixel_shader=white, width=BAR_W, height=1, x=x, y=TRACK_Y)
            )
            bar = vectorio.Rectangle(pixel_shader=white, width=1, height=5, x=x, y=BAR_Y)
            name = label.Label(terminalio.FONT, text=" " * 9, color=0xFFFFFF, x=x, y=NAME_Y)
            val = label.Label(
                terminalio.FONT, text=" " * 5, color=0xFFFFFF, x=x, y=VALUE_Y, scale=2
            )
            self.append(bar)
            self.append(name)
            self.append(val)
            self.bars.append(bar)
            self.names.append(name)
            self.values.append(val)

        self.footer = label.Label(
            terminalio.FONT, text=" " * 16, color=0xFFFFFF, x=COL_X[0], y=FOOTER_Y
        )
        self.append(self.footer)
        display.root_group = self

    def _set_text(self, lbl, text):
        """Write only on a real change. Returns True if it wrote."""
        if lbl.text == text:
            return False
        lbl.text = text
        return True

    def _set_value(self, i, text):
        """Write one value, dropping to scale 1 if it will not fit at 2.

        The slot is 60px wide either way: five 12px characters at scale 2,
        or ten 6px ones at scale 1. Holding the width identical is what
        keeps a long value from widening the dirty region, and in the
        right-hand column from running off the screen entirely. Only a
        text_func returning names rather than numbers can trigger it.
        """
        lbl = self.values[i]
        if len(text) > 5:
            scale, text = 1, "%10.10s" % text
        else:
            scale, text = 2, "%5s" % text
        changed = False
        if lbl.scale != scale:
            lbl.scale = scale
            changed = True
        return self._set_text(lbl, text) or changed

    def update(self, oct_name=""):
        """Redraw from the ParamSet. Returns True if anything changed.

        Does NOT refresh the display: the caller picks the moment, so
        the I2C burst can be kept out of the same pass as a note-on.
        """
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
            # Fixed-width text keeps each label's bitmap the same size from
            # one write to the next, so the dirty region never grows.
            changed |= self._set_text(self.names[i], "%-9s" % p.name)
            changed |= self._set_value(i, self.text_func(p))
            # vectorio rejects a zero width, so an empty bar is 1 px
            w = int(BAR_W * (p.val - p.vmin) / p.span)
            w = min(max(w, 1), BAR_W)
            if self.bars[i].width != w:
                self.bars[i].width = w
                changed = True

        # same trick as above: only build the string when its state moved
        foot = (ps.idx, oct_name)
        if foot != self._seen_foot:
            self._seen_foot = foot
            changed |= self._set_text(
                self.footer, "P%d/%d  %s" % (ps.idx + 1, ps.nknobsets, oct_name)
            )

        self.dirty = self.dirty or changed
        return changed
