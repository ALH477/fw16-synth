"""
Keyboard Input Module

Handles QWERTY keyboard mapping, velocity tracking, and key event processing.
"""

import time
import math
import logging
from typing import Optional, Dict, List

try:
    import evdev
    from evdev import ecodes, InputDevice
except ImportError:
    evdev = None
    ecodes = None
    InputDevice = None

from ..fw16_synth import SynthConfig

log = logging.getLogger(__name__)


class KeyboardMapper:
    """Maps QWERTY keyboard to MIDI notes"""

    NOTE_MAP: Dict[int, int] = {
        # Number row - black keys
        ecodes.KEY_2: 1, ecodes.KEY_3: 3, ecodes.KEY_5: 6,
        ecodes.KEY_6: 8, ecodes.KEY_7: 10, ecodes.KEY_9: 13, ecodes.KEY_0: 15,
        # QWERTY row
        ecodes.KEY_Q: 0, ecodes.KEY_W: 2, ecodes.KEY_E: 4, ecodes.KEY_R: 5,
        ecodes.KEY_T: 7, ecodes.KEY_Y: 9, ecodes.KEY_U: 11, ecodes.KEY_I: 12,
        ecodes.KEY_O: 14, ecodes.KEY_P: 16, ecodes.KEY_LEFTBRACE: 17,
        ecodes.KEY_RIGHTBRACE: 19,
        # Home row (-1 octave)
        ecodes.KEY_A: -12, ecodes.KEY_S: -10, ecodes.KEY_D: -8, ecodes.KEY_F: -7,
        ecodes.KEY_G: -5, ecodes.KEY_H: -3, ecodes.KEY_J: -1, ecodes.KEY_K: 0,
        ecodes.KEY_L: 2, ecodes.KEY_SEMICOLON: 4, ecodes.KEY_APOSTROPHE: 5,
        # Bottom row (-2 octaves)
        ecodes.KEY_Z: -24, ecodes.KEY_X: -22, ecodes.KEY_C: -20, ecodes.KEY_V: -19,
        ecodes.KEY_B: -17, ecodes.KEY_N: -15, ecodes.KEY_M: -13,
        ecodes.KEY_COMMA: -12, ecodes.KEY_DOT: -10, ecodes.KEY_SLASH: -8,
    }

    KEY_CHARS: Dict[int, str] = {
        ecodes.KEY_2: '2', ecodes.KEY_3: '3', ecodes.KEY_5: '5',
        ecodes.KEY_6: '6', ecodes.KEY_7: '7', ecodes.KEY_9: '9', ecodes.KEY_0: '0',
        ecodes.KEY_Q: 'Q', ecodes.KEY_W: 'W', ecodes.KEY_E: 'E', ecodes.KEY_R: 'R',
        ecodes.KEY_T: 'T', ecodes.KEY_Y: 'Y', ecodes.KEY_U: 'U', ecodes.KEY_I: 'I',
        ecodes.KEY_O: 'O', ecodes.KEY_P: 'P', ecodes.KEY_LEFTBRACE: '[',
        ecodes.KEY_RIGHTBRACE: ']',
        ecodes.KEY_A: 'A', ecodes.KEY_S: 'S', ecodes.KEY_D: 'D', ecodes.KEY_F: 'F',
        ecodes.KEY_G: 'G', ecodes.KEY_H: 'H', ecodes.KEY_J: 'J', ecodes.KEY_K: 'K',
        ecodes.KEY_L: 'L', ecodes.KEY_SEMICOLON: ';', ecodes.KEY_APOSTROPHE: "'",
        ecodes.KEY_Z: 'Z', ecodes.KEY_X: 'X', ecodes.KEY_C: 'C', ecodes.KEY_V: 'V',
        ecodes.KEY_B: 'B', ecodes.KEY_N: 'N', ecodes.KEY_M: 'M', ecodes.KEY_COMMA: ',',
        ecodes.KEY_DOT: '.', ecodes.KEY_SLASH: '/',
    }

    # Control keys
    CTRL_OCTAVE_UP = ecodes.KEY_EQUAL
    CTRL_OCTAVE_DOWN = ecodes.KEY_MINUS
    CTRL_SUSTAIN = ecodes.KEY_SPACE
    CTRL_PROG_UP = ecodes.KEY_PAGEUP
    CTRL_PROG_DOWN = ecodes.KEY_PAGEDOWN
    CTRL_PANIC = ecodes.KEY_ESC
    CTRL_HELP = ecodes.KEY_SLASH  # ? key (with shift)
    CTRL_TRANSPOSE_UP = ecodes.KEY_DOT     # > key
    CTRL_TRANSPOSE_DOWN = ecodes.KEY_COMMA  # < key
    CTRL_LAYER = ecodes.KEY_L
    CTRL_ARP = ecodes.KEY_A
    CTRL_SOUNDFONT = ecodes.KEY_TAB
    CTRL_DOWNLOAD = ecodes.KEY_D
    CTRL_MIDI = ecodes.KEY_M  # Toggle MIDI input (FW16 Piano Keyboard Module)
    CTRL_FAVORITE = ecodes.KEY_F

    NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

    PRESET_KEYS = [
        ecodes.KEY_F1, ecodes.KEY_F2, ecodes.KEY_F3, ecodes.KEY_F4,
        ecodes.KEY_F5, ecodes.KEY_F6, ecodes.KEY_F7, ecodes.KEY_F8,
        ecodes.KEY_F9, ecodes.KEY_F10, ecodes.KEY_F11, ecodes.KEY_F12,
    ]

    @classmethod
    def get_note(cls, keycode: int, base_octave: int, transpose: int = 0) -> Optional[int]:
        if keycode not in cls.NOTE_MAP:
            return None
        offset = cls.NOTE_MAP[keycode]
        note = (base_octave * 12) + offset + transpose
        return max(0, min(127, note))

    @classmethod
    def get_key_char(cls, keycode: int) -> Optional[str]:
        return cls.KEY_CHARS.get(keycode)

    @classmethod
    def note_name(cls, note: int) -> str:
        octave = (note // 12) - 1
        name = cls.NOTE_NAMES[note % 12]
        return f"{name}{octave}"


class ParameterSmoother:
    """Parameter smoothing for anti-zipper effects"""

    def __init__(self, smoothing: float = 0.9, threshold: float = 0.001):
        self.smoothing = smoothing
        self.threshold = threshold
        self._current: Dict[str, float] = {}
        self._target: Dict[str, float] = {}

    def set_target(self, name: str, value: float):
        self._target[name] = value
        if name not in self._current:
            self._current[name] = value

    def get(self, name: str, default: float = 0.0) -> float:
        return self._current.get(name, default)

    def update(self) -> Dict[str, float]:
        changed = {}
        for name, target in self._target.items():
            current = self._current.get(name, target)
            new_val = current * self.smoothing + target * (1 - self.smoothing)
            if abs(new_val - current) > self.threshold:
                self._current[name] = new_val
                changed[name] = new_val
            elif abs(target - current) > self.threshold:
                self._current[name] = target
                changed[name] = target
        return changed


class VelocityTracker:
    """Velocity calculation from keypress timing"""

    def __init__(self, config: SynthConfig):
        self.config = config
        self._last_release: Dict[int, float] = {}

    def key_pressed(self, keycode: int) -> int:
        if self.config.velocity_fixed is not None:
            return self.config.velocity_fixed

        now = time.perf_counter()
        if keycode in self._last_release:
            elapsed = now - self._last_release[keycode]
        else:
            elapsed = (self.config.velocity_time_fast + self.config.velocity_time_slow) / 2

        return self._time_to_velocity(elapsed)

    def key_released(self, keycode: int):
        self._last_release[keycode] = time.perf_counter()

    def _time_to_velocity(self, elapsed: float) -> int:
        t_fast = self.config.velocity_time_fast
        t_slow = self.config.velocity_time_slow
        v_min = self.config.velocity_min
        v_max = self.config.velocity_max

        elapsed = max(t_fast, min(t_slow, elapsed))
        normalized = (elapsed - t_fast) / (t_slow - t_fast)

        if self.config.velocity_curve == "soft":
            normalized = math.sqrt(normalized)

        elif self.config.velocity_curve == "hard":
            normalized = normalized ** 2

        velocity = int(v_max - normalized * (v_max - v_min))
        return max(1, min(127, velocity))


class KeyboardInputHandler:
    """Main keyboard input handler"""

    def __init__(self, config: SynthConfig):
        self.config = config
        self.mapper = KeyboardMapper()
        self.velocity_tracker = VelocityTracker(config)
        self.active_keys: set = set()
        self.octave = config.base_octave
        self.transpose = 0

    def handle_key_event(self, event) -> tuple[Optional[int], Optional[int], bool]:
        """
        Handle keyboard event

        Returns:
            Tuple of (note, velocity, is_control)
        """
        if evdev is None:
            return None, None, False

        is_control = False

        # Check for control keys
        if event.code == KeyboardMapper.CTRL_OCTAVE_UP:
            self.octave = min(8, self.octave + 1)
            return None, None, True
        elif event.code == KeyboardMapper.CTRL_OCTAVE_DOWN:
            self.octave = max(0, self.octave - 1)
            return None, None, True
        elif event.code == KeyboardMapper.CTRL_SUSTAIN:
            return None, None, True  # Sustain handled elsewhere
        elif event.code == KeyboardMapper.CTRL_PANIC:
            return None, None, True  # Panic handled elsewhere

        # Get note for key
        if event.value == 1:  # Key press
            note = self.mapper.get_note(event.code, self.octave, self.transpose)
            if note is not None:
                self.active_keys.add(event.code)
                velocity = self.velocity_tracker.key_pressed(event.code)
                key_char = self.mapper.get_key_char(event.code) or ""
                log.debug(f"Key press: {key_char} → Note {note}, Vel {velocity}")
                return note, velocity, False

        elif event.value == 0:  # Key release
            self.active_keys.discard(event.code)
            self.velocity_tracker.key_released(event.code)
            return None, None, False

        return None, None, False

    def set_octave(self, octave: int):
        self.octave = max(0, min(8, octave))

    def set_transpose(self, transpose: int):
        self.transpose = transpose

    def get_octave(self) -> int:
        return self.octave

    def get_transpose(self) -> int:
        return self.transpose
