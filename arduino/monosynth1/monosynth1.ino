/**
 * monosynth1 wubwubwub synth using LowPassFilter
 * based on 'monosynth1' from https://github.com/todbot/mozzi_experiments
 * based MozziScout "mozziscout_monosynth1"
 *
 * Responds to Serial (DIN) MIDI In and USB MIDI
 *
 * @todbot 3 Jan 2021
 **/

// set DEBUG_MIDI 1 to show CCs received in Serial Monitor
#define DEBUG_MIDI 1

#include <Adafruit_TinyUSB.h>
#include <MIDI.h>
#include <TouchyTouch.h>

#include "MozziConfigValues.h"  // for named option values
#define MOZZI_AUDIO_MODE MOZZI_OUTPUT_I2S_DAC
#define MOZZI_AUDIO_CHANNELS MOZZI_STEREO 
#define MOZZI_AUDIO_BITS 16
#define MOZZI_AUDIO_RATE 32768 // must be power of two
#define MOZZI_I2S_PIN_BCK 20
#define MOZZI_I2S_PIN_WS (MOZZI_I2S_PIN_BCK+1) // HAS TO BE NEXT TO pBCLK, i.e. default is 21
#define MOZZI_I2S_PIN_DATA 22
#define MOZZI_ANALOG_READ MOZZI_ANALOG_READ_NONE  // we're using regular analogRead()
//#define OSCIL_DITHER_PHASE 1 
// Mozzi's controller update rate, seems to have issues at 1024
// If slower than 512 can't get all MIDI from Live
#define MOZZI_CONTROL_RATE 512  // mozzi rate for updateControl()
//#define MOZZI_CONTROL_RATE 128 // mozzi rate for updateControl()

#include <Mozzi.h>
#include <Oscil.h>
#include <tables/triangle_analogue512_int8.h>
#include <tables/square_analogue512_int8.h>
#include <tables/saw_analogue512_int8.h>
#include <tables/cos2048_int8.h> // for filter modulation
#include <ResonantFilter.h>
#include <ADSR.h>
#include <Portamento.h>
#include <mozzi_midi.h> // for mtof()
#include <mozzi_rand.h> // for rand()


#define sw_pin         28
#define knobB_pin      27
#define knobA_pin      26
#define led_pin        25  // regular LED, not neopixel
#define pico_pwr_pin   23  // HIGH = improved ripple (lower noise) but less efficient
#define i2s_data_pin   22  //
#define i2s_lclk_pin   21
#define i2s_bclk_pin   20
#define i2c_scl_pin    19  // on I2C1 aka Wire1
#define i2c_sda_pin    18
#define uart_rx_pin    17  // on UART0 aka Serial1
#define uart_tx_pin    16

Adafruit_USBD_MIDI usb_midi;                                  // USB MIDI object
MIDI_CREATE_INSTANCE(Adafruit_USBD_MIDI, usb_midi, MIDIusb);  // USB MIDI
// MIDI_CREATE_INSTANCE(HardwareSerial, Serial1, MIDIuart);      // Serial MIDI

const int touch_pins[] = { 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15 };
const int touch_count = sizeof(touch_pins) / sizeof(int);
const int touch_threshold_adjust = 100;

TouchyTouch touches[touch_count];
bool touched[touch_count];

// SETTINGS
//int portamento_time = 50;  // milliseconds
//int env_release_time = 1000; // milliseconds
byte patch_num = 0; // patch number / program change
bool retrig_lfo = true;

enum KnownCCs {
  Modulation=0,
  Resonance,
  FilterCutoff,
  PortamentoTime,
  EnvReleaseTime,
  CC_COUNT
};

// mapping of KnownCCs to MIDI CC numbers (this is somewhat standardized)
uint8_t midi_ccs[] = {
  1,   // modulation
  71,  // resonance
  74,  // filter cutoff
  5,   // portamento time
  72,  // env release time
};
uint8_t mod_vals[ CC_COUNT ];

typedef struct {
    int wave_type; // 0 = saw, 
    int filter_type; // 0 = lpf, 1 = bpf, 2 = hpf
    float detune;
    float filter_f;
    float filter_q;
    float filtermod_freq;
    float attack_time;
    float release_time;
} Patch;


