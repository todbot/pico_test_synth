# SPDX-FileCopyrightText: Copyright (c) 2025 Tod Kurt
# SPDX-License-Identifier: MIT
"""
`pitch_glider.py`
================================================================================

Portamento tool for synthio.Note

10 Feb 2025 - @todbot / Tod Kurt

"""
# pitch_glider.py --
# part of todbot circuitpython synthio tutorial
# 10 Feb 2025 - @todbot / Tod Kurt

import synthio
import ulab.numpy as np

class Glider:
    """Attach a Glider to note.bend to implement portamento"""
    def __init__(self, glide_time, midi_note):
        glide_time = glide_time or 0.001
        self.pos = synthio.LFO(once=True, rate=1/glide_time,
                               waveform=np.array((0,32767), dtype=np.int16))
        self.lerp = synthio.Math(synthio.MathOperation.CONSTRAINED_LERP,
                                 0, 0, self.pos)
        self.midi_note = midi_note

    def update(self, new_midi_note):
        """Update the glide destination based on new midi note"""
        self.lerp.a = self.bend_amount(new_midi_note, self.midi_note)
        self.lerp.b = 0  # end on the new note
        self.pos.retrigger()  # restart the lerp
        #print("bend_amount:", self.bend_amount(self.midi_note, new_midi_note),
        #      "old", self.midi_note, "new:", new_midi_note, self.lerp.a, self.lerp.b)
        self.midi_note = new_midi_note

    def bend_amount(self, old_midi_note, new_midi_note):
        """Calculate how much note.bend has to happen between two notes"""
        return (new_midi_note - old_midi_note)  * (1/12)

    @property
    def glide_time(self):
        return 1 / self.pos.rate
    
    @glide_time.setter
    def glide_time(self, glide_time):
        glide_time = glide_time or 0.001
        self.pos.rate = 1 / glide_time
