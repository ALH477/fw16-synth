"""
Production Synth Controller

Production-ready wrapper for FW16 Synth with comprehensive
error handling, resource management, and health monitoring.
Preserves all existing functionality including excellent velocity system.
"""

import asyncio
import logging
import signal
import time
from typing import Optional, Any, Dict
from .error_handler import ProductionErrorHandler, ErrorContext, ErrorSeverity
from .resource_manager import ProductionResourceManager
from .device_manager import ProductionDeviceManager
from .retry_manager import ProductionRetryManager, RetryResult
from .health_monitor import ProductionHealthMonitor, HealthStatus

log = logging.getLogger(__name__)


class ProductionSynthController:
    """Production-ready wrapper for FW16 Synth"""
    
    def __init__(self, base_synth, config=None):
        self.base = base_synth
        self.config = config
        
        # Initialize production components
        self.error_handler = ProductionErrorHandler()
        self.resource_manager = ProductionResourceManager()
        self.device_manager = ProductionDeviceManager(log)
        self.retry_manager = ProductionRetryManager()
        self.health_monitor = ProductionHealthMonitor(log)
        
        # Production state
        self.production_mode = True
        self.shutdown_requested = False
        self.graceful_shutdown_timeout = 30.0  # seconds
        
        # Setup production features
        self._setup_production_features()
        self._register_resources()
        self._setup_health_callbacks()
    
    def initialize(self) -> bool:
        """Initialize synth with production error handling"""
        try:
            log.info("Initializing production FW16 Synth...")
            
            # Validate configuration
            if not self._validate_configuration():
                return False
            
            # Initialize base synth with retry
            def init_base():
                return self.base.initialize()
            
            result = self.retry_manager.execute_with_result(
                init_base, 'fluidsynth_init'
            )
            
            if result.failed:
                self.error_handler.handle_error(
                    result.error, 'fluidsynth_init', ErrorSeverity.HIGH
                )
                return False
            
            # Setup device management
            if not self._setup_devices():
                return False
            
            # Start health monitoring
            if not self.health_monitor.start_monitoring():
                log.warning("Health monitoring failed to start")
            
            log.info("✓ Production FW16 Synth initialized successfully")
            return True
            
        except Exception as e:
            self.error_handler.handle_error(
                e, 'synth_initialization', ErrorSeverity.CRITICAL
            )
            return False
    
    async def run(self) -> bool:
        """Run synth with production monitoring"""
        try:
            log.info("Starting production FW16 Synth main loop...")
            
            # Setup signal handling
            self._setup_signal_handlers()
            
            # Start device monitoring
            self.device_manager.start_hotplug_monitoring()
            self.device_manager.start_health_monitoring()
            
            # Wrap base run method
            run_result = await self._run_with_monitoring()
            
            log.info("✓ Production FW16 Synth run completed")
            return run_result
            
        except Exception as e:
            self.error_handler.handle_error(
                e, 'synth_execution', ErrorSeverity.CRITICAL
            )
            return False
        finally:
            await self._production_cleanup()
    
    def stop(self):
        """Stop synth with production cleanup"""
        log.info("Stopping production FW16 Synth...")
        self.shutdown_requested = True
        
        # Stop health monitoring
        self.health_monitor.stop_monitoring()
        
        # Stop device monitoring
        self.device_manager.stop_monitoring()
        
        # Stop base synth
        try:
            self.base.stop()
        except Exception as e:
            self.error_handler.handle_error(
                e, 'synth_shutdown', ErrorSeverity.MEDIUM
            )
        
        # Clean up resources
        cleanup_results = self.resource_manager.cleanup_all()
        
        # Log cleanup results
        failed_cleanups = sum(1 for success in cleanup_results.values() if not success)
        if failed_cleanups > 0:
            log.warning(f"{failed_cleanups} resources failed to clean up")
        else:
            log.info("✓ All resources cleaned up successfully")
        
        # Log final metrics
        self._log_final_metrics()
    
    def handle_event(self, event) -> bool:
        """Handle input event with production error handling"""
        try:
            # Record event for health monitoring
            self.health_monitor.record_note_on()
            
            # Delegate to base synth
            return self.base._handle_event(event)
            
        except Exception as e:
            self.error_handler.handle_error(
                e, 'event_handling', ErrorSeverity.MEDIUM
            )
            self.health_monitor.record_error('event_handling')
            return False
    
    def get_health_report(self) -> Dict[str, Any]:
        """Get comprehensive health report"""
        return self.health_monitor.get_health_status()
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """Get error handling statistics"""
        return self.error_handler.get_error_statistics()
    
    def get_resource_metrics(self) -> Dict[str, Any]:
        """Get resource management metrics"""
        return self.resource_manager.get_metrics()
    
    def _setup_production_features(self):
        """Setup production features without breaking existing functionality"""
        # Wrap velocity tracking to monitor without modifying behavior
        self._wrap_velocity_tracking()
        
        # Wrap MIDI handling for error recovery
        self._wrap_midi_handling()
        
        # Wrap audio engine for monitoring
        self._wrap_audio_engine()
        
        # Wrap glitch prevention features
        self._wrap_glitch_prevention()
    
    def _wrap_velocity_tracking(self):
        """Wrap velocity tracking for production monitoring"""
        if not hasattr(self.base, 'velocity') or not hasattr(self.base, 'ui'):
            return
        
        original_note_on = self.base.ui.note_on
        
        def production_note_on(key: str, note_name: str, velocity: int, source: str = "timing"):
            try:
                # Record velocity metrics
                self.health_monitor.record_velocity(velocity, source)
                
                # Call original method
                original_note_on(key, note_name, velocity, source)
                
            except Exception as e:
                self.error_handler.handle_error(
                    e, 'velocity_tracking', ErrorSeverity.LOW
                )
        
        # Replace method
        self.base.ui.note_on = production_note_on
        log.debug("✓ Wrapped velocity tracking for production monitoring")
    
    def _wrap_midi_handling(self):
        """Wrap MIDI handling for production error recovery"""
        if not hasattr(self.base, 'engine'):
            return
        
        # Wrap critical MIDI methods
        original_note_on = self.base.engine.note_on
        original_note_off = self.base.engine.note_off
        original_control_change = self.base.engine.control_change
        
        def production_note_on(note: int, velocity: int, layer: bool = False):
            try:
                return original_note_on(note, velocity, layer)
            except Exception as e:
                self.error_handler.handle_error(
                    e, 'midi_note_on', ErrorSeverity.MEDIUM
                )
                self.health_monitor.record_error('midi_note_on')
                return False
        
        def production_note_off(note: int, layer: bool = False):
            try:
                return original_note_off(note, layer)
            except Exception as e:
                self.error_handler.handle_error(
                    e, 'midi_note_off', ErrorSeverity.MEDIUM
                )
                self.health_monitor.record_error('midi_note_off')
        
        def production_control_change(cc: int, value: int, layer: bool = False):
            try:
                return original_control_change(cc, value, layer)
            except Exception as e:
                self.error_handler.handle_error(
                    e, 'midi_control_change', ErrorSeverity.MEDIUM
                )
                self.health_monitor.record_error('midi_control_change')
                return False
        
        # Replace methods
        self.base.engine.note_on = production_note_on
        self.base.engine.note_off = production_note_off
        self.base.engine.control_change = production_control_change
        log.debug("✓ Wrapped MIDI handling for production error recovery")
    
    def _wrap_audio_engine(self):
        """Wrap audio engine for monitoring and error recovery"""
        if not hasattr(self.base, 'engine'):
            return
        
        # Wrap audio operations
        original_initialize = getattr(self.base.engine, 'initialize', None)
        
        if original_initialize:
            def production_initialize():
                start_time = time.time()
                try:
                    result = original_initialize()
                    latency = (time.time() - start_time) * 1000  # ms
                    self.health_monitor.record_latency(latency)
                    return result
                except Exception as e:
                    self.error_handler.handle_error(
                        e, 'audio_initialize', ErrorSeverity.HIGH
                    )
                    return False
            
            self.base.engine.initialize = production_initialize
            log.debug("✓ Wrapped audio engine for production monitoring")
    
    def _wrap_glitch_prevention(self):
        """Wrap components with glitch prevention features"""
        try:
            # Try to import glitch prevention
            try:
                from .glitch_integration import enhance_fw16_synth
                enhance_fw16_synth(self.base)
                log.info("✓ Glitch prevention features enabled")
            except ImportError:
                log.debug("Glitch prevention module not available, continuing without enhanced protection")
        except Exception as e:
            log.warning(f"Failed to setup glitch prevention: {e}")
    
    def _register_resources(self):
        """Register synth resources with production manager"""
        # Register FluidSynth engine
        if hasattr(self.base, 'engine'):
            self.resource_manager.register_resource(
                'fluidsynth_engine', 
                self.base.engine,
                lambda: getattr(self.base.engine, 'shutdown', lambda: None)()
            )
        
        # Register devices
        if hasattr(self.base, '_devices'):
            def cleanup_devices():
                # Release devices first
                self.device_manager.release_all_devices()
                # Close devices
                for device in self.base._devices:
                    try:
                        if hasattr(device, 'close'):
                            device.close()
                    except Exception:
                        pass
            
            self.resource_manager.register_resource(
                'input_devices',
                self.base._devices,
                cleanup_devices
            )
        
        # Register UI
        if hasattr(self.base, 'ui') and self.base.ui:
            self.resource_manager.register_resource(
                'ui',
                self.base.ui,
                lambda: getattr(self.base.ui, 'stop', lambda: None)()
            )
        
        log.debug("✓ Registered resources with production manager")
    
    def _setup_health_callbacks(self):
        """Setup health monitoring callbacks"""
        def health_callback(health_data):
            # Check for critical conditions
            if health_data['status'] == HealthStatus.CRITICAL.value:
                log.critical("🚨 CRITICAL HEALTH STATUS DETECTED")
                
                # Could trigger automatic recovery here
                # For now, just log the issue
            
            self.health_monitor.register_health_callback(health_callback)
            log.debug("✓ Setup health monitoring callbacks")
    
    def _validate_configuration(self) -> bool:
        """Validate synth configuration"""
        try:
            # Check critical configuration items
            if not hasattr(self.base, 'config'):
                log.error("No configuration found")
                return False
            
            config = self.base.config
            
            # Validate audio driver
            if hasattr(config, 'audio_driver'):
                valid_drivers = ['pulseaudio', 'alsa', 'jack']
                if config.audio_driver not in valid_drivers:
                    log.error(f"Invalid audio driver: {config.audio_driver}")
                    return False
            
            # Validate velocity settings
            if hasattr(config, 'velocity_source'):
                valid_sources = ['timing', 'pressure', 'position', 'combined']
                if config.velocity_source not in valid_sources:
                    log.error(f"Invalid velocity source: {config.velocity_source}")
                    return False
            
            log.debug("✓ Configuration validation passed")
            return True
            
        except Exception as e:
            log.error(f"Configuration validation failed: {e}")
            return False
    
    def _setup_devices(self) -> bool:
        """Setup devices with production error handling"""
        try:
            # Enumerate devices
            if not self.device_manager.enumerate_devices():
                self.error_handler.handle_error(
                    Exception("No input devices found"),
                    'device_enumeration',
                    ErrorSeverity.HIGH
                )
                return False
            
            # Grab devices
            grabbed_count = self.device_manager.grab_all_devices()
            if grabbed_count == 0:
                self.error_handler.handle_error(
                    Exception("Could not grab any devices"),
                    'device_grab',
                    ErrorSeverity.HIGH
                )
                return False
            
            # Register devices with base synth
            self.base._devices = [
                info.device for info in self.device_manager.get_active_devices()
                if info.device is not None
            ]
            
            log.debug(f"✓ Setup {grabbed_count} devices successfully")
            return True
            
        except Exception as e:
            self.error_handler.handle_error(
                e, 'device_setup', ErrorSeverity.HIGH
            )
            return False
    
    def _setup_signal_handlers(self):
        """Setup production signal handlers"""
        def signal_handler(signum, frame):
            if self.shutdown_requested:
                log.warning("Force shutdown requested")
                sys.exit(1)
            
            log.info(f"Received signal {signum}, initiating graceful shutdown...")
            self.shutdown_requested = True
            
            # Create async task for graceful shutdown
            if hasattr(asyncio, 'create_task'):
                asyncio.create_task(self._graceful_shutdown())
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        log.debug("✓ Setup production signal handlers")
    
    async def _run_with_monitoring(self):
        """Run base synth with production monitoring"""
        try:
            # Start base synth's run method
            if hasattr(self.base, 'run') and asyncio.iscoroutinefunction(self.base.run):
                return await self.base.run()
            elif hasattr(self.base, '_run'):
                # Call the original _run method
                return await self.base._run()
            else:
                log.error("No valid run method found in base synth")
                return False
                
        except Exception as e:
            self.error_handler.handle_error(
                e, 'synth_run', ErrorSeverity.CRITICAL
            )
            return False
    
    async def _graceful_shutdown(self):
        """Perform graceful shutdown with timeout"""
        try:
            # Wait for graceful shutdown with timeout
            start_time = time.time()
            
            while (time.time() - start_time) < self.graceful_shutdown_timeout:
                if not self.base._running:
                    break
                
                await asyncio.sleep(0.1)
            
            # Force shutdown if timeout
            if self.base._running:
                log.warning("Graceful shutdown timeout, forcing exit")
                self.base._running = False
                
        except Exception as e:
            log.error(f"Graceful shutdown error: {e}")
    
    async def _production_cleanup(self):
        """Production-specific cleanup"""
        try:
            # Log final health report
            health_report = self.health_monitor.get_health_status()
            log.info("Final Health Report:")
            log.info(self.health_monitor.get_detailed_report())
            
            # Log error statistics
            error_stats = self.error_handler.get_error_statistics()
            log.info(f"Error Statistics: {error_stats}")
            
            # Log resource metrics
            resource_metrics = self.resource_manager.get_metrics()
            log.info(f"Resource Metrics: {resource_metrics}")
            
        except Exception as e:
            log.error(f"Production cleanup error: {e}")
    
    def _log_final_metrics(self):
        """Log final production metrics"""
        try:
            # Get comprehensive metrics
            health_metrics = self.health_monitor.get_health_status()
            error_metrics = self.error_handler.get_error_statistics()
            resource_metrics = self.resource_manager.get_metrics()
            device_metrics = self.device_manager.get_metrics()
            retry_metrics = self.retry_manager.get_metrics()
            
            log.info("╔═══════════════════════════════════════════════════════════════════════╗")
            log.info("║                        PRODUCTION FINAL METRICS                        ║")
            log.info("╠═══════════════════════════════════════════════════════════════════════╣")
            log.info(f"║ Uptime: {health_metrics['uptime']:.1f}s                                     ║")
            log.info(f"║ Status: {health_metrics['status'].upper():<20}                                        ║")
            log.info(f"║ Notes Played: {health_metrics['metrics']['application']['notes_played']:5d}                   ║")
            log.info(f"║ Total Errors: {error_metrics['total_errors']:3d}                                        ║")
            log.info(f"║ Resources Cleaned: {resource_metrics['resources_cleaned']:3d}/{resource_metrics['resources_registered']:3d}      ║")
            log.info(f"║ Devices Managed: {device_metrics['active_devices']:2d}/{device_metrics['total_devices']:2d}                ║")
            log.info(f"║ Retry Success Rate: {retry_metrics['success_rate']:.1f}%                              ║")
            log.info("╚═════════════════════════════════════════════════════════════════════════╝")
            
        except Exception as e:
            log.error(f"Failed to log final metrics: {e}")