# SPDX-FileCopyrightText: Copyright (c) 2023 Tod Kurt
# SPDX-License-Identifier: MIT
"""
`instrument`
================================================================================

An Instrument receives note on/off events to manage sound creation
with `synthio`. `Instruemnt` uses a `Patch` and maybe a `Wavetable`
to create the internal objects needed by `synthio`.

Part of synth_tools.

"""

import synthio

from synth_tools.patch import Patch, WaveType
from synth_tools.waves import Waves, Wavetable, lerp


class Instrument():
    """
    Basic instrument that uses synthio
    """
    
    def __init__(self, synth, patch=None):
        self.synth = synth
        self.patch = patch or Patch('init')
        self.voices = {}  # keys = midi note, vals = oscs

    def update(self):
        """
        Update internal instrument state.  The update() method should be
        called regularly and as fast as possible, so the instrument can
        update things like filter envelopes and wave mixing.
        This base instrument does nothing but print to REPL currently-sounding
        notes.
        """
        for v in self.voices:
            print("note:",v)

    def note_on(self, midi_note, midi_vel=127):
        """
        Turn on a synthesizer note, using standard MIDI note & velocity values.
        Currently playing notes are kept track of internally.
        """
        # FIXME: deal with multiple note_ons of same note
        f = synthio.midi_to_hz(midi_note)
        amp_env = self.patch.amp_env_params.make_env()
        voice = synthio.Note( frequency=f, envelope=amp_env )
        self.voices[midi_note] = voice
        self.synth.press( voice )

    def note_off(self, midi_note, midi_vel=0):
        """Turn off a synthesizer note, using stadnard MIDI note & velocity values."""
        voice = self.voices.get(midi_note, None)
        if voice:
            self.synth.release(voice)
            self.voices.pop(midi_note)  # FIXME: need to run filter after release cycle



