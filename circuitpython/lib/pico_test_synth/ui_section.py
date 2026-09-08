# SPDX-FileCopyrightText: Copyright (c) 2025 Tod Kurt
# SPDX-License-Identifier: MIT
#
# pico_test_synth/ui_section.py -- sectioned parameter screen, 128x64 OLED
#
# Two pots edit two params, a button tap advances the pair, and the screen
# shows the whole SECTION the pair belongs to as readable text: name, bar
# and value per row, with a bracket down the left marking the two the knobs
# are holding. OPTIONAL, like ui.py; the package does not import it.
#
#     from pico_test_synth.ui_section import SectionUI
#
#     SECTIONS = (("OSC", 2), ("FILTER", 2), ("AMP ENV", 4), ...)
#     ui = SectionUI(display, param_set, SECTIONS, param_text)
#     if ui.update("C3"):
#         display.refresh()
#
# Sections must hold an EVEN number of params, at most ROWS of them: two
# pots edit two params at a time, so an odd section would put a knob pair
# across a section boundary and there would be nothing sensible to draw.
# The constructor checks it.
#
# Why sections rather than a sliding window: it makes the cheap action the
# common one. A refresh costs ~0.6 ms per dirty region plus ~0.03 ms per
# byte, and a byte is one column of an 8-row page, so:
#
#   * a tap WITHIN a section moves one 3px bracket, ~1 ms;
#   * a tap into a new section rewrites every row, ~60-70 ms, which is what
#     a page turn in ui.py already costs;
#   * turning one knob rewrites one scale-1 value and its bar, ~8 ms, which
#     unlike ui.py's scale-2 pair fits the 11.6 ms mixer deadline.
#
# Grouping also does the readable work: seeing attack/decay/sustain/release
# together is the thing a two-at-a-time screen cannot show you.
# synthtools' tests/hw/test_display_cost.py measures the numbers above.
#
# Everything is built once and update() compares before assigning, since
# assigning an identical string still re-renders the glyph bitmap and
# dirties the region. A row's name is only rewritten when the row changes
# PARAM, not when its value moves.

import displayio
import terminalio
import vectorio
from adafruit_display_text import bitmap_label as label

ROWS = 4  # param rows under the header; also the largest section
ROW_H = 12  # terminalio.FONT is 6x12
ROW_TOP = 12  # first row's top pixel; the header is above it
HEAD_Y = 5  # scale 1 -> rows 0..11
MARK_X, MARK_W = 0, 3
MARK_H = 20  # spans the two rows of a pair, as one region rather than two
NAME_X = 6  # 8 chars -> x 6..53
BAR_X, BAR_W = 58, 30
VAL_X = 92  # 5 chars -> x 92..121
POS_X = 66  # "3/7", the section's place in the whole set
OCT_X = 110


