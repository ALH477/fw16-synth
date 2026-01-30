"""
Production Configuration Validator

Comprehensive configuration validation with detailed error reporting.
Ensures all synth settings are valid before initialization.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

log = logging.getLogger(__name__)


class ValidationError:
    """Configuration validation error"""
    
    def __init__(self, field: str, message: str, severity: str = "error"):
        self.field = field
        self.message = message
        self.severity = severity


class ProductionConfigValidator:
    """Production-ready configuration validator"""
    
    def __init__(self):
        self.validation_rules = self._setup_validation_rules()
    
    def validate(self, config) -> List[ValidationError]:
        """
        Validate configuration object
        
        Args:
            config: Configuration object to validate
            
        Returns:
            List of validation errors
        """
        errors = []
        
        for rule in self.validation_rules:
            try:
                rule_errors = rule(config)
                errors.extend(rule_errors)
            except Exception as e:
                log.warning(f"Validation rule failed: {e}")
                errors.append(ValidationError(
                    "validation", f"Rule execution failed: {e}", "warning"
                ))
        
        return errors
    
    def validate_and_report(self, config) -> Tuple[bool, List[str]]:
        """
        Validate configuration and return user-friendly report
        
        Args:
            config: Configuration object to validate
            
        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = self.validate(config)
        
        if not errors:
            return True, []
        
        # Group errors by severity
        critical_errors = [e for e in errors if e.severity == "critical"]
        warning_errors = [e for e in errors if e.severity == "warning"]
        
        messages = []
        
        if critical_errors:
            messages.append("Critical Configuration Errors:")
            for error in critical_errors:
                messages.append(f"  • {error.field}: {error.message}")
        
        if warning_errors:
            if critical_errors:
                messages.append("")
            messages.append("Configuration Warnings:")
            for error in warning_errors:
                messages.append(f"  • {error.field}: {error.message}")
        
        return False, messages
    
    def _setup_validation_rules(self) -> List[callable]:
        """Setup configuration validation rules"""
        return [
            self._validate_audio_driver,
            self._validate_velocity_settings,
            self._validate_touchpad_settings,
            self._validate_midi_settings,
            self._validate_file_paths,
            self._validate_performance_settings,
            self._validate_display_settings,
        ]
    
    def _validate_audio_driver(self, config) -> List[ValidationError]:
        """Validate audio driver configuration"""
        errors = []
        
        if not hasattr(config, 'audio_driver'):
            return errors
        
        driver = config.audio_driver
        valid_drivers = ['pulseaudio', 'pipewire', 'alsa', 'jack']
        
        if driver not in valid_drivers:
            errors.append(ValidationError(
                "audio_driver",
                f"Invalid driver '{driver}'. Valid options: {', '.join(valid_drivers)}",
                "critical"
            ))
        
        return errors
    
    def _validate_velocity_settings(self, config) -> List[ValidationError]:
        """Validate velocity configuration"""
        errors = []
        
        # Validate velocity source
        if hasattr(config, 'velocity_source'):
            source = config.velocity_source
            valid_sources = ['timing', 'pressure', 'position', 'combined']
            
            if source not in valid_sources:
                errors.append(ValidationError(
                    "velocity_source",
                    f"Invalid source '{source}'. Valid: {', '.join(valid_sources)}",
                    "critical"
                ))
        
        # Validate velocity ranges
        if hasattr(config, 'velocity_min') and hasattr(config, 'velocity_max'):
            min_vel = config.velocity_min
            max_vel = config.velocity_max
            
            if not (0 <= min_vel <= 127):
                errors.append(ValidationError(
                    "velocity_min",
                    f"Velocity min must be 0-127, got {min_vel}",
                    "critical"
                ))
            
            if not (0 <= max_vel <= 127):
                errors.append(ValidationError(
                    "velocity_max",
                    f"Velocity max must be 0-127, got {max_vel}",
                    "critical"
                ))
            
            if min_vel >= max_vel:
                errors.append(ValidationError(
                    "velocity_range",
                    f"Velocity min ({min_vel}) must be less than max ({max_vel})",
                    "critical"
                ))
        
        # Validate timing parameters
        if hasattr(config, 'velocity_time_fast') and hasattr(config, 'velocity_time_slow'):
            fast = config.velocity_time_fast
            slow = config.velocity_time_slow
            
            if not (0.001 <= fast <= 1.0):
                errors.append(ValidationError(
                    "velocity_time_fast",
                    f"Fast time must be 0.001-1.0s, got {fast}",
                    "warning"
                ))
            
            if not (0.01 <= slow <= 2.0):
                errors.append(ValidationError(
                    "velocity_time_slow",
                    f"Slow time must be 0.01-2.0s, got {slow}",
                    "warning"
                ))
            
            if fast >= slow:
                errors.append(ValidationError(
                    "velocity_timing",
                    f"Fast time ({fast}) must be less than slow time ({slow})",
                    "warning"
                ))
        
        return errors
    
    def _validate_touchpad_settings(self, config) -> List[ValidationError]:
        """Validate touchpad configuration"""
        errors = []
        
        # Validate touchpad enabled
        if hasattr(config, 'touchpad_enabled'):
            if not isinstance(config.touchpad_enabled, bool):
                errors.append(ValidationError(
                    "touchpad_enabled",
                    "Touchpad enabled must be boolean",
                    "critical"
                ))
        
        # Validate smoothing
        if hasattr(config, 'touchpad_smoothing'):
            smoothing = config.touchpad_smoothing
            if not (0.0 <= smoothing <= 1.0):
                errors.append(ValidationError(
                    "touchpad_smoothing",
                    f"Smoothing must be 0.0-1.0, got {smoothing}",
                    "warning"
                ))
        
        return errors
    
    def _validate_midi_settings(self, config) -> List[ValidationError]:
        """Validate MIDI configuration"""
        errors = []
        
        # Validate MIDI input enabled
        if hasattr(config, 'midi_input_enabled'):
            if not isinstance(config.midi_input_enabled, bool):
                errors.append(ValidationError(
                    "midi_input_enabled",
                    "MIDI input enabled must be boolean",
                    "critical"
                ))
        
        # Validate MIDI port
        if hasattr(config, 'midi_port') and config.midi_port:
            port = config.midi_port
            if not isinstance(port, str):
                errors.append(ValidationError(
                    "midi_port",
                    "MIDI port must be string",
                    "critical"
                ))
            elif len(port.strip()) == 0:
                errors.append(ValidationError(
                    "midi_port",
                    "MIDI port cannot be empty",
                    "critical"
                ))
        
        return errors
    
    def _validate_file_paths(self, config) -> List[ValidationError]:
        """Validate file path configurations"""
        errors = []
        
        # Validate soundfont path
        if hasattr(config, 'soundfont') and config.soundfont:
            soundfont_path = Path(config.soundfont)
            
            if not soundfont_path.exists():
                errors.append(ValidationError(
                    "soundfont",
                    f"SoundFont file not found: {soundfont_path}",
                    "critical"
                ))
            elif not soundfont_path.is_file():
                errors.append(ValidationError(
                    "soundfont",
                    f"SoundFont path is not a file: {soundfont_path}",
                    "critical"
                ))
            elif not soundfont_path.suffix.lower().endswith('.sf2'):
                errors.append(ValidationError(
                    "soundfont",
                    f"SoundFont must have .sf2 extension: {soundfont_path}",
                    "warning"
                ))
        
        # Validate log file path
        if hasattr(config, 'log_file') and config.log_file:
            log_path = Path(config.log_file)
            
            # Check if parent directory exists and is writable
            parent_dir = log_path.parent
            if parent_dir.exists() and not parent_dir.is_dir():
                errors.append(ValidationError(
                    "log_file",
                    f"Log directory does not exist: {parent_dir}",
                    "warning"
                ))
            elif parent_dir.exists() and not os.access(parent_dir, os.W_OK):
                errors.append(ValidationError(
                    "log_file",
                    f"Log directory is not writable: {parent_dir}",
                    "warning"
                ))
        
        return errors
    
    def _validate_performance_settings(self, config) -> List[ValidationError]:
        """Validate performance configuration"""
        errors = []
        
        # Validate refresh rate
        if hasattr(config, 'refresh_rate'):
            rate = config.refresh_rate
            if not (1.0 <= rate <= 120.0):
                errors.append(ValidationError(
                    "refresh_rate",
                    f"Refresh rate must be 1-120 Hz, got {rate}",
                    "warning"
                ))
        
        # Validate pitch bend range
        if hasattr(config, 'pitch_bend_semitones'):
            semitones = config.pitch_bend_semitones
            if not (1 <= semitones <= 24):
                errors.append(ValidationError(
                    "pitch_bend_semitones",
                    f"Pitch bend must be 1-24 semitones, got {semitones}",
                    "warning"
                ))
        
        return errors
    
    def _validate_display_settings(self, config) -> List[ValidationError]:
        """Validate display configuration"""
        errors = []
        
        # Validate TUI enabled
        if hasattr(config, 'show_tui'):
            if not isinstance(config.show_tui, bool):
                errors.append(ValidationError(
                    "show_tui",
                    "TUI enabled must be boolean",
                    "warning"
                ))
        
        # Validate verbose logging
        if hasattr(config, 'verbose'):
            if not isinstance(config.verbose, bool):
                errors.append(ValidationError(
                    "verbose",
                    "Verbose logging must be boolean",
                    "warning"
                ))
        
        return errors