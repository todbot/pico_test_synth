# pico_test_synth_hwtest_code.py -- test hardware of pico_test_synth board
# 27 Jun 2023 - 15 Feb 2024 - @todbot / Tod Kurt
# 3 May 2025 - updated for CircuitPython 10
# 24 Nov 2025 - updated to be compatible with pico_test_synth2
#
# Functionality:
# - touch pads to trigger synth notes (defined in 'midi_notes')
# - middle button triggers random synth notes
# - left knob controls filter cutoff
# - right knob controls filter resonance
# - sending TRS UART MIDI will print out those bytes to the REPL
#
# Libaries needed:
# - asyncio
# - adafruit_displayio_ssd1306
# - adafruit_display_text
# - adafruit_midi
# Install them all with:
#   circup install asyncio adafruit_displayio_ssd1306 adafruit_display_text adafruit_midi
#
#
import asyncio
import time, random
import board, digitalio, busio
import analogio, keypad
import audiobusio, audiomixer, synthio
import ulab.numpy as np
import i2cdisplaybus, displayio, terminalio
import adafruit_displayio_ssd1306
from adafruit_display_text import bitmap_label as label
import touchio
import usb_midi
import adafruit_midi
from adafruit_midi.note_on import NoteOn
from adafruit_midi.note_off import NoteOff
from adafruit_midi.control_change import ControlChange

SAMPLE_RATE = 28000
BUFFER_SIZE = 4096   # need a bigger buffer when screen updated
midi_notes = list(range(48,48+16))  # which MIDI notes the touch pads send
filter_freq = 4000
filter_resonance = 1.2
output_volume = 1.0   # change to suit your input device

# set which way touch pads work
pull_type = digitalio.Pull.UP    # default for pico_test_synth2
#pull_type = digitalio.Pull.DOWN  # only option for pico_test_synth original

# pin definitions
sw_pin        = board.GP28
knobB_pin     = board.GP27
knobA_pin     = board.GP26
i2s_data_pin  = board.GP22
i2s_lclk_pin  = board.GP21
i2s_bclk_pin  = board.GP20
i2c_scl_pin   = board.GP19
i2c_sda_pin   = board.GP18
uart_rx_pin   = board.GP17
uart_tx_pin   = board.GP16

touch_pins = (
    board.GP0, board.GP1, board.GP2, board.GP3, board.GP4, board.GP5,
    board.GP6, board.GP7 ,board.GP8, board.GP9, board.GP10, board.GP11,
    board.GP12, board.GP13, board.GP14, board.GP15 )
num_touch_pins = len(touch_pins)

# begin board setup
displayio.release_displays()

# set up our knobs and button
knobA = analogio.AnalogIn(knobA_pin)
knobB = analogio.AnalogIn(knobB_pin)
keys = keypad.Keys( pins=(sw_pin,),  value_when_pressed=False )

# set up touch pins
touchins = []
for pin in touch_pins:
    print("touch pin:", pin)
    touchin = touchio.TouchIn(pin, pull=pull_type)
    touchin.threshold = int(touchin.threshold * 1.1)
    touchins.append(touchin)

print("starting up...")
i2c = busio.I2C(scl=i2c_scl_pin, sda=i2c_sda_pin, frequency=1_000_000)
uart = busio.UART(rx=uart_rx_pin, tx=uart_tx_pin, baudrate=31250, timeout=0.001)
midi_uart = adafruit_midi.MIDI(midi_in=uart, midi_out=uart)
midi_usb = adafruit_midi.MIDI(midi_in=usb_midi.ports[0], midi_out=usb_midi.ports[1])

dw,dh = 128, 64
display_bus = i2cdisplaybus.I2CDisplayBus(i2c, device_address=0x3c)
display = adafruit_displayio_ssd1306.SSD1306(display_bus, width=dw, height=dh, rotation=180)

# set up the synth->audio system
audio = audiobusio.I2SOut(bit_clock=i2s_bclk_pin, word_select=i2s_lclk_pin, data=i2s_data_pin)
mixer = audiomixer.Mixer(voice_count=1, sample_rate=SAMPLE_RATE, channel_count=1,
                         bits_per_sample=16, samples_signed=True,
                         buffer_size=BUFFER_SIZE) 
