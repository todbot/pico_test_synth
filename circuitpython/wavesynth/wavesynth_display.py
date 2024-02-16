# wavesynth_display.py -- wavesynth display management for qtpy_synth
# 28 Jul 2023 - @todbot / Tod Kurt
# part of https://github.com/todbot/qtpy_synth

import os
import displayio, terminalio, vectorio
from adafruit_display_text import bitmap_label as label

from pico_test_synth.synthio_instrument import FiltType

# class WavesynthDisplay(displayio.Group):
#     def __init__(self, display):
#         super().__init(x=0,y=0,scale=1)
#         self.display = display
#         self.display_setup()

class WavesynthDisplay:
    def __init__(self, display, patch):
        self.display = display
        self.patch = patch
        self.selected_info = 0 # which part of the display is currently selected
        self.update_wave_selects()
        self.display_setup()
        self.display_update()
        print("WavesynthDisplay:init: patch=",patch)

    def display_setup(self):
        disp_group = displayio.Group()
        self.display.root_group = disp_group

        lwave_sel = label.Label(terminalio.FONT, text=self.patch.wave_select(), x=2, y=6)
        lwave_mix = label.Label(terminalio.FONT, text=str(self.patch.wave_mix), x=80, y=6)

        ldetune  = label.Label(terminalio.FONT, text="-", x=2, y=19)
        lwave_lfo= label.Label(terminalio.FONT, text="-", x=75, y=19)

        lfilt_type = label.Label(terminalio.FONT, text="-", x=2,y=32)
        lfilt_f  = label.Label(terminalio.FONT, text="-", x=75,y=32)

        lfilt_q  = label.Label(terminalio.FONT, text="-", x=2,y=45)
        lfilt_env= label.Label(terminalio.FONT, text="-", x=70,y=45)

        self.disp_line1 = displayio.Group()
        for l in (lwave_sel, lwave_mix):
            self.disp_line1.append(l)
        disp_group.append(self.disp_line1)

        self.disp_line2 = displayio.Group()
        for l in (ldetune, lwave_lfo):
            self.disp_line2.append(l)
        disp_group.append(self.disp_line2)

        self.disp_line3 = displayio.Group()
        for l in (lfilt_type, lfilt_f):
            self.disp_line3.append(l)
        disp_group.append(self.disp_line3)

        self.disp_line4 = displayio.Group()
        for l in (lfilt_q, lfilt_env):
            self.disp_line4.append(l)
        disp_group.append(self.disp_line4)

        # selection lines
        pal = displayio.Palette(1)
        pal[0] = 0xffffff
        selectF = vectorio.Rectangle(pixel_shader=pal, width=128, height=1, x=0, y=6 + 8)
        selectW = vectorio.Rectangle(pixel_shader=pal, width=128, height=1, x=0, y=19 + 8)
        selectG = vectorio.Rectangle(pixel_shader=pal, width=128, height=1, x=0, y=32 + 8)
        selectH = vectorio.Rectangle(pixel_shader=pal, width=128, height=1, x=0, y=45 + 8)

        self.disp_selects = displayio.Group()
        for s in (selectF,selectW,selectG, selectH):
            s.hidden=True
            self.disp_selects.append(s)
        disp_group.append(self.disp_selects)

    def display_update(self):
        self.disp_select()
        self.display_update_line1()
        self.display_update_line2()
        self.display_update_line3()
        self.display_update_line4()

    def disp_select(self):
        for s in self.disp_selects:
            s.hidden = True
        self.disp_selects[self.selected_info].hidden = False

    def display_update_line1(self):
        wave_select = self.patch.wave_select()
        wave_mix = "%.2f:mix" % self.patch.wave_mix

        if self.disp_line1[0].text != wave_select:
            self.disp_line1[0].text = wave_select
        if self.disp_line1[1].text != wave_mix:
            self.disp_line1[1].text = wave_mix

    def display_update_line2(self):
        detune = "detun:%1.3f" % self.patch.detune
        wave_lfo = "%1.2f:wlfo" % self.patch.wave_mix_lfo_amount

        if self.disp_line2[0].text != detune:
            self.disp_line2[0].text = detune
        if self.disp_line2[1].text != wave_lfo:
            self.disp_line2[1].text = wave_lfo

    def display_update_line3(self):
        filt_type = "filter:"+FiltType.str(self.patch.filt_type)
        filt_f = "freq:%1.1fk" % (self.patch.filt_f / 1000)

        if self.disp_line3[0].text != filt_type:
            self.disp_line3[0].text = filt_type
        if self.disp_line3[1].text != filt_f:
            self.disp_line3[1].text = filt_f

    def display_update_line4(self):
        filt_q = "filtq:%1.1f" % self.patch.filt_q
        filt_env = "fenv:%1.2f" % self.patch.filt_env_params.attack_time

        if self.disp_line4[0].text != filt_q:
            self.disp_line4[0].text = filt_q
        if self.disp_line4[1].text != filt_env:
            print("!")
            self.disp_line4[1].text = filt_env

    # utility methods for dealing with these "wave_selects" I've gotten myself into

    def update_wave_selects(self):   # fixme: why isn't this a Patch class method?
        wave_selects = [
            "osc:SAW/TRI",
            "osc:SAW/SQU",
            "osc:SAW/SIN",
            "osc:SQU/SIN"
        ]
        # fixme: check for bad/none dir_path
        for path in os.listdir(self.patch.wave_dir):
            path = path.upper()
            if path.endswith('.WAV') and not path.startswith('.'):
                wave_selects.append("wtb:"+path.replace('.WAV',''))
        self.wave_selects = wave_selects

    def wave_select_pos(self):
        print("wave_select_pos:",self.patch.wave_select())
        return self.wave_selects.index( self.patch.wave_select() ) # fixme: this seems wrong

    def wave_select(self):
        return self.patch.wave_select()
