# SPDX-FileCopyrightText: Copyright (c) 2023 Tod Kurt
# SPDX-License-Identifier: MIT
"""
`code.py`
================================================================================

TB-303-like synth for CircuitPtyhon synthio. Designed for RP2350 

12 May 2025 - @todbot / Tod Kurt

"""
# Sorta like a TB303
import synthio
import ulab.numpy as np
try:
    import audiofilters
    from audiofilters import Distortion, Filter
except (ImportError, NameError):
    pass

from pitch_glider import Glider

wave_size = 128
wave_vol = 32677
waves = (
    np.linspace(wave_vol, -wave_vol, num=wave_size, dtype=np.int16),   # saw
    np.concatenate((np.ones(wave_size//2, dtype=np.int16) * wave_vol,  # square
                    np.ones(wave_size//2, dtype=np.int16) * -wave_vol)),
    
)

class TBishSynth:
    def __init__(self, sample_rate, channel_count):
        self.synth = synthio.Synthesizer(sample_rate=sample_rate,
                                         channel_count=channel_count)
        self.note = None
        self.secs_per_step = 0.1
        self.wavenum = 1   # which waveform to use: saw=0, square=1
        self.cutoff = 8000  # aka 'filter frequency'
        self.envmod = 0.5  # aka 'filter depth'
        self.envdecay = 0.01
        #self.envelope = synthio.Envelope(attack_time=0.0,
        #                                 decay_time=self.envdecay,
        #                                 release_time=0.01)  # FIXME: decay time
        self.filt_env = synthio.LFO(rate=1, scale=self.cutoff, once=True,
                                    waveform=np.array((32767,0),dtype=np.int16))
        self.filter = synthio.Biquad(mode=synthio.FilterMode.LOW_PASS,
                                     frequency=self.filt_env, Q=1.0)
        self.glider = Glider(0.1, 0)
 
    def add_audioeffects(self):
        """ Set up the necessary effects chain for TBsynth and
        return an audio object that can be attached to a Mixer or effect """
        fxcfg = { 'sample_rate': self.synth.sample_rate,
                  'channel_count': self.synth.channel_count,
                  'buffer_size': 1024 }
        
        # No distortion on rp2040 (not enough CPU)
        self.fx_distortion = Distortion(**fxcfg, mix = 0.0,
                                        # other distortion modes are too slow? 
                                        mode = audiofilters.DistortionMode.LOFI,
                                        soft_clip = True,
                                        pre_gain = 30,
                                        post_gain = -10)
        # but yes filter on rp2040 with custom compile
        self.fx_filter1 = Filter(**fxcfg, mix=1.0)
        self.fx_filter2 = Filter(**fxcfg, mix=1.0)

        # stacked filters to give steeper slope, for a more squelchy sound
        self.fx_filter1.filter = synthio.Biquad(synthio.FilterMode.LOW_PASS,
                                                frequency=self.filt_env,
                                                Q=self.resonance)
        self.fx_filter2.filter = synthio.Biquad(synthio.FilterMode.LOW_PASS,
                                                frequency=self.filt_env,
                                                Q=self.resonance)

        self.fx_distortion.play(self.fx_filter2)  # plug 2nd filter into distortion
        self.fx_filter2.play(self.fx_filter1)  # plug 1st filter into 2nd filter
        self.fx_filter1.play(self.synth)   # plug synth into 1st filter
        return self.fx_distortion  # this "output" of this synth

    def note_on(self, midi_note, vel=127):
        frate = 1/self.secs_per_step # (vel/127) * 5
        self.glider.glide_time = 0.3 - 0.3 * (vel/127)   #random.choice( (0, 0.1, 0.2) )
        self.glider.update(midi_note)  # glide up to new note
        self.filt_env.offset = ((1-self.envmod) * self.cutoff)
        self.filt_env.scale = self.cutoff - self.filt_env.offset
        self.filt_env.rate = frate  # 0.75 / self.secs_per_step
        self.filt_env.retrigger()  # must retrigger once-shot LFOs
        ampenv = synthio.Envelope(attack_time=0.0,
                                  decay_time=self.envdecay,
                                  release_time=self.envdecay)  # FIXME: decay time
        self.note = synthio.Note(synthio.midi_to_hz(midi_note),
                                 bend = self.glider.lerp,
                                 filter = self.filter,
                                 envelope = ampenv,
                                 waveform = waves[self.wavenum])
        self.synth.press(self.note)

    def note_off(self, midi_note, vel=0):
        if self.note:
            self.synth.release(self.note)

    @property
    def decay(self):
        return self.envdecay
    
    @decay.setter
    def decay(self,t):
        self.envdecay = t
        
    @property
    def drive(self):
        return self.fx_distortion.pre_gain
    
    @drive.setter
    def drive(self,d):
        self.fx_distortion.pre_gain = d

    @property
    def drive_mix(self):
        return self.fx_distortion.mix
    
    @drive_mix.setter
    def drive_mix(self, m):
        self.fx_distortion.mix = m
        
    @property
    def resonance(self):
        return self.filter.Q
    
    @resonance.setter
    def resonance(self,q):
        self.filter.Q = q
        if self.fx_filter1:
            self.fx_filter1.filter.Q = q
            self.fx_filter2.filter.Q = q
