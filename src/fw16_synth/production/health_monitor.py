"""
Production Health Monitor

System health monitoring and performance metrics.
Provides real-time health assessment and automated responses.
"""

import time
import psutil
import threading
import statistics
import logging
from typing import Dict, List, Deque, Callable, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
from collections import deque

log = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health status levels"""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass
class HealthMetrics:
    """Health metrics data structure"""
    audio_latency: Deque[float] = field(default_factory=lambda: deque(maxlen=100))
    cpu_usage: Deque[float] = field(default_factory=lambda: deque(maxlen=60))
    memory_usage: Deque[float] = field(default_factory=lambda: deque(maxlen=60))
    error_rate: Deque[float] = field(default_factory=lambda: deque(maxlen=60))
    velocity_distribution: Dict[int, int] = field(default_factory=dict)
    notes_played: int = 0
    errors_count: int = 0
    start_time: float = field(default_factory=time.time)
    lock: threading.Lock = field(default_factory=threading.Lock)


@dataclass
class HealthThresholds:
    """Thresholds for health assessment"""
    max_audio_latency: float = 50.0  # ms
    p95_audio_latency: float = 100.0  # ms
    max_cpu_usage: float = 80.0  # percent
    max_memory_usage: float = 85.0  # percent
    max_error_rate: float = 0.05  # errors per second
    min_uptime: float = 60.0  # seconds before health checks


class ProductionHealthMonitor:
    """Production-ready health monitoring system"""
    
    def __init__(self, logger=None, thresholds: Optional[HealthThresholds] = None):
        self.logger = logger or logging.getLogger(__name__)
        self.thresholds = thresholds or HealthThresholds()
        self.metrics = HealthMetrics()
        
        # Monitoring state
        self.monitoring_active = False
        self.health_check_interval = 1.0  # seconds
        self.performance_check_interval = 5.0  # seconds
        self.shutdown_event = threading.Event()
        
        # Threading
        self.health_thread: Optional[threading.Thread] = None
        self.performance_thread: Optional[threading.Thread] = None
        
        # Health callbacks
        self.health_callbacks: List[Callable] = []
        
        # Alerts
        self.alerts_sent: Dict[str, float] = {}
        self.alert_cooldown = 300.0  # seconds
        
        try:
            self.psutil_available = True
        except ImportError:
            self.psutil_available = False
            self.logger.warning("psutil not available - system monitoring limited")
    
    def start_monitoring(self) -> bool:
        """
        Start health monitoring
        
        Returns:
            True if monitoring started successfully
        """
        if self.monitoring_active:
            self.logger.warning("Health monitoring already active")
            return True
        
        try:
            self.shutdown_event.clear()
            
            # Start health monitoring thread
            self.health_thread = threading.Thread(
                target=self._health_monitoring_loop,
                daemon=True,
                name="HealthMonitor"
            )
            self.health_thread.start()
            
            # Start performance monitoring thread
            self.performance_thread = threading.Thread(
                target=self._performance_monitoring_loop,
                daemon=True,
                name="PerformanceMonitor"
            )
            self.performance_thread.start()
            
            self.monitoring_active = True
            self.logger.info("✓ Health monitoring started")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start health monitoring: {e}")
            return False
    
    def stop_monitoring(self):
        """Stop health monitoring"""
        if not self.monitoring_active:
            return
        
        self.logger.info("Stopping health monitoring...")
        
        # Signal threads to stop
        self.shutdown_event.set()
        
        # Wait for threads to finish
        if self.health_thread and self.health_thread.is_alive():
            self.health_thread.join(timeout=2.0)
        
        if self.performance_thread and self.performance_thread.is_alive():
            self.performance_thread.join(timeout=2.0)
        
        self.monitoring_active = False
        self.logger.info("✓ Health monitoring stopped")
    
    def record_latency(self, latency_ms: float):
        """Record audio latency measurement"""
        self.metrics.audio_latency.append(latency_ms)
    
    def record_error(self, error_context: str):
        """Record an error event"""
        current_time = time.time()
        
        with self.metrics.lock:
            self.metrics.errors_count += 1
            
            # Calculate error rate based on total errors and uptime
            uptime = current_time - self.metrics.start_time
            error_rate = (self.metrics.errors_count / max(uptime, 1.0))
            
            self.metrics.error_rate.append(error_rate)
        
        self.logger.debug(f"Error recorded: {error_context} (rate: {error_rate:.3f}/s)")
    
    def record_velocity(self, velocity: int, source: str):
        """Record velocity measurement"""
        with self.metrics.lock:
            velocity_bucket = (velocity // 10) * 10  # Group by 10s
            self.metrics.velocity_distribution[velocity_bucket] = (
                self.metrics.velocity_distribution.get(velocity_bucket, 0) + 1
            )
            
            self.metrics.notes_played += 1
    
    def record_note_on(self):
        """Record a note-on event"""
        self.metrics.notes_played += 1
    
    def register_health_callback(self, callback: Callable):
        """Register a callback for health events"""
        self.health_callbacks.append(callback)
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get comprehensive health status"""
        current_time = time.time()
        uptime = current_time - self.metrics.start_time
        
        # Calculate metrics
        avg_latency = self._calculate_average(self.metrics.audio_latency)
        p95_latency = self._calculate_percentile(self.metrics.audio_latency, 95)
        avg_cpu = self._calculate_average(self.metrics.cpu_usage)
        avg_memory = self._calculate_average(self.metrics.memory_usage)
        avg_error_rate = self._calculate_average(self.metrics.error_rate)
        
        # Determine overall status
        status = self._calculate_health_status(
            avg_latency, p95_latency, avg_cpu, avg_memory, avg_error_rate, uptime
        )
        
        return {
            'status': status.value,
            'uptime': uptime,
            'metrics': {
                'audio_latency': {
                    'average': avg_latency,
                    'p95': p95_latency,
                    'count': len(self.metrics.audio_latency)
                },
                'system': {
                    'cpu_usage': avg_cpu,
                    'memory_usage': avg_memory
                },
                'application': {
                    'error_rate': avg_error_rate,
                    'notes_played': self.metrics.notes_played,
                    'errors_count': self.metrics.errors_count
                },
                'velocity': {
                    'distribution': dict(self.metrics.velocity_distribution),
                    'most_common': self._get_most_common_velocity()
                }
            }
        }
    
    def get_detailed_report(self) -> str:
        """Get formatted health report"""
        health = self.get_health_status()
        status = health['status']
        uptime = health['uptime']
        
        lines = []
        lines.append("╔" + "═" * 74 + "╗")
        lines.append(f"║  FW16 Synth Health Report - Status: {status.upper():<20} Uptime: {uptime:.0f}s ║")
        lines.append("╠" + "═" * 74 + "╣")
        
        # Audio metrics
        audio = health['metrics']['audio_latency']
        lines.append(f"║  Audio Latency:  Avg:{audio['average']:.1f}ms  P95:{audio['p95']:.1f}ms  Samples:{audio['count']:3d} ║")
        
        # System metrics
        system = health['metrics']['system']
        lines.append(f"║  System:         CPU:{system['cpu_usage']:.1f}%  Memory:{system['memory_usage']:.1f}% ║")
        
        # Application metrics
        app = health['metrics']['application']
        lines.append(f"║  Application:    Notes:{app['notes_played']:5d}  Errors:{app['errors_count']:3d}  Rate:{app['error_rate']:.3f}/s ║")
        
        # Velocity metrics
        velocity = health['metrics']['velocity']
        most_common = velocity['most_common']
        lines.append(f"║  Velocity:       Range:{min(velocity['distribution'].keys() or [0])}-{max(velocity['distribution'].keys() or [127])}  Peak:{most_common} ║")
        
        lines.append("╚" + "═" * 74 + "╝")
        
        return "\n".join(lines)
    
    def reset_metrics(self):
        """Reset all health metrics"""
        self.metrics = HealthMetrics()
        self.alerts_sent.clear()
        self.logger.info("Health metrics reset")
    
    def _health_monitoring_loop(self):
        """Main health monitoring loop"""
        self.logger.debug("Starting health monitoring loop")
        
        while not self.shutdown_event.is_set():
            try:
                # Get current health status
                health = self.get_health_status()
                status = health['status']
                
                # Check for alerts
                self._check_alerts(health)
                
                # Notify callbacks
                for callback in self.health_callbacks:
                    try:
                        callback(health)
                    except Exception as e:
                        self.logger.error(f"Health callback error: {e}")
                
                # Wait for next check
                self.shutdown_event.wait(self.health_check_interval)
                
            except Exception as e:
                self.logger.error(f"Health monitoring error: {e}")
                self.shutdown_event.wait(self.health_check_interval)
        
        self.logger.debug("Health monitoring loop ended")
    
    def _performance_monitoring_loop(self):
        """Performance monitoring loop"""
        self.logger.debug("Starting performance monitoring loop")
        
        while not self.shutdown_event.is_set():
            try:
                if self.psutil_available:
                    # Get CPU usage
                    cpu_percent = psutil.cpu_percent(interval=None)
                    self.metrics.cpu_usage.append(cpu_percent)
                    
                    # Get memory usage
                    memory = psutil.virtual_memory()
                    memory_percent = memory.percent
                    self.metrics.memory_usage.append(memory_percent)
                
                # Wait for next measurement
                self.shutdown_event.wait(self.performance_check_interval)
                
            except Exception as e:
                self.logger.error(f"Performance monitoring error: {e}")
                self.shutdown_event.wait(self.performance_check_interval)
        
        self.logger.debug("Performance monitoring loop ended")
    
    def _calculate_health_status(self, avg_latency: float, p95_latency: float, 
                              avg_cpu: float, avg_memory: float, 
                              avg_error_rate: float, uptime: float) -> HealthStatus:
        """Calculate overall health status"""
        
        # Check critical conditions
        if (avg_latency > self.thresholds.max_audio_latency or 
            p95_latency > self.thresholds.p95_audio_latency or
            avg_cpu > self.thresholds.max_cpu_usage or
            avg_memory > self.thresholds.max_memory_usage or
            avg_error_rate > self.thresholds.max_error_rate):
            return HealthStatus.CRITICAL
        
        # Check warning conditions
        if (avg_latency > self.thresholds.max_audio_latency * 0.7 or
            p95_latency > self.thresholds.p95_audio_latency * 0.7 or
            avg_cpu > self.thresholds.max_cpu_usage * 0.7 or
            avg_memory > self.thresholds.max_memory_usage * 0.7 or
            avg_error_rate > self.thresholds.max_error_rate * 0.7):
            return HealthStatus.WARNING
        
        # Check minimum uptime
        if uptime < self.thresholds.min_uptime:
            return HealthStatus.UNKNOWN
        
        return HealthStatus.HEALTHY
    
    def _check_alerts(self, health: Dict[str, Any]):
        """Check for alert conditions and send notifications"""
        status = health['status']
        current_time = time.time()
        
        # Critical alerts
        if status == HealthStatus.CRITICAL.value:
            alert_key = "critical"
            if self._should_send_alert(alert_key, current_time):
                self._send_alert(alert_key, "CRITICAL", health)
        
        # Warning alerts
        elif status == HealthStatus.WARNING.value:
            alert_key = "warning"
            if self._should_send_alert(alert_key, current_time):
                self._send_alert(alert_key, "WARNING", health)
    
    def _should_send_alert(self, alert_key: str, current_time: float) -> bool:
        """Check if alert should be sent (cooldown logic)"""
        last_sent = self.alerts_sent.get(alert_key, 0)
        return (current_time - last_sent) > self.alert_cooldown
    
    def _send_alert(self, alert_key: str, level: str, health: Dict[str, Any]):
        """Send health alert"""
        self.logger.warning(f"🚨 HEALTH ALERT [{level}]: {health['status']}")
        
        # Log specific issues
        metrics = health['metrics']
        
        if metrics['audio_latency']['average'] > self.thresholds.max_audio_latency:
            self.logger.warning(f"High audio latency: {metrics['audio_latency']['average']:.1f}ms")
        
        if metrics['system']['cpu_usage'] > self.thresholds.max_cpu_usage:
            self.logger.warning(f"High CPU usage: {metrics['system']['cpu_usage']:.1f}%")
        
        if metrics['system']['memory_usage'] > self.thresholds.max_memory_usage:
            self.logger.warning(f"High memory usage: {metrics['system']['memory_usage']:.1f}%")
        
        if metrics['application']['error_rate'] > self.thresholds.max_error_rate:
            self.logger.warning(f"High error rate: {metrics['application']['error_rate']:.3f}/s")
        
        # Record alert time
        self.alerts_sent[alert_key] = time.time()
    
    def _calculate_average(self, values: Deque[float]) -> float:
        """Calculate average of values"""
        return statistics.mean(values) if values else 0.0
    
    def _calculate_percentile(self, values: Deque[float], percentile: int) -> float:
        """Calculate percentile of values"""
        if not values:
            return 0.0
        
        sorted_values = sorted(values)
        index = int((percentile / 100) * len(sorted_values))
        index = min(index, len(sorted_values) - 1)
        return sorted_values[index]
    
    def _get_most_common_velocity(self) -> int:
        """Get most commonly used velocity range"""
        if not self.metrics.velocity_distribution:
            return 0
        
        return max(self.metrics.velocity_distribution.items(), key=lambda x: x[1])[0]