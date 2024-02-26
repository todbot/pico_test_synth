class Param:
    def __init__(self, name, fullname, val, ):
        self.name = name
        self.fullname = fullname
        self.val = val

class ParamRange:
    def __init__(self, name, fullname, val, fmt, minval, maxval, setter=None):
        Param.__init__(self,name,fullname,val)
        self.fmt = fmt
        self.minval = minval
        self.maxval = maxval
        self.valrange = maxval-minval
        self.setter = setter
        
    def get_text(self):
        return self.fmt % self.val  # text representation
    
    def set_by_gauge_val(self, gv):  # gv ranges 0-127
        self.val = (gv * (self.valrange) / 127) + self.minval
        if self.setter: self.setter(self.val)
        
    def get_by_gauge_val(self):
        return (self.val - self.minval)/(self.valrange) * 127

class ParamChoice:
    def __init__(self, name, fullname, val, choices, setter=None):
        Param.__init__(self,name,fullname,val)
        self.choices = choices
        self.num_choices = len(choices)
        self.setter = setter
        
    def get_text(self):
        return self.choices[self.val]  # text representation
    
    def set_by_gauge_val(self, gv):  # gv ranges 0-127
        self.val = int(gv * (self.num_choices-1) / 127 )
        if self.setter: self.setter(self.val)
        
    def get_by_gauge_val(self):
        return int(self.val * 127 / (self.num_choices-1))  # FIXME: check this
    