//struct MySettings : public MIDI_NAMESPACE::DefaultSettings {
//  static const bool Use1ByteParsing = false; // Allow MIDI.read to handle all received data in one go
//  static const long BaudRate = 31250;        // Doesn't build without this...
//};
//MIDI_CREATE_CUSTOM_INSTANCE(HardwareSerial, Serial1, MIDI, MySettings); // for USB-based SAMD
//MIDI_CREATE_DEFAULT_INSTANCE();

//
Oscil<SAW_ANALOGUE512_NUM_CELLS, MOZZI_AUDIO_RATE> aOsc1(SAW_ANALOGUE512_DATA);
Oscil<SAW_ANALOGUE512_NUM_CELLS, MOZZI_AUDIO_RATE> aOsc2(SAW_ANALOGUE512_DATA);

Oscil<COS2048_NUM_CELLS, MOZZI_CONTROL_RATE> kFilterMod(COS2048_DATA); // filter mod

ADSR <CONTROL_RATE, MOZZI_AUDIO_RATE> envelope;
Portamento <MOZZI_CONTROL_RATE> portamento;
LowPassFilter lpf;

int notes_on = 0;
uint32_t last_debug_millis; 

// core0 is UI
void setup() { 
  pinMode(LED_BUILTIN, OUTPUT);

  // Serial1.setRX(uart_rx_pin);
  // Serial1.setTX(uart_tx_pin);

  Serial.begin(115200);
  MIDIusb.begin(MIDI_CHANNEL_OMNI);
  MIDIusb.turnThruOff();   // turn off echo
  // MIDIuart.begin(MIDI_CHANNEL_OMNI); // don't forget OMNI
  // MIDIuart.turnThruOff();  // turn off echo

  // TOUCH
  for (int i = 0; i < touch_count; i++) {
    touches[i].begin(touch_pins[i]);
    touches[i].threshold += touch_threshold_adjust;  // make a bit more noise-proof
    touched[i] = false;
  }
}

// core0 is UI
void loop() { 
  handleMIDI();
  
  updateInputs();

  if( millis() - last_debug_millis > 100 ) { 
    last_debug_millis = millis();
    for (int i = 0; i < touch_count; i++) {
      char t = touches[i].touched() ? '|' : ' ';  // indicates a touched value
      int touchval = touches[i].raw_value / 100;  // make a more printalbe value
      Serial.printf("%c%2d%c", t, touchval, t);
    }
    Serial.println();
  }

}

// core1 is audio
void setup1() {
  startMozzi(MOZZI_CONTROL_RATE);
  handleProgramChange(patch_num); // set our initial patch
 }
 
// core1 is audio
void loop1() {
  audioHook();
}

//
void handleNoteOn(byte channel, byte note, byte velocity) {
  (void) channel;
  (void) velocity;
  #if DEBUG_MIDI
  Serial.println("midi_test handleNoteOn!");
  #endif
  digitalWrite(LED_BUILTIN,HIGH);
  portamento.start(note);
  envelope.noteOn();
  notes_on++;
}

//
void handleNoteOff(byte channel, byte note, byte velocity) {
  (void) channel;
  (void) note;
  (void) velocity;
  digitalWrite(LED_BUILTIN,LOW);
  notes_on--;
  if( ! notes_on ) { 
    envelope.noteOff();
  }
}

//
void handleControlChange(byte channel, byte cc_num, byte cc_val) {
  (void) channel;
  #if DEBUG_MIDI 
  Serial.printf("CC %d %d\n", cc_num, cc_val);
  #endif
  for( int i=0; i<CC_COUNT; i++) { 
    if( midi_ccs[i] == cc_num ) { // we got one
      mod_vals[i] = cc_val;
      // special cases, not set every updateControl()
      if( i == PortamentoTime ) { 
        portamento.setTime( mod_vals[PortamentoTime] * 2);
      }
      else if( i == EnvReleaseTime ) {
         envelope.setReleaseTime( mod_vals[EnvReleaseTime]*10 );
      }
    }
  }
}

