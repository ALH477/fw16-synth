"""
MIDI Handler Module

Handles MIDI input processing, message parsing, and device management.
"""

import asyncio
import time
import threading
import logging
from typing import Optional, Set, Dict, Callable, List

try:
    import rtmidi
    RTMIDI_AVAILABLE = True
except ImportError:
    RTMIDI_AVAILABLE = False
    rtmidi = None

from ..fw16_synth import FluidSynthEngine, ArpMode

log = logging.getLogger(__name__)


class MIDIInputController:
    """
    MIDI input handler for external MIDI devices.

    Supports the Framework 16 Piano Keyboard Module (pitstop_tech) and other
    USB MIDI controllers. Features:
    - Auto-detection of MIDI input devices
    - Velocity-sensitive note input
    - Aftertouch (channel pressure) support
    - Pitch bend and CC passthrough
    - Hot-plug detection
    - Hot-plug detection

    The FW16 Piano Keyboard Module appears as a standard USB MIDI device
    with velocity and aftertouch support.
    """

    # Known Framework 16 MIDI module identifiers
    FW16_MIDI_KEYWORDS = ['framework', 'fw16', 'piano', 'pitstop']

    def __init__(self, engine: FluidSynthEngine, callback: Optional[Callable] = None):
        self.engine = engine
        self.callback = callback  # For UI updates
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._midi_in = None
        self._port_name: str = ""
        self._connected = False
        self._last_activity: float = 0.0

        # State tracking
        self._active_notes: Set[int] = set()
        self._aftertouch_value: int = 0
        self._pitch_bend: int = 8192  # Center

        if not RTMIDI_AVAILABLE:
            log.warning("python-rtmidi not available - MIDI input disabled")
            log.info("Install with: pip install python-rtmidi")

    @property
    def available(self) -> bool:
        """Check if MIDI input is available"""
        return RTMIDI_AVAILABLE

    @property
    def connected(self) -> bool:
        """Check if connected to MIDI device"""
        return self._connected

    def list_ports(self) -> List[str]:
        """List available MIDI input ports"""
        if not RTMIDI_AVAILABLE:
            return []

        midi_in = rtmidi.RtMidiIn()
        ports = midi_in.get_ports()
        return ports

    def find_fw16_port(self) -> Optional[str]:
        """Auto-detect FW16 Piano Keyboard Module"""
        if not RTMIDI_AVAILABLE:
            return None

        ports = self.list_ports()

        # Look for keywords in port names
        for port in ports:
            port_lower = port.lower()
            for keyword in self.FW16_MIDI_KEYWORDS:
                if keyword in port_lower:
                    log.info(f"Auto-detected FW16 MIDI module: {port}")
                    return port

        return None

    def connect(self, port_name: Optional[str] = None, auto_detect: bool = True) -> bool:
        """
        Connect to MIDI input device

        Args:
            port_name: Specific port name (optional)
            auto_detect: Auto-detect FW16 module if True

        Returns:
            True if connection successful
        """
        if not RTMIDI_AVAILABLE:
            return False

        try:
            # Auto-detect FW16 module if enabled
            if auto_detect and port_name is None:
                port_name = self.find_fw16_port()

            # Use first available if no specific port and no FW16 detected
            if port_name is None:
                ports = self.list_ports()
                if ports:
                    port_name = ports[0]
                    log.info(f"Using first available MIDI port: {port_name}")
                else:
                    log.warning("No MIDI input devices found")
                    return False

            # Connect to device
            self._midi_in = rtmidi.RtMidiIn()
            self._midi_in.open_port(port_name)
            self._port_name = port_name
            self._connected = True
            self._last_activity = time.time()

            log.info(f"MIDI connected: {port_name}")
            return True

        except Exception as e:
            log.error(f"MIDI connection failed: {e}")
            self._connected = False
            return False

    def disconnect(self):
        """Disconnect from MIDI device"""
        if self._midi_in:
            try:
                self._midi_in.close_port()
                log.info("MIDI disconnected")
            except Exception as e:
                log.error(f"MIDI disconnect error: {e}")
            finally:
                self._midi_in = None
                self._connected = False
                self._active_notes.clear()

    def process_message(self, status: int, data1: Optional[int] = None,
                     data2: Optional[int] = None) -> bool:
        """
        Process a MIDI message

        Args:
            status: Status byte (includes channel)
            data1: First data byte
            data2: Second data byte (for pitch bend)

        Returns:
            True if message was handled, False otherwise
        """
        # Extract channel and status
        channel = status & 0x0F
        message_status = status & 0xF0

        # Note On (0x9n)
        if 0x90 <= message_status <= 0x9F and data1 is not None:
            note = data1
            velocity = data2 if data2 is not None else 127

            self._active_notes.add(note)
            self._last_activity = time.time()

            if self.engine:
                self.engine.note_on(note, velocity)

            log.debug(f"MIDI Note On: CH{channel} N{note} V{velocity}")
            return True

        # Note Off (0x8n)
        elif 0x80 <= message_status <= 0x8F and data1 is not None:
            note = data1
            self._active_notes.discard(note)
            self._last_activity = time.time()

            if self.engine:
                self.engine.note_off(note)

            log.debug(f"MIDI Note Off: CH{channel} N{note}")
            return True

        # Control Change (0xBn)
        elif message_status == 0xB0 and data1 is not None:
            cc_number = data1
            cc_value = data2 if data2 is not None else 0

            # Aftertouch (Channel Pressure) - CC 2
            if cc_number == 2:
                self._aftertouch_value = cc_value
                log.debug(f"MIDI Aftertouch: CH{channel} V{cc_value}")
            # Pitch Bend - CC 128-131 (RPN/NRPN)
            elif 128 <= cc_number <= 131:
                # Handle RPN/NRPN for pitch bend
                pass
            # Other CC
            else:
                if self.engine:
                    self.engine.control_change(cc_number, cc_value)

            log.debug(f"MIDI CC: CH{channel} {cc_number}={cc_value}")
            self._last_activity = time.time()
            return True

        # Pitch Bend (0xE0)
        elif message_status == 0xE0 and data1 is not None and data2 is not None:
            self._pitch_bend = (data2 << 7) | data1

            if self.engine:
                self.engine.pitch_bend(self._pitch_bend)

            log.debug(f"MIDI Pitch Bend: CH{channel} {self._pitch_bend}")
            self._last_activity = time.time()
            return True

        # Program Change (0xCn)
        elif message_status == 0xC0 and data1 is not None:
            program = data1

            if self.engine:
                self.engine.program_change(program)

            log.debug(f"MIDI Program Change: CH{channel} {program}")
            self._last_activity = time.time()
            return True

        return False

    def all_notes_off(self):
        """Turn off all active notes (panic)"""
        for note in list(self._active_notes):
            if self.engine:
                self.engine.note_off(note)
        self._active_notes.clear()
        log.debug("MIDI: All notes off (panic)")


class MIDIMessage:
    """MIDI message representation for testing"""

    def __init__(self, status_byte: int, data1: Optional[int] = None,
                 data2: Optional[int] = None, timestamp: float = 0.0):
        self.status_byte = status_byte
        self.data1 = data1
        self.data2 = data2
        self.timestamp = timestamp

    @property
    def channel(self) -> int:
        return self.status_byte & 0x0F

    @property
    def status(self) -> int:
        return self.status_byte & 0xF0

    @property
    def is_note_on(self) -> bool:
        return 0x90 <= self.status <= 0x9F

    @property
    def is_note_off(self) -> bool:
        return 0x80 <= self.status <= 0x8F

    @property
    def is_control_change(self) -> bool:
        return self.status == 0xB0

    @property
    def is_pitch_bend(self) -> bool:
        return self.status == 0xE0

    @property
    def is_program_change(self) -> bool:
        return self.status == 0xC0
