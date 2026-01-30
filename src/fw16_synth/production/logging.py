"""
Production Logging

Enhanced logging with rotation, structured output, and performance tracking.
Provides production-ready logging capabilities.
"""

import logging
import sys
import time
import os
from typing import Optional, Dict, Any, TextIO
from pathlib import Path
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from collections import deque
import threading

from .color import Color


class ProductionFormatter(logging.Formatter):
    """Enhanced formatter with colors and performance tracking"""
    
    def __init__(self, include_colors: bool = True, include_perf: bool = False):
        super().__init__()
        self.include_colors = include_colors and sys.stdout.isatty()
        self.include_perf = include_perf
        self.start_times = {}
    
    def format(self, record):
        # Get basic formatted message
        formatted = super().format(record)
        
        # Add colors for console
        if self.include_colors:
            formatted = self._add_colors(formatted, record.levelno)
        
        # Add performance timing
        if self.include_perf and hasattr(record, 'perf_start'):
            if record.perf_start in self.start_times:
                duration = time.time() - self.start_times[record.perf_start]
                formatted += f" [perf:{duration*1000:.1f}ms]"
                del self.start_times[record.perf_start]
        
        return formatted
    
    def _add_colors(self, message: str, level: int) -> str:
        """Add colors based on log level"""
        colors = {
            logging.DEBUG: Color.GRAY,
            logging.INFO: Color.WHITE,
            logging.WARNING: Color.YELLOW,
            logging.ERROR: Color.RED,
            logging.CRITICAL: Color.RED + Color.BOLD,
        }
        
        color = colors.get(level, Color.WHITE)
        return f"{color}{message}{Color.RESET}"
    
    def start_timer(self, record_name: str):
        """Start performance timer for record"""
        self.start_times[record_name] = time.time()


class ProductionLogger:
    """Production-ready logger with rotation and structured output"""
    
    def __init__(self, name: str, log_file: Optional[Path] = None, 
                 verbose: bool = False, max_file_size: int = 10*1024*1024,  # 10MB
                 backup_count: int = 5):
        self.name = name
        self.verbose = verbose
        self.max_file_size = max_file_size
        self.backup_count = backup_count
        
        # Create logger
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG if verbose else logging.INFO)
        
        # Setup handlers
        self._setup_console_handler()
        if log_file:
            self._setup_file_handler(log_file)
        
        # Performance tracking
        self.performance_metrics = deque(maxlen=1000)
        self.performance_lock = threading.Lock()
    
    def _setup_console_handler(self):
        """Setup console logging handler with colors"""
        handler = logging.StreamHandler(sys.stdout)
        formatter = ProductionFormatter(include_colors=True, include_perf=self.verbose)
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
    
    def _setup_file_handler(self, log_file: Path):
        """Setup file logging handler with rotation"""
        try:
            # Ensure log directory exists
            log_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Use rotating file handler
            handler = RotatingFileHandler(
                log_file,
                maxBytes=self.max_file_size,
                backupCount=self.backup_count,
                encoding='utf-8'
            )
            
            # File formatter (no colors)
            formatter = ProductionFormatter(include_colors=False, include_perf=True)
            handler.setFormatter(formatter)
            
            self.logger.addHandler(handler)
            
        except Exception as e:
            self.logger.warning(f"Failed to setup file logging: {e}")
    
    def debug(self, message: str, perf_id: Optional[str] = None, **kwargs):
        """Log debug message with optional performance tracking"""
        if perf_id:
            self._start_perf(perf_id)
        self.logger.debug(message, extra={'perf_start': perf_id} if perf_id else None, **kwargs)
    
    def info(self, message: str, perf_id: Optional[str] = None, **kwargs):
        """Log info message with optional performance tracking"""
        if perf_id:
            self._start_perf(perf_id)
        self.logger.info(message, extra={'perf_start': perf_id} if perf_id else None, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message"""
        self.logger.warning(message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """Log error message"""
        self.logger.error(message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        """Log critical message"""
        self.logger.critical(message, **kwargs)
    
    def exception(self, message: str, exc_info=True, **kwargs):
        """Log exception with traceback"""
        self.logger.exception(message, exc_info=exc_info, **kwargs)
    
    def log_metrics(self, category: str, value: float, unit: str = ""):
        """Log performance metrics"""
        with self.performance_lock:
            self.performance_metrics.append({
                'timestamp': time.time(),
                'category': category,
                'value': value,
                'unit': unit
            })
            
            # Keep only recent metrics
            if len(self.performance_metrics) > 1000:
                self.performance_metrics.popleft()
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance metrics summary"""
        if not self.performance_metrics:
            return {}
        
        # Group by category
        categories = {}
        for metric in self.performance_metrics:
            cat = metric['category']
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(metric['value'])
        
        # Calculate statistics
        summary = {}
        for cat, values in categories.items():
            if values:
                summary[cat] = {
                    'count': len(values),
                    'average': sum(values) / len(values),
                    'min': min(values),
                    'max': max(values),
                    'unit': next((m['unit'] for m in self.performance_metrics if m['category'] == cat), "")
                }
        
        return summary
    
    def _start_perf(self, perf_id: str):
        """Start performance timer"""
        # This would be used by the formatter
        pass


def setup_production_logging(verbose: bool = False, log_file: Optional[Path] = None) -> logging.Logger:
    """
    Setup production logging system
    
    Args:
        verbose: Enable verbose logging
        log_file: Optional log file path
        
    Returns:
        Configured logger instance
    """
    # Create production logger
    production_logger = ProductionLogger(
        'fw16_synth.production',
        log_file=log_file,
        verbose=verbose,
        max_file_size=50*1024*1024,  # 50MB
        backup_count=10
    )
    
    return production_logger.logger


class StructuredLogger:
    """Structured logger for JSON-formatted output"""
    
    def __init__(self, name: str, output_file: Optional[Path] = None):
        self.logger = logging.getLogger(name)
        self.output_file = output_file
        
        # Setup JSON formatter
        formatter = self._create_json_formatter()
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        # File handler if specified
        if output_file:
            file_handler = logging.FileHandler(output_file)
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
    
    def _create_json_formatter(self):
        """Create JSON formatter for structured logging"""
        import json
        
        def json_formatter(record):
            log_entry = {
                'timestamp': time.time(),
                'level': record.levelname,
                'logger': record.name,
                'message': record.getMessage(),
                'module': record.module,
                'function': record.funcName,
                'line': record.lineno,
            }
            
            if hasattr(record, 'extra') and record.extra:
                log_entry.update(record.extra)
            
            return json.dumps(log_entry)
        
        return json_formatter
    
    def log_structured(self, event_type: str, data: Dict[str, Any]):
        """Log structured event"""
        self.logger.info("", extra={
            'event_type': event_type,
            'structured_data': data
        })