class PolyWaveSynth(Instrument):
    """
    This implementation of Instrument is a two-oscillator per voice
    subtractive synth with detunable oscillators,
    with configurable filter w/ filter envelope and an amplitude envelope.
    Each oscillator can also be a customized wavetable with wavemixing
    between two different waveforms.
    """
    def __init__(self, synth, patch):
        super().__init__(synth)
        self.load_patch(patch)

    def load_patch(self, patch):
        """Loads patch specifics from passed-in Patch object.
           ##### FIXME: no it doesnt: Will reload patch if patch is not specified. """
        self.patch = patch #  self.patch or patch
        #print("PolyWaveSynth.load_patch:", patch)

        self.synth.blocks.clear()   # remove any global LFOs

        #raw_lfo1 = synthio.LFO(rate = 0.3)  #, scale=0.5, offset=0.5)  # FIXME: set lfo rate by patch param
        raw_lfo1 = synthio.LFO(rate = self.patch.wave_mix_lfo_rate) 
        lfo1 = synthio.Math( synthio.MathOperation.SCALE_OFFSET, raw_lfo1, 0.5, 0.5) # unipolar
        self.wave_lfo = lfo1
        self.synth.blocks.append(lfo1)  # global lfo for wave_lfo

        # standard two-osc oscillator patch
        if patch.wave_type == WaveType.OSC:
            self.waveform = Waves.make_waveform('silence')  # our working buffer, overwritten w/ wavemix
            self.waveformA = Waves.make_waveform( patch.wave, volume=16000 )
            self.waveformB = None
            if patch.waveB:
                self.waveformB = Waves.make_waveform( patch.waveB, volume=16000 )
            else:
                self.waveform = self.waveformA

        # wavetable patch
        elif patch.wave_type == WaveType.WTB:
            self.wavetable = Wavetable(patch.wave_dir+"/"+patch.wave+".WAV")
            self.waveform = self.wavetable.waveform

        #self.filt_env_wave = Waves.lfo_triangle()  # FIXME

    def reload_patch(self):
        """Reload the set patch, turns off all notes"""
        self.note_off_all()
        self.synth.blocks.clear()  # clear out global wavetable LFOs (if any)
        self.load_patch(self.patch)

    def _update_filter(self, osc1, osc2, filt_env):
        # prevent filter instability around note frequency
        #if self.patch.filt_f / osc1.frequency < 1.2:  filt_q = filt_q / 2
        #filt_f = max(self.patch.filt_f * filt_env.value, osc1.frequency*0.75) # filter unstable <oscfreq?
        #filt_f = max(self.patch.filt_f * filt_env.value, 0) # filter unstable <100?
        
        filt_amount = self.patch.filt_env_amount
        filt_fmax = 8000   # FIXME: put this and a filt_fmin somewhere (instrument?)
        filt_mod = filt_amount * filt_fmax * (filt_env.value/2)  # 8k/2 = max freq
        filt_f = min(max(self.patch.filt_f + filt_mod, 60), 8000)
        filt_q = self.patch.filt_q
        filt = None
        if self.patch.filt_type == "LP":
            filt = self.synth.low_pass_filter( filt_f,filt_q )
        elif self.patch.filt_type == "HP":
            filt = self.synth.high_pass_filter( filt_f,filt_q )
        elif self.patch.filt_type == "BP":
            filt = self.synth.band_pass_filter( filt_f,filt_q )
        else:
            print("unknown filt_type:", self.patch.filt_type)
            
        #print("%s: %.1f %.1f %.1f %.1f"%(self.patch.filt_type,osc1.frequency,filt_f,self.patch.filt_f,filt_q))
        osc1.filter = filt
        if self.patch.detune:
            osc2.filter = filt
        

    def update(self):
        """Update filter envelope and wave-mixing, must be called frequently"""
        for (osc1,osc2,filt_env,amp_env) in self.voices.values():

            # let Wavetable do the work  # FIXME: don't need to do this per osc1 yeah?
            if self.patch.wave_type == WaveType.WTB:
                self.wave_lfo.a.rate = self.patch.wave_mix_lfo_rate  # FIXME: danger
                wave_pos = self.wave_lfo.value * self.patch.wave_mix_lfo_amount * 10  # FIXME what is this range
                wave_pos += self.patch.wave_mix * self.wavetable.num_waves
                self.wavetable.set_wave_pos( wave_pos )

            # else simple osc wave mixing
            else:
                if self.waveformB:
                    # FIXME: does not work yet
                    #wave_mix = self.patch.wave_mix + self.wave_lfo.a.rate * self.patch.wave_mix_lfo_amount * 2
                    wave_mix = self.patch.wave_mix  # but this works
                    osc1.waveform[:] = lerp(self.waveformA, self.waveformB, wave_mix) #self.patch.wave_mix)
                    if self.patch.detune:
                        osc2.waveform[:] = lerp(self.waveformA, self.waveformB, wave_mix) #self.patch.wave_mix)

            # for each voice, update filter
            self._update_filter(osc1,osc2,filt_env)
            

    def note_on(self, midi_note, midi_vel=127):
        amp_env = self.patch.amp_env.make_env()

        filt_env_wave = Waves.from_ar_times( self.patch.filt_env.attack_time,
                                             self.patch.filt_env.release_time )
        filt_env_time = (self.patch.filt_env.attack_time  +
                         self.patch.filt_env.release_time)
        filt_env_rate = 1 / filt_env_time  # guaranteed to never be zero
        # use an LFO to fake an Envelope since we can't get envelope.value
        filt_env = synthio.LFO(once=True, scale=0.9, offset=1.01, # fixme: make always positve
                               waveform=filt_env_wave, rate=filt_env_rate ) 

        f = synthio.midi_to_hz(midi_note)
        osc1 = synthio.Note( frequency=f, waveform=self.waveform, envelope=amp_env )
        osc2 = synthio.Note( frequency=f * self.patch.detune, waveform=self.waveform, envelope=amp_env )
        
        self._update_filter(osc1, osc2, filt_env)
        
        self.voices[midi_note] = (osc1, osc2, filt_env, amp_env)
        self.synth.press( (osc1,osc2) )
        self.synth.blocks.append(filt_env) # not tracked automaticallly by synthio

    def note_off(self, midi_note, midi_vel=0):
        (osc1,osc2,filt_env,amp_env) = self.voices.get(midi_note, (None,None,None,None)) # FIXME
        #print("note_off:",osc1)
        if osc1:  # why this check? in case user tries to note_off a non-existant note
            self.synth.release( (osc1,osc2) )
            self.voices.pop(midi_note)  # FIXME: let filter run on release, check amp_env?
            self.synth.blocks.remove(filt_env)  # FIXME: figure out how to release after note is done
        #print("note_off: blocks:", self.synth.blocks)

    def note_off_all(self):
        """Turn off all currently playing notes"""
        for n in self.voices.keys():
            print("note_off_all:",n)
            self.note_off(n)

    def redetune(self):
        """Update detune settings in realtime"""
        for (osc1,osc2,filt_env,amp_env) in self.voices.values():
            osc2.frequency = osc1.frequency * self.patch.detune


#
# class MonoOsc(Instrument):
#     def __init__(self, synth, patch):
#         super().__init__(synth)
#         self.load_patch(patch)
