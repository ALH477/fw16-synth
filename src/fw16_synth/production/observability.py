"""
Production Observability Module

Enhanced monitoring, logging, and metrics collection for production environments.
Provides structured logging, performance metrics, and health dashboards.
"""

import logging
import time
import threading
import json
import os
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, asdict
from collections import deque, defaultdict
import psutil


@dataclass
class PerformanceMetric:
    """Performance metric with timestamp and context"""
    name: str
    value: float
    unit: str
    timestamp: float
    context: Dict[str, Any] = None


@dataclass
class SystemHealth:
    """System health snapshot"""
    timestamp: float
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    audio_latency_ms: float
    input_latency_ms: float
    ui_latency_ms: float
    active_notes: int
    error_count: int
    uptime_seconds: float


class ProductionLogger:
    """Structured logging for production environments"""
    
    def __init__(self, log_file: Optional[Path] = None, level: str = "INFO"):
        self.logger = logging.getLogger('fw16synth.production')
        self.logger.setLevel(getattr(logging, level.upper()))
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        # File handler (if specified)
        if log_file:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
    
    def log_event(self, event_type: str, message: str, **kwargs):
        """Log structured event"""
        event_data = {
            'event_type': event_type,
            'message': message,
            **kwargs
        }
        self.logger.info(f"EVENT: {json.dumps(event_data)}")
    
    def log_metric(self, metric_name: str, value: float, unit: str = "ms", **context):
        """Log performance metric"""
        metric_data = {
            'metric': metric_name,
            'value': value,
            'unit': unit,
            **context
        }
        self.logger.debug(f"METRIC: {json.dumps(metric_data)}")
    
    def log_error(self, error_type: str, error_message: str, **context):
        """Log error with context"""
        error_data = {
            'error_type': error_type,
            'error_message': error_message,
            **context
        }
        self.logger.error(f"ERROR: {json.dumps(error_data)}")
    
    def log_warning(self, warning_type: str, warning_message: str, **context):
        """Log warning with context"""
        warning_data = {
            'warning_type': warning_type,
            'warning_message': warning_message,
            **context
        }
        self.logger.warning(f"WARNING: {json.dumps(warning_data)}")


class MetricsCollector:
    """Collects and aggregates performance metrics"""
    
    def __init__(self, max_history: int = 1000):
        self.max_history = max_history
        self.metrics: deque = deque(maxlen=max_history)
        self.aggregated: Dict[str, Dict[str, float]] = defaultdict(lambda: {
            'count': 0, 'sum': 0, 'min': float('inf'), 'max': 0, 'avg': 0
        })
        self.lock = threading.Lock()
    
    def record_metric(self, name: str, value: float, unit: str = "ms", **context):
        """Record a performance metric"""
        metric = PerformanceMetric(
            name=name,
            value=value,
            unit=unit,
            timestamp=time.time(),
            context=context
        )
        
        with self.lock:
            self.metrics.append(metric)
            
        # Update aggregated stats
        agg = self.aggregated[name]
        agg['count'] += 1
        agg['sum'] += value
        agg['min'] = min(agg['min'], value)
        agg['max'] = max(agg['max'], value)
        agg['avg'] = agg['sum'] / agg['count']
    
    def get_aggregated_metrics(self) -> Dict[str, Dict[str, float]]:
        """Get aggregated metrics"""
        with self.lock:
            return dict(self.aggregated)
    
    def get_recent_metrics(self, name: Optional[str] = None, minutes: int = 5) -> List[PerformanceMetric]:
        """Get recent metrics within time window"""
        cutoff = time.time() - (minutes * 60)
        
        with self.lock:
            if name:
                return [m for m in self.metrics if m.name == name and m.timestamp >= cutoff]
            else:
                return [m for m in self.metrics if m.timestamp >= cutoff]
    
    def get_health_snapshot(self) -> SystemHealth:
        """Get current system health snapshot"""
        # Get system metrics
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Get application metrics
        audio_latency = self._get_avg_latency('audio_processing')
        input_latency = self._get_avg_latency('input_processing')
        ui_latency = self._get_avg_latency('ui_update')
        
        # Get current state
        active_notes = 0  # Would be injected by synth controller
        error_count = 0   # Would be injected by error handler
        uptime = time.time() - getattr(self, '_start_time', time.time())
        
        return SystemHealth(
            timestamp=time.time(),
            cpu_percent=cpu_percent,
            memory_percent=memory.percent,
            disk_percent=(disk.used / disk.total) * 100,
            audio_latency_ms=audio_latency,
            input_latency_ms=input_latency,
            ui_latency_ms=ui_latency,
            active_notes=active_notes,
            error_count=error_count,
            uptime_seconds=uptime
        )
    
    def _get_avg_latency(self, metric_name: str) -> float:
        """Get average latency for a specific metric"""
        recent = self.get_recent_metrics(metric_name, minutes=1)
        if not recent:
            return 0.0
        return sum(m.value for m in recent) / len(recent)


