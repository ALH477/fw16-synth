"""
Production Device Manager

Robust device detection and management with hot-plug support.
Handles device disconnection, reconnection, and health monitoring.
"""

import os
import time
import threading
import logging
from typing import Dict, List, Optional, Callable, Set
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

try:
    import evdev
    from evdev import InputDevice, InputEvent, ecodes
except ImportError:
    evdev = None
    InputDevice = None
    ecodes = None

log = logging.getLogger(__name__)


class DeviceStatus(Enum):
    """Device status states"""
    UNKNOWN = "unknown"
    ACTIVE = "active"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    GRABBED = "grabbed"
    RELEASED = "released"


@dataclass
class DeviceInfo:
    """Information about a managed device"""
    path: str
    name: str
    device: Optional[InputDevice] = None
    status: DeviceStatus = DeviceStatus.UNKNOWN
    capabilities: Set[int] = field(default_factory=set)
    last_seen: float = field(default_factory=time.time)
    grab_count: int = 0
    error_count: int = 0
    last_error: Optional[Exception] = None


class ProductionDeviceManager:
    """Production-ready device manager with hot-plug support"""
    
    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger(__name__)
        self.devices: Dict[str, DeviceInfo] = {}
        self.device_watchers: List[Callable] = []
        self.hotplug_enabled = True
        self.health_check_interval = 5.0  # seconds
        self.device_timeout = 30.0  # seconds before device considered disconnected
        
        # Threading
        self.hotplug_thread: Optional[threading.Thread] = None
        self.health_thread: Optional[threading.Thread] = None
        self.shutdown_event = threading.Event()
        
        # Metrics
        self.metrics = {
            'devices_found': 0,
            'devices_connected': 0,
            'devices_failed': 0,
            'hotplug_events': 0,
            'grab_failures': 0,
        }
        
        # Check if evdev is available
        if evdev is None:
            self.logger.error("evdev module not available - device management disabled")
            self.hotplug_enabled = False
    
    def enumerate_devices(self) -> bool:
        """
        Scan for and enumerate available devices
        
        Returns:
            True if enumeration successful
        """
        if evdev is None:
            self.logger.error("Cannot enumerate devices - evdev not available")
            return False
        
        try:
            self.logger.info("Enumerating input devices...")
            device_paths = evdev.list_devices()
            found_devices = 0
            
            for path in device_paths:
                if self._try_register_device(path):
                    found_devices += 1
            
            self.metrics['devices_found'] = found_devices
            self.logger.info(f"✓ Found {found_devices} input devices")
            return found_devices > 0
            
        except Exception as e:
            self.logger.error(f"Device enumeration failed: {e}")
            return False
    
    def grab_all_devices(self) -> int:
        """
        Attempt to grab all registered devices
        
        Returns:
            Number of successfully grabbed devices
        """
        grabbed_count = 0
        
        for device_info in self.devices.values():
            if self._try_grab_device(device_info):
                grabbed_count += 1
        
        self.logger.info(f"✓ Grabbed {grabbed_count} devices")
        return grabbed_count
    
    def release_all_devices(self) -> int:
        """
        Release all grabbed devices
        
        Returns:
            Number of successfully released devices
        """
        released_count = 0
        
        for device_info in self.devices.values():
            if self._try_release_device(device_info):
                released_count += 1
        
        self.logger.info(f"✓ Released {released_count} devices")
        return released_count
    
    def start_hotplug_monitoring(self) -> bool:
        """
        Start monitoring for device hot-plug events
        
        Returns:
            True if monitoring started successfully
        """
        if not self.hotplug_enabled or evdev is None:
            self.logger.warning("Hot-plug monitoring not available")
            return False
        
        if self.hotplug_thread and self.hotplug_thread.is_alive():
            self.logger.warning("Hot-plug monitoring already running")
            return True
        
        try:
            self.shutdown_event.clear()
            self.hotplug_thread = threading.Thread(
                target=self._monitor_hotplug, 
                daemon=True,
                name="DeviceHotPlugMonitor"
            )
            self.hotplug_thread.start()
            
            self.logger.info("✓ Started hot-plug monitoring")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start hot-plug monitoring: {e}")
            return False
    
    def start_health_monitoring(self) -> bool:
        """
        Start device health monitoring
        
        Returns:
            True if monitoring started successfully
        """
        if self.health_thread and self.health_thread.is_alive():
            self.logger.warning("Health monitoring already running")
            return True
        
        try:
            self.shutdown_event.clear()
            self.health_thread = threading.Thread(
                target=self._monitor_device_health,
                daemon=True,
                name="DeviceHealthMonitor"
            )
            self.health_thread.start()
            
            self.logger.info("✓ Started device health monitoring")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start health monitoring: {e}")
            return False
    
    def stop_monitoring(self):
        """Stop all monitoring threads"""
        self.logger.info("Stopping device monitoring...")
        
        # Signal threads to stop
        self.shutdown_event.set()
        
        # Wait for threads to finish
        if self.hotplug_thread and self.hotplug_thread.is_alive():
            self.hotplug_thread.join(timeout=2.0)
            if self.hotplug_thread.is_alive():
                self.logger.warning("Hot-plug thread did not stop cleanly")
        
        if self.health_thread and self.health_thread.is_alive():
            self.health_thread.join(timeout=2.0)
            if self.health_thread.is_alive():
                self.logger.warning("Health monitoring thread did not stop cleanly")
        
        self.logger.info("✓ Device monitoring stopped")
    
    def register_device_watcher(self, callback: Callable):
        """Register a callback for device events"""
        self.device_watchers.append(callback)
    
    def get_device_info(self, path: str) -> Optional[DeviceInfo]:
        """Get information about a specific device"""
        return self.devices.get(path)
    
    def get_all_devices(self) -> Dict[str, DeviceInfo]:
        """Get all registered devices"""
        return dict(self.devices)
    
    def get_active_devices(self) -> List[DeviceInfo]:
        """Get list of active devices"""
        return [info for info in self.devices.values() 
                if info.status in [DeviceStatus.ACTIVE, DeviceStatus.GRABBED]]
    
    def get_metrics(self) -> Dict[str, any]:
        """Get device management metrics"""
        active_count = sum(1 for info in self.devices.values() 
                         if info.status in [DeviceStatus.ACTIVE, DeviceStatus.GRABBED])
        error_count = sum(1 for info in self.devices.values() 
                        if info.status == DeviceStatus.ERROR)
        
        return {
            **self.metrics,
            'total_devices': len(self.devices),
            'active_devices': active_count,
            'error_devices': error_count,
            'device_success_rate': (
                (self.metrics['devices_connected'] / max(1, self.metrics['devices_found'])) * 100
            )
        }
    
    def cleanup(self):
        """Cleanup device manager resources"""
        self.logger.info("Cleaning up device manager...")
        
        # Stop monitoring
        self.stop_monitoring()
        
        # Release all devices
        self.release_all_devices()
        
        # Clear device tracking
        self.devices.clear()
        
        self.logger.info("✓ Device manager cleaned up")
    
    def _try_register_device(self, path: str) -> bool:
        """Try to register a single device"""
        try:
            if not os.path.exists(path):
                return False
            
            # Check if already registered
            if path in self.devices:
                return True
            
            # Create device object
            device = InputDevice(path)
            
            # Get device capabilities
            capabilities = set()
            try:
                caps = device.capabilities()
                for ev_type, items in caps.items():
                    capabilities.add(ev_type)
            except Exception as e:
                self.logger.debug(f"Could not get capabilities for {path}: {e}")
            
            # Create device info
            device_info = DeviceInfo(
                path=path,
                name=device.name,
                device=device,
                status=DeviceStatus.ACTIVE,
                capabilities=capabilities
            )
            
            self.devices[path] = device_info
            self.metrics['devices_found'] += 1
            
            self.logger.debug(f"✓ Registered device: {device.name} ({path})")
            
            # Notify watchers
            self._notify_watchers('device_registered', device_info)
            return True
            
        except Exception as e:
            self.logger.debug(f"Failed to register device {path}: {e}")
            return False
    
    def _try_grab_device(self, device_info: DeviceInfo) -> bool:
        """Try to grab a device"""
        if device_info.device is None:
            return False
        
        try:
            device_info.device.grab()
            device_info.status = DeviceStatus.GRABBED
            device_info.grab_count += 1
            
            self.logger.debug(f"✓ Grabbed device: {device_info.name}")
            self._notify_watchers('device_grabbed', device_info)
            return True
            
        except Exception as e:
            device_info.status = DeviceStatus.ERROR
            device_info.last_error = e
            device_info.error_count += 1
            self.metrics['grab_failures'] += 1
            
            self.logger.debug(f"Failed to grab {device_info.name}: {e}")
            self._notify_watchers('device_error', device_info)
            return False
    
    def _try_release_device(self, device_info: DeviceInfo) -> bool:
        """Try to release a device"""
        if device_info.device is None:
            return False
        
        try:
            device_info.device.ungrab()
            device_info.status = DeviceStatus.RELEASED
            
            self.logger.debug(f"✓ Released device: {device_info.name}")
            self._notify_watchers('device_released', device_info)
            return True
            
        except Exception as e:
            device_info.status = DeviceStatus.ERROR
            device_info.last_error = e
            device_info.error_count += 1
            
            self.logger.debug(f"Failed to release {device_info.name}: {e}")
            self._notify_watchers('device_error', device_info)
            return False
    
    def _monitor_hotplug(self):
        """Monitor for device hot-plug events"""
        self.logger.debug("Starting hot-plug monitoring loop")
        
        # Monitor /dev/input directory for changes
        input_dir = Path("/dev/input")
        
        while not self.shutdown_event.is_set():
            try:
                # Get current devices
                current_paths = set(str(p) for p in input_dir.glob("event*"))
                known_paths = set(self.devices.keys())
                
                # Find new devices
                new_paths = current_paths - known_paths
                for path in new_paths:
                    if self._try_register_device(path):
                        self.metrics['hotplug_events'] += 1
                        self.metrics['devices_connected'] += 1
                
                # Find removed devices
                removed_paths = known_paths - current_paths
                for path in removed_paths:
                    if path in self.devices:
                        device_info = self.devices[path]
                        device_info.status = DeviceStatus.DISCONNECTED
                        self._notify_watchers('device_disconnected', device_info)
                
                # Wait for next check
                self.shutdown_event.wait(1.0)
                
            except Exception as e:
                self.logger.error(f"Hot-plug monitoring error: {e}")
                self.shutdown_event.wait(1.0)
        
        self.logger.debug("Hot-plug monitoring loop ended")
    
    def _monitor_device_health(self):
        """Monitor health of registered devices"""
        self.logger.debug("Starting device health monitoring loop")
        
        while not self.shutdown_event.is_set():
            try:
                current_time = time.time()
                
                for device_info in self.devices.values():
                    # Check if device has timed out
                    if (current_time - device_info.last_seen) > self.device_timeout:
                        if device_info.status != DeviceStatus.DISCONNECTED:
                            device_info.status = DeviceStatus.DISCONNECTED
                            self.logger.warning(f"Device timeout: {device_info.name}")
                            self._notify_watchers('device_disconnected', device_info)
                    
                    # Check for too many errors
                    if device_info.error_count > 5:
                        if device_info.status != DeviceStatus.ERROR:
                            device_info.status = DeviceStatus.ERROR
                            self.logger.warning(f"Device error threshold: {device_info.name}")
                            self._notify_watchers('device_error', device_info)
                
                # Wait for next health check
                self.shutdown_event.wait(self.health_check_interval)
                
            except Exception as e:
                self.logger.error(f"Health monitoring error: {e}")
                self.shutdown_event.wait(self.health_check_interval)
        
        self.logger.debug("Device health monitoring loop ended")
    
    def _notify_watchers(self, event_type: str, device_info: DeviceInfo):
        """Notify all registered device watchers"""
        for callback in self.device_watchers:
            try:
                callback(event_type, device_info)
            except Exception as e:
                self.logger.error(f"Device watcher callback error: {e}")