# pylint: disable=too-many-arguments, too-many-positional-arguments

KNOB_MODE_PICKUP = 0
KNOB_MODE_SCALE = 1
KNOB_MODE_RELATIVE = 2

class Param:
    """Params are a UI- and implementation-independent way of describing
    a named numerical parameter with a min/max, a display format, and
    (optionally) an object attribute that they represent.
    """

    def __init__(self, name, val, min_val, max_val, fmt, objattr=None):
        self.name = name
        self.val = val
        self.vmin = min_val
        self.vmax = max_val
        self.fmt = fmt
        self.objattr = objattr

    def __str__(self):
        return("Param('" + self.name + "'," + str(self.val) + "," +
               str(self.vmin) + "," + str(self.vmax) + ",'" + str(self.fmt) + "')")

    def __repr__(self):
        return self.__str__()

    def param_val_for_knob(self, knobval):
        """Knobval ranges 0.0-1.0"""
        return self.vmin + (self.vmax-self.vmin) * knobval

    def update(self, new_knob_val):
        """Set a param val with a knob, bounded by the param's min/max attributes"""
        self.val = self.param_val_for_knob(new_knob_val)
        return self.val

    def apply_to_obj(self,o):
        """Apply a parameter to the given object"""
        if self.objattr:
            setattr(o, self.objattr, self.val)

class ParamSet:
    """ParamSet is a collection of Params that track normalized knob positions,
    especially for the case when there are fewer knobs than Params.
    """

    def __init__(self, params, num_knobs, min_knob_change=0.1):
        self.params = params
        self.nparams = len(params)
        self.nknobs = num_knobs
        self.min_change = min_knob_change
        self.nknobsets = self.nparams // self.nknobs
        self._idx = 0
        self.is_tracking = [False] * self.nknobs

    def next_knobset(self):
        self.idx = (self._idx + 1) % self.nknobsets  # calls def idx()
        return self._idx

    @property
    def idx(self):
        return self._idx

    @idx.setter
    def idx(self, i):
        if i != self._idx:
            self.is_tracking  = [False] * self.nknobs  # reset tracking
        self._idx = i

    def update_knobs(self, new_knob_vals):
        """new_knob_val is list of new knob vals, each 0.0-1.0"""
        for i in range(self.nknobs):
            param = self.params[ self._idx * self.nknobsets + i ]
            new_val = param.knob_to_val(new_knob_vals[i])
            if self.is_tracking[i]:
                param.val = new_val    #update(new_knob_vals[i])
            else:
                delta = param.val - new_val
                # delta = abs(self.vals[self._idx][i] - new_knob_vals[i])
                if abs(delta) < self.min_change:
                    self.is_tracking[i] = True
                    param.val = new_val

    def apply_knobset_to_obj(obj):
        """ Apply all vals in a knobset to given object """
        for i in range(self.nknobs):
            self.param[ self._idx * self.nknobsets + 1].apply_to_obj(obj)
        
    def __str__(self):
        return("ParamSet(nknobs="+str(self.nknobs) + ", " +
               "nknobsets="+str(self.nknobsets) +
               ", params="+str(self.params)+")")

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
