## pylint: disable=invalid-name,too-many-arguments,multiple-statements
#multiple-statements,too-many-instance-attributes
# SPDX-FileCopyrightText: Copyright (c) 2023 Tod Kurt
# SPDX-License-Identifier: MIT
"""
`waves`
================================================================================

`Waves` is a set of waveform construction tools for `synthio`.
`Wavetable` uses `Waves` to create a Wavetable waveform for `Instrument`
that can load arbitrary two waveforms and mix between them.

Part of synth_tools.

"""

import random
import ulab.numpy as np
import adafruit_wave

""" mix between values a and b, works with numpy arrays too,  t ranges 0-1"""
def lerp(a, b, t):  return (1-t)*a + t*b  # pylint: disable=missing-function-docstring

class Waves:
    """
    Generate waveforms for either oscillator or LFO use
    By default, audio waveforms are half-amplitude (+/- 16383)
    """

    waveform_types = ('SIN', 'SQU', 'SAW', 'TRI', 'SIL', 'NZE')

    @staticmethod
    def make_waveform(waveid, size=512, volume=32767//2):
        """Return a waveform by string name, one of `waveform_types`"""
        waveid = waveid.upper()
        wavef = None
        if waveid in ('SIN', 'SINE'):
            wavef = Waves.sine(size,volume)
        elif waveid in ('SQU', 'SQUARE'):
            wavef = Waves.square(size,volume)
        elif waveid in ('SAW'):
            wavef = Waves.saw(size,volume)
        elif waveid in ('TRI', 'TRIANGLE'):
            wavef = Waves.triangle(size, -volume, volume)
        elif waveid in ('SIL', 'SILENCE'):
            wavef = Waves.silence(size)
        elif waveid in ('NZE', 'NOISE'):
            wavef =  Waves.noise(size,volume)
        else:
            print("unknown wave type", waveid)
        return wavef

    @staticmethod
    def sine(size, volume):
        """Sine waveform"""
        return np.array(np.sin(np.linspace(0, 2*np.pi, size, endpoint=False))
                        * volume, dtype=np.int16)

    @staticmethod
    def square(size, volume):
        """Square waveform"""
        return np.concatenate((np.ones(size//2, dtype=np.int16) * volume,
                               np.ones(size//2, dtype=np.int16) * -volume))

    @staticmethod
    def triangle(size, min_vol, max_vol):
        """Triangle waveform"""
        return np.concatenate((np.linspace(min_vol, max_vol, num=size//2, dtype=np.int16),
                               np.linspace(max_vol, min_vol, num=size//2, dtype=np.int16)))

    @staticmethod
    def saw(size, volume):
        """Saw (aka Ramp) waveform"""
        return Waves.saw_down(size,volume)

    @staticmethod
    def saw_down(size, volume):
        """Saw waveform from max to min"""
        return np.linspace(volume, -volume, num=size, dtype=np.int16)

    @staticmethod
    def saw_up(size, volume):
        """Saw waveform from min to max"""
        return np.linspace(-volume, volume, num=size, dtype=np.int16)

    @staticmethod
    def silence(size):
        """All zeros waveform"""
        return np.zeros(size, dtype=np.int16)

    @staticmethod
    def noise(size,volume):
        """White noise waveform (from random.randint)"""
        return np.array([random.randint(-volume, volume) for i in range(size)], dtype=np.int16)

    @staticmethod
    def from_list( vals ):
        """Waveform from a list of values, useful for LFOs"""
        #print("Waves.from_list: vals=",vals)
        return np.array( [int(v) for v in vals], dtype=np.int16 )

    @staticmethod
    def lfo_ramp_up_pos():
        """Simple two-element ramp-up waveform for synthio.LFO (which does interpolation)"""
        return np.array( (0,32767), dtype=np.int16)

    @staticmethod
    def lfo_ramp_down_pos():
        """Simple two-element row-downwaveform for synthio.LFO (which does interpolation)"""
        return np.array( (32767,0), dtype=np.int16)

    @staticmethod
    def lfo_triangle_pos():
        """Simple three-element triangle waveform for synthio.LFO (which does interpolation)"""
        return np.array( (0, 32767, 0), dtype=np.int16)

    @staticmethod
    def lfo_triangle():
        """Simple four-element triangle waveform for synthio.LFO (which does interpolation)"""
        return np.array( (0, 32767, 0, -32767), dtype=np.int16)

    @staticmethod
    def from_ar_times(attack_time=1, release_time=1):
        """
        Generate a fake Attack/Release 'Envelope' using an LFO waveform.
        This is a dumb way of doing it, but since we cannot get .value()
        out of Envelope, we have to fake it with an LFO.        
        """
        #s = attack_time + release_time
        a10 = int(attack_time * 10)
        r10 = int(release_time*10)
        a = [i*65535//a10 - 32767 for i in range(a10)]
        r = [32767 - i*65535//r10 for i in range(r10)]
        return Waves.from_list(a + [32767,] + r)  # add a max middle

    @staticmethod
    def wav(filepath, size=256, pos=0):
        """Create a waveform from a WAV file using adafruit_wave"""
        with adafruit_wave.open(filepath) as w:
            if w.getsampwidth() != 2 or w.getnchannels() != 1:
                raise ValueError("unsupported format")
            #n = w.getnframes() if size==0 else size
            n = size
            w.setpos(pos)
            return np.frombuffer(w.readframes(n), dtype=np.int16)

    @staticmethod
    def wav_info(filepath):
        """return (nframes,nchannels,sampwidth) from a WAV filename"""
        with adafruit_wave.open(filepath) as w:
            return (w.getnframes(), w.getnchannels(), w.getsampwidth())


class Wavetable:
    """
    A 'waveform' for synthio.Note that uses a wavetable with a scannable
    wave position. A wavetable is a collection of harmonically-related
    single-cycle waveforms. Often the waveforms are 256 samples long and
    the wavetable containing 64 waves. The wavetable oscillator lets the
    user pick which of those 64 waves to use, usually allowing one to mix
    between two waves.

    Some example wavetables usable by this classs: https://waveeditonline.com/

    In this implementation, you select a wave position (wave_pos) that can be
    fractional, and the fractional part allows for mixing of the waves
    at wave_pos and wave_pos+1.

    Note: each waveform (either basic or wavetable) has a max amplitude
    of +/-16383 instead of +/-32767 to provide from summing headroom
    when doing multiple voices (synthio tries to do this, but I still
    experience clipping)
    """

    def __init__(self, filepath, size=256, in_memory=False):
        self.filepath = filepath
        """Sample size of each wave in the table"""
        self.size = size
        self.w = adafruit_wave.open(filepath)
        if self.w.getsampwidth() != 2 or self.w.getnchannels() != 1:
            raise ValueError("unsupported WAV format")
        self.wav = None
        if in_memory:  # load entire WAV into RAM
            self.wav = np.frombuffer(self.w.readframes(self.w.getnframes()), dtype=np.int16)
        self.samp_posA = -1

        """How many waves in this wavetable"""
        self.num_waves = self.w.getnframes() / self.size
        """ The waveform to be used by synthio.Note """
        self.waveform = Waves.silence(size) # makes a buffer for us to lerp into
        self.set_wave_pos(0)

    def set_wave_pos(self,wave_pos):
        """
        wave_pos integer part of specifies which wave from 0-num_waves,
        and fractional part specifies mix between wave and wave next to it
        (e.g. wave_pos=15.66 chooses 1/3 of waveform 15 and 2/3 of waveform 16)
        """
        wave_pos = min(max(wave_pos, 0), self.num_waves-1)  # constrain
        self.wave_pos = wave_pos

        samp_posA = int(wave_pos) * self.size
        samp_posB = int(wave_pos+1) * self.size
        #print("samp_posA", samp_posA, self.samp_posA, wave_pos)
        if samp_posA != self.samp_posA:  # avoid needless computation
            if self.wav:  # if we've loaded the entire wavetable into RAM
                waveformA = self.wav[samp_posA : samp_posA + self.size] # slice
                waveformB = self.wav[samp_posB : samp_posB + self.size]
            else:
                self.w.setpos(samp_posA)
                waveformA = np.frombuffer(self.w.readframes(self.size), dtype=np.int16)
                self.w.setpos(samp_posB)
                waveformB = np.frombuffer(self.w.readframes(self.size), dtype=np.int16)

            self.samp_posA = samp_posA  # save
            self.waveformA = waveformA
            self.waveformB = waveformB

        # fractional position between a wave A & B
        wave_pos_frac = wave_pos - int(wave_pos)
        # mix waveforms A & B and copy result into waveform used by synthio
        # and reduce volume of wavetable by 2 so multi-voice doesn't distort as much
        self.waveform[:] = lerp(self.waveformA, self.waveformB, wave_pos_frac) // 2

    def deinit(self):
        """Close the WAV file used by this wavetable"""
        self.w.close()
