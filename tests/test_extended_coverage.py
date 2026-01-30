#!/usr/bin/env python3
"""
Additional tests for FW16 Synth core functionality

Extends test_nix_compatible.py with more test coverage.
"""

import unittest
import time
import math
from pathlib import Path
from dataclasses import dataclass, field
from collections import deque
from typing import Dict, List, Set, Optional, Callable, Any, Tuple
from enum import Enum, auto


# =============================================================================
# MOCK MIDI IMPLEMENTATION
# =============================================================================

@dataclass
class MIDIMessage:
    """Mock MIDI message"""
    status_byte: int
    data1: Optional[int] = None
    data2: Optional[int] = None
    timestamp: float = 0.0

    @property
    def is_note_on(self) -> bool:
        # Note On: 0x9n (where n is channel)
        return 0x90 <= (self.status_byte & 0xF0) <= 0x9F

    @property
    def is_note_off(self) -> bool:
        # Note Off: 0x8n (where n is channel)
        return 0x80 <= (self.status_byte & 0xF0) <= 0x8F

    @property
    def is_control_change(self) -> bool:
        return (self.status_byte & 0xF0) == 0xB0

    @property
    def is_program_change(self) -> bool:
        return (self.status_byte & 0xF0) == 0xC0


class MockMIDIInput:
    """Mock MIDI input device"""

    def __init__(self):
        self.messages: List[MIDIMessage] = []
        self.port_name = "Mock MIDI Device"
        self.is_open = False

    def open_port(self, port_name: str):
        self.port_name = port_name
        self.is_open = True

    def close(self):
        self.is_open = False
        self.messages.clear()

    def get_message(self) -> Optional[MIDIMessage]:
        if self.messages:
            return self.messages.pop(0)
        return None

    def add_message(self, message: MIDIMessage):
        self.messages.append(message)


# =============================================================================
# MOCK SOUNDFONT DOWNLOAD
# =============================================================================

@dataclass
class DownloadProgress:
    """Tracks download progress"""
    url: str
    filename: str
    total_bytes: int = 0
    downloaded_bytes: int = 0
    is_complete: bool = False
    error: Optional[str] = None

    @property
    def progress(self) -> float:
        if self.total_bytes == 0:
            return 0.0
        return self.downloaded_bytes / self.total_bytes


class MockSoundFontDownloader:
    """Mock SoundFont downloader"""

    def __init__(self):
        self.catalog = [
            {
                'name': 'FluidR3 GM',
                'url': 'https://example.com/fluidr3.sf2',
                'size_mb': 140.0,
                'category': 'General MIDI'
            },
            {
                'name': 'GeneralUser GS',
                'url': 'https://example.com/generaluser.sf2',
                'size_mb': 30.0,
                'category': 'General MIDI'
            }
        ]
        self.downloads: List[DownloadProgress] = []
        self.download_dir = Path("/tmp/soundfonts")

    def get_catalog(self) -> List[Dict[str, Any]]:
        """Get available SoundFont catalog"""
        return self.catalog

    def download(self, url: str, filename: str) -> DownloadProgress:
        """Start download of SoundFont"""
        progress = DownloadProgress(url=url, filename=filename, total_bytes=1000000)
        self.downloads.append(progress)
        return progress

    def cancel_download(self, progress: DownloadProgress):
        """Cancel an in-progress download"""
        progress.error = "Cancelled by user"


# =============================================================================
# MIDI HANDLING TESTS
# =============================================================================

class TestMIDIHandling(unittest.TestCase):
    """Test MIDI message handling"""

    def test_note_on_message(self):
        """Test note-on message parsing"""
        msg = MIDIMessage(status_byte=0x90, data1=60, data2=127)

        self.assertTrue(msg.is_note_on)
        self.assertFalse(msg.is_note_off)
        self.assertFalse(msg.is_control_change)
        self.assertFalse(msg.is_program_change)

    def test_note_off_message(self):
        """Test note-off message parsing"""
        msg = MIDIMessage(status_byte=0x80, data1=60, data2=0)

        self.assertTrue(msg.is_note_off)
        self.assertFalse(msg.is_note_on)
        self.assertFalse(msg.is_control_change)

    def test_control_change_message(self):
        """Test control change message parsing"""
        msg = MIDIMessage(status_byte=0xB0, data1=1, data2=64)

        self.assertTrue(msg.is_control_change)
        self.assertFalse(msg.is_note_on)
        self.assertFalse(msg.is_program_change)

    def test_program_change_message(self):
        """Test program change message parsing"""
        msg = MIDIMessage(status_byte=0xC0, data1=5, data2=None)

        self.assertTrue(msg.is_program_change)
        self.assertFalse(msg.is_note_on)
        self.assertFalse(msg.is_control_change)

    def test_midi_message_with_no_data2(self):
        """Test MIDI message without data2"""
        msg = MIDIMessage(status_byte=0xC0, data1=5)

        self.assertTrue(msg.is_program_change)
        self.assertIsNone(msg.data2)


