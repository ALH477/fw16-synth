#!/usr/bin/env python3
"""
FW16 Synth - FluidSynth controller using Framework 16 keyboard and touchpad
============================================================================
Transforms the Framework 16 into a synthesizer:
- Keyboard: Piano keys with velocity sensitivity (tap speed)
- Touchpad: X=Pitch Bend, Y=Modulation, Pressure=Expression

DeMoD LLC - Anti-corporate synthesis for the people
"""

import asyncio
import sys
import os
import time
import signal
import argparse
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Callable
from enum import IntEnum
from pathlib import Path

try:
    import evdev
    from evdev import ecodes, InputDevice, categorize, UInput
except ImportError:
    print("ERROR: evdev not found. Install with: pip install evdev")
    sys.exit(1)

try:
    import fluidsynth
except ImportError:
    print("ERROR: pyfluidsynth not found. Install with: pip install pyfluidsynth")
    sys.exit(1)


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class SynthConfig:
    """Runtime configuration for the synthesizer"""
    soundfont: str = "/usr/share/soundfonts/default.sf2"
    audio_driver: str = "pulseaudio"  # pulseaudio, jack, alsa, pipewire
    sample_rate: int = 48000
    
    # Keyboard settings
    base_octave: int = 4  # Middle C octave
    velocity_min: int = 40
    velocity_max: int = 127
    velocity_time_min: float = 0.01  # Fastest keypress (max velocity)
    velocity_time_max: float = 0.15  # Slowest keypress (min velocity)
    
    # Touchpad modulation mapping
    touchpad_x_cc: int = 1      # Modulation wheel
    touchpad_y_cc: int = 74     # Filter cutoff (brightness)
    touchpad_pressure_cc: int = 11  # Expression
    pitch_bend_range: int = 2   # Semitones
    
    # Visual feedback
    show_notes: bool = True
    show_touchpad: bool = True


# =============================================================================
# KEYBOARD MAPPING - QWERTY to MIDI Notes
# =============================================================================

