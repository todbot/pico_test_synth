# SPDX-FileCopyrightText: Copyright (c) 2024 Tod Kurt
# SPDX-License-Identifier: MIT
"""
`param_scaler`
================================================================================

`ParamScaler` attempts to solve the "knob pickup" problem when a control's
position does not match the Param position.

The scaler will increase/decrease its internal value relative to the change
of the incoming knob position and the amount of "runway" remaining on the
value. Once the knob reaches its max or min position, the value will
move in sync with the knob.  The value will always decrease/increase
in the same direction as the knob.
This mirrors how the Deluge synth's "SCALE" mode works.

Part of synthtools; vendored here as a flat module.
synthtools/ui/ has no __init__.py and is not shipped by
`circup install synthtools`, so it cannot be imported as
synthtools.ui.* on-device. Keep in sync by hand.

"""

from micropython import const

knob_min, knob_max = const(0), const(255)
val_min, val_max = const(0), const(255)


class ParamScaler:
    """
    ParamScaler will scale its value based on input knob position, always
    trying to 'do the right thing' no matter where the current value of
    the knob is in relation to its own value
    """

    def __init__(self, val, knob_pos):
        """val and knob_pos range from 0-255, floating point"""
        self.val = val
        self.knob_pos_last = knob_pos
        self.knob_match = False

    def reset(self, val=None, knob_pos=None):
        """Reset the ParamScaler's value and knob_pos memory"""
        if val is not None:
            self.val = val
        if knob_pos is not None:
            self.knob_pos_last = knob_pos
        self.knob_match = False

    def update(self, knob_pos):
        """Update the ParamScaler's internal value based on new knob_pos"""
        # print("k:%3d lk:%3d m:%1d" % (knob_pos, self.knob_pos_last, self.knob_match))
        if self.knob_match:
            # print("!! ==")
            self.val = knob_pos
            self.knob_pos_last = knob_pos
            return knob_pos

        knob_delta = knob_pos - self.knob_pos_last
        self.knob_pos_last = knob_pos

        if abs(knob_pos - self.val) < 5:  # todfixme: make configurable
            # print("!!!!")
            self.knob_match = True
            self.val = knob_pos
            return knob_pos

        val_max_pos_delta = val_max - self.val
        val_min_pos_delta = self.val - val_min
        knob_max_pos_delta = val_max - knob_pos
        knob_min_pos_delta = knob_pos - val_min

        if knob_delta > 0 and knob_max_pos_delta != 0:
            # print("+ ", end='')
            val_percent_change = knob_delta * val_max_pos_delta / knob_max_pos_delta
        elif knob_delta < 0 and knob_min_pos_delta != 0:
            # print("- ", end='')
            val_percent_change = knob_delta * val_min_pos_delta / knob_min_pos_delta
        else:
            # print(". ", end='')
            val_percent_change = 0

        # print("val_percent_change: %2.2f" % val_percent_change)
        self.val = min(max(self.val + val_percent_change, val_min), val_max)
        return self.val
