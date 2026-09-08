# SPDX-FileCopyrightText: Copyright (c) 2025 Tod Kurt
# SPDX-License-Identifier: MIT
#
# pico_test_synth/ui_list.py -- scrolling parameter list for a 128x64 OLED
#
# An alternative to ui.py's two-pot screen: four params visible at once as
# name / bar / value, the left pot moving a cursor through the whole list,
# the right pot editing whatever the cursor lands on. OPTIONAL, like ui.py;
# the package does not import it.
#
#     from pico_test_synth.ui_list import ListUI
#
#     ui = ListUI(display, param_set, param_text)
#     ui.select(knobA)                    # cursor
#     param_set.update_knobs((knobB,))    # edit
#     if not ui.scrolled:
#         ui.update("C3")
#
# The ParamSet must be built with num_knobs=1, which makes param_set.idx the
# cursor index and gets the soft-takeover reset for free: idx's setter clears
# is_tracking, which is exactly what should happen when the cursor moves.
#
# Measured on an rp2040 at 200 MHz, SSD1306 on I2C at 1 MHz, as
# update() + refresh() in ms. The mixer's refill deadline is 11.6 ms and a
# 16-pad scan spends 4.4 of it:
#
#            this          ui.py's two-pot screen
#   idle     0.3           0.2
#   edit     6.7 +  4.4    6.6 +  9.9
#   move     5.8 +  4.2   32.2 + 28.8   (cursor here, a page turn there)
#   scroll  55.3 + 35.5    --
#
# So editing and navigating are both cheaper than what they replace; only
# the scroll is dearer, and unlike a page turn it is not the only way to get
# anywhere. Nothing here fits 11.6 ms except the idle pass, which is also
# true of ui.py: a page turn there is 61 ms.
#
# A refresh costs ~0.6 ms per dirty area plus ~0.03 ms per byte, a byte being
# one column of an 8-row page, so WIDTH is what a layout pays for. Two things
# follow. The cursor is a moved 3px rectangle and not an inverted row, which
# would send a full-width row twice for the cheapest interaction there is.
# And this uses bitmap_label even though adafruit_display_text.label assigns
# text faster: label is a TileGrid that dirties one area per changed GLYPH,
# and it costs more RAM, not less. See CircuitPython_Synth_Tools'
# tests/hw/test_display_cost.py, which measures all of it.
#
# A scroll cannot be made to fit, so the caller gets `scrolled` and owes it
# passes with no pad scan in them; see synthtools_polysynth/code.py.
#
# Everything else follows ui.py: built once, compared before assigning, and
# formatted in fixed widths so a label's bitmap never changes size.
#
# The 12px row pitch cannot align to the SSD1306's 8-row pages: a row
# straddles two wherever it sits. 16px would align but costs a whole row and
# saves nothing, since neither the edit nor the scroll case is page-bound.

import displayio
import terminalio
import vectorio
from adafruit_display_text import bitmap_label as label

ROWS = 4  # param rows below the header
ROW_H = 12  # terminalio.FONT is 6x12
ROW_TOP = 12  # first param row's top pixel; above it is the header
HEAD_Y = 5  # scale 1 -> rows 0..11
NAME_X = 5  # 8 chars -> x 5..53
BAR_X = 56
BAR_W = 36
VAL_X = 95  # 5 chars -> x 95..125
CUR_W = 3
CUR_H = 7
# Fraction of a slot the knob must enter before the cursor follows. A slot is
# ~8% of travel against ~0.13% of pot jitter, so this is not about jitter: it
# is about resting exactly on a boundary.
HYST = 0.25