class KeyboardLayout:
    """
    Maps QWERTY keyboard to piano keys in a chromatic layout.
    
    Layout (2 rows of keys like a piano):
    
    Upper row (black keys + higher octave):
    2  3     5  6  7     9  0
    C# D#    F# G# A#    C# D#  (octave+1)
    
    Lower row (white keys):
    Q  W  E  R  T  Y  U  I  O  P  [  ]
    C  D  E  F  G  A  B  C  D  E  F  G
    
    Additional lower rows for bass:
    A  S  D  F  G  H  J  K  L  ;  '
    C  D  E  F  G  A  B  C  D  E  F  (octave-1)
    
    Z  X  C  V  B  N  M  ,  .  /
    C  D  E  F  G  A  B  C  D  E  (octave-2)
    """
    
    # Key code to semitone offset from base octave C
    KEYMAP: Dict[int, int] = {
        # Number row - sharps/flats (black keys)
        ecodes.KEY_2: 1,   # C#
        ecodes.KEY_3: 3,   # D#
        ecodes.KEY_5: 6,   # F#
        ecodes.KEY_6: 8,   # G#
        ecodes.KEY_7: 10,  # A#
        ecodes.KEY_9: 13,  # C# (octave+1)
        ecodes.KEY_0: 15,  # D# (octave+1)
        
        # QWERTY row - white keys
        ecodes.KEY_Q: 0,   # C
        ecodes.KEY_W: 2,   # D
        ecodes.KEY_E: 4,   # E
        ecodes.KEY_R: 5,   # F
        ecodes.KEY_T: 7,   # G
        ecodes.KEY_Y: 9,   # A
        ecodes.KEY_U: 11,  # B
        ecodes.KEY_I: 12,  # C (octave+1)
        ecodes.KEY_O: 14,  # D (octave+1)
        ecodes.KEY_P: 16,  # E (octave+1)
        ecodes.KEY_LEFTBRACE: 17,   # F (octave+1)
        ecodes.KEY_RIGHTBRACE: 19,  # G (octave+1)
        
        # Home row - one octave down
        ecodes.KEY_A: -12,  # C
        ecodes.KEY_S: -10,  # D
        ecodes.KEY_D: -8,   # E
        ecodes.KEY_F: -7,   # F
        ecodes.KEY_G: -5,   # G
        ecodes.KEY_H: -3,   # A
        ecodes.KEY_J: -1,   # B
        ecodes.KEY_K: 0,    # C (same as Q for layering)
        ecodes.KEY_L: 2,    # D
        ecodes.KEY_SEMICOLON: 4,  # E
        ecodes.KEY_APOSTROPHE: 5, # F
        
        # Bottom row - two octaves down
        ecodes.KEY_Z: -24,  # C
        ecodes.KEY_X: -22,  # D
        ecodes.KEY_C: -20,  # E
        ecodes.KEY_V: -19,  # F
        ecodes.KEY_B: -17,  # G
        ecodes.KEY_N: -15,  # A
        ecodes.KEY_M: -13,  # B
        ecodes.KEY_COMMA: -12,  # C
        ecodes.KEY_DOT: -10,    # D
        ecodes.KEY_SLASH: -8,   # E
    }
    
    # Control keys
    OCTAVE_UP = ecodes.KEY_EQUAL      # + key
    OCTAVE_DOWN = ecodes.KEY_MINUS    # - key
    SUSTAIN = ecodes.KEY_SPACE        # Sustain pedal
    PROGRAM_UP = ecodes.KEY_PAGEUP    # Next instrument
    PROGRAM_DOWN = ecodes.KEY_PAGEDOWN  # Previous instrument
    PANIC = ecodes.KEY_ESC            # All notes off
    
    @classmethod
    def get_note(cls, keycode: int, base_octave: int) -> Optional[int]:
        """Convert keycode to MIDI note number"""
        if keycode not in cls.KEYMAP:
            return None
        semitone_offset = cls.KEYMAP[keycode]
        note = (base_octave * 12) + semitone_offset
        # Clamp to valid MIDI range
        return max(0, min(127, note))
    
    @staticmethod
    def note_name(note: int) -> str:
        """Convert MIDI note to human-readable name"""
        names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        octave = (note // 12) - 1
        name = names[note % 12]
        return f"{name}{octave}"


# =============================================================================
# TOUCHPAD HANDLER
# =============================================================================

@dataclass
class TouchpadState:
    """Current touchpad state"""
    x: float = 0.5          # Normalized 0-1
    y: float = 0.5          # Normalized 0-1
    pressure: float = 0.0   # Normalized 0-1
    touching: bool = False
    
    # Raw ranges (calibrated at runtime)
    x_min: int = 0
    x_max: int = 1
    y_min: int = 0
    y_max: int = 1
    pressure_max: int = 1


class TouchpadHandler:
    """Handles touchpad input and converts to MIDI CC/pitch bend"""
    
    def __init__(self, synth: 'FW16Synth', config: SynthConfig):
        self.synth = synth
        self.config = config
        self.state = TouchpadState()
        self._calibrated = False
    
    def calibrate(self, device: InputDevice):
        """Auto-calibrate touchpad ranges from device capabilities"""
        absinfo = device.capabilities().get(ecodes.EV_ABS, [])
        for code, info in absinfo:
            if code == ecodes.ABS_X or code == ecodes.ABS_MT_POSITION_X:
                self.state.x_min = info.min
                self.state.x_max = info.max
            elif code == ecodes.ABS_Y or code == ecodes.ABS_MT_POSITION_Y:
                self.state.y_min = info.min
                self.state.y_max = info.max
            elif code == ecodes.ABS_PRESSURE or code == ecodes.ABS_MT_PRESSURE:
                self.state.pressure_max = info.max
        self._calibrated = True
        print(f"[TOUCHPAD] Calibrated: X={self.state.x_min}-{self.state.x_max}, "
              f"Y={self.state.y_min}-{self.state.y_max}, P_max={self.state.pressure_max}")
    
    def handle_event(self, event):
        """Process touchpad event"""
        if event.type == ecodes.EV_ABS:
            self._handle_abs(event)
        elif event.type == ecodes.EV_KEY:
            # BTN_TOUCH for finger down/up
            if event.code == ecodes.BTN_TOUCH:
                self.state.touching = bool(event.value)
                if not self.state.touching:
                    # Reset modulation when finger lifts
                    self._reset_modulation()
    
    def _handle_abs(self, event):
        """Handle absolute position events"""
        code = event.code
        value = event.value
        
        # Handle both single-touch and multitouch protocols
        if code in (ecodes.ABS_X, ecodes.ABS_MT_POSITION_X):
            self.state.x = self._normalize(value, self.state.x_min, self.state.x_max)
            self._send_pitch_bend()
        
        elif code in (ecodes.ABS_Y, ecodes.ABS_MT_POSITION_Y):
            self.state.y = self._normalize(value, self.state.y_min, self.state.y_max)
            self._send_y_modulation()
        
        elif code in (ecodes.ABS_PRESSURE, ecodes.ABS_MT_PRESSURE):
            self.state.pressure = self._normalize(value, 0, self.state.pressure_max)
            self._send_pressure()
    
    def _normalize(self, value: int, min_val: int, max_val: int) -> float:
        """Normalize value to 0-1 range"""
        if max_val == min_val:
            return 0.5
        return max(0.0, min(1.0, (value - min_val) / (max_val - min_val)))
    
    def _send_pitch_bend(self):
        """Send pitch bend from X position (center = no bend)"""
        if not self.state.touching:
            return
        # Convert 0-1 to pitch bend range (-8192 to 8191)
        bend = int((self.state.x - 0.5) * 2 * 8191)
        bend = max(-8192, min(8191, bend))
        self.synth.pitch_bend(bend)
        
        if self.config.show_touchpad:
            cents = int((self.state.x - 0.5) * 2 * self.config.pitch_bend_range * 100)
            print(f"[BEND] {cents:+d} cents", end='\r')
    
    def _send_y_modulation(self):
        """Send CC from Y position"""
        if not self.state.touching:
            return
        # Invert Y so top of touchpad = max value
        cc_value = int((1.0 - self.state.y) * 127)
        self.synth.control_change(self.config.touchpad_y_cc, cc_value)
    
    def _send_pressure(self):
        """Send expression from pressure"""
        cc_value = int(self.state.pressure * 127)
        self.synth.control_change(self.config.touchpad_pressure_cc, cc_value)
    
    def _reset_modulation(self):
        """Reset all modulation to neutral when finger lifts"""
        self.synth.pitch_bend(0)
        # Optionally reset CCs - commented out to allow "latch" behavior
        # self.synth.control_change(self.config.touchpad_y_cc, 0)
        # self.synth.control_change(self.config.touchpad_pressure_cc, 64)


# =============================================================================
# VELOCITY CALCULATOR
# =============================================================================

class VelocityTracker:
    """
    Calculates note velocity based on keypress timing.
    Faster keypresses = higher velocity.
    """
    
    def __init__(self, config: SynthConfig):
        self.config = config
        self._press_times: Dict[int, float] = {}  # keycode -> timestamp
    
    def key_down(self, keycode: int) -> int:
        """Record keydown and calculate velocity"""
        now = time.monotonic()
        
        # Check if we have a previous release time for this key
        if keycode in self._press_times:
            elapsed = now - self._press_times[keycode]
            velocity = self._time_to_velocity(elapsed)
        else:
            # First press, use medium velocity
            velocity = 80
        
        self._press_times[keycode] = now
        return velocity
    
    def _time_to_velocity(self, elapsed: float) -> int:
        """Convert elapsed time to velocity value"""
        t_min = self.config.velocity_time_min
        t_max = self.config.velocity_time_max
        v_min = self.config.velocity_min
        v_max = self.config.velocity_max
        
        # Clamp elapsed time to range
        elapsed = max(t_min, min(t_max, elapsed))
        
        # Invert: shorter time = higher velocity
        ratio = 1.0 - (elapsed - t_min) / (t_max - t_min)
        velocity = int(v_min + ratio * (v_max - v_min))
        
        return max(1, min(127, velocity))


# =============================================================================
# MAIN SYNTHESIZER CLASS
# =============================================================================

class FW16Synth:
    """Main synthesizer controller"""
    
    def __init__(self, config: SynthConfig):
        self.config = config
        self.fs: Optional[fluidsynth.Synth] = None
        self.sfid: int = 0
        self.channel: int = 0
        self.program: int = 0
        self.octave: int = config.base_octave
        self.sustain: bool = False
        
        self.velocity_tracker = VelocityTracker(config)
        self.touchpad_handler = TouchpadHandler(self, config)
        
        self._active_notes: Dict[int, int] = {}  # keycode -> note
        self._devices: List[InputDevice] = []
        self._running = False
    
    def initialize(self) -> bool:
        """Initialize FluidSynth and audio"""
        print(f"[INIT] Starting FluidSynth with {self.config.audio_driver} driver...")
        
        try:
            self.fs = fluidsynth.Synth()
            self.fs.start(driver=self.config.audio_driver)
            
            # Load soundfont
            sf_path = Path(self.config.soundfont)
            if not sf_path.exists():
                # Try common locations
                for path in [
                    Path("/usr/share/soundfonts/default.sf2"),
                    Path("/usr/share/sounds/sf2/FluidR3_GM.sf2"),
                    Path("/usr/share/soundfonts/FluidR3_GM.sf2"),
                    Path("~/.local/share/soundfonts/default.sf2").expanduser(),
                ]:
                    if path.exists():
                        sf_path = path
                        break
            
            if not sf_path.exists():
                print(f"[ERROR] Soundfont not found: {self.config.soundfont}")
                print("        Please specify a valid soundfont with --soundfont")
                return False
            
            print(f"[INIT] Loading soundfont: {sf_path}")
            self.sfid = self.fs.sfload(str(sf_path))
            if self.sfid < 0:
                print("[ERROR] Failed to load soundfont")
                return False
            
            self.fs.program_select(self.channel, self.sfid, 0, 0)
            
            # Set pitch bend range
            self.fs.cc(self.channel, 101, 0)  # RPN MSB
            self.fs.cc(self.channel, 100, 0)  # RPN LSB (pitch bend range)
            self.fs.cc(self.channel, 6, self.config.pitch_bend_range)  # Data entry
            
            print(f"[INIT] FluidSynth ready - Program: {self.program} (Piano)")
            return True
            
        except Exception as e:
            print(f"[ERROR] FluidSynth initialization failed: {e}")
            return False
    
    def find_devices(self) -> bool:
        """Find Framework 16 keyboard and touchpad"""
        print("[SCAN] Scanning for input devices...")
        
        devices = [InputDevice(path) for path in evdev.list_devices()]
        keyboard_found = False
        touchpad_found = False
        
        for dev in devices:
            caps = dev.capabilities()
            name = dev.name.lower()
            
            # Look for keyboard (has EV_KEY with letter keys)
            if ecodes.EV_KEY in caps:
                key_caps = caps[ecodes.EV_KEY]
                if ecodes.KEY_Q in key_caps and ecodes.KEY_A in key_caps:
                    print(f"[FOUND] Keyboard: {dev.name} ({dev.path})")
                    self._devices.append(dev)
                    keyboard_found = True
            
            # Look for touchpad (has EV_ABS with X/Y)
            if ecodes.EV_ABS in caps and not touchpad_found:
                abs_caps = [c[0] if isinstance(c, tuple) else c for c in caps[ecodes.EV_ABS]]
                has_xy = (ecodes.ABS_X in abs_caps or ecodes.ABS_MT_POSITION_X in abs_caps)
                
                if has_xy and ('touchpad' in name or 'trackpad' in name or 'touch' in name):
                    print(f"[FOUND] Touchpad: {dev.name} ({dev.path})")
                    self._devices.append(dev)
                    self.touchpad_handler.calibrate(dev)
                    touchpad_found = True
        
        if not keyboard_found:
            print("[WARN] No keyboard found - using any available keyboard")
            for dev in devices:
                caps = dev.capabilities()
                if ecodes.EV_KEY in caps and ecodes.KEY_Q in caps.get(ecodes.EV_KEY, []):
                    print(f"[USING] Keyboard: {dev.name}")
                    self._devices.append(dev)
                    keyboard_found = True
                    break
        
        if not touchpad_found:
            print("[WARN] No touchpad found - modulation disabled")
        
        return keyboard_found
    
    def note_on(self, note: int, velocity: int):
        """Send note on"""
        self.fs.noteon(self.channel, note, velocity)
        if self.config.show_notes:
            name = KeyboardLayout.note_name(note)
            print(f"[NOTE] {name} ON  vel={velocity}")
    
    def note_off(self, note: int):
        """Send note off"""
        self.fs.noteoff(self.channel, note)
        if self.config.show_notes:
            name = KeyboardLayout.note_name(note)
            print(f"[NOTE] {name} OFF")
    
    def pitch_bend(self, value: int):
        """Send pitch bend (-8192 to 8191)"""
        # FluidSynth expects 0-16383, center at 8192
        self.fs.pitch_bend(self.channel, value + 8192)
    
    def control_change(self, cc: int, value: int):
        """Send control change"""
        self.fs.cc(self.channel, cc, value)
    
    def program_change(self, program: int):
        """Change instrument"""
        self.program = program % 128
        self.fs.program_select(self.channel, self.sfid, 0, self.program)
        
        # GM instrument names (abbreviated)
        gm_names = [
            "Piano", "Bright Piano", "E.Grand", "Honky-tonk", "E.Piano 1", "E.Piano 2",
            "Harpsichord", "Clavinet", "Celesta", "Glockenspiel", "Music Box", "Vibraphone",
            "Marimba", "Xylophone", "Tubular Bells", "Dulcimer", "Drawbar Organ", "Perc Organ",
            "Rock Organ", "Church Organ", "Reed Organ", "Accordion", "Harmonica", "Bandoneon",
            "Nylon Guitar", "Steel Guitar", "Jazz Guitar", "Clean Guitar", "Muted Guitar",
            "Overdrive", "Distortion", "Harmonics", "Acoustic Bass", "Finger Bass", "Pick Bass",
            "Fretless", "Slap Bass 1", "Slap Bass 2", "Synth Bass 1", "Synth Bass 2",
            "Violin", "Viola", "Cello", "Contrabass", "Tremolo Str", "Pizzicato", "Harp",
            "Timpani", "Strings 1", "Strings 2", "Synth Str 1", "Synth Str 2", "Choir Aahs",
            "Voice Oohs", "Synth Voice", "Orchestra Hit", "Trumpet", "Trombone", "Tuba",
            "Muted Trumpet", "French Horn", "Brass", "Synth Brass 1", "Synth Brass 2",
            "Soprano Sax", "Alto Sax", "Tenor Sax", "Bari Sax", "Oboe", "English Horn",
            "Bassoon", "Clarinet", "Piccolo", "Flute", "Recorder", "Pan Flute", "Bottle",
            "Shakuhachi", "Whistle", "Ocarina", "Square Lead", "Saw Lead", "Calliope",
            "Chiff Lead", "Charang", "Voice Lead", "Fifth Lead", "Bass+Lead", "New Age",
            "Warm Pad", "Polysynth", "Choir Pad", "Bowed Pad", "Metal Pad", "Halo Pad",
            "Sweep Pad", "Rain", "Soundtrack", "Crystal", "Atmosphere", "Brightness",
            "Goblins", "Echoes", "Sci-Fi", "Sitar", "Banjo", "Shamisen", "Koto",
            "Kalimba", "Bagpipe", "Fiddle", "Shanai", "Tinkle Bell", "Agogo", "Steel Drums",
            "Woodblock", "Taiko", "Melodic Tom", "Synth Drum", "Rev Cymbal", "Fret Noise",
            "Breath", "Seashore", "Bird Tweet", "Telephone", "Helicopter", "Applause", "Gunshot"
        ]
        name = gm_names[self.program] if self.program < len(gm_names) else f"Program {self.program}"
        print(f"[PROG] {self.program}: {name}")
    
    def panic(self):
        """All notes off"""
        self.fs.cc(self.channel, 123, 0)  # All notes off
        self.fs.cc(self.channel, 121, 0)  # Reset all controllers
        self._active_notes.clear()
        print("[PANIC] All notes off")
    
    def handle_key(self, event):
        """Handle keyboard event"""
        keycode = event.code
        
        # Control keys
        if event.value == 1:  # Key down
            if keycode == KeyboardLayout.OCTAVE_UP:
                self.octave = min(8, self.octave + 1)
                print(f"[OCT] Octave: {self.octave}")
                return
            elif keycode == KeyboardLayout.OCTAVE_DOWN:
                self.octave = max(0, self.octave - 1)
                print(f"[OCT] Octave: {self.octave}")
                return
            elif keycode == KeyboardLayout.PROGRAM_UP:
                self.program_change(self.program + 1)
                return
            elif keycode == KeyboardLayout.PROGRAM_DOWN:
                self.program_change(self.program - 1)
                return
            elif keycode == KeyboardLayout.PANIC:
                self.panic()
                return
            elif keycode == KeyboardLayout.SUSTAIN:
                self.sustain = True
                self.control_change(64, 127)
                print("[SUS] Sustain ON")
                return
        
        elif event.value == 0:  # Key up
            if keycode == KeyboardLayout.SUSTAIN:
                self.sustain = False
                self.control_change(64, 0)
                print("[SUS] Sustain OFF")
                return
        
        # Note keys
        note = KeyboardLayout.get_note(keycode, self.octave)
        if note is None:
            return
        
        if event.value == 1:  # Key down
            if keycode not in self._active_notes:
                velocity = self.velocity_tracker.key_down(keycode)
                self._active_notes[keycode] = note
                self.note_on(note, velocity)
        
        elif event.value == 0:  # Key up
            if keycode in self._active_notes:
                active_note = self._active_notes.pop(keycode)
                self.note_off(active_note)
    
    async def event_loop(self, device: InputDevice):
        """Async event loop for a single device"""
        try:
            async for event in device.async_read_loop():
                if not self._running:
                    break
                
                if event.type == ecodes.EV_KEY:
                    self.handle_key(event)
                elif event.type in (ecodes.EV_ABS,):
                    self.touchpad_handler.handle_event(event)
        except Exception as e:
            print(f"[ERROR] Device error: {e}")
    
    async def run(self):
        """Main run loop"""
        self._running = True
        
        print("\n" + "=" * 60)
        print("FW16 SYNTH - Framework 16 Synthesizer Controller")
        print("=" * 60)
        print("\nControls:")
        print("  QWERTY/ASDF/ZXCV rows = Piano keys (3 octaves)")
        print("  Number row (2,3,5,6,7,9,0) = Black keys (sharps)")
        print("  +/- = Octave up/down")
        print("  Space = Sustain pedal")
        print("  Page Up/Down = Change instrument")
        print("  ESC = Panic (all notes off)")
        print("  Ctrl+C = Exit")
        print("\nTouchpad:")
        print("  X axis = Pitch bend")
        print("  Y axis = Filter/Modulation")
        print("  Pressure = Expression")
        print("=" * 60 + "\n")
        
        # Grab devices for exclusive access
        grabbed = []
        for dev in self._devices:
            try:
                dev.grab()
                grabbed.append(dev)
                print(f"[GRAB] Exclusive access: {dev.name}")
            except Exception as e:
                print(f"[WARN] Could not grab {dev.name}: {e}")
        
        try:
            # Create tasks for all devices
            tasks = [asyncio.create_task(self.event_loop(dev)) for dev in self._devices]
            await asyncio.gather(*tasks)
        finally:
            # Release grabbed devices
            for dev in grabbed:
                try:
                    dev.ungrab()
                except:
                    pass
    
    def stop(self):
        """Stop the synthesizer"""
        self._running = False
        if self.fs:
            self.panic()
            self.fs.delete()
        print("\n[EXIT] Synthesizer stopped")
    
    def cleanup(self):
        """Cleanup resources"""
        for dev in self._devices:
            try:
                dev.close()
            except:
                pass


# =============================================================================
# ENTRY POINT
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="FW16 Synth - Turn your Framework 16 into a synthesizer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                           # Use defaults
  %(prog)s --soundfont /path/to.sf2  # Custom soundfont
  %(prog)s --driver jack             # Use JACK audio
  %(prog)s --octave 3                # Start at lower octave

Keyboard Layout:
  Numbers: 2=C# 3=D# 5=F# 6=G# 7=A# 9=C# 0=D#
  QWERTY:  Q=C  W=D  E=E  R=F  T=G  Y=A  U=B  I=C ...
  ASDF:    A=C  S=D  D=E  F=F  G=G  H=A  J=B  (octave down)
  ZXCV:    Z=C  X=D  C=E  V=F  B=G  N=A  M=B  (2 octaves down)
        """
    )
    
    parser.add_argument('--soundfont', '-s', default="/usr/share/soundfonts/default.sf2",
                        help="Path to SoundFont file (.sf2)")
    parser.add_argument('--driver', '-d', default="pulseaudio",
                        choices=['pulseaudio', 'jack', 'alsa', 'pipewire'],
                        help="Audio driver (default: pulseaudio)")
    parser.add_argument('--octave', '-o', type=int, default=4,
                        help="Starting octave 0-8 (default: 4)")
    parser.add_argument('--program', '-p', type=int, default=0,
                        help="Starting GM program 0-127 (default: 0=Piano)")
    parser.add_argument('--quiet', '-q', action='store_true',
                        help="Suppress note output")
    
    args = parser.parse_args()
    
    config = SynthConfig(
        soundfont=args.soundfont,
        audio_driver=args.driver,
        base_octave=args.octave,
        show_notes=not args.quiet,
    )
    
    synth = FW16Synth(config)
    
    # Handle signals
    def signal_handler(sig, frame):
        synth.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Initialize
    if not synth.initialize():
        sys.exit(1)
    
    # Find devices
    if not synth.find_devices():
        print("[ERROR] No input devices found")
        sys.exit(1)
    
    # Set starting program
    if args.program != 0:
        synth.program_change(args.program)
    
    # Run
    try:
        asyncio.run(synth.run())
    finally:
        synth.cleanup()


if __name__ == "__main__":
    main()
