# SPDX-FileCopyrightText: Copyright (c) 2023 Tod Kurt
# SPDX-License-Identifier: MIT
"""
`tbish_synth`
================================================================================

TB-303-like synth for CircuitPtyhon synthio. Designed for RP2350.
 
12 May 2025 - @todbot / Tod Kurt

Implementation Notes
--------------------

A TB-303 synth voice has the following attributes:

* VCO: monophonic single-oscillator with either saw or square waveforms,
  with a "slide" portamento feature that can be enabled per step.
  The slide time is fixed, traditionally.

* VCF: 24 dB low-pass filter, with adjustable cutoff and adjustable squelchy resonance

* EG: A decay-only envelope generator controls both filter cutoff and amplitude.
  The EG is retriggered on every step and has no sustain or release

Common post effects added to TB-303 are:

* Overdrive / Distortion
* Delay, usually tempo-sync'd

The 16-step sequencer of the TB-303 is different than most, having 3 attributes
per step:

 * pitch value - note pitch of a step
 * accent on/off - boosts the cutoff, resonance, and VCA level for a step
 * slide on/off - glides pitch from previous step to current step

This code does not implement the sequencer, but does implement accent and slide.


"""
# Sorta like a TB303
import synthio
import ulab.numpy as np
try:
    import audiofilters
    from audiofilters import Distortion, Filter
    import audiodelays
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
        self.secs_per_step = 0.125
        self.wavenum = 1   # which waveform to use: saw=0, square=1
        self.cutoff = 8000  # aka 'filter frequency'
        self.envmod = 0.5  # aka 'filter depth'
        self.envdecay = 0.01
        self._accent = 0.5
        self.autoslide = True  # FIXME unused yet
        self.filt_env = synthio.LFO(rate=1, scale=self.cutoff, once=True,
                                    waveform=np.array((32767,0),dtype=np.int16))
        self.filter = synthio.Biquad(mode=synthio.FilterMode.LOW_PASS,
                                     frequency=self.filt_env, Q=1.0)
        self.glider = Glider(0.0, 0)
 
    def add_audioeffects(self):
        """ Set up the necessary effects chain for TBsynth and
        return an audio object that can be attached to a Mixer or effect """
        fxcfg = { 'sample_rate': self.synth.sample_rate,
                  'channel_count': self.synth.channel_count,
                  'buffer_size': 1024 }
        
        # No distortion on rp2040 (not enough CPU)
        self.fx_distortion = Distortion(**fxcfg, mix = 0.0,
                                        mode = audiofilters.DistortionMode.LOFI,
                                        # other distortion modes are too slow? 
                                        #mode = audiofilters.DistortionMode.OVERDRIVE,
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

        self.fx_delay = audiodelays.Echo(**fxcfg, mix=0.0,
                                         max_delay_ms = 400,
                                         delay_ms = self.secs_per_step * 1000 * 2,
                                         decay = 0.1,
                                         freq_shift = False,
                                         )
        self.fx_delay.play(self.fx_distortion)
        self.fx_distortion.play(self.fx_filter2)  # plug 2nd filter into distortion
        self.fx_filter2.play(self.fx_filter1)  # plug 1st filter into 2nd filter
        self.fx_filter1.play(self.synth)   # plug synth into 1st filter
        #return self.fx_distortion  # the "output" of this synth
        return self.fx_delay   # the "output" of this synth

    def note_on_step(self, midi_note, slide=False, accent=False):
        print("note_on_step: %3d %1d %1d" % (midi_note, slide, accent))
        self.note_off(midi_note) # must do when in step mode
        attack_level = 0.8
        cutoff = self.cutoff
        # resonance = self.resonance  # fixme how to do this
        envmod = self.envmod
        glide_time = 0.001  # minimal slide
        if accent:
            attack_level +=  0.2 
            cutoff *= 1.3   # FIXME: verify
            #resonance *= 1.3
            envmod *= 0.5
        if slide:
            glide_time = 0.1
            # FIXME also do appropriate other actions for slide
        envdecay = max(0.05, self.secs_per_step * self.envdecay * 1.5)  # 1.5 fudge 
        frate = 1 / envdecay
        self.filt_env.offset = ((1-envmod) * cutoff) 
        self.filt_env.scale = cutoff - self.filt_env.offset
        self.filt_env.rate = frate
        self.filt_env.retrigger()  # must retrigger once-shot LFOs
        self.glider.glide_time = glide_time
        self.glider.update(midi_note)  # glide up to new note
        ampenv = synthio.Envelope(attack_time=0.001,
                                  attack_level = attack_level,
                                  decay_time = envdecay,
                                  sustain_level=0,
                                  release_time=0.01) 
        self.note = synthio.Note(synthio.midi_to_hz(midi_note),
                                 bend = self.glider.lerp,
                                 filter = self.filter,
                                 envelope = ampenv,
                                 waveform = waves[self.wavenum])
        self.synth.press(self.note)
        

    def note_on(self, midi_note, vel=100):
        """For MIDI use"""
        self.note_on_step(midi_note, slide=(vel==1), accent=(vel==127))

    def note_off(self, midi_note, vel=0):
        """Used for both MIDI and sequencer mode"""
        if self.note:
            self.synth.release(self.note)
            self.note = None

    @property
    def decay(self):
        return self.envdecay
    
    @decay.setter
    def decay(self,t):
        self.envdecay = t
        
    @property
    def accent(self):
        return self.accent
    
    @accent.setter
    def accent(self, v):
        self.accent = v
        
    @property
    def resonance(self):
        return self.filter.Q
    
    @resonance.setter
    def resonance(self,q):
        self.filter.Q = q
        if self.fx_filter1:
            self.fx_filter1.filter.Q = q
            self.fx_filter2.filter.Q = q

    @property
    def drive(self):
        return self.fx_distortion.pre_gain
    
    @drive.setter
    def drive(self,d):
        self.fx_distortion.post_gain = -d/2
        self.fx_distortion.pre_gain = d

    @property
    def delay_mix(self):
        return self.fx_delay.mix
    
    @delay_mix.setter
    def delay_mix(self, m):
        self.fx_delay.mix = m
        
    @property
    def delay_time(self):
        return self.fx_delay.delay_ms / (self.secs_per_step * 100 * 2)
    
    @delay_time.setter
    def delay_time(self, m):
        self.fx_delay.delay_ms = self.secs_per_step * 1000 * 2 * m