class ListUI(displayio.Group):
    """Scrolling parameter list over a ``paramset.ParamSet`` of one knob.

    Holds the ParamSet itself rather than copies, so there is nothing to
    keep in sync.

    ``text_func(param)`` formats one param's value, for the case where the
    value is not really a number (a waveform index). Defaults to
    ``param.fmt % val``.
    """

    def __init__(self, display, param_set, text_func=None):
        super().__init__()
        self.display = display
        self.param_set = param_set
        self.text_func = text_func or (lambda p: p.fmt % p.val)
        #: sticky: set by update(), cleared by whoever calls display.refresh()
        self.dirty = True
        #: set when the window moved, cleared by update(). The caller owes
        #: this a pass of its own; see the module comment.
        self.scrolled = True
        self.nrows = min(ROWS, param_set.nparams)
        self.win = 0  # index of the param drawn on the top row
        # Where the select pot was when something other than the pot moved
        # the cursor. Until it has been turned a full slot from there, an
        # absolute selector would just snap the cursor back.
        self._latch_k = None
        self._k = 0.0
        self._seen = [None] * self.nrows
        self._seen_head = None

        white = displayio.Palette(1)
        white[0] = 0xFFFFFF

        self.cursor = vectorio.Rectangle(
            pixel_shader=white, width=CUR_W, height=CUR_H, x=0, y=ROW_TOP + 3
        )
        self.append(self.cursor)

        self.names = []
        self.values = []
        self.bars = []
        for r in range(self.nrows):
            top = ROW_TOP + r * ROW_H
            # the rail under each bar, so an empty bar still shows its range
            self.append(
                vectorio.Rectangle(pixel_shader=white, width=BAR_W, height=1, x=BAR_X, y=top + 9)
            )
            bar = vectorio.Rectangle(pixel_shader=white, width=1, height=5, x=BAR_X, y=top + 3)
            name = label.Label(terminalio.FONT, text=" " * 8, color=0xFFFFFF, x=NAME_X, y=top + 5)
            val = label.Label(terminalio.FONT, text=" " * 5, color=0xFFFFFF, x=VAL_X, y=top + 5)
            self.append(bar)
            self.append(name)
            self.append(val)
            self.bars.append(bar)
            self.names.append(name)
            self.values.append(val)

        # Two labels, not one: the octave changes rarely and the counter
        # changes on every cursor step, so splitting them keeps a cursor move
        # down to the 30px it actually needs.
        self.oct = label.Label(terminalio.FONT, text=" " * 3, color=0xFFFFFF, x=NAME_X, y=HEAD_Y)
        self.pos = label.Label(terminalio.FONT, text=" " * 5, color=0xFFFFFF, x=VAL_X, y=HEAD_Y)
        self.append(self.oct)
        self.append(self.pos)
        display.root_group = self

    # --- cursor ----------------------------------------------------------

    def select(self, k):
        """Move the cursor from the select pot, 0.0-1.0. True if it moved."""
        self._k = k
        n = self.param_set.nparams
        if self._latch_k is not None:
            if abs(k - self._latch_k) < 1.0 / n:
                return False
            self._latch_k = None
        raw = k * n
        i = int(raw)
        if i >= n:  # a pot does reach exactly 1.0; read_pots() snaps it there
            i = n - 1
        cur = self.param_set.idx
        if i == cur:
            return False
        # Hysteresis is only about resting ON a boundary, so it applies to
        # the neighbouring slot alone; a knob that has jumped further than
        # that has plainly been turned and should be obeyed at once.
        frac = raw - i
        if i - cur == 1 and frac <= HYST:
            return False
        if cur - i == 1 and frac >= 1.0 - HYST:
            return False
        self._move(i)
        return True

    def step(self):
        """Advance the cursor one param, for a button tap."""
        self._move((self.param_set.idx + 1) % self.param_set.nparams)
        self._latch_k = self._k

    def _move(self, i):
        self.param_set.idx = i  # the setter resets soft-takeover tracking
        w = self.win
        if i < w:
            w = i
        elif i > w + self.nrows - 1:
            w = i - self.nrows + 1
        w = max(0, min(w, self.param_set.nparams - self.nrows))
        if w != self.win:
            self.win = w
            self.scrolled = True

    # --- drawing ---------------------------------------------------------

    def _set_text(self, lbl, text):
        """Write only on a real change. Returns True if it wrote."""
        if lbl.text == text:
            return False
        lbl.text = text
        return True

    def _set_bar(self, r, p):
        bar = self.bars[r]
        if p.vmin < 0 < p.vmax:
            # bipolar: grow out from zero, so a centred value does not read as half full
            z = int(BAR_W * -p.vmin / p.span)
            v = int(BAR_W * (p.val - p.vmin) / p.span)
            x, w = (v, z - v) if v < z else (z, v - z)
        else:
            x, w = 0, int(BAR_W * (p.val - p.vmin) / p.span)
        w = min(max(w, 1), BAR_W)  # vectorio rejects a zero width
        x = BAR_X + min(max(x, 0), BAR_W - 1)
        if bar.x == x and bar.width == w:
            return False
        bar.x = x
        bar.width = w
        return True

    def update(self, oct_name=""):
        """Redraw from the ParamSet. Returns True if anything changed.

        Does NOT refresh the display: the caller picks the moment, so the
        I2C burst can be kept out of the same pass as a note-on.
        """
        ps = self.param_set
        self.scrolled = False
        changed = False
        for r in range(self.nrows):
            p = ps.params[self.win + r]
            # Identity catches a scroll, the float compare catches a knob
            # move. Anything else stops here, with no formatting.
            seen = self._seen[r]
            if seen is not None and seen[0] is p and seen[1] == p.val:
                continue
            self._seen[r] = (p, p.val)
            changed |= self._set_text(self.names[r], "%-8s" % p.name)
            changed |= self._set_text(self.values[r], "%5s" % self.text_func(p))
            changed |= self._set_bar(r, p)

        y = ROW_TOP + (ps.idx - self.win) * ROW_H + 3
        if self.cursor.y != y:
            self.cursor.y = y
            changed = True

        head = (ps.idx, oct_name)
        if head != self._seen_head:
            self._seen_head = head
            changed |= self._set_text(self.oct, "%-3s" % oct_name)
            changed |= self._set_text(self.pos, "%5s" % ("%d/%d" % (ps.idx + 1, ps.nparams)))

        self.dirty = self.dirty or changed
        return changed
