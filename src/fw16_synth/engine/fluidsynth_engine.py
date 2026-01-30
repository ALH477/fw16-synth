"""
FluidSynth Audio Engine Module

Provides a clean interface to the FluidSynth library
for audio synthesis and MIDI control.
"""

import logging
from pathlib import Path
from typing import Optional

try:
    import fluidsynth
except ImportError:
    fluidsynth = None

from ..fw16_synth import SynthConfig

log = logging.getLogger(__name__)


class FluidSynthEngine:
    """FluidSynth audio engine wrapper"""

    def __init__(self, config: SynthConfig):
        self.config = config
        self.fs: Optional[fluidsynth.Synth] = None
        self.sfid: int = -1
        self.channel: int = config.midi_channel
        self.layer_channel: int = 1
        self._initialized = False

    def initialize(self, soundfont_path: Optional[Path] = None) -> bool:
        """Initialize the audio engine"""
        if fluidsynth is None:
            log.error("FluidSynth library not available")
            return False

        try:
            self.fs = fluidsynth.Synth()
            driver = self.config.audio_driver.value
            log.info(f"Starting FluidSynth ({driver})")
            self.fs.start(driver=driver)

            if soundfont_path and soundfont_path.exists():
                return self.load_soundfont(soundfont_path)

            self._initialized = True
            return True
        except Exception as e:
            log.error(f"FluidSynth init failed: {e}")
            return False

    def load_soundfont(self, path: Path) -> bool:
        """Load a soundfont (can be called at runtime)"""
        try:
            # Unload previous
            if self.sfid >= 0:
                self.all_notes_off()
                self.fs.sfunload(self.sfid)

            log.info(f"Loading: {path.name}")
            self.sfid = self.fs.sfload(str(path))

            if self.sfid < 0:
                log.error("Failed to load soundfont")
                return False

            # Initialize channels
            self.fs.program_select(self.channel, self.sfid, 0, 0)
            self.fs.program_select(self.layer_channel, self.sfid, 0, 48)

            # Set pitch bend range
            self._set_pitch_bend_range(self.config.pitch_bend_semitones)

            self._initialized = True
            return True
        except Exception as e:
            log.error(f"Load soundfont failed: {e}")
            return False

    def _set_pitch_bend_range(self, semitones: int):
        """Set pitch bend range in semitones"""
        for ch in [self.channel, self.layer_channel]:
            self.fs.cc(ch, 101, 0)
            self.fs.cc(ch, 100, 0)
            self.fs.cc(ch, 6, semitones)
            self.fs.cc(ch, 38, 0)
            self.fs.cc(ch, 101, 127)
            self.fs.cc(ch, 100, 127)

    def note_on(self, note: int, velocity: int, layer: bool = False):
        """Play a note"""
        if self._initialized:
            self.fs.noteon(self.channel, note, velocity)
            if layer:
                self.fs.noteon(self.layer_channel, note, max(1, velocity - 20))

    def note_off(self, note: int, layer: bool = False):
        """Stop a note"""
        if self._initialized:
            self.fs.noteoff(self.channel, note)
            if layer:
                self.fs.noteoff(self.layer_channel, note)

    def pitch_bend(self, value: int, layer: bool = False):
        """Apply pitch bend (0-16383)"""
        if self._initialized:
            value = max(0, min(16383, value))
            self.fs.pitch_bend(self.channel, value)
            if layer:
                self.fs.pitch_bend(self.layer_channel, value)

    def control_change(self, cc: int, value: int, layer: bool = False):
        """Send control change message"""
        if self._initialized:
            value = max(0, min(127, value))
            self.fs.cc(self.channel, cc, value)
            if layer:
                self.fs.cc(self.layer_channel, cc, value)

    def program_change(self, program: int, bank: int = 0, channel: Optional[int] = None):
        """Change instrument program"""
        if self._initialized:
            ch = channel if channel is not None else self.channel
            self.fs.program_select(ch, self.sfid, bank, program % 128)

    def all_notes_off(self):
        """Turn off all notes"""
        if self._initialized:
            for ch in [self.channel, self.layer_channel]:
                self.fs.cc(ch, 123, 0)
                self.fs.cc(ch, 121, 0)

    def shutdown(self):
        """Shutdown the audio engine"""
        if self.fs:
            self.all_notes_off()
            self.fs.delete()
            self.fs = None
            self._initialized = False
