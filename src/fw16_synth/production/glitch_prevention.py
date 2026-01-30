"""
Glitch Prevention Module for FW16 Synth

This module provides comprehensive glitch prevention and detection mechanisms
to ensure stable audio operation and prevent audio artifacts, crashes, and
unexpected behavior.

Key Features:
- State validation and protection
- Operation rate limiting
- Input sanitization and validation
- Resource monitoring and cleanup
- Error recovery mechanisms
- Performance monitoring
"""

import asyncio
import time
import threading
import logging
import queue
from collections import deque, defaultdict
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Callable, Any, Tuple
import numpy as np
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


class GlitchType(Enum):
    """Types of glitches that can be detected and prevented"""
    AUDIO_ENGINE_CRASH = auto()
    DEVICE_HOTPLUG = auto()
    MIDI_BUFFER_OVERFLOW = auto()
    TOUCHPAD_CALIBRATION_DRIFT = auto()
    RESOURCE_LEAK = auto()
    STATE_CORRUPTION = auto()
    TIMING_JITTER = auto()
    AUDIO_DROP_OUT = auto()


@dataclass
class GlitchEvent:
    """Represents a detected glitch event"""
    glitch_type: GlitchType
    timestamp: float
    severity: str  # 'low', 'medium', 'high', 'critical'
    message: str
    context: Dict[str, Any] = field(default_factory=dict)
    recovery_action: Optional[str] = None


@dataclass
class OperationMetrics:
    """Tracks operation metrics for rate limiting and monitoring"""
    operation_count: int = 0
    last_operation_time: float = 0.0
    operation_times: deque = field(default_factory=lambda: deque(maxlen=100))
    error_count: int = 0
    consecutive_errors: int = 0


class RateLimiter:
    """Rate limiter for device operations to prevent spam and glitches"""
    
    def __init__(self, max_operations: int = 10, time_window: float = 1.0):
        self.max_operations = max_operations
        self.time_window = time_window
        self.operations = deque()
        self.lock = threading.Lock()
    
    def can_proceed(self, operation_name: str = "operation") -> bool:
        """Check if operation can proceed without exceeding rate limit"""
        with self.lock:
            current_time = time.time()
            
            # Clean old operations
            while self.operations and self.operations[0] < current_time - self.time_window:
                self.operations.popleft()
            
            if len(self.operations) >= self.max_operations:
                logger.warning(f"Rate limit exceeded for {operation_name}")
                return False
            
            self.operations.append(current_time)
            return True
    
    def wait_if_needed(self, operation_name: str = "operation") -> float:
        """Wait if rate limit would be exceeded, returns wait time"""
        with self.lock:
            if self.can_proceed(operation_name):
                return 0.0
            
            # Calculate wait time
            oldest_operation = self.operations[0] if self.operations else time.time()
            wait_time = (oldest_operation + self.time_window) - time.time()
            return max(0.0, wait_time)


