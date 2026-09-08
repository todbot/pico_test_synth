# CircuitPython apps for pico_test_synth

CircuitPython demos for the pico_test_synth and pico_test_synth2 boards.

* [`hwtest`](hwtest/) - canonical hardware/pin reference for this board and a simple synth. Start here. 
* [`synth1`](synth1/) - small demo synth: filter sweeps, detune, MIDI in 
* [`wavesynth`](wavesynth/) - wavetable polysynth with 9 saveable patches 
* [`tbish`](tbish/) - TB-303-like monosynth with step-sequencer
* [`tbish2`](tbish2/) - TB-303-style acid bassline on `BasslineSynth`, with a step sequencer. Will try to use `audiofilters`/`audiodelays` for fatter sound
* [`synthtools_polysynth`](synthtools_polysynth/) - 16-pad chromatic polysynth on `SubtractiveSynth`, 18 parameters grouped into 7 named sections, two pots per pair 
* [`synthtools_arp`](synthtools_arp/) - hold pads, `Arpeggiator` plays them back 
* [`synthtools_swarm`](synthtools_swarm/) - `SwarmSynth` drone — up to 8 detuned oscillators per note 



## Install

You can use circup to install needed libraries:
```
circup install -r requirements.txt
```

For each demo, copy the contents of the directory flat onto the CIRCUITPY
root and reset.


## Notes

### Sample rate

These demos run at 22050 Hz sample rate in stereo, this works on RP2040 (Pico)
and RP2350 (Pico2). The Pico2 can do 44100 Hz sample rate. 

Every demo sets `FILT_F_MAX` on its synth subclass before constructing it to
be below the Nyquist frequency for the sample rate (e.g. 11 kHz for 22050 Hz),
since filter frequency above Nyquist is undefined. 
