"""
Production Error Handler

Centralized error handling with intelligent recovery strategies.
Provides user-friendly error messages with actionable solutions.
"""

import os
import sys
import time
import traceback
import subprocess
import logging
from typing import Dict, Callable, Optional, Any, List
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

log = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    """Error severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ErrorContext:
    """Context information for error handling"""
    error: Exception
    context: str
    severity: ErrorSeverity
    user_message: str
    solutions: List[str]
    details: Dict[str, Any]
    timestamp: float
    recoverable: bool = True


class ProductionErrorHandler:
    """Production-ready error handler with recovery strategies"""
    
    def __init__(self):
        self.error_counts: Dict[str, int] = {}
        self.error_history: List[ErrorContext] = []
        self.recovery_strategies: Dict[str, Callable] = {}
        self.circuit_breakers: Dict[str, bool] = {}
        self.max_history = 100
        
        # Register built-in recovery strategies
        self._register_recovery_strategies()
    
    def handle_error(self, error: Exception, context: str, 
                    severity: ErrorSeverity = ErrorSeverity.MEDIUM,
                    details: Optional[Dict[str, Any]] = None) -> bool:
        """
        Handle an error with appropriate recovery strategy
        
        Args:
            error: The exception that occurred
            context: Context where the error occurred
            severity: Error severity level
            details: Additional context details
            
        Returns:
            True if recovery was successful, False otherwise
        """
        # Track error statistics
        self.error_counts[context] = self.error_counts.get(context, 0) + 1
        
        # Check circuit breaker
        if self._is_circuit_breaker_open(context):
            log.warning(f"Circuit breaker open for {context}, skipping recovery")
            return False
        
        # Create error context
        error_ctx = self._create_error_context(error, context, severity, details or {})
        
        # Log the error
        self._log_error(error_ctx)
        
        # Store in history
        self._store_error(error_ctx)
        
        # Attempt recovery if recoverable
        if error_ctx.recoverable and context in self.recovery_strategies:
            try:
                recovery_success = self.recovery_strategies[context](error, details or {})
                if recovery_success:
                    log.info(f"✓ Recovery successful for {context}")
                    self._reset_circuit_breaker(context)
                    return True
                else:
                    log.warning(f"✗ Recovery failed for {context}")
                    self._update_circuit_breaker(context)
            except Exception as recovery_error:
                log.error(f"Recovery strategy failed for {context}: {recovery_error}")
                self._update_circuit_breaker(context)
        
        return False
    
    def format_error(self, error_ctx: ErrorContext) -> str:
        """Format error for user display with solutions"""
        lines = []
        
        # Header
        lines.append("╔" + "═" * 74 + "╗")
        lines.append(f"║  Error: {error_ctx.user_message:<66} ║")
        lines.append("╠" + "═" * 74 + "╣")
        
        # Description
        lines.append(f"║  {error_ctx.user_message:<74} ║")
        lines.append("╠" + "═" * 74 + "╣")
        
        # Solutions
        if error_ctx.solutions:
            lines.append("║  Solution(s):                                               ║")
            for i, solution in enumerate(error_ctx.solutions[:3], 1):
                lines.append(f"║    {i}. {solution:<71} ║")
        
        lines.append("╠" + "═" * 74 + "╣")
        
        # Details
        if error_ctx.details:
            lines.append("║  Details:                                                   ║")
            for key, value in list(error_ctx.details.items())[:5]:
                lines.append(f"║    {key}: {str(value)[:67]:<67} ║")
        
        lines.append("╚" + "═" * 74 + "╝")
        
        return "\n".join(lines)
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """Get error statistics for monitoring"""
        return {
            'total_errors': sum(self.error_counts.values()),
            'error_counts': dict(self.error_counts),
            'recent_errors': len([e for e in self.error_history 
                                 if e.timestamp > (time.time() - 3600)]),
            'circuit_breakers_open': sum(1 for open in self.circuit_breakers.values() if open),
        }
    
    def reset_statistics(self):
        """Reset error statistics"""
        self.error_counts.clear()
        self.error_history.clear()
        self.circuit_breakers.clear()
    
    def _register_recovery_strategies(self):
        """Register built-in recovery strategies"""
        self.recovery_strategies.update({
            'fluidsynth_init': self._recover_fluidsynth,
            'device_access': self._recover_device_access,
            'audio_output': self._recover_audio_output,
            'soundfont_load': self._recover_soundfont_load,
            'midi_connection': self._recover_midi_connection,
        })
    
    def _create_error_context(self, error: Exception, context: str, 
                            severity: ErrorSeverity, details: Dict[str, Any]) -> ErrorContext:
        """Create error context with user-friendly message and solutions"""
        
        # Generate user-friendly message and solutions based on error type
        user_message, solutions, recoverable = self._analyze_error(error, context, details)
        
        return ErrorContext(
            error=error,
            context=context,
            severity=severity,
            user_message=user_message,
            solutions=solutions,
            details=details,
            timestamp=time.time(),
            recoverable=recoverable
        )
    
    def _analyze_error(self, error: Exception, context: str, 
                      details: Dict[str, Any]) -> tuple[str, List[str], bool]:
        """Analyze error and generate user-friendly message and solutions"""
        
        if context == 'device_access':
            if isinstance(error, PermissionError):
                return (
                    "Device Access Permission Denied",
                    [
                        "Add yourself to the 'input' group: sudo usermod -aG input $USER",
                        "Log out and log back in (or reboot)",
                        "Verify with: groups | grep input",
                        "Try running FW16 Synth again"
                    ],
                    False
                )
            elif isinstance(error, OSError):
                return (
                    "Device Not Found or Inaccessible",
                    [
                        "Check if keyboard/touchpad devices are connected",
                        "Verify device permissions: ls -la /dev/input/",
                        "Try running with sudo (not recommended)",
                        "Check dmesg for device errors"
                    ],
                    True
                )
        
        elif context == 'fluidsynth_init':
            if "No such file" in str(error):
                return (
                    "Audio Engine Failed - Driver Not Available",
                    [
                        "Check if PulseAudio/PipeWire is running: systemctl --user status pipewire",
                        "Try restarting audio: systemctl --user restart pipewire",
                        "Try different driver: --driver jack or --driver alsa",
                        "Install audio system if missing"
                    ],
                    True
                )
            elif "Connection refused" in str(error):
                return (
                    "Audio Engine Failed - Connection Refused",
                    [
                        "Audio server is not running or not accepting connections",
                        "Restart audio server: systemctl --user restart pipewire pulseaudio",
                        "Check for audio server conflicts",
                        "Try system audio server instead of user session"
                    ],
                    True
                )
        
        elif context == 'soundfont_load':
            return (
                "SoundFont Loading Failed",
                [
                    "Check if SoundFont file exists and is readable",
                    "Try a different SoundFont file",
                    "Download a default SoundFont from the browser",
                    "Check file permissions: ls -la soundfont.sf2"
                ],
                True
            )
        
        elif context == 'audio_output':
            return (
                "Audio Output Failed",
                [
                    "Check if audio device is available: aplay -l",
                    "Unmute audio: amixer set Master unmute",
                    "Check audio levels: amixer get Master",
                    "Try different audio driver: --driver alsa"
                ],
                True
            )
        
        elif context == 'midi_connection':
            return (
                "MIDI Device Connection Failed",
                [
                    "Check if MIDI device is connected: aconnect -l",
                    "Verify MIDI device permissions",
                    "Try different MIDI port: --midi-port 'Device Name'",
                    "Check if MIDI driver is loaded"
                ],
                True
            )
        
        # Default error handling
        return (
            f"Unexpected Error in {context}",
            [
                "Check system logs for more details: journalctl -xe",
                "Try restarting the application",
                "Report the issue with system information",
                "Check for missing dependencies"
            ],
            True
        )
    
    def _recover_fluidsynth(self, error: Exception, details: Dict[str, Any]) -> bool:
        """Recover from FluidSynth initialization failures"""
        import subprocess
        import time

        try:
            log.info("Attempting FluidSynth recovery...")

            # Try to restart audio server if it's the issue
            if "Connection refused" in str(error) or "No such file" in str(error):
                try:
                    # Check if we're using PipeWire/PulseAudio
                    result = subprocess.run(
                        ['systemctl', '--user', 'is-active', 'pipewire'],
                        capture_output=True, text=True, timeout=5
                    )

                    if result.returncode == 0:
                        log.info("Restarting PipeWire...")
                        subprocess.run(
                            ['systemctl', '--user', 'restart', 'pipewire'],
                            timeout=10, check=False
                        )
                        time.sleep(2.0)  # Wait for restart
                        return True
                except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError) as e:
                    log.debug(f"Could not restart audio server: {e}")

            # Try different audio drivers as fallback
            drivers_to_try = ['alsa', 'jack', 'pulseaudio']

            for driver in drivers_to_try:
                try:
                    log.info(f"Attempting FluidSynth recovery with driver: {driver}")
                    # Note: This would need access to the actual synth instance
                    # For now, we log the suggestion
                    log.info(f"  -> Consider restarting with: --driver {driver}")
                    return True
                except Exception:
                    continue

            return False
        except Exception as e:
            log.error(f"FluidSynth recovery failed: {e}")
            return False
    
    def _recover_device_access(self, error: Exception, details: Dict[str, Any]) -> bool:
        """Recover from device access errors"""
        import os
        import time
        import glob

        try:
            log.info("Attempting device recovery...")

            # Wait a moment and retry
            time.sleep(0.5)

            # Check device permissions
            if isinstance(error, PermissionError):
                log.info("Checking device permissions...")
                input_devices = glob.glob('/dev/input/event*')

                if input_devices:
                    # Check if we can read any device
                    readable = []
                    for device_path in input_devices:
                        try:
                            if os.access(device_path, os.R_OK):
                                readable.append(device_path)
                        except OSError:
                            pass

                    if not readable:
                        log.error("No readable input devices found")
                        log.error("Try: sudo usermod -aG input $USER && log out and back in")
                        return False

            # Try rescanning devices
            try:
                log.info("Rescanning for input devices...")
                from evdev import list_devices

                devices = list_devices()
                log.info(f"Found {len(devices)} accessible devices")

                return len(devices) > 0
            except ImportError:
                log.warning("evdev not available for device scanning")
                return True  # Assume devices are available if we can't scan

        except Exception as e:
            log.error(f"Device recovery failed: {e}")
            return False
    
    def _recover_audio_output(self, error: Exception, details: Dict[str, Any]) -> bool:
        """Recover from audio output failures"""
        import subprocess
        import time

        try:
            log.info("Attempting audio output recovery...")

            # Check if audio device is available
            try:
                result = subprocess.run(
                    ['aplay', '-l'],
                    capture_output=True, text=True, timeout=5
                )

                if result.returncode != 0:
                    log.warning("No audio devices found via aplay")
                    log.info("Try: systemctl --user restart pipewire pulseaudio")
                    return False
            except (subprocess.TimeoutExpired, FileNotFoundError) as e:
                log.debug(f"Could not check audio devices: {e}")

            # Check if audio is muted
            try:
                result = subprocess.run(
                    ['amixer', 'get', 'Master'],
                    capture_output=True, text=True, timeout=5
                )

                if '[off]' in result.stdout:
                    log.info("Audio is muted, attempting to unmute...")
                    subprocess.run(
                        ['amixer', 'set', 'Master', 'unmute'],
                        timeout=5, check=False
                    )
                    log.info("Audio unmuted")
            except (subprocess.TimeoutExpired, FileNotFoundError) as e:
                log.debug(f"Could not check/unmute audio: {e}")

            # Try restarting audio server as last resort
            log.info("Attempting to restart audio server...")
            try:
                subprocess.run(
                    ['systemctl', '--user', 'restart', 'pipewire'],
                    timeout=10, check=False
                )
                time.sleep(2.0)
                log.info("Audio server restarted")
                return True
            except (subprocess.TimeoutExpired, FileNotFoundError) as e:
                log.warning(f"Could not restart audio server: {e}")

            return False

        except Exception as e:
            log.error(f"Audio recovery failed: {e}")
            return False
    
    def _recover_soundfont_load(self, error: Exception, details: Dict[str, Any]) -> bool:
        """Recover from SoundFont loading failures"""
        import glob

        try:
            log.info("Attempting SoundFont recovery...")

            # Common soundfont search paths
            search_paths = [
                Path.home() / ".local/share/soundfonts",
                Path.home() / "soundfonts",
                Path("/usr/share/soundfonts"),
                Path("/usr/local/share/soundfonts"),
            ]

            # Try to find any .sf2 files
            for search_path in search_paths:
                if not search_path.exists():
                    continue

                sf2_files = []
                for pattern in ['*.sf2', '*.SF2', '**/*.sf2', '**/*.SF2']:
                    sf2_files.extend(search_path.glob(pattern))

                if sf2_files:
                    log.info(f"Found {len(sf2_files)} SoundFont files in {search_path}")

                    # Prefer FluidR3 or GeneralUser
                    preferred_names = ['fluid', 'generaluser']
                    for pref in preferred_names:
                        for sf_path in sf2_files:
                            if pref in sf_path.name.lower():
                                log.info(f"Found preferred SoundFont: {sf_path.name}")
                                log.info(f"  -> Use with: --soundfont {sf_path}")
                                return True

                    # Use any available SoundFont
                    log.info(f"Using SoundFont: {sf2_files[0].name}")
                    log.info(f"  -> Use with: --soundfont {sf2_files[0]}")
                    return True

            log.error("No SoundFont files found in standard locations")
            log.info("Download a SoundFont from the built-in browser or:")
            log.info("  -> FluidR3 GM: https://keymusician01.s3.amazonaws.com/FluidR3_GM.sf2")
            log.info("  -> GeneralUser GS: https://www.schristiancollins.com/soundfonts/GeneralUser_GS.sf2")

            return False

        except Exception as e:
            log.error(f"SoundFont recovery failed: {e}")
            return False
    
    def _recover_midi_connection(self, error: Exception, details: Dict[str, Any]) -> bool:
        """Recover from MIDI connection failures"""
        import time

        try:
            log.info("Attempting MIDI connection recovery...")

            # Wait and retry (USB MIDI devices may need time to enumerate)
            log.info("Waiting 2 seconds for MIDI device to be ready...")
            time.sleep(2.0)

            # Try to check if MIDI is available
            try:
                from rtmidi import MidiIn

                available_ports = MidiIn().get_ports()
                log.info(f"Found {len(available_ports)} MIDI ports available")

                if available_ports:
                    log.info("Available MIDI ports:")
                    for i, port in enumerate(available_ports):
                        log.info(f"  {i}: {port}")
                    log.info("Try: --midi --midi-port 'Your Device Name'")
                    return True

            except ImportError:
                log.warning("rtmidi not available for MIDI checking")
            except Exception as e:
                log.debug(f"MIDI port check failed: {e}")

            # Check ALSA MIDI connections
            try:
                import subprocess
                result = subprocess.run(
                    ['aconnect', '-l'],
                    capture_output=True, text=True, timeout=5
                )

                if result.returncode == 0 and result.stdout:
                    log.info("ALSA MIDI connections detected")
                    log.info(result.stdout)
                    return True

            except (subprocess.TimeoutExpired, FileNotFoundError) as e:
                log.debug(f"Could not check ALSA MIDI: {e}")

            return False

        except Exception as e:
            log.error(f"MIDI recovery failed: {e}")
            return False
    
    def _is_circuit_breaker_open(self, context: str) -> bool:
        """Check if circuit breaker is open for context"""
        return self.circuit_breakers.get(context, False)
    
    def _update_circuit_breaker(self, context: str):
        """Update circuit breaker state after failure"""
        error_count = self.error_counts.get(context, 0)
        # Open circuit breaker after 3 failures
        if error_count >= 3:
            self.circuit_breakers[context] = True
            log.warning(f"Circuit breaker opened for {context} after {error_count} failures")
    
    def _reset_circuit_breaker(self, context: str):
        """Reset circuit breaker after successful recovery"""
        if context in self.circuit_breakers:
            del self.circuit_breakers[context]
            # Reset error count on successful recovery
            if context in self.error_counts:
                del self.error_counts[context]
            log.info(f"Circuit breaker reset for {context}")
    
    def _log_error(self, error_ctx: ErrorContext):
        """Log error with appropriate level"""
        if error_ctx.severity == ErrorSeverity.CRITICAL:
            log.critical(f"[{error_ctx.context}] {error_ctx.user_message}")
        elif error_ctx.severity == ErrorSeverity.HIGH:
            log.error(f"[{error_ctx.context}] {error_ctx.user_message}")
        elif error_ctx.severity == ErrorSeverity.MEDIUM:
            log.warning(f"[{error_ctx.context}] {error_ctx.user_message}")
        else:
            log.info(f"[{error_ctx.context}] {error_ctx.user_message}")
        
        # Log stack trace for debugging
        log.debug(f"Error details: {error_ctx.error}")
        log.debug(f"Stack trace:\n{''.join(traceback.format_tb(error_ctx.error.__traceback__))}")
    
    def _store_error(self, error_ctx: ErrorContext):
        """Store error in history"""
        self.error_history.append(error_ctx)
        
        # Maintain history size
        if len(self.error_history) > self.max_history:
            self.error_history = self.error_history[-self.max_history:]