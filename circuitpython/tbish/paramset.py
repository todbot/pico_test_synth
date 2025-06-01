# pylint: disable=too-many-arguments, too-many-positional-arguments
# SPDX-FileCopyrightText: Copyright (c) 2023 Tod Kurt
# SPDX-License-Identifier: MIT
"""
`param_set.py`
================================================================================

`ParamSet` is a collection of `Param` that track normalized knob positions,
    especially for the case when there are fewer knobs than `Param`s.

`Param`s are a UI- and implementation-independent way of describing
    a named numerical parameter with a min/max, a display format, and
    (optionally) an object attribute that they represent.

20 May 2025 - @todbot / Tod Kurt

"""

import json

class Param:
    """Params are a UI- and implementation-independent way of describing
    a named numerical parameter with a min/max, a display format, and
    (optionally) an object attribute that they represent.
    """

    def __init__(self, name, val, vmin, vmax, fmt, objattr=None):
        self.name = name
        self.val = val
        self.vmin = vmin
        self.vmax = vmax
        self.fmt = fmt
        self.objattr = objattr

    def __str__(self):
        obstr = 'None' if self.objattr is None else "'%s'" % self.objattr
        return("Param('" + self.name + "'," + str(self.val) + "," +
               str(self.vmin) + "," + str(self.vmax) + ",'" + str(self.fmt) +
               "'," + obstr + ")")

    def __repr__(self):
        return self.__str__()

    @property
    def span(self):
        return self.vmax - self.vmin
    
    def knob_to_val(self, knobval):
        """Knobval ranges 0.0-1.0"""
        return self.vmin + (self.vmax-self.vmin) * knobval

    def update(self, new_knob_val):
        """Set a param val with a knob, bounded by the param's min/max attributes"""
        self.val = self.knob_to_val(new_knob_val)
        return self.val

    def apply_to_obj(self,o):
        """Apply a parameter to the given object"""
        if self.objattr:
            setattr(o, self.objattr, self.val)

class ParamSet:
    """ParamSet is a collection of Params that track normalized knob positions,
    especially for the case when there are fewer knobs than Params.
    """

    KNOB_PICKUP = 0
    KNOB_SCALE = 1
    KNOB_RELATIVE = 2

    def __init__(self, params, num_knobs, min_knob_change=0.05,
                 knob_smooth=0.5, knob_mode = KNOB_PICKUP):
        self.params = params
        self.knob_mode = knob_mode
        self.nparams = len(params)
        self.nknobs = num_knobs
        self.min_change = min_knob_change
        self.smoothing = knob_smooth
        self.nknobsets = self.nparams // self.nknobs
        self._idx = 0  # which knobset we're modifying
        self.is_tracking = [False] * self.nknobs

    def next_knobset(self):
        self.idx = (self._idx + 1) % self.nknobsets  # calls def idx()
        return self._idx

    @property
    def idx(self):
        """ Which knobset is currently being edited """
        return self._idx

    @idx.setter
    def idx(self, i):
        """ Set which knobset to edit, resets knob tracking """
        if i != self._idx:
            self.is_tracking  = [False] * self.nknobs  # reset tracking
        self._idx = i

    def update_knobs(self, new_knob_vals):
        if self.knob_mode == ParamSet.KNOB_PICKUP:
            self.update_knobs_pickup(new_knob_vals)
        elif self.knob_mode == ParamSet.KNOB_SCALE:
            self.update_knobs_scale(new_knob_vals)

    def update_knobs_pickup(self, new_knob_vals):
        """new_knob_vals is list of new knob vals, each 0.0-1.0"""
        for i in range(self.nknobs):
            param = self.params[ (self._idx * self.nknobs) + i ]
            new_val = param.knob_to_val(new_knob_vals[i])
            if self.is_tracking[i]:
                # only change param val if difference is big enough FIXME
                if abs(new_val - param.val) >= 0.1 * self.min_change * param.span:
                    param.val = new_val
            else:
                delta = param.val - new_val
                if abs(delta) < self.min_change * param.span:
                    self.is_tracking[i] = True

    def update_knobs_scale(self, new_knob_vals):
        """new_knob_val is list of new knob vals, each normalized 0.0-1.0"""
        # note this sucks currently
        for i in range(self.nknobs):
            param = self.params[ (self._idx * self.nknobs) + i ]
            new_val = param.knob_to_val(new_knob_vals[i])
            delta_val = new_val - param.val
            
            val_min, val_max = param.vmin, param.vmax
            knob_min, knob_max = 0.0, 1.0
            
            val_max_pos_delta = val_max - param.val
            val_min_pos_delta = param.val - val_min
            knob_max_pos_delta = val_max - new_val
            knob_min_pos_delta = new_val - val_min
            
            if delta_val > 0 and knob_max_pos_delta != 0:
                val_percent_change = delta_val * val_max_pos_delta / knob_max_pos_delta
            elif delta_val < 0 and knob_min_pos_delta != 0:
                val_percent_change = delta_val * val_min_pos_delta / knob_min_pos_delta
            else:
                val_percent_change = 0

            param.val = min(max(param.val + val_percent_change, val_min), val_max)
            

    def apply_params(self, obj):
        """ Apply all params to given object """
        for i in range(self.nparams):
            self.params[i].apply_to_obj(obj)
            
    def apply_knobset(self, obj):
        """ Apply all vals in a knobset to given object """
        for i in range(self.nknobs):
            self.params[ (self._idx * self.nknobs) + i].apply_to_obj(obj)

    def param_for_name(self, name):
        for p in filter(lambda p: p.name == name, self.params):
            return p
        return None

    def __str__(self):
        return("ParamSet(nknobs="+str(self.nknobs) + ", " +
               "nknobsets="+str(self.nknobsets) +
               ", params="+str(self.params)+")")

    @staticmethod
    def load(dumpstr):
        dumpobj = json.loads(dumpstr)
        newparams = [Param(**d) for d in dumpobj['params']]
        return newparams
    
    @staticmethod
    def dump(paramset):
        dumpobj = {
            'params': [p.__dict__ for p in paramset.params]
            }
        return json.dumps(dumpobj)
        
# simple test

if __name__ == "__main__":

    myparams = [
        Param("cutoff", 8000, 0, 9000, "%4d", "filt_frequency"),
        Param("envmod", 0.5,  0.0, 1.0, "%.2f", "filt_env_depth"),

        Param("resq", 8000, 0, 9000, "%4d", "resonance"),
        Param("decay", 0.5,  0.0, 1.0, "%.2f", "decay"),
    ]

    param_set = ParamSet(myparams, num_knobs=2)

    print("param_set:",param_set)
