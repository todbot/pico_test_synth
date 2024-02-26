import displayio
import terminalio
from adafruit_display_text import bitmap_label as label

from synth_tools.gauge_cluster import GaugeCluster
from synth_tools.param_scaler import ParamScaler


class SynthUI(displayio.Group):
    def __init__(self, display, params, knobAval, knobBval):
        super().__init__()
        display.root_group = self
        self.params = params
        self.num_params = len(params)
        
        self.cluster = GaugeCluster(self.num_params, x=12, y=4, width=7, height=40, xstride=2.5)
        self.append(self.cluster.gauges)
        self.append(self.cluster.select_lines)  # indicates which param set is editable
        fnt = terminalio.FONT
        cw = 0xFFFFFF
        
        # text fields of the currently editable parameters
        self.textA = label.Label(fnt, text="tA", color=cw, x=1, y=60)
        self.textB = label.Label(fnt, text="tB", color=cw, x=64, y=60)
        
        # labels above the currently ediable parameters
        self.labelA = label.Label(fnt, text="labA", color=cw, x=1, y=50)
        self.labelB = label.Label(fnt, text="labB", color=cw, x=104, y=50)
        
        for l in (self.textA, self.textB, self.labelA, self.labelB):
            self.append(l)

        for i in range(self.num_params):
            self.cluster.set_gauge_val(i, int(self.params[i].get_by_gauge_val()))

        self.scalerA = ParamScaler(self.params[0].get_by_gauge_val(), knobAval)
        self.scalerB = ParamScaler(self.params[1].get_by_gauge_val(), knobBval)
        self.pairnum = 0
        self.select_pair(0)

    def select_pair(self,p):
        self.cluster.select_line(self.pairnum, False)  # deselect old
        self.pairnum = p
        self.cluster.select_line(self.pairnum)  # select new
        
        i = self.pairnum * 2
        self.labelA.text = self.params[i+0].name
        self.labelB.text = self.params[i+1].name
        self.labelB.x = 128 - self.labelB.width
        self.scalerA.reset(self.params[i+0].get_by_gauge_val())
        self.scalerB.reset(self.params[i+1].get_by_gauge_val())

    def setA(self,v):  # v = 0-127
        i = self.pairnum * 2
        v = int(self.scalerA.update(v))
        self.cluster.set_gauge_val(i,v)
        self.params[i].set_by_gauge_val(v)
        t = self.params[i].get_text()
        if t != self.textA.text:
            self.textA.text = t
        # fixme: need formatting info

    def setB(self, v): # v = 0-127
        i = self.pairnum * 2 + 1
        v = self.scalerB.update(v)
        self.params[i].set_by_gauge_val(v)
        v = self.params[i].get_by_gauge_val()
        self.cluster.set_gauge_val(i,int(v))
        t = self.params[i].get_text()
        if t != self.textB.text:
            self.textB.text = t
            self.textB.x = 128 - self.textB.width

