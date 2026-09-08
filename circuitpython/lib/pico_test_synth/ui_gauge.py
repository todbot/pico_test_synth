# SPDX-FileCopyrightText: Copyright (c) 2025 Tod Kurt
# SPDX-License-Identifier: MIT
#
# pico_test_synth/ui_gauge.py -- all-params gauge display for a 128x64 OLED
#
# ui.py's two-pot screen with the whole patch drawn underneath it: two pots
# edit two params, a button tap moves to the next pair, and a bar per param
# along the bottom shows every value at once with a line marking the pair
# the knobs are holding. OPTIONAL, like ui.py; the package does not import
# it.
#
#     from pico_test_synth.ui_gauge import GaugeUI
#
#     ui = GaugeUI(display, param_set, param_text)   # ParamSet of 2 knobs
#     if ui.update("C3"):
#         display.refresh()
#
# The bars are synthtools' GaugeCluster, imported as a submodule so this
# needs nothing else from the package.
#
# The cluster is close to free, which is what makes showing everything
# affordable: a refresh costs ~0.6 ms per dirty region plus ~0.03 ms per
# byte, and a byte is one column of an 8-row page, so a 5px-wide gauge is
# 15 bytes and well under a millisecond. All eighteen repaint in less time
# than one row of text. WIDTH is what a layout pays for, not how many
# elements moved; synthtools' tests/hw/test_display_cost.py measures it.
#
# What is NOT free is the pair of scale-2 value labels inherited from
# ui.py, at ~60x24 each. Turning a knob rewrites one of them, which is the
# common case and fits the 11.6 ms mixer deadline. A button tap rewrites
# both names and both values and is the expensive event, the same as a page
# turn in ui.py and no worse.
#
# Everything is built once and update() compares before assigning, because
# assigning an identical string still re-renders the glyph bitmap and
# dirties the region.

import displayio
import terminalio
import vectorio
from adafruit_display_text import bitmap_label as label
from synthtools.gauge_cluster import GaugeCluster

# Label x/y are BASELINE-ish anchors; terminalio.FONT is 6x12 with ascent
# 10, so a Label's top row is `y - 5*scale`.
COL_X = (2, 66)  # left and right column origins
NAME_Y = 5  # scale 1 -> rows  0..11, pages 0-1; 8 chars, x+0..47
VALUE_Y = 26  # scale 2 -> rows 16..39, pages 2-4; 12px/char, 5 chars
OCT_X = 116  # 2 chars at scale 1 -> x 116..127, beside the right name
GAUGE_Y = 46  # h=18 -> rows 46..63, pages 5-7
GAUGE_W = 5  # px per bar; GaugeCluster spaces pairs at GAUGE_W + 2
GAUGE_H = 18
# GaugeCluster multiplies this by its own (width + 2) to get the pitch
# between PAIRS, so 2.0 gives 14 px and nine pairs span x = 1..124.
GAUGE_STRIDE = 2.0


class GaugeUI(displayio.Group):
    """Two-pot editor over a ``paramset.ParamSet``, with every param drawn.

    Holds the ParamSet itself rather than copies, so there is nothing to
    keep in sync: whatever the pots wrote is what gets drawn.

    ``text_func(param)`` formats one param's value; it exists so a caller
    can special-case a param whose value is not really a number (a waveform
    index). Defaults to ``param.fmt % param.val``.
    """

    def __init__(self, display, param_set, text_func=None):
        super().__init__()
        if param_set.nknobs != 2:
            raise ValueError("GaugeUI needs a ParamSet built with num_knobs=2")
        if param_set.nparams % 2:
            raise ValueError("GaugeCluster draws in pairs, so nparams must be even")
        self.display = display
        self.param_set = param_set
        self.text_func = text_func or (lambda p: p.fmt % p.val)
        #: sticky: set by update(), cleared by whoever calls display.refresh()
        self.dirty = True
        # Last (param, value) drawn per column, and per-param the value the
        # gauge was last built from. Compared BEFORE any arithmetic: a float
        # compare is nothing, 255-scaling eighteen params every pass is not.
        self._seen = [None, None]
        self._seen_gauge = [None] * param_set.nparams
        self._seen_oct = None

        white = displayio.Palette(1)
        white[0] = 0xFFFFFF

        self.cluster = GaugeCluster(
            param_set.nparams,
            x=1,
            y=GAUGE_Y,
            width=GAUGE_W,
            height=GAUGE_H,
            xstride=GAUGE_STRIDE,
        )
        # not a Group itself, and the select lines have to sit above the bars
        self.append(self.cluster.gauges)
        self.append(self.cluster.select_lines)

        self.names = []
        self.values = []
        for x in COL_X:
            name = label.Label(terminalio.FONT, text=" " * 8, color=0xFFFFFF, x=x, y=NAME_Y)
            val = label.Label(
                terminalio.FONT, text=" " * 5, color=0xFFFFFF, x=x, y=VALUE_Y, scale=2
            )
            self.append(name)
            self.append(val)
            self.names.append(name)
            self.values.append(val)

        self.oct = label.Label(terminalio.FONT, text=" " * 2, color=0xFFFFFF, x=OCT_X, y=NAME_Y)
        self.append(self.oct)

        self._sel = param_set.idx
        self.cluster.select_line(self._sel, True)
        display.root_group = self

    def _set_text(self, lbl, text):
        """Write only on a real change. Returns True if it wrote."""
        if lbl.text == text:
            return False
        lbl.text = text
        return True

    def refresh_gauges(self):
        """Force every bar to be rebuilt, e.g. after loading a patch."""
        self._seen_gauge = [None] * self.param_set.nparams

    def update(self, oct_name=""):
        """Redraw from the ParamSet. Returns True if anything changed.

        Does NOT refresh the display: the caller picks the moment, so the
        I2C burst can be kept out of the same pass as a note-on.
        """
        ps = self.param_set
        changed = False

        for i in range(2):
            p = ps.params[ps.idx * 2 + i]
            # Identity catches a pair change, the float compare catches a
            # knob move. Anything else stops here, with no formatting.
            seen = self._seen[i]
            if seen is not None and seen[0] is p and seen[1] == p.val:
                continue
            self._seen[i] = (p, p.val)
            # Fixed-width text keeps each label's bitmap the same size from
            # one write to the next, so the dirty region never grows.
            changed |= self._set_text(self.names[i], "%-8s" % p.name)
            changed |= self._set_text(self.values[i], "%5s" % self.text_func(p))

        for i in range(ps.nparams):
            p = ps.params[i]
            if self._seen_gauge[i] == p.val:
                continue
            self._seen_gauge[i] = p.val
            g = int(255 * (p.val - p.vmin) / p.span)
            g = min(max(g, 0), 255)
            if g != self.cluster.get_gauge_val(i):
                self.cluster.set_gauge_val(i, g)
                changed = True

        if ps.idx != self._sel:
            self.cluster.select_line(self._sel, False)
            self.cluster.select_line(ps.idx, True)
            self._sel = ps.idx
            changed = True

        if oct_name != self._seen_oct:
            self._seen_oct = oct_name
            changed |= self._set_text(self.oct, "%-2s" % oct_name)

        self.dirty = self.dirty or changed
        return changed