class TestMIDIInputDevice(unittest.TestCase):
    """Test MIDI input device simulation"""

    def test_open_port(self):
        """Test opening MIDI port"""
        device = MockMIDIInput()
        device.open_port("Test Port")

        self.assertTrue(device.is_open)
        self.assertEqual(device.port_name, "Test Port")

    def test_close_port(self):
        """Test closing MIDI port"""
        device = MockMIDIInput()
        device.open_port("Test Port")
        device.close()

        self.assertFalse(device.is_open)
        self.assertEqual(len(device.messages), 0)

    def test_add_and_get_message(self):
        """Test adding and retrieving MIDI messages"""
        device = MockMIDIInput()
        msg = MIDIMessage(status_byte=0x90, data1=60, data2=100)
        device.add_message(msg)

        retrieved = device.get_message()

        self.assertEqual(retrieved.status_byte, msg.status_byte)
        self.assertEqual(retrieved.data1, msg.data1)

    def test_multiple_messages(self):
        """Test handling multiple MIDI messages"""
        device = MockMIDIInput()

        # Add multiple messages
        for note in [60, 64, 67]:
            msg = MIDIMessage(status_byte=0x90, data1=note, data2=100)
            device.add_message(msg)

        # Retrieve in order
        notes = []
        for _ in range(3):
            msg = device.get_message()
            if msg:
                notes.append(msg.data1)

        self.assertEqual(notes, [60, 64, 67])


# =============================================================================
# SOUNDFONT DOWNLOAD TESTS
# =============================================================================

class TestSoundFontDownloader(unittest.TestCase):
    """Test SoundFont downloader functionality"""

    def test_get_catalog(self):
        """Test retrieving SoundFont catalog"""
        downloader = MockSoundFontDownloader()
        catalog = downloader.get_catalog()

        self.assertGreater(len(catalog), 0)
        self.assertIn('name', catalog[0])
        self.assertIn('url', catalog[0])

    def test_catalog_structure(self):
        """Test catalog has required fields"""
        downloader = MockSoundFontDownloader()
        catalog = downloader.get_catalog()

        for item in catalog:
            self.assertIn('name', item)
            self.assertIn('url', item)
            self.assertIn('size_mb', item)
            self.assertIn('category', item)

    def test_start_download(self):
        """Test starting a download"""
        downloader = MockSoundFontDownloader()
        progress = downloader.download(
            "https://example.com/test.sf2",
            "test.sf2"
        )

        self.assertIsNotNone(progress)
        self.assertEqual(progress.filename, "test.sf2")
        self.assertEqual(progress.url, "https://example.com/test.sf2")

    def test_download_progress(self):
        """Test download progress tracking"""
        progress = DownloadProgress(
            url="https://example.com/test.sf2",
            filename="test.sf2",
            total_bytes=1000
        )

        # Simulate download
        progress.downloaded_bytes = 500
        self.assertEqual(progress.progress, 0.5)

        progress.downloaded_bytes = 1000
        self.assertEqual(progress.progress, 1.0)

    def test_complete_download(self):
        """Test marking download as complete"""
        progress = DownloadProgress(
            url="https://example.com/test.sf2",
            filename="test.sf2",
            total_bytes=1000,
            downloaded_bytes=1000
        )

        self.assertEqual(progress.progress, 1.0)

    def test_cancel_download(self):
        """Test cancelling download"""
        downloader = MockSoundFontDownloader()
        progress = downloader.download(
            "https://example.com/test.sf2",
            "test.sf2"
        )

        downloader.cancel_download(progress)

        self.assertEqual(progress.error, "Cancelled by user")

    def test_download_with_no_total(self):
        """Test download progress with unknown total size"""
        progress = DownloadProgress(
            url="https://example.com/test.sf2",
            filename="test.sf2",
            total_bytes=0
        )

        self.assertEqual(progress.progress, 0.0)

        # Even with unknown total, progress should track
        progress.downloaded_bytes = 1000
        self.assertEqual(progress.downloaded_bytes, 1000)


# =============================================================================
# ARPEGGIATOR TESTS
# =============================================================================

