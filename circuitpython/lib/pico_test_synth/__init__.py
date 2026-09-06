# SPDX-FileCopyrightText: Copyright (c) 2023 Tod Kurt
# SPDX-License-Identifier: MIT
#
# pico_test_synth -- board support for the pico_test_synth boards
#
# Hardware is re-exported here, so both of these work:
#
#     from pico_test_synth import Hardware
#     from pico_test_synth.hardware import Hardware
#
# `ui` is deliberately NOT imported. It pulls in displayio,
# adafruit_display_text and vectorio, and plenty of programs draw their
# own screen (tbish2) or bring their own UI library (wavesynth). Ask for
# it by name if you want the general one:
#
#     from pico_test_synth.ui import SynthUI

from .hardware import Hardware

__all__ = ("Hardware",)