class StateValidator:
    """Validates system state to prevent corruption and glitches"""
    
    def __init__(self):
        self.expected_states = {}
        self.state_history = deque(maxlen=100)
    
    def set_expected_state(self, component: str, state: Dict[str, Any]):
        """Set the expected state for a component"""
        self.expected_states[component] = state
    
    def validate_state(self, component: str, current_state: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate current state against expected state"""
        if component not in self.expected_states:
            return True, []
        
        expected = self.expected_states[component]
        issues = []
        
        # Check for required keys
        for key, expected_value in expected.items():
            if key not in current_state:
                issues.append(f"Missing required key: {key}")
                continue
            
            # Type checking
            if type(expected_value) != type and not isinstance(current_state[key], type(expected_value)):
                issues.append(f"Type mismatch for {key}: expected {type(expected_value)}, got {type(current_state[key])}")
        
        # Record state for history
        self.state_history.append((time.time(), component, current_state.copy()))
        
        return len(issues) == 0, issues


class InputSanitizer:
    """Sanitizes and validates input data to prevent glitches"""
    
    @staticmethod
    def sanitize_midi_cc(cc_number: int, cc_value: int) -> Tuple[int, int]:
        """Sanitize MIDI CC values"""
        # Clamp CC number to valid range
        cc_number = max(0, min(127, cc_number))
        
        # Clamp CC value to valid range
        cc_value = max(0, min(127, cc_value))
        
        return cc_number, cc_value
    
    @staticmethod
    def sanitize_touchpad_coords(x: float, y: float, width: int, height: int) -> Tuple[float, float]:
        """Sanitize touchpad coordinates"""
        # Clamp to valid ranges
        x = max(0.0, min(float(width), x))
        y = max(0.0, min(float(height), y))
        
        return x, y
    
    @staticmethod
    def validate_audio_parameters(sample_rate: int, buffer_size: int, channels: int) -> Tuple[bool, str]:
        """Validate audio parameters"""
        if sample_rate <= 0 or sample_rate > 192000:
            return False, f"Invalid sample rate: {sample_rate}"
        
        if buffer_size <= 0 or buffer_size > 8192:
            return False, f"Invalid buffer size: {buffer_size}"
        
        if channels <= 0 or channels > 32:
            return False, f"Invalid channel count: {channels}"
        
        return True, "Valid"


class ResourceMonitor:
    """Monitors system resources to detect leaks and issues"""
    
    def __init__(self):
        self.resource_counters = defaultdict(int)
        self.allocation_history = deque(maxlen=1000)
        self.lock = threading.Lock()
    
    def allocate_resource(self, resource_type: str, resource_id: str):
        """Track resource allocation"""
        with self.lock:
            self.resource_counters[resource_type] += 1
            self.allocation_history.append((time.time(), 'allocate', resource_type, resource_id))
    
    def deallocate_resource(self, resource_type: str, resource_id: str):
        """Track resource deallocation"""
        with self.lock:
            if self.resource_counters[resource_type] > 0:
                self.resource_counters[resource_type] -= 1
            self.allocation_history.append((time.time(), 'deallocate', resource_type, resource_id))
    
    def check_for_leaks(self) -> List[Dict[str, Any]]:
        """Check for potential resource leaks"""
        with self.lock:
            leaks = []
            current_time = time.time()
            
            # Check for resources allocated but not deallocated
            for resource_type, count in self.resource_counters.items():
                if count > 0:
                    # Look at recent allocations for this type
                    recent_allocations = [
                        (t, op, rt, rid) for t, op, rt, rid in self.allocation_history
                        if rt == resource_type and op == 'allocate' and current_time - t < 300  # 5 minutes
                    ]
                    
                    if len(recent_allocations) > count * 2:  # Many more allocations than current count
                        leaks.append({
                            'type': resource_type,
                            'leaked_count': count,
                            'recent_allocations': len(recent_allocations),
                            'severity': 'high' if count > 10 else 'medium'
                        })
            
            return leaks


class TouchpadProcessor:
    """Processes touchpad input with smoothing and drift detection"""
    
    def __init__(self, smoothing_factor: float = 0.3, drift_threshold: float = 0.1):
        self.smoothing_factor = smoothing_factor
        self.drift_threshold = drift_threshold
        self.last_x = 0.0
        self.last_y = 0.0
        self.calibration_center_x = 0.0
        self.calibration_center_y = 0.0
        self.movement_history = deque(maxlen=50)
        
    def process_input(self, x: float, y: float, width: int, height: int) -> Tuple[float, float, bool]:
        """Process touchpad input with smoothing and drift detection"""
        # Sanitize input
        x, y = InputSanitizer.sanitize_touchpad_coords(x, y, width, height)
        
        # Apply smoothing (exponential moving average)
        smoothed_x = self.smoothing_factor * x + (1 - self.smoothing_factor) * self.last_x
        smoothed_y = self.smoothing_factor * y + (1 - self.smoothing_factor) * self.last_y
        
        # Update last values
        self.last_x = smoothed_x
        self.last_y = smoothed_y
        
        # Calculate movement magnitude
        movement = np.sqrt((smoothed_x - self.calibration_center_x)**2 + 
                          (smoothed_y - self.calibration_center_y)**2)
        
        # Detect drift
        drift_detected = movement < self.drift_threshold * min(width, height)
        
        # Record movement
        self.movement_history.append((time.time(), smoothed_x, smoothed_y, movement))
        
        return smoothed_x, smoothed_y, drift_detected
    
    def recalibrate(self, x: float, y: float):
        """Recalibrate touchpad center"""
        self.calibration_center_x = x
        self.calibration_center_y = y
        logger.info(f"Touchpad recalibrated to center: ({x}, {y})")


class GlitchDetector:
    """Main glitch detection and prevention system"""
    
    def __init__(self):
        self.rate_limiters = defaultdict(RateLimiter)
        self.state_validator = StateValidator()
        self.resource_monitor = ResourceMonitor()
        self.touchpad_processor = TouchpadProcessor()
        self.metrics = defaultdict(OperationMetrics)
        self.glitch_events = deque(maxlen=1000)
        self.recovery_callbacks = {}
        self.lock = threading.Lock()
        
        # Configure rate limiters
        self.rate_limiters['device_operation'] = RateLimiter(max_operations=5, time_window=1.0)
        self.rate_limiters['midi_event'] = RateLimiter(max_operations=100, time_window=0.1)
        self.rate_limiters['audio_parameter_change'] = RateLimiter(max_operations=10, time_window=1.0)
    
    def register_recovery_callback(self, glitch_type: GlitchType, callback: Callable):
        """Register a recovery callback for a specific glitch type"""
        self.recovery_callbacks[glitch_type] = callback
    
    def detect_and_prevent_glitch(self, operation: str, context: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Main method to detect and prevent glitches"""
        with self.lock:
            # Rate limiting check
            if operation in self.rate_limiters:
                if not self.rate_limiters[operation].can_proceed(operation):
                    wait_time = self.rate_limiters[operation].wait_if_needed(operation)
                    if wait_time > 0:
                        glitch_event = GlitchEvent(
                            glitch_type=GlitchType.TIMING_JITTER,
                            timestamp=time.time(),
                            severity='medium',
                            message=f"Rate limit exceeded for {operation}",
                            context=context,
                            recovery_action=f"Waiting {wait_time:.3f}s"
                        )
                        self.glitch_events.append(glitch_event)
                        return False, f"Rate limited (wait {wait_time:.3f}s)"
            
            # Update metrics
            metrics = self.metrics[operation]
            metrics.operation_count += 1
            metrics.last_operation_time = time.time()
            metrics.operation_times.append(time.time())
            
            return True, None
    
    def report_glitch(self, glitch_type: GlitchType, message: str, 
                     severity: str = 'medium', context: Dict[str, Any] = None):
        """Report a detected glitch"""
        with self.lock:
            glitch_event = GlitchEvent(
                glitch_type=glitch_type,
                timestamp=time.time(),
                severity=severity,
                message=message,
                context=context or {},
                recovery_action=None
            )
            self.glitch_events.append(glitch_event)
            
            # Log based on severity
            log_method = {
                'low': logger.debug,
                'medium': logger.info,
                'high': logger.warning,
                'critical': logger.error
            }.get(severity, logger.info)
            
            log_method(f"GLITCH DETECTED [{severity.upper()}]: {message}")
            
            # Attempt recovery if callback is registered
            if glitch_type in self.recovery_callbacks:
                try:
                    recovery_action = self.recovery_callbacks[glitch_type](context or {})
                    glitch_event.recovery_action = recovery_action
                    logger.info(f"Recovery action taken: {recovery_action}")
                except Exception as e:
                    logger.error(f"Recovery callback failed: {e}")
    
    def get_recent_glitches(self, time_window: float = 60.0) -> List[GlitchEvent]:
        """Get recent glitches within time window"""
        current_time = time.time()
        return [
            event for event in self.glitch_events
            if current_time - event.timestamp <= time_window
        ]
    
    def get_health_report(self) -> Dict[str, Any]:
        """Get overall system health report"""
        current_time = time.time()
        recent_glitches = self.get_recent_glitches(60.0)
        resource_leaks = self.resource_monitor.check_for_leaks()
        
        return {
            'timestamp': current_time,
            'recent_glitch_count': len(recent_glitches),
            'glitch_rate': len(recent_glitches) / 60.0,
            'severity_breakdown': {
                severity: len([g for g in recent_glitches if g.severity == severity])
                for severity in ['low', 'medium', 'high', 'critical']
            },
            'resource_leaks': resource_leaks,
            'operation_metrics': {
                op: {
                    'count': metrics.operation_count,
                    'avg_interval': np.mean(list(metrics.operation_times)) if len(metrics.operation_times) > 1 else 0,
                    'error_rate': metrics.error_count / max(1, metrics.operation_count)
                }
                for op, metrics in self.metrics.items()
            },
            'system_health': 'healthy' if len(recent_glitches) < 5 and not resource_leaks else 'degraded'
        }


# Global glitch detector instance
_glitch_detector = None

def get_glitch_detector() -> GlitchDetector:
    """Get the global glitch detector instance"""
    global _glitch_detector
    if _glitch_detector is None:
        _glitch_detector = GlitchDetector()
    return _glitch_detector


@asynccontextmanager
async def glitch_protection(operation: str, context: Dict[str, Any] = None):
    """Context manager for glitch protection"""
    detector = get_glitch_detector()
    context = context or {}
    
    # Check for potential glitches
    can_proceed, reason = detector.detect_and_prevent_glitch(operation, context)
    
    if not can_proceed:
        detector.report_glitch(
            glitch_type=GlitchType.TIMING_JITTER,
            message=f"Operation {operation} blocked: {reason}",
            severity='medium',
            context=context
        )
        raise RuntimeError(f"Operation blocked by glitch protection: {reason}")
    
    try:
        yield detector
    except Exception as e:
        detector.metrics[operation].error_count += 1
        detector.metrics[operation].consecutive_errors += 1
        
        detector.report_glitch(
            glitch_type=GlitchType.STATE_CORRUPTION,
            message=f"Operation {operation} failed: {str(e)}",
            severity='high',
            context={**context, 'error': str(e)}
        )
        raise
    else:
        detector.metrics[operation].consecutive_errors = 0


# Decorator for automatic glitch protection
def protect_from_glitches(operation: str = None, context: Dict[str, Any] = None):
    """Decorator to protect functions from glitches"""
    def decorator(func):
        operation_name = operation or f"{func.__module__}.{func.__name__}"
        
        async def async_wrapper(*args, **kwargs):
            async with glitch_protection(operation_name, context):
                return await func(*args, **kwargs)
        
        def sync_wrapper(*args, **kwargs):
            detector = get_glitch_detector()
            func_context = {**context} if context else {}
            func_context.update({
                'args': str(args)[:100],  # Limit size
                'kwargs': str(kwargs)[:100]
            })
            
            can_proceed, reason = detector.detect_and_prevent_glitch(operation_name, func_context)
            if not can_proceed:
                detector.report_glitch(
                    glitch_type=GlitchType.TIMING_JITTER,
                    message=f"Function {operation_name} blocked: {reason}",
                    severity='medium',
                    context=func_context
                )
                raise RuntimeError(f"Function blocked by glitch protection: {reason}")
            
            try:
                return func(*args, **kwargs)
            except Exception as e:
                detector.metrics[operation_name].error_count += 1
                detector.metrics[operation_name].consecutive_errors += 1
                
                detector.report_glitch(
                    glitch_type=GlitchType.STATE_CORRUPTION,
                    message=f"Function {operation_name} failed: {str(e)}",
                    severity='high',
                    context={**func_context, 'error': str(e)}
                )
                raise
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator