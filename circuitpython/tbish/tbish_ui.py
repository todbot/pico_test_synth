import displayio
import vectorio
import terminalio
from adafruit_display_text import bitmap_label as label

fnt = terminalio.FONT
cw = 0xFFFFFF

class TBishUI(displayio.Group):
    def __init__(self, display, params): #, knobAval, knobBval):
        """
        params are a list of Param objects, conceptually grouped in pairs,
        with only one pair active and visible at any time
        """
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
        self.labelB = label.Label(fnt, text="labB", color=cw, x=104, y=8, scale=1)

        # self.param_names = displayio.Group()
        # for i in range(len(params)//2):
        #     txtL = self.params[i*2+0].name
        #     txtR = self.params[i*2+1].name
        #     pnameL = label.Label(fnt, text=txtL, color=cw, x=1, y=5+i*10, scale=1)
        #     pnameR = label.Label(fnt, text=txtR, color=cw, x=104, y=5+i*10, scale=1)
        #     self.param_names.append(pnameL)
        #     self.param_names.append(pnameR)
        # self.append(self.param_names)
        
        palette = displayio.Palette(1)
        palette[0] = cw
        self.rect = vectorio.Rectangle(pixel_shader=palette, width=4, height=4, x=32, y=5)
        self.append(self.rect)
        
        for l in (self.textA, self.textB, self.labelA, self.labelB):
            self.append(l)

        self.display.refresh()

    def select_param_pair(self, i):
        self.curr_param_pair = i
        self.rect.x = 45 + 10*(self.curr_param_pair)
        
    # def next_param_pair(self):
    #     self.curr_param_pair = (self.curr_param_pair+1) % self.num_param_pairs
    #     self.rect.x = 45 + 10*(self.curr_param_pair)
        
    def update(self):
        """ Update the currently-visible params """
        paramL = self.params[self.curr_param_pair*2+0]
        paramR = self.params[self.curr_param_pair*2+1]
        self.labelA.text = paramL.name
        self.labelB.text = paramR.name
        self.textA.text = paramL.fmt % paramL.val
        self.textB.text = paramR.fmt % paramR.val
        #print("refreshing")
        self.display.refresh()
        
