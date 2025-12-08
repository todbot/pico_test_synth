## pylint: disable=invalid-name
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

lfo_exp_wave = Waves.lfo_exp_wave()

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

    def note_on(self, midi_note, midi_vel=127):  # pylint: disable=unused-argument
        """
        Turn on a synthesizer note, using standard MIDI note & velocity values.
        Currently playing notes are kept track of internally.
        """
        # TODFIXME: deal with multiple note_ons of same note
        f = synthio.midi_to_hz(midi_note)
        amp_env = self.patch.amp_env_params.make_env()
        voice = synthio.Note( frequency=f, envelope=amp_env )
        self.voices[midi_note] = voice
        self.synth.press( voice )

    def note_off(self, midi_note, midi_vel=0):  # pylint: disable=unused-argument
        """Turn off a synthesizer note, using stadnard MIDI note & velocity values."""
        voice = self.voices.get(midi_note, None)
        if voice:
            self.synth.release(voice)
            self.voices.pop(midi_note)  # TODFIXME: need to run filter after release cycle



class PolyWaveSynth(Instrument):
    """
    This implementation of Instrument is a two-oscillator per voice
    subtractive synth with detunable oscillators,
    with configurable filter w/ filter envelope and an amplitude envelope.
    Each oscillator can also be a customized wavetable with wavemixing
    between two different waveforms.
    
    Note: each waveform (either basic or wavetable) has a max amplitude
    of +/-16383 instead of +/-32767 to provide from summing headroom
    when doing multiple voices (synthio tries to do this, but I still
    experience clipping)
    """

    def __init__(self, synth, patch):
        super().__init__(synth)
        self.load_patch(patch)

    def update_filter_mode(self):
        if self.patch.filt_type == "LP":
            self.filter_mode = synthio.FilterMode.LOW_PASS
        elif self.patch.filt_type == "HP":
            self.filter_mode = synthio.FilterMode.HIGH_PASS
        elif self.patch.filt_type == "BP":
            self.filter_mode = synthio.FilterMode.BAND_PASS
        else: 
            self.filter_mode = None

    def load_patch(self, patch):
        """Loads patch specifics from passed-in Patch object.
           ##### FIXME: no it doesnt: Will reload patch if patch is not specified. """
        self.patch = patch #  self.patch or patch
        print("PolyWaveSynth.load_patch:", patch, patch.wave_dir)

        self.synth.blocks.clear()   # remove any global LFOs

        raw_lfo1 = synthio.LFO(rate = self.patch.wave_mix_lfo_rate)
        lfo1 = synthio.Math( synthio.MathOperation.SCALE_OFFSET, raw_lfo1, 0.5, 0.5) # unipolar
        self.wave_lfo = lfo1
        self.synth.blocks.append(lfo1)  # global lfo for wave_lfo
        
        # standard two-osc oscillator patch
        if patch.wave_type == WaveType.OSC:
            # self.waveform is our working buffer, overwritten w/ wavemix
            self.waveform = Waves.make_waveform('silence')
            self.waveformA = Waves.make_waveform(patch.wave)
            self.waveformB = None
            if patch.waveB:
                self.waveformB = Waves.make_waveform(patch.waveB)
            else:
                self.waveform = self.waveformA

        # wavetable patch
        elif patch.wave_type == WaveType.WTB:
            self.wavetable = Wavetable(patch.wave_dir+"/"+patch.wave+".WAV")
            self.waveform = self.wavetable.waveform

    def reload_patch(self):
        """Reload the set patch, turns off all notes"""
        self.note_off_all()
        self.synth.blocks.clear()  # clear out global wavetable LFOs (if any)
        self.load_patch(self.patch)

    def _update_filter(self, osc1, osc2, filt_env):
        # FIXME: rethink this
        #filt_amount = self.patch.filt_env_amount
        #filt_fmax = 8000   # TODFIXME: put this & filt_fmin somewhere (instrument?)
        #filt_mod = filt_amount * filt_fmax * (filt_env.value/2)  # 8k/2 = max freq
        #filt_f = min(max(self.patch.filt_f + filt_mod, 60), 8000)
        filt_f = self.patch.filt_f
        osc1.filter.frequency.scale = filt_f
        if osc2:
            osc2.filter.frequency.scale = filt_f

    def update(self):
        """Update filter envelope and wave-mixing, should be called frequently"""
        p = self.patch
        for (osc1,osc2,filt_env) in self.voices.values():

            # for each voice, update filter
            self._update_filter(osc1,osc2,filt_env)

            # if wavetable, wave_mix is normalized wave pos in wavetable
            if p.wave_type == WaveType.WTB:
                self.wave_lfo.a.rate = p.wave_mix_lfo_rate  # TODFIXME: danger
                # TODFIXME what is wave_mix_lfo_amount range
                wave_pos = self.wave_lfo.value * p.wave_mix_lfo_amount * 10
                wave_pos += p.wave_mix * self.wavetable.num_waves
                self.wavetable.set_wave_pos(wave_pos)

            # else simple osc wave mixing between two waveforms
            else:
                if self.waveformB:
                    # TODFIXME: does not work yet
                    #wave_mix = self.patch.wave_mix + self.wave_lfo.a.rate
                    #  * self.patch.wave_mix_lfo_amount * 2
                    wave_mix = self.patch.wave_mix  # but at least this works
                    osc1.waveform[:] = lerp(self.waveformA, self.waveformB, wave_mix)
                    if osc2:
                        osc2.waveform[:] = lerp(self.waveformA, self.waveformB, wave_mix)

    def note_on(self, midi_note, midi_vel=127):
        # amp_env = self.patch.amp_env.make_env()
        self.update_filter_mode()  # sigh
        #print("filt_type:", self.filter_mode, self.patch.filt_type)
        lvl = 0.25 + (midi_vel/127/2)
        amp_env = synthio.Envelope(attack_time = self.patch.amp_env.attack_time,
                                   decay_time = self.patch.amp_env.decay_time,
                                   release_time = self.patch.amp_env.release_time,
                                   attack_level = lvl,
                                   sustain_level = lvl)

        filt_min_freq = 100  # fixme
        filt_env_rate = 1 / (self.patch.filt_env.attack_time + 0.001)
        filt_env = synthio.LFO(once=True, rate=filt_env_rate,
                               offset=filt_min_freq, scale=self.patch.filt_f,
                               waveform=lfo_exp_wave)

        filt = synthio.Biquad(self.filter_mode, frequency=filt_env, Q=self.patch.filt_q)
                              
        f = synthio.midi_to_hz(midi_note)
        osc1 = synthio.Note( frequency=f, waveform=self.waveform, envelope=amp_env, filter=filt)
        ## osc2 = None
        ## if self.patch.detune:
        osc2 = synthio.Note(frequency=f * self.patch.detune,
                            waveform=self.waveform,
                            envelope=amp_env, filter=filt)

        self.voices[midi_note] = (osc1, osc2, filt_env)
        self.update()  # update filter and wave before note press
        self.synth.press( (osc1,osc2) )
        self.synth.blocks.append(filt_env) # not tracked automaticallly by synthio


    def note_off(self, midi_note, midi_vel=0):
        (osc1,osc2,filt_env) = self.voices.get(midi_note, (None,None,None))
        #print("note_off:",osc1)

        # FIXME: add release envelope to filter
        
        if osc1:  # why this check: in case user tries to note_off a non-existant note
            self.synth.release((osc1,osc2))
            # TODFIXME: let filter run on release, check amp_env?
            self.voices.pop(midi_note)
            # TODFIXME: figure out how to release after note is done
            self.synth.blocks.remove(filt_env)
        #print("note_off: blocks:", self.synth.blocks)

    def note_off_all(self):
        """Turn off all currently playing notes"""
        for n in self.voices:
            print("note_off_all:",n)
            self.note_off(n)

    def redetune(self):
        """Update detune settings in realtime"""
        for (osc1,osc2,*_) in self.voices.values():
            osc2.frequency = osc1.frequency * self.patch.detune

#
# class MonoOsc(Instrument):
#     def __init__(self, synth, patch):
#         super().__init__(synth)
#         self.load_patch(patch)