synth = synthio.Synthesizer(sample_rate=SAMPLE_RATE)
audio.play(mixer)
mixer.voice[0].level = output_volume
mixer.voice[0].play(synth)

# set up the synth
wave_saw = np.linspace(32000,-32000, num=256, dtype=np.int16)  # default squ is too clippy
amp_env = synthio.Envelope(attack_time=0.2, release_time=0.4, decay_time=0.5, attack_level=0.5, sustain_level=0.5)
synth.envelope = amp_env

# set up info to be displayed
maingroup = displayio.Group()
display.root_group = maingroup
text1 = label.Label(terminalio.FONT, text="pico_test_synth", x=0, y=10)
text2 = label.Label(terminalio.FONT, text="@todbot", x=0, y=25)
text3 = label.Label(terminalio.FONT, text="pico_test_synth!", x=0, y=50)
for t in (text1, text2, text3):
    maingroup.append(t)
time.sleep(1)

notes_pressed = {}
sw_pressed = False

def note_on(midi_note):
    print("note_on:", midi_note)
    note_off(midi_note)  # only one note per midi_note allowed 
    f = synthio.midi_to_hz(midi_note)
    filter = synthio.Biquad(synthio.FilterMode.LOW_PASS, filter_freq, filter_resonance)
    n = synthio.Note(frequency=f, waveform=wave_saw, filter=filter, amplitude=0.75)
    synth.press( n )
    notes_pressed[midi_note] = n

def note_off(midi_note):
    if n := notes_pressed.get(midi_note,None):
        synth.release(n)

            
# print to REPL current state of knobs, button, and touchpads
async def debug_printer():
    t1_last = ""
    t2_last = ""
    while True:
        t1 = "K1:%3d   S:%d   %3d:K2" % (knobA.value//255, sw_pressed, knobB.value//255)
        t2 = "T:" + ''.join('%1d' % t.value for t in touchins)
        if t1 != t1_last:
            t1_last = t1
            text1.text = t1  # only change screen when we need to
        if t2 != t2_last:
            t2_last = t2
            text2.text = t2
        print(text1.text)
        print(text2.text)
        #print("T:" + ''.join(["%3d " % (t.raw_value//16) for t in touchins[0:4]]))
        await asyncio.sleep(0.2)

# handle all user input: knobs, button, and touchpads
async def input_handler():
    global filter_freq, filter_resonance, sw_pressed

    last_touches = [False] * num_touch_pins
    
    while True:
        filter_freq = knobA.value/65535 * 8000 + 100  # range 100-8100
        filter_resonance = knobB.value/65535 * 3 + 0.2  # range 0.2-3.2

        for n in notes_pressed.values():  # real-time adjustment of filter
            if n:
                n.filter.frequency = filter_freq
                n.filter.Q = filter_resonance
                
        for i in range(num_touch_pins):
            t = touchins[i].value
            lt = last_touches[i]
            last_touches[i] = t
            if t and not lt:   # press
                print("\t\ttouch press  ",i)
                midi_note = midi_notes[i]
                note_on(midi_note)
                msg = NoteOn(midi_note, velocity=100)
                midi_usb.send( msg )
                midi_uart.send( msg )
            elif not t and lt:
                print("\t\ttouch release",i)
                midi_note = midi_notes[i]
                note_off(midi_note)
                msg = NoteOff(midi_note, velocity=0)
                midi_usb.send( msg )
                midi_uart.send( msg )       

        if key := keys.events.get():
            if key.pressed:
                sw_pressed = True
                midi_note = random.randint(32,60)
                note_on(midi_note)
            if key.released:
                sw_pressed = False
                note_off(midi_note)
        
        await asyncio.sleep(0.003)


async def midi_handler():
    while True:
        while msg := midi_usb.receive() or midi_uart.receive():
            if isinstance(msg, NoteOn) and msg.velocity != 0:
                note_on(msg.note)
            elif isinstance(msg,NoteOff) or isinstance(msg,NoteOn) and msg.velocity==0:
                note_off(msg.note)
        await asyncio.sleep(0.001)


# main coroutine
async def main():  # Don't forget the async!
    task1 = asyncio.create_task(debug_printer())
    task2 = asyncio.create_task(input_handler())
    task3 = asyncio.create_task(midi_handler())
    await asyncio.gather(task1,task2,task3)

print("hello pico_test_synth hwtest")
asyncio.run(main())
