import time, random, board
import audiocore, audiobusio
import audiomixer, synthio

# pin definitions
sw_pin        = board.GP28
knobB_pin     = board.GP27
knobA_pin     = board.GP26
led_pin       = board.GP25  # regular LED, not neopixel
pico_pwr_pin  = board.GP23  # HIGH = improved ripple (lower noise) but less efficient
i2s_data_pin  = board.GP22
i2s_lclk_pin  = board.GP21
i2s_bclk_pin  = board.GP20
i2c_scl_pin   = board.GP19
i2c_sda_pin   = board.GP18
uart_rx_pin   = board.GP17
uart_tx_pin   = board.GP16
touch_pins = (board.GP0, board.GP1, board.GP2, board.GP3,
              board.GP4, board.GP5, board.GP6, board.GP7,
              board.GP8, board.GP9, board.GP10, board.GP11,
              board.GP12, board.GP13, board.GP14, board.GP15)

sample_rate = 22100
CHANNEL_COUNT=2
buffer_size = 2048
audio = audiobusio.I2SOut(bit_clock=i2s_bclk_pin,
                                       word_select=i2s_lclk_pin,
                                       data=i2s_data_pin)
mixer = audiomixer.Mixer(sample_rate=sample_rate, voice_count=1,
                                      channel_count=CHANNEL_COUNT,
                                      bits_per_sample=16, samples_signed=True,
                                      buffer_size=buffer_size)
synth = synthio.Synthesizer(sample_rate=sample_rate,
                            channel_count=CHANNEL_COUNT)
audio.play(mixer)
mixer.voice[0].play(synth)

while True:
    synth.release_all()
    synth.press( random.randint(33,66) )
    print("hi")
    time.sleep(1)
    
