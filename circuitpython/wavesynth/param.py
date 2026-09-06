## pylint: disable=invalid-name,too-many-arguments,multiple-statements
# SPDX-FileCopyrightText: Copyright (c) 2024 Tod Kurt
# SPDX-License-Identifier: MIT
"""
`param`
================================================================================

A `Param` is a named represention of an on-screen configuration value.

A `ParamRange` is a Param with a numeric range and setter function to update
when the Param is changed.

A `ParamChoice` is a Param with a list of options to choose from and
a setter function to update when the Param is changed.

Part of synthtools; vendored here as a flat module.
synthtools/ui/ has no __init__.py and is not shipped by
`circup install synthtools`, so it cannot be imported as
synthtools.ui.* on-device. Keep in sync by hand.

"""


class Param:  # pylint: disable=too-few-public-methods
    """Param is a named representation of an on-screen config value"""

    def __init__(self, name, fullname, val):
        self.name = name
        self.fullname = fullname
        self.val = val


class ParamRange:
    """ParamRange is a Param with a numeric range and setter/getter functions
    to update and set the represented value"""

    def __init__(self, name, fullname, val, fmt, minval, maxval, setter=None, getter=None):
        self.name = name
        self.fullname = fullname
        self.val = val
        self.fmt = fmt
        self.minval = minval
        self.maxval = maxval
        self.valrange = maxval - minval
        self.setter = setter
        self.getter = getter

    def __repr__(self):
        return "ParamRange('%s', %s, %s,%s)" % (
            self.name,
            self.fmt % self.val,
            self.fmt % self.minval,
            self.fmt % self.maxval,
        )

    def update(self):
        """Update the param's value using the getter"""
        if self.getter:
            self.val = self.getter()

    def get_text(self):
        """Return a text version of the param's value, using its fmt"""
        return self.fmt % self.val  # text representation

    def set_by_gauge_val(self, gv):  # gv ranges 0-255
        """Set the param's value (and the underlying value the param is
        representing, using the 0-255 'gauge value' range"""
        self.val = (gv * (self.valrange) / 255) + self.minval
        if self.setter:
            self.setter(self.val)

    def get_by_gauge_val(self):
        """Get the param's value in terms of the 0-255 'gauge value'"""
        return (self.val - self.minval) / (self.valrange) * 255


class ParamChoice:
    """ParamChoice is a Param with a list of options and setter/getter functions
    to update and set the represented value"""

    def __init__(self, name, fullname, val, choices, setter=None, getter=None):
        self.name = name
        self.fullname = fullname
        self.val = val
        self.choices = choices
        self.num_choices = len(choices)
        self.setter = setter
        self.getter = getter

    def __repr__(self):
        return "ParamChoice('%s', %s, %s)" % (self.name, self.val, self.choices)

    def update(self):
        """Update the param's value using the getter"""
        if self.getter:
            self.val = self.getter()

    def get_text(self):
        """Return a text version of the param's value, using its fmt"""
        return self.choices[self.val]  # text representation

    def set_by_gauge_val(self, gv):  # gv ranges 0-255
        """Set the param's value (and the underlying value the param is
        representing, using the 0-255 'gauge value' range"""
        self.val = int(gv * (self.num_choices - 1) / 255)
        if self.setter:
            self.setter(self.val)

    def get_by_gauge_val(self):
        """Get the param's value in terms of the 0-255 'gauge value'"""
        return int(self.val * 255 / (self.num_choices - 1))
