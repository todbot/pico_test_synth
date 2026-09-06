##pylint: disable=invalid-name
# SPDX-FileCopyrightText: Copyright (c) 2024 Tod Kurt
# SPDX-License-Identifier: MIT
"""
`gauge_cluster`
================================================================================

A group of `displayio` objects that display a list of values graphically.

Part of synthtools; vendored here as a flat module.
synthtools/ui/ has no __init__.py and is not shipped by
`circup install synthtools`, so it cannot be imported as
synthtools.ui.* on-device. Keep in sync by hand.

"""

import displayio
from vectorio import Rectangle


class GaugeCluster:  # (dispalyio.Group) ?
    """
    GaugeCluster is a group of `displayio` objects that display a list
    of values graphically.
    """

    # pylint: disable=too-many-arguments,too-many-locals
    def __init__(self, num_vals, x=2, y=4, width=5, height=40, xstride=3):
        self.gauge_vals = [0] * num_vals  # 0-255 is val range
        self.x = x
        self.y = y
        self.w = width
        self.h = height
        palW = displayio.Palette(1)
        palW[0] = 0xFFFFFF
        palB = displayio.Palette(1)
        palB[0] = 0x000000
        xspacing = width + 2  # 7
        xstride = int(xspacing * xstride)  # 21 orig
        gauges = displayio.Group()
        select_lines = displayio.Group()
        # fmt: off
        for i in range(num_vals // 2):
            rL = Rectangle(pixel_shader=palW, width=self.w, height=self.h,
                           x=self.x + (i * xstride),
                           y=self.y)
            rLB = Rectangle(pixel_shader=palB, width=self.w-2, height=self.h,
                            x=self.x+1+(i*xstride),
                            y=self.y+1)
            rR = Rectangle(pixel_shader=palW, width=self.w, height=self.h,
                           x=self.x+xspacing+(i*xstride),
                           y=self.y)
            rRB = Rectangle(pixel_shader=palB,width=self.w-2, height=self.h,
                            x=self.x + xspacing+1+(i*xstride),
                            y=self.y + 1)
            for r in (rL, rLB, rR, rRB):
                gauges.append(r)

            # add in the select lines, above the actual cluster
            line = Rectangle(pixel_shader=palW, width=self.w*2+2, height=2,
                             x=self.x+(i*xstride),
                             y=self.y-3)
            line.hidden = True
            select_lines.append(line)
        # fmt: on

        self.gauges = gauges
        self.select_lines = select_lines

    def set_gauge_val(self, i, v):
        """Set gauge `i` with value `v`. v ranges from 0-255"""
        self.gauge_vals[i] = v  # 0-255
        self.gauges[1 + (i * 2)].height = self.h - 2 - ((v * (self.h - 2)) // 255)

    def get_gauge_val(self, i):
        """Get gauge value of gauge `i`, return value ranges from 0-255"""
        return self.gauge_vals[i]

    def select_line(self, i, show=True):
        """Show a bar above two of the gauges, indicating they are the pair
        able to be edited  (this should maybe go in synthui)"""
        self.select_lines[i].hidden = not show