class HealthDashboard:
    """Real-time health dashboard for production monitoring"""
    
    def __init__(self, metrics_collector: MetricsCollector, logger: ProductionLogger):
        self.metrics_collector = metrics_collector
        self.logger = logger
        self.alert_callbacks: List[Callable] = []
        self._running = False
        self._thread: Optional[threading.Thread] = None
        
        # Alert thresholds
        self.thresholds = {
            'cpu_percent': 80.0,
            'memory_percent': 85.0,
            'disk_percent': 90.0,
            'audio_latency_ms': 20.0,
            'error_rate_per_minute': 10
        }
    
    def add_alert_callback(self, callback: Callable[[str, Dict], None]):
        """Add callback for alert notifications"""
        self.alert_callbacks.append(callback)
    
    def start_monitoring(self):
        """Start background health monitoring"""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self._thread.start()
        self.logger.log_event('health_monitoring', 'Started health monitoring')
    
    def stop_monitoring(self):
        """Stop background health monitoring"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5.0)
        self.logger.log_event('health_monitoring', 'Stopped health monitoring')
    
    def _monitoring_loop(self):
        """Background monitoring loop"""
        while self._running:
            try:
                health = self.metrics_collector.get_health_snapshot()
                self._check_thresholds(health)
                self._log_health_snapshot(health)
                time.sleep(30)  # Check every 30 seconds
            except Exception as e:
                self.logger.log_error('monitoring_error', str(e))
                time.sleep(10)
    
    def _check_thresholds(self, health: SystemHealth):
        """Check health metrics against thresholds and trigger alerts"""
        checks = [
            ('cpu_percent', health.cpu_percent),
            ('memory_percent', health.memory_percent),
            ('disk_percent', health.disk_percent),
            ('audio_latency_ms', health.audio_latency_ms)
        ]
        
        for metric_name, value in checks:
            threshold = self.thresholds.get(metric_name, float('inf'))
            if value > threshold:
                alert_data = {
                    'metric': metric_name,
                    'value': value,
                    'threshold': threshold,
                    'severity': 'HIGH' if value > threshold * 1.2 else 'MEDIUM'
                }
                self._trigger_alert(f'health_threshold_exceeded', alert_data)
    
    def _trigger_alert(self, alert_type: str, data: Dict):
        """Trigger alert to all registered callbacks"""
        for callback in self.alert_callbacks:
            try:
                callback(alert_type, data)
            except Exception as e:
                self.logger.log_error('alert_callback_error', str(e), callback=str(callback))
    
    def _log_health_snapshot(self, health: SystemHealth):
        """Log health snapshot"""
        self.logger.log_metric('system_health', health.cpu_percent, 'percent', 
                              memory_percent=health.memory_percent,
                              disk_percent=health.disk_percent,
                              audio_latency=health.audio_latency_ms,
                              uptime=health.uptime_seconds)


class PerformanceProfiler:
    """Performance profiling and bottleneck detection"""
    
    def __init__(self, metrics_collector: MetricsCollector):
        self.metrics_collector = metrics_collector
        self.profiles: Dict[str, List[float]] = defaultdict(list)
        self.max_profile_samples = 100
    
    def profile_section(self, section_name: str):
        """Context manager for profiling code sections"""
        return ProfileContext(self, section_name)
    
    def record_profile(self, section_name: str, duration_ms: float):
        """Record profiling data"""
        self.profiles[section_name].append(duration_ms)
        
        # Keep only recent samples
        if len(self.profiles[section_name]) > self.max_profile_samples:
            self.profiles[section_name] = self.profiles[section_name][-self.max_profile_samples:]
        
        # Log metric
        self.metrics_collector.record_metric(
            f'profile_{section_name}',
            duration_ms,
            'ms'
        )
    
    def get_bottlenecks(self, threshold_ms: float = 5.0) -> List[Dict]:
        """Get performance bottlenecks"""
        bottlenecks = []
        
        for section, durations in self.profiles.items():
            if not durations:
                continue
            
            avg_duration = sum(durations) / len(durations)
            max_duration = max(durations)
            
            if avg_duration > threshold_ms:
                bottlenecks.append({
                    'section': section,
                    'avg_duration_ms': avg_duration,
                    'max_duration_ms': max_duration,
                    'sample_count': len(durations)
                })
        
        # Sort by average duration
        bottlenecks.sort(key=lambda x: x['avg_duration_ms'], reverse=True)
        return bottlenecks
    
    def get_performance_report(self) -> Dict:
        """Get comprehensive performance report"""
        bottlenecks = self.get_bottlenecks()
        aggregated = self.metrics_collector.get_aggregated_metrics()
        
        return {
            'timestamp': time.time(),
            'bottlenecks': bottlenecks,
            'aggregated_metrics': aggregated,
            'profile_sections': list(self.profiles.keys())
        }


class ProfileContext:
    """Context manager for profiling code sections"""
    
    def __init__(self, profiler: PerformanceProfiler, section_name: str):
        self.profiler = profiler
        self.section_name = section_name
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.perf_counter()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration_ms = (time.perf_counter() - self.start_time) * 1000
            self.profiler.record_profile(self.section_name, duration_ms)


class ProductionObservability:
    """Main observability orchestrator"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.log_file = Path(config.get('log_file', 'fw16-synth-production.log'))
        
        # Initialize components
        self.logger = ProductionLogger(self.log_file, config.get('log_level', 'INFO'))
        self.metrics_collector = MetricsCollector()
        self.health_dashboard = HealthDashboard(self.metrics_collector, self.logger)
        self.profiler = PerformanceProfiler(self.metrics_collector)
        
        # Start monitoring
        self.health_dashboard.start_monitoring()
        
        # Inject start time
        self.metrics_collector._start_time = time.time()
        
        self.logger.log_event('observability_initialized', 'Production observability system started')
    
    def shutdown(self):
        """Shutdown observability system"""
        self.health_dashboard.stop_monitoring()
        self.logger.log_event('observability_shutdown', 'Production observability system stopped')
    
    def get_health_report(self) -> Dict:
        """Get comprehensive health report"""
        health = self.metrics_collector.get_health_snapshot()
        bottlenecks = self.profiler.get_bottlenecks()
        aggregated = self.metrics_collector.get_aggregated_metrics()
        
        return {
            'health_snapshot': asdict(health),
            'bottlenecks': bottlenecks,
            'aggregated_metrics': aggregated,
            'recent_errors': self._get_recent_errors(),
            'system_info': self._get_system_info()
        }
    
    def _get_recent_errors(self) -> List[Dict]:
        """Get recent error events (last hour)"""
        # This would integrate with the error handler to get actual errors
        return []
    
    def _get_system_info(self) -> Dict:
        """Get system information"""
        return {
            'platform': os.name,
            'python_version': os.sys.version,
            'psutil_available': True,
            'log_file': str(self.log_file)
        }
    
    def add_alert_callback(self, callback: Callable[[str, Dict], None]):
        """Add alert callback"""
        self.health_dashboard.add_alert_callback(callback)
    
    def profile(self, section_name: str):
        """Get profiler context for a section"""
        return self.profiler.profile_section(section_name)
    
    def record_metric(self, name: str, value: float, unit: str = "ms", **context):
        """Record a metric"""
        self.metrics_collector.record_metric(name, value, unit, **context)
    
    def log_event(self, event_type: str, message: str, **kwargs):
        """Log an event"""
        self.logger.log_event(event_type, message, **kwargs)