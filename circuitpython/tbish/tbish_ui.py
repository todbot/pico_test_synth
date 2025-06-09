# SPDX-FileCopyrightText: Copyright (c) 2025 Tod Kurt
# SPDX-License-Identifier: MIT
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
        self.paramspot = vectorio.Rectangle(pixel_shader=palette, width=4, height=4, x=32, y=5)
        self.stepspot =  vectorio.Rectangle(pixel_shader=palette, width=5, height=5, x=64, y=60)
        self.append(self.paramspot)
        self.append(self.stepspot)
        
        for l in (self.textA, self.textB, self.labelA, self.labelB):
        #for l in (self.textA, self.textB):
            self.append(l)

        self.logo = label.Label(fnt, text="TBishBassSynth", color=cw, x=20,y=45)
        self.append(self.logo)

        self.display.refresh()

    def next_param_pair(self):
        self.curr_param_pair = (self.curr_param_pair+1) % self.num_param_pairs

    def stop(self):
        pass
    
    def start(self):
        pass
    
    def show_beat(self, step, steps_per_beat, seq_len):
        self.stepspot.x = 5 + step * 6
        
        # this doesn't work right but sorta works
        #if step % steps_per_beat == 0 :
        #    self.stepspot.hidden = False
        #else:
        #    self.stepspot.hidden = True
        
    def update_param_pairs(self):
        self.paramspot.x = 45 + 4*(self.curr_param_pair)

        paramL = self.params[self.curr_param_pair*2+0]
        paramR = self.params[self.curr_param_pair*2+1]
        textAnew = paramL.fmt % paramL.val
        textBnew = paramR.fmt % paramR.val
        # try to be smart and only update what's needed
        if paramL.name != self.labelA.text:
            self.labelA.text = paramL.name
        if paramR.name != self.labelB.text:
            self.labelB.text = paramR.name
        if self.textA.text != textAnew:
            self.textA.text = textAnew
        if self.textB.text != textBnew:
            self.textB.text = textBnew
        self.display.refresh()
        
