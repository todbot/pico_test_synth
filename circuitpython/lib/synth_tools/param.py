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

Part of synth_tools.

"""


class Param:
    def __init__(self, name, fullname, val, ):
        self.name = name
        self.fullname = fullname
        self.val = val

class ParamRange:
    def __init__(self, name, fullname, val, fmt, minval, maxval, setter=None, getter=None):
        Param.__init__(self,name,fullname,val)
        self.fmt = fmt
        self.minval = minval
        self.maxval = maxval
        self.valrange = maxval-minval
        self.setter = setter
        self.getter = getter
        
    def __repr__(self):
        return "ParamRange('%s', %s, %s,%s)" % (self.name,
                                                self.fmt % self.val,
                                                self.fmt % self.minval,
                                                self.fmt % self.maxval)
    
    def update(self):
        if self.getter: self.val = self.getter()
        
    def get_text(self):
        return self.fmt % self.val  # text representation
    
    def set_by_gauge_val(self, gv):  # gv ranges 0-255
        self.val = (gv * (self.valrange) / 255) + self.minval
        if self.setter: self.setter(self.val)
        
    def get_by_gauge_val(self):
        return (self.val - self.minval)/(self.valrange) * 255


class ParamChoice:
    def __init__(self, name, fullname, val, choices, setter=None, getter=None):
        Param.__init__(self,name,fullname,val)
        self.choices = choices
        self.num_choices = len(choices)
        self.setter = setter
        self.getter = getter
    def __repr__(self):
        return "ParamChoice('%s', %s, %s)" % (self.name, self.val, self.choices)
        
    def update(self):
        if self.getter: self.val = self.getter()
        
    def get_text(self):
        return self.choices[self.val]  # text representation
    
    def set_by_gauge_val(self, gv):  # gv ranges 0-255
        self.val = int(gv * (self.num_choices-1) / 255 )
        if self.setter: self.setter(self.val)
        
    def get_by_gauge_val(self):
        return int(self.val * 255 / (self.num_choices-1))  # FIXME: check this
    
