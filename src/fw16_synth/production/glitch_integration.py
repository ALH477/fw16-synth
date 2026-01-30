"""
Glitch Prevention Integration Wrapper

This module provides enhanced glitch prevention for the FW16 Synth by wrapping
existing components with additional validation, monitoring, and protection mechanisms.
"""

import threading
import time
import logging
from typing import Optional, Dict, Any, Callable
from pathlib import Path
import os

log = logging.getLogger(__name__)

class EnhancedFluidSynthEngine:
    """
    Enhanced FluidSynth engine with glitch prevention capabilities.
    This wrapper adds state validation, error recovery, and monitoring
    to the base FluidSynthEngine.
    """
    
    def __init__(self, base_engine):
        """
        Initialize the enhanced engine with a base engine instance.
        
        Args:
            base_engine: The original FluidSynthEngine instance to enhance
        """
        self.base = base_engine
        self._lock = threading.RLock()
        self._operation_count = 0
        self._last_operation_time = 0.0
        self._error_count = 0
        self._consecutive_errors = 0
        self._last_error_time = 0.0
        
        # Rate limiting
        self._max_operations_per_second = 1000
        self._operation_times = []
        
        log.info("Enhanced FluidSynth engine initialized with glitch prevention")
    
    def _check_rate_limit(self) -> bool:
        """Check if we're exceeding operation rate limits"""
        current_time = time.time()
        
        # Clean old entries (older than 1 second)
        self._operation_times = [t for t in self._operation_times if current_time - t < 1.0]
        
        # Check if we're at the limit
        if len(self._operation_times) >= self._max_operations_per_second:
            log.warning(f"Operation rate limit exceeded: {len(self._operation_times)}/s")
            return False
        
        self._operation_times.append(current_time)
        return True
    
    def _validate_midi_range(self, value: int, min_val: int = 0, max_val: int = 127) -> int:
        """Validate and clamp MIDI values to valid ranges"""
        if value < min_val or value > max_val:
            log.debug(f"Clamping MIDI value {value} to range [{min_val}, {max_val}]")
        return max(min_val, min(max_val, value))
    
    def _track_operation(self, operation_name: str):
        """Track operation for monitoring and rate limiting"""
        self._operation_count += 1
        self._last_operation_time = time.time()
    
    def _handle_error(self, operation: str, error: Exception, context: Dict[str, Any] = None):
        """Handle errors with logging and potential recovery"""
        self._error_count += 1
        self._consecutive_errors += 1
        self._last_error_time = time.time()
        
        context_str = f" (context: {context})" if context else ""
        log.error(f"Error in {operation}: {error}{context_str}")
        
        # Reset consecutive errors after successful operations
        if self._consecutive_errors > 5:
            log.warning(f"Multiple consecutive errors in {operation}. Consider system restart.")
    
    def _record_success(self):
        """Record successful operation to reset error counters"""
        if self._consecutive_errors > 0:
            self._consecutive_errors = 0
    
    # Enhanced methods with glitch prevention
    def initialize(self, soundfont_path: Optional[Path] = None) -> bool:
        """Enhanced initialization with validation"""
        with self._lock:
            self._track_operation("initialize")
            
            try:
                # Check if already initialized
                if self.base._initialized:
                    log.warning("FluidSynth already initialized")
                    return True
                
                # Validate soundfont path if provided
                if soundfont_path:
                    if not soundfont_path.exists():
                        log.error(f"Soundfont file not found: {soundfont_path}")
                        return False
                    
                    if not os.access(soundfont_path, os.R_OK):
                        log.error(f"Soundfont file not readable: {soundfont_path}")
                        return False
                    
                    # Check file size
                    if soundfont_path.stat().st_size == 0:
                        log.error(f"Soundfont file is empty: {soundfont_path}")
                        return False
                
                # Validate basic audio parameters
                if self.base.config.sample_rate <= 0 or self.base.config.buffer_size <= 0:
                    log.error("Invalid audio parameters detected")
                    return False
                
                # Call base initialization
                result = self.base.initialize(soundfont_path)
                
                if result:
                    self._record_success()
                    log.info("Enhanced FluidSynth initialization successful")
                else:
                    self._handle_error("initialize", Exception("Base initialization failed"))
                
                return result
                
            except Exception as e:
                self._handle_error("initialize", e, {'soundfont': str(soundfont_path) if soundfont_path else None})
                return False
    
    def load_soundfont(self, path: Path) -> bool:
        """Enhanced soundfont loading with validation"""
        with self._lock:
            if not self._check_rate_limit():
                return False
            
            self._track_operation("load_soundfont")
            
            try:
                # Validate file
                if not path.exists():
                    log.error(f"Soundfont file not found: {path}")
                    return False
                
                if not path.is_file():
                    log.error(f"Soundfont path is not a file: {path}")
                    return False
                
                # Check file extension
                if path.suffix.lower() not in ['.sf2', '.sf3']:
                    log.warning(f"Unexpected soundfont extension: {path.suffix}")
                
                result = self.base.load_soundfont(path)
                
                if result:
                    self._record_success()
                    log.info(f"Enhanced soundfont loading successful: {path.name}")
                else:
                    self._handle_error("load_soundfont", Exception("Base soundfont loading failed"), 
                                     {'path': str(path)})
                
                return result
                
            except Exception as e:
                self._handle_error("load_soundfont", e, {'path': str(path)})
                return False
    
    def note_on(self, note: int, velocity: int, layer: bool = False):
        """Enhanced note_on with validation"""
        with self._lock:
            if not self._check_rate_limit():
                return
            
            self._track_operation("note_on")
            
            try:
                # Validate inputs
                note = self._validate_midi_range(note, 0, 127)
                velocity = self._validate_midi_range(velocity, 0, 127)
                
                # Only proceed if velocity > 0
                if velocity > 0:
                    self.base.note_on(note, velocity, layer)
                    self._record_success()
                
            except Exception as e:
                self._handle_error("note_on", e, {'note': note, 'velocity': velocity, 'layer': layer})
    
    def note_off(self, note: int, layer: bool = False):
        """Enhanced note_off with validation"""
        with self._lock:
            if not self._check_rate_limit():
                return
            
            self._track_operation("note_off")
            
            try:
                # Validate note
                note = self._validate_midi_range(note, 0, 127)
                self.base.note_off(note, layer)
                self._record_success()
                
            except Exception as e:
                self._handle_error("note_off", e, {'note': note, 'layer': layer})
    
    def pitch_bend(self, value: int, layer: bool = False):
        """Enhanced pitch_bend with validation"""
        with self._lock:
            if not self._check_rate_limit():
                return
            
            self._track_operation("pitch_bend")
            
            try:
                # Validate pitch bend range (0-16383)
                value = self._validate_midi_range(value, 0, 16383)
                self.base.pitch_bend(value, layer)
                self._record_success()
                
            except Exception as e:
                self._handle_error("pitch_bend", e, {'value': value, 'layer': layer})
    
    def control_change(self, cc: int, value: int, layer: bool = False):
        """Enhanced control_change with validation"""
        with self._lock:
            if not self._check_rate_limit():
                return
            
            self._track_operation("control_change")
            
            try:
                # Validate CC inputs
                cc = self._validate_midi_range(cc, 0, 127)
                value = self._validate_midi_range(value, 0, 127)
                
                self.base.control_change(cc, value, layer)
                self._record_success()
                
            except Exception as e:
                self._handle_error("control_change", e, {'cc': cc, 'value': value, 'layer': layer})
    
    def program_change(self, program: int, bank: int = 0, channel: Optional[int] = None):
        """Enhanced program_change with validation"""
        with self._lock:
            if not self._check_rate_limit():
                return
            
            self._track_operation("program_change")
            
            try:
                # Validate inputs
                program = self._validate_midi_range(program, 0, 127)
                bank = self._validate_midi_range(bank, 0, 127)
                
                if channel is not None:
                    channel = self._validate_midi_range(channel, 0, 15)
                
                self.base.program_change(program, bank, channel)
                self._record_success()
                
            except Exception as e:
                self._handle_error("program_change", e, {'program': program, 'bank': bank, 'channel': channel})
    
    def all_notes_off(self):
        """Enhanced all_notes_off with error handling"""
        with self._lock:
            self._track_operation("all_notes_off")
            
            try:
                self.base.all_notes_off()
                self._record_success()
                
            except Exception as e:
                self._handle_error("all_notes_off", e)
    
    def shutdown(self):
        """Enhanced shutdown with cleanup"""
        with self._lock:
            self._track_operation("shutdown")
            
            try:
                self.base.shutdown()
                self._record_success()
                log.info("Enhanced FluidSynth shutdown completed")
                
            except Exception as e:
                self._handle_error("shutdown", e)
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get current health and performance status"""
        current_time = time.time()
        uptime = current_time - self._last_operation_time if self._operation_count > 0 else 0
        
        return {
            'operations_total': self._operation_count,
            'errors_total': self._error_count,
            'consecutive_errors': self._consecutive_errors,
            'last_error_time': self._last_error_time,
            'uptime_seconds': uptime,
            'operations_per_second': len(self._operation_times),
            'rate_limited': len(self._operation_times) >= self._max_operations_per_second,
            'initialized': self.base._initialized if hasattr(self.base, '_initialized') else False,
            'soundfont_loaded': self.base.sfid >= 0 if hasattr(self.base, 'sfid') else False
        }


class EnhancedMIDIInput:
    """
    Enhanced MIDI input with validation and glitch prevention.
    """
    
    def __init__(self, base_midi_input):
        """
        Initialize enhanced MIDI input with base instance.
        
        Args:
            base_midi_input: The original MIDIInput instance to enhance
        """
        self.base = base_midi_input
        self._lock = threading.RLock()
        self._message_count = 0
        self._error_count = 0
        self._last_activity = 0.0
        
        # Rate limiting
        self._max_messages_per_second = 500
        self._message_times = []
        
        log.info("Enhanced MIDI input initialized with glitch prevention")
    
    def _check_message_rate(self) -> bool:
        """Check if we're exceeding message rate limits"""
        current_time = time.time()
        
        # Clean old entries
        self._message_times = [t for t in self._message_times if current_time - t < 1.0]
        
        if len(self._message_times) >= self._max_messages_per_second:
            log.debug(f"MIDI message rate limit exceeded: {len(self._message_times)}/s")
            return False
        
        self._message_times.append(current_time)
        return True
    
    def _validate_midi_message(self, msg_type: str, *args) -> tuple:
        """Validate and sanitize MIDI message parameters"""
        validated_args = []
        
        for i, arg in enumerate(args):
            if isinstance(arg, int):
                # Clamp MIDI values to valid ranges
                if msg_type in ['note_on', 'note_off'] and i == 0:  # Note number
                    validated_args.append(max(0, min(127, arg)))
                elif msg_type in ['note_on'] and i == 1:  # Velocity
                    validated_args.append(max(0, min(127, arg)))
                elif msg_type in ['control_change'] and i == 0:  # CC number
                    validated_args.append(max(0, min(127, arg)))
                elif msg_type in ['control_change'] and i == 1:  # CC value
                    validated_args.append(max(0, min(127, arg)))
                elif msg_type in ['pitch_bend']:  # Pitch bend value
                    validated_args.append(max(0, min(16383, arg)))
                elif msg_type in ['program_change']:  # Program number
                    validated_args.append(max(0, min(127, arg)))
                else:
                    validated_args.append(arg)
            else:
                validated_args.append(arg)
        
        return tuple(validated_args)
    
    def process_enhanced_message(self, msg):
        """Process MIDI message with enhanced validation and protection"""
        with self._lock:
            if not self._check_message_rate():
                return
            
            try:
                self._message_count += 1
                self._last_activity = time.time()
                
                # Use the original processing logic but with validation
                self._process_message_enhanced(msg)
                
            except Exception as e:
                self._error_count += 1
                log.error(f"Enhanced MIDI message processing error: {e}")
    
    def _process_message_enhanced(self, msg):
        """Enhanced message processing with validation"""
        # This would contain the enhanced logic from the original _process_message
        # but with added validation and error handling
        try:
            # For now, delegate to the original processor
            if hasattr(self.base, '_process_message'):
                self.base._process_message(msg)
            else:
                log.warning("Base MIDI processor not found")
        except Exception as e:
            log.error(f"Error in enhanced message processing: {e}")
            raise
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get MIDI input health status"""
        return {
            'messages_processed': self._message_count,
            'errors_total': self._error_count,
            'messages_per_second': len(self._message_times),
            'rate_limited': len(self._message_times) >= self._max_messages_per_second,
            'last_activity': self._last_activity,
            'connected': getattr(self.base, 'connected', False) if hasattr(self.base, 'connected') else False
        }


def enhance_fw16_synth(synth_instance) -> None:
    """
    Enhance an existing FW16 Synth instance with glitch prevention.
    
    Args:
        synth_instance: The main synth instance to enhance
    """
    try:
        # Enhance the engine if it exists
        if hasattr(synth_instance, 'engine') and synth_instance.engine:
            enhanced_engine = EnhancedFluidSynthEngine(synth_instance.engine)
            synth_instance.engine = enhanced_engine
            log.info("FluidSynth engine enhanced with glitch prevention")
        
        # Enhance MIDI input if it exists
        if hasattr(synth_instance, 'midi_input') and synth_instance.midi_input:
            enhanced_midi = EnhancedMIDIInput(synth_instance.midi_input)
            synth_instance.midi_input = enhanced_midi
            log.info("MIDI input enhanced with glitch prevention")
        
        # Add health monitoring method
        def get_system_health():
            health = {'timestamp': time.time(), 'components': {}}
            
            if hasattr(synth_instance, 'engine'):
                health['components']['engine'] = synth_instance.engine.get_health_status()
            
            if hasattr(synth_instance, 'midi_input'):
                health['components']['midi'] = synth_instance.midi_input.get_health_status()
            
            return health
        
        synth_instance.get_system_health = get_system_health
        log.info("FW16 Synth enhanced with comprehensive glitch prevention")
        
    except Exception as e:
        log.error(f"Failed to enhance FW16 Synth: {e}")
        raise


# Convenience function for easy integration
def apply_glitch_prevention():
    """
    Apply glitch prevention to the current synth instance.
    This should be called after the main synth is initialized.
    """
    # Import here to avoid circular imports
    try:
        import sys
        if 'fw16_synth' in sys.modules:
            synth_module = sys.modules['fw16_synth']
            # Look for a global synth instance or similar
            for attr_name in dir(synth_module):
                attr = getattr(synth_module, attr_name)
                if hasattr(attr, 'engine') and hasattr(attr, 'midi_input'):
                    enhance_fw16_synth(attr)
                    return True
        
        log.warning("Could not find synth instance to enhance")
        return False
        
    except Exception as e:
        log.error(f"Failed to apply glitch prevention: {e}")
        return False