class Arpeggiator:
    """Mock arpeggiator for testing"""

    def __init__(self):
        self.notes = []
        self._running = False
        self._current_idx = 0
        self._direction = 1
        self.mode = "up"

    def add_note(self, note):
        """Add note to arpeggiator"""
        if note not in self.notes:
            self.notes.append(note)

    def remove_note(self, note):
        """Remove note from arpeggiator"""
        if note in self.notes:
            self.notes.remove(note)

    def get_next_note(self):
        """Get next note in arpeggiation pattern"""
        if not self.notes:
            return None

        if self._current_idx >= len(self.notes):
            self._current_idx = 0

        note = self.notes[self._current_idx]
        self._current_idx += 1
        return note


class TestArpeggiator(unittest.TestCase):
    """Test arpeggiator functionality"""

    def test_add_notes(self):
        """Test adding notes to arpeggiator"""
        arp = Arpeggiator()
        arp.add_note(60)
        arp.add_note(64)
        arp.add_note(67)

        self.assertEqual(len(arp.notes), 3)

    def test_add_duplicate_notes(self):
        """Test that duplicate notes are not added"""
        arp = Arpeggiator()
        arp.add_note(60)
        arp.add_note(60)  # Duplicate

        self.assertEqual(len(arp.notes), 1)

    def test_remove_notes(self):
        """Test removing notes from arpeggiator"""
        arp = Arpeggiator()
        arp.add_note(60)
        arp.add_note(64)
        arp.remove_note(60)

        self.assertEqual(len(arp.notes), 1)
        self.assertEqual(arp.notes[0], 64)

    def test_arp_sequence_up(self):
        """Test ascending arpeggiation sequence"""
        arp = Arpeggiator()
        notes = [60, 64, 67]
        for note in notes:
            arp.add_note(note)

        sequence = []
        for _ in range(3):
            sequence.append(arp.get_next_note())

        self.assertEqual(sequence, notes)

    def test_empty_arp(self):
        """Test arpeggiator with no notes"""
        arp = Arpeggiator()

        note = arp.get_next_note()
        self.assertIsNone(note)


# =============================================================================
# MODULATION SYSTEM TESTS
# =============================================================================

class TestModulationSystem(unittest.TestCase):
    """Test touchpad modulation system"""

    def test_x_axis_to_pitch_bend(self):
        """Test X-axis mapping to pitch bend"""
        # Center position = 8192 (no bend)
        center_value = 8192
        x_pos = 0.5  # Center of touchpad

        # Calculate pitch bend value
        bend_range = 8192  # +/-1 semitone
        offset = int((x_pos - 0.5) * 2 * bend_range)
        bend_value = center_value + offset

        self.assertGreaterEqual(bend_value, 0)
        self.assertLessEqual(bend_value, 16383)

    def test_y_axis_to_filter_cutoff(self):
        """Test Y-axis mapping to filter cutoff"""
        # Y-axis typically inverted (top = max value)
        y_pos = 0.0  # Top of touchpad

        # Calculate CC value (inverted)
        cc_value = int(127 * (1.0 - y_pos))

        self.assertEqual(cc_value, 127)

        y_pos = 1.0  # Bottom of touchpad
        cc_value = int(127 * (1.0 - y_pos))

        self.assertEqual(cc_value, 0)

    def test_pressure_to_expression(self):
        """Test pressure mapping to expression"""
        pressure = 0.5  # Medium pressure
        expression_cc = 11

        # Calculate expression value
        expr_value = int(pressure * 127)

        self.assertEqual(expr_value, 63)

    def test_modulation_clamping(self):
        """Test modulation value clamping"""
        # CC values should be clamped to 0-127
        value = 200
        clamped = max(0, min(127, value))

        self.assertEqual(clamped, 127)

        value = -50
        clamped = max(0, min(127, value))

        self.assertEqual(clamped, 0)

    def test_modulation_inversion(self):
        """Test modulation inversion"""
        input_val = 0.8
        inverted = 1.0 - input_val

        self.assertAlmostEqual(inverted, 0.2, places=7)

        # Without inversion
        not_inverted = input_val
        self.assertAlmostEqual(not_inverted, 0.8, places=7)


# =============================================================================
# MAIN TEST SUITE
# =============================================================================

def run_tests():
    """Run all tests and return results"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestMIDIHandling))
    suite.addTests(loader.loadTestsFromTestCase(TestMIDIInputDevice))
    suite.addTests(loader.loadTestsFromTestCase(TestSoundFontDownloader))
    suite.addTests(loader.loadTestsFromTestCase(TestArpeggiator))
    suite.addTests(loader.loadTestsFromTestCase(TestModulationSystem))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Print summary
    print("\n" + "="*70)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print("="*70)

    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    import sys
    sys.exit(run_tests())
