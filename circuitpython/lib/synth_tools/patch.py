## pylint: disable=invalid-name,too-many-arguments,multiple-statements,too-many-instance-attributes
# SPDX-FileCopyrightText: Copyright (c) 2023 Tod Kurt
# SPDX-License-Identifier: MIT
"""
`patch`
================================================================================

Patch, a representation of a synthesizer settings, used by an `Instrument`.

Part of synth_tools.

"""

import os
import synthio
from micropython import const

class LFOParams:
    """
    Parameters to configure a synthio.LFO object
    """
    def __init__(self, rate=None, scale=None, offset=None, once=False,
                 waveform=None):
        self.rate = rate
        self.scale = scale
        self.offset = offset
        self.once = once
        self.waveform = waveform

    def make_lfo(self):
        """Create a synthio.LFO from LFOParam"""
        return synthio.LFO(rate=self.rate, once=self.once,
                           scale=self.scale, offset=self.offset,
                           waveform=self.waveform)

class EnvParams():
    """
    Parameters to configure a synthio.Envelope object
    """
    def __init__(self, attack_time=0.1, decay_time=0.01, release_time=0.2,
                 attack_level=1.0, sustain_level=1.0):
        self.attack_time = attack_time
        self.decay_time = decay_time
        self.release_time = release_time
        self.attack_level = attack_level
        self.sustain_level = sustain_level

    def make_env(self):
        """Create a synthio.Envelope from EnvParam"""
        return synthio.Envelope(attack_time = self.attack_time,
                                decay_time = self.decay_time,
                                release_time = self.release_time,
                                attack_level = self.attack_level,
                                sustain_level = self.sustain_level)


def generate_wave_selects(wave_dir):
    """
    Generate a list of possible 'wave_select' values.
    'wave_select's are a string shorthand for the wave_type/waveA/waveB
    settings for a Patch.
    """
    wave_selects = [
        "osc:SAW/TRI",
        "osc:SAW/SQU",
        "osc:SAW/SIN",
        "osc:SQU/SIN",
        "osc:SIN/NZE",
    ]
    # todfixme: check for bad/none dir_path
    for path in os.listdir(wave_dir):
        path = path.upper()
        if path.endswith('.WAV') and not path.startswith('.'):
            wave_selects.append("wtb:"+path.replace('.WAV',''))
    return wave_selects

class WaveType:
    """ Represent which type of waveform the patch's oscillators are"""
    OSC = const(0)  # standard oscillator
    WTB = const(1)  # wavetable oscillator
    @staticmethod
    def to_str(t):
        """Create string repr of a WaveType"""
        if t==WaveType.WTB:  return 'wtb'
        return 'osc'
    @staticmethod
    def from_str(s):
        """Return a WaveType for a string repr"""
        if s=='wtb':  return WaveType.WTB
        return WaveType.OSC


class Patch:
    """
    Patch is a serializable data structure for the Instrument's settings.
    """

    wave_selects = generate_wave_selects('/wav')
    filter_types = ("LP", "BP", "HP")

    def __init__(self, name='initpatch', wave_type=WaveType.OSC, wave='SAW',
                 detune=1.01, filt_type="LP", filt_f=4000, filt_q=0.7,
                 filt_env_params=None, amp_env_params=None):
        """
        Creates a Patch object used by Instrument.
        'wave_type' must be a WaveType
        'wave' is one of Waves.waveform_types or a WAV filename
        """
        self.name = name
        self.wave_type = wave_type  # WaveType.OSC or WaveType.WTB
        self.wave = wave
        self.waveB = 'TRI'
        self.wave_mix = 0.0  # 0 = wave, 1 = waveB
        self.wave_mix_lfo_amount = 1  # TODFIXME: what is this range
        self.wave_mix_lfo_rate = 0.5  # Hz
        self.wave_dir = '/wav'
        self.detune = detune
        self.filt_type = filt_type   # allowed values:
        self.filt_f = filt_f
        self.filt_q = filt_q
        self.filt_env_amount = 0.3
        self.filt_env = filt_env_params or EnvParams()
        self.amp_env = amp_env_params or EnvParams()
        self.octave = 0

    def wave_select(self):
        """Construct a 'wave_select' string from patch parts.
        Used to summarize the wave_type/waveA/waveB settings."""
        waveB_str = "/"+self.waveB if self.waveB else ""
        waveA_str = self.wave.replace('.WAV','')  # if it's a wavetable
        wave_select = WaveType.to_str(self.wave_type) + ":" + waveA_str + waveB_str
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