//
void handleProgramChange(byte m) {
  Serial.print("program change:"); Serial.println((byte)m);
  patch_num = m;
  if( patch_num == 0 ) {    
    aOsc1.setTable(SAW_ANALOGUE512_DATA);
    aOsc2.setTable(SAW_ANALOGUE512_DATA);
    
    mod_vals[Modulation] = 0;   // FIXME: modulation unused currently
    mod_vals[Resonance] = 93;
    mod_vals[FilterCutoff] = 50;
    mod_vals[PortamentoTime] = 50; // actually in milliseconds
    mod_vals[EnvReleaseTime] = 100; // in 10x milliseconds (100 = 1000 msecs)

    lpf.setCutoffFreqAndResonance(mod_vals[FilterCutoff], mod_vals[Resonance]*2);
    
    kFilterMod.setFreq(4.0f);  // fast
    envelope.setADLevels(255, 255);
    envelope.setTimes(50, 200, 20000, mod_vals[EnvReleaseTime]*10 );
    portamento.setTime( mod_vals[PortamentoTime] );
  }
  else if ( patch_num == 1 ) {
    aOsc1.setTable(SQUARE_ANALOGUE512_DATA);
    aOsc2.setTable(SQUARE_ANALOGUE512_DATA);
    
    mod_vals[Resonance] = 50;
    mod_vals[EnvReleaseTime] = 15;
    
    lpf.setCutoffFreqAndResonance(mod_vals[FilterCutoff], mod_vals[Resonance]*2);
    
    kFilterMod.setFreq(0.5f);     // slow
    envelope.setADLevels(255, 255);
    envelope.setTimes(50, 100, 20000, (uint16_t)mod_vals[EnvReleaseTime]*10 );
    portamento.setTime( mod_vals[PortamentoTime] );
  }
  else if ( patch_num == 2 ) {
    aOsc1.setTable(TRIANGLE_ANALOGUE512_DATA);
    aOsc2.setTable(TRIANGLE_ANALOGUE512_DATA);
    mod_vals[FilterCutoff] = 65;
    //kFilterMod.setFreq(0.25f);    // slower
    //retrig_lfo = false;
  }
}

//
void handleMIDI() {
  // Serial.printf("handleMIDI: %ld\n", millis());
  while( MIDIusb.read() ) {  // use while() to read all pending MIDI, shouldn't hang
    switch(MIDIusb.getType()) {
      case midi::ProgramChange:
        handleProgramChange(MIDIusb.getData1());
        break;
      case midi::ControlChange:
        handleControlChange(0, MIDIusb.getData1(), MIDIusb.getData2());
        break;
      case midi::NoteOn:
        handleNoteOn( 0, MIDIusb.getData1(),MIDIusb.getData2());
        break;
      case midi::NoteOff:
        handleNoteOff( 0, MIDIusb.getData1(),MIDIusb.getData2());
        break;
      default:
        break;
    }
  }
}

void updateInputs() {
  static int touchi = 0;

  // button.update();
  // knobA_update();
  // knobB_update();

  // only check one touch button per loop since touchytouch spinloops
  touches[touchi].update();
  if( touches[touchi].pressed() ) { 
    handleNoteOn( 0, 36 + touchi, 127);
  }
  if( touches[touchi].released() ) { 
    handleNoteOff( 0, 36 + touchi, 0);
  }
  touchi = (touchi+1) % touch_count;

}

// Mozzi function, called at CONTROL_RATE times per second on core1
void updateControl() {

  lpf.setCutoffFreqAndResonance(mod_vals[FilterCutoff], mod_vals[Resonance]*2);  // don't *2 filter since we want 0-4096Hz

  envelope.update();
  
  Q16n16 pf = portamento.next();  // Q16n16 is a fixed-point fraction in 32-bits (16bits . 16bits)
  aOsc1.setFreq_Q16n16(pf);
  aOsc2.setFreq_Q16n16(pf * 1.001);  // FIXME: adjustable detune plz
}

// Mozzi function, called at AUDIO_RATE times per second on core1
AudioOutput updateAudio() {
  int32_t asig = aOsc1.next() + aOsc2.next();
  asig = lpf.next( asig );
  asig = envelope.next() * asig;
  return StereoOutput::fromAlmostNBit(18, asig, asig); // 16 = 8 signal bits + 8 envelope bits
}
