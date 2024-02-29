from micropython import const

knob_min, knob_max = const(0), const(255) 
val_min, val_max = const(0), const(255) 

class ParamScaler:
    def __init__(self, val, knob_pos):
        """ val and knob_pos range from 0-127, floating point """
        self.val = val
        self.knob_pos_last = knob_pos
        self.reset(val,knob_pos)
        
    def reset(self, val=None, knob_pos=None):
        if val is not None:
            self.val = val
        if knob_pos is not None:
            self.knob_pos_last = knob_pos
        self.knob_match = False
        
    def update(self, knob_pos):
        #print("k:%3d lk:%3d m:%1d" % (knob_pos, self.knob_pos_last, self.knob_match))
        if self.knob_match:
            #print("!! ==")
            self.val = knob_pos
            self.knob_pos_last = knob_pos
            return knob_pos
        
        knob_delta = knob_pos - self.knob_pos_last
        self.knob_pos_last = knob_pos
        
        if abs(knob_pos - self.val) < 5: # fixme: make configurable
            #print("!!!!")
            self.knob_match = True
            self.val = knob_pos
            return knob_pos

        val_max_pos_delta = val_max - self.val
        val_min_pos_delta = self.val - val_min
        knob_max_pos_delta = val_max - knob_pos
        knob_min_pos_delta = knob_pos - val_min
        
        if knob_delta > 0 and knob_max_pos_delta !=0:
            #print("+ ", end='')
            val_percent_change = knob_delta * val_max_pos_delta / knob_max_pos_delta
        elif knob_delta < 0 and knob_min_pos_delta !=0:
            #print("- ", end='')
            val_percent_change = knob_delta * val_min_pos_delta / knob_min_pos_delta
        else:
            #print(". ", end='')
            val_percent_change = 0
        
        #print("val_percent_change: %2.2f" % val_percent_change)
        self.val = min(max(self.val + val_percent_change, val_min), val_max)
        return self.val
