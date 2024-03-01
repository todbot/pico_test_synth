# synthio_patch.py
#

import os
import synthio


class LFOParams:
    """
    """
    def __init__(self, rate=None, scale=None, offset=None, once=False, waveform=None):
        self.rate = rate
        self.scale = scale
        self.offset = offset
        self.once = once
        self.waveform = waveform

    def make_lfo(self):
        return synthio.LFO(rate=self.rate, once=self.once,
                           scale=self.scale, offset=self.offset,
                           waveform=self.waveform)

class EnvParams():
    """
    """
    def __init__(self, attack_time=0.1, decay_time=0.01, release_time=0.2, attack_level=1.0, sustain_level=1.0):
        self.attack_time = attack_time
        self.decay_time = decay_time
        self.release_time = release_time
        self.attack_level = attack_level
        self.sustain_level = sustain_level

    def make_env(self):
        return synthio.Envelope(attack_time = self.attack_time,
                                decay_time = self.decay_time,
                                release_time = self.release_time,
                                attack_level = self.attack_level,
                                sustain_level = self.sustain_level)

# FIXME: this needs a rethink
class WaveType:
    OSC = const(0)
    WTB = const(1)
    def str(t):
        if t==WTB:  return 'wtb'
        return 'osc'
    def from_str(s):
        if s=='wtb':  return WTB
        return OSC


class Patch:
    """ Patch is a serializable data structure for the Instrument's settings
    """
    def __init__(self, name, wave_type=WaveType.OSC, wave='SAW', detune=1.01,
                 filt_type="LP", filt_f=8000, filt_q=1.2,
                 filt_env_params=None, amp_env_params=None):
        self.name = name
        self.wave_type = wave_type  # or 'osc' or 'wav' or 'wtb'
        self.wave = wave
        self.waveB = None
        self.wave_mix = 0.0  # 0 = wave, 1 = waveB
        self.wave_mix_lfo_amount = 3  # FIXME: what is this range
        self.wave_mix_lfo_rate = 0.5  # Hz
        self.wave_dir = '/wav'
        self.detune = detune
        self.filt_type = filt_type   # allowed values:
        self.filt_f = filt_f
        self.filt_q = filt_q
        self.filt_env_amount = 0
        self.filt_env = filt_env_params or EnvParams()
        self.amp_env = amp_env_params or EnvParams()
        self.octave = 0

    def wave_select(self):
        """Construct a 'wave_select' string from patch parts"""
        waveB_str = "/"+self.waveB if self.waveB else ""
        waveA_str = self.wave.replace('.WAV','')  # if it's a wavetable
        wave_select = WaveType.str(self.wave_type) + ":" + waveA_str + waveB_str
        return wave_select

    def set_by_wave_select(self, wave_select):
        """ Parse a 'wave_select' string and set patch from it"""
        wave_type_str, oscs = wave_select.split(':')
        self.wave_type = WaveType.from_str(wave_type_str)
        self.wave, *waveB = oscs.split('/')  # wave contains wavetable filename if wave_type=='wtb'
        self.waveB = waveB[0] if waveB and len(waveB) else None  # can this be shorter?

    def __repr__(self):
        return "Patch('%s','%s','%.2f','%d %1.1f')" % (
            self.name, self.wave_select(), self.wave_mix,
            self.filt_f, self.filt_q)

    def generate_wave_selects(self):   # fixme: why isn't this a Patch class method?
        wave_selects = [
            "osc:SAW/TRI",
            "osc:SAW/SQU",
            "osc:SAW/SIN",
            "osc:SQU/SIN"
        ]
        # fixme: check for bad/none dir_path
        for path in os.listdir(self.wave_dir):
            path = path.upper()
            if path.endswith('.WAV') and not path.startswith('.'):
                wave_selects.append("wtb:"+path.replace('.WAV',''))
        return wave_selects

    def get_filter_types(self):
        return ("LP", "BP", "HP") 
    
# class FiltType:
#     """ """
#     LP = const(0)
#     HP = const(1)
#     BP = const(2)
#     def str(t):
#         if t==LP: return 'LP'
#         elif t==HP: return 'HP'
#         elif t==BP: return 'BP'
#         return 'UN'

    
