"""
MIDI Module

Provides MIDI input handling and message processing for FW16 Synth.
"""

from .midi_handler import (
    MIDIInputController,
    MIDIMessage,
)

__all__ = [
    'MIDIInputController',
    'MIDIMessage',
]
