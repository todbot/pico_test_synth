import displayio
import vectorio
import terminalio
from adafruit_display_text import bitmap_label as label
fnt = terminalio.FONT
cw = 0xFFFFFF

class TBishUI(displayio.Group):
    def __init__(self, display, params={}): #, knobAval, knobBval):
        # params is an ordered dict of numeric parameters to change
        super().__init__()
        self.display = display
        display.root_group = self
        self.params = params
        self.num_param_pairs = len(params)//2
        self.curr_param_pair = 0
        
        # text of the currently editable parameters
        self.textA = label.Label(fnt, text="tA", color=cw, x=1, y=24, scale=2)
        self.textB = label.Label(fnt, text="tB", color=cw, x=75, y=24, scale=2)

        # labels for the currently editable parameters
        self.labelA = label.Label(fnt, text="labA", color=cw, x=1, y=8, scale=1)
        self.labelB = label.Label(fnt, text="labB", color=cw, x=75, y=8, scale=1)
        
        palette = displayio.Palette(1)
        palette[0] = cw
        #self.rect = vectorio.Rectangle(pixel_shader=palette, width=64, height=1, x=32, y=1)
        self.rect = vectorio.Rectangle(pixel_shader=palette, width=4, height=4, x=32, y=5)
        self.append(self.rect)
        
        for l in (self.textA, self.textB, self.labelA, self.labelB):
        #for l in (self.textA, self.textB):
            self.append(l)

        self.display.refresh()

    def next_param_pair(self):
        self.curr_param_pair = (self.curr_param_pair+1) % self.num_param_pairs
        self.rect.x = 45 + 5*(self.curr_param_pair)
        #self.rect.y = 5 + 10*(self.curr_param_pair)
        
    def update_param_pairs(self):
        paramL = self.params[self.curr_param_pair*2+0]
        paramR = self.params[self.curr_param_pair*2+1]
        self.labelA.text = paramL.name
        self.labelB.text = paramR.name
        self.textA.text = paramL.fmt % paramL.val
        self.textB.text = paramR.fmt % paramR.val
        #print("refreshing")
        self.display.refresh()
        