class SectionUI(displayio.Group):
    """Two-pot editor over a ``paramset.ParamSet``, a section at a time.

    Holds the ParamSet itself rather than copies, so there is nothing to
    keep in sync: whatever the pots wrote is what gets drawn.

    ``sections`` is a sequence of ``(name, count)``, in the same order as
    the ParamSet's params.

    ``text_func(param)`` formats one param's value; it exists so a caller
    can special-case a param whose value is not really a number (a waveform
    index). Defaults to ``param.fmt % param.val``.
    """

    def __init__(self, display, param_set, sections, text_func=None):
        super().__init__()
        if param_set.nknobs != 2:
            raise ValueError("SectionUI needs a ParamSet built with num_knobs=2")
        total = 0
        for name, count in sections:
            if count % 2 or not 0 < count <= ROWS:
                raise ValueError("section '%s' must hold 2..%d params, evenly" % (name, ROWS))
            total += count
        if total != param_set.nparams:
            raise ValueError(
                "sections cover %d params, ParamSet has %d" % (total, param_set.nparams)
            )

        self.display = display
        self.param_set = param_set
        self.sections = sections
        self.text_func = text_func or (lambda p: p.fmt % p.val)
        #: sticky: set by update(), cleared by whoever calls display.refresh()
        self.dirty = True

        # For each knob pair: which section it lives in, and which row of
        # that section it starts on. Built once so update() is a lookup.
        self._pair = []
        first = 0
        for s, (name, count) in enumerate(sections):
            for r in range(0, count, 2):
                self._pair.append((s, first, r))
            first += count

        self._seen = [None] * ROWS
        self._seen_sec = None
        self._seen_oct = None

        white = displayio.Palette(1)
        white[0] = 0xFFFFFF

        self.mark = vectorio.Rectangle(
            pixel_shader=white, width=MARK_W, height=MARK_H, x=MARK_X, y=ROW_TOP + 2
        )
        self.append(self.mark)

        self.names, self.values, self.bars, self.tracks = [], [], [], []
        for r in range(ROWS):
            top = ROW_TOP + r * ROW_H
            # the rail under each bar, so an empty bar still shows its range
            trk = vectorio.Rectangle(pixel_shader=white, width=BAR_W, height=1, x=BAR_X, y=top + 9)
            bar = vectorio.Rectangle(pixel_shader=white, width=1, height=5, x=BAR_X, y=top + 3)
            name = label.Label(terminalio.FONT, text=" " * 8, color=0xFFFFFF, x=NAME_X, y=top + 5)
            val = label.Label(terminalio.FONT, text=" " * 5, color=0xFFFFFF, x=VAL_X, y=top + 5)
            for o in (trk, bar, name, val):
                self.append(o)
            self.tracks.append(trk)
            self.bars.append(bar)
            self.names.append(name)
            self.values.append(val)

        self.sec = label.Label(terminalio.FONT, text=" " * 8, color=0xFFFFFF, x=NAME_X, y=HEAD_Y)
        self.pos = label.Label(terminalio.FONT, text=" " * 3, color=0xFFFFFF, x=POS_X, y=HEAD_Y)
        self.oct = label.Label(terminalio.FONT, text=" " * 2, color=0xFFFFFF, x=OCT_X, y=HEAD_Y)
        for o in (self.sec, self.pos, self.oct):
            self.append(o)
        display.root_group = self

    def _set_text(self, lbl, text):
        """Write only on a real change. Returns True if it wrote."""
        if lbl.text == text:
            return False
        lbl.text = text
        return True

    def _set_bar(self, r, p):
        bar = self.bars[r]
        if p.vmin < 0 < p.vmax:
            # bipolar: grow out from zero, so a centred value does not read
            # as half full
            z = int(BAR_W * -p.vmin / p.span)
            v = int(BAR_W * (p.val - p.vmin) / p.span)
            x, w = (v, z - v) if v < z else (z, v - z)
        else:
            x, w = 0, int(BAR_W * (p.val - p.vmin) / p.span)
        w = min(max(w, 1), BAR_W)  # vectorio rejects a zero width
        x = BAR_X + min(max(x, 0), BAR_W - 1)
        if bar.x == x and bar.width == w:
            return False
        bar.x, bar.width = x, w
        return True

    def _show_row(self, r, on):
        for o in (self.names[r], self.values[r], self.bars[r], self.tracks[r]):
            o.hidden = not on

    def update(self, oct_name=""):
        """Redraw from the ParamSet. Returns True if anything changed.

        Does NOT refresh the display: the caller picks the moment, so the
        I2C burst can be kept out of the same pass as a note-on.
        """
        ps = self.param_set
        sec, first, row = self._pair[ps.idx]
        count = self.sections[sec][1]
        changed = False

        if sec != self._seen_sec:
            self._seen_sec = sec
            changed |= self._set_text(self.sec, "%-8s" % self.sections[sec][0])
            changed |= self._set_text(self.pos, "%d/%d" % (sec + 1, len(self.sections)))
            # rows this section does not use are hidden rather than blanked:
            # hiding costs no glyph render, writing spaces would
            for r in range(ROWS):
                self._show_row(r, r < count)
            changed = True

        for r in range(count):
            p = ps.params[first + r]
            seen = self._seen[r]
            if seen is not None and seen[0] is p:
                if seen[1] == p.val:
                    continue
                # same param, moved: the name is already right
                self._seen[r] = (p, p.val)
            else:
                self._seen[r] = (p, p.val)
                changed |= self._set_text(self.names[r], "%-8s" % p.name)
            changed |= self._set_text(self.values[r], "%5s" % self.text_func(p))
            changed |= self._set_bar(r, p)

        y = ROW_TOP + row * ROW_H + 2
        if self.mark.y != y:
            self.mark.y = y
            changed = True

        if oct_name != self._seen_oct:
            self._seen_oct = oct_name
            changed |= self._set_text(self.oct, "%-2s" % oct_name)

        self.dirty = self.dirty or changed
        return changed
