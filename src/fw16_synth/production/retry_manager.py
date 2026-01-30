"""
Production Retry Manager

Intelligent retry logic with exponential backoff and jitter.
Provides configurable retry policies for transient failures.
"""

import time
import random
import logging
from typing import Callable, Any, Dict, Optional, Type
from dataclasses import dataclass
from enum import Enum

log = logging.getLogger(__name__)


class RetryStrategy(Enum):
    """Retry strategies"""
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    FIXED_DELAY = "fixed_delay"
    IMMEDIATE = "immediate"


@dataclass
class RetryConfig:
    """Configuration for retry behavior"""
    max_attempts: int = 3
    base_delay: float = 0.1
    max_delay: float = 60.0
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
    jitter: bool = True
    multiplier: float = 2.0
    retryable_exceptions: tuple = (Exception,)  # Types of exceptions to retry
    
    def should_retry(self, exception: Exception, attempt: int) -> bool:
        """Check if exception should be retried"""
        return (
            attempt < self.max_attempts and
            isinstance(exception, self.retryable_exceptions)
        )


class RetryResult:
    """Result of a retry operation"""
    
    def __init__(self, success: bool, result: Any = None, error: Exception = None, 
                 attempts: int = 0, total_time: float = 0.0):
        self.success = success
        self.result = result
        self.error = error
        self.attempts = attempts
        self.total_time = total_time
    
    @property
    def failed(self) -> bool:
        """Check if retry operation failed"""
        return not self.success


class ProductionRetryManager:
    """Production-ready retry manager with intelligent backoff"""
    
    def __init__(self, default_configs: Optional[Dict[str, RetryConfig]] = None):
        self.default_configs = default_configs or {}
        self.metrics = {
            'total_retries': 0,
            'successful_retries': 0,
            'failed_retries': 0,
            'total_retry_time': 0.0,
            'exceptions_by_type': {},
        }
        
        # Default retry configurations for common operations
        self._setup_default_configs()
    
    def retry_sync(self, operation: Callable, config_name: str, 
                  *args, **kwargs) -> Any:
        """
        Execute operation with retry logic (synchronous)
        
        Args:
            operation: Function to retry
            config_name: Name of retry configuration to use
            *args: Arguments to pass to operation
            **kwargs: Keyword arguments to pass to operation
            
        Returns:
            Result of operation if successful
            
        Raises:
            Last exception if all retries exhausted
        """
        config = self._get_config(config_name)
        start_time = time.time()
        last_exception = None
        
        for attempt in range(config.max_attempts):
            try:
                result = operation(*args, **kwargs)
                
                # Success - log and return result
                if attempt > 0:
                    retry_time = time.time() - start_time
                    self.metrics['successful_retries'] += 1
                    self.metrics['total_retries'] += attempt
                    self.metrics['total_retry_time'] += retry_time
                    
                    log.info(f"✓ Retry successful for {config_name} (attempt {attempt + 1})")
                
                return result
                
            except Exception as e:
                last_exception = e
                
                # Track exception types
                exc_type = type(e).__name__
                self.metrics['exceptions_by_type'][exc_type] = (
                    self.metrics['exceptions_by_type'].get(exc_type, 0) + 1
                )
                
                # Check if should retry
                if not config.should_retry(e, attempt):
                    break
                
                # Log retry attempt
                if attempt < config.max_attempts - 1:
                    delay = self._calculate_delay(config, attempt)
                    log.debug(f"Retry attempt {attempt + 1} failed for {config_name}: {e}")
                    log.debug(f"Waiting {delay:.2f}s before retry...")
                    time.sleep(delay)
                else:
                    log.warning(f"All retry attempts failed for {config_name}: {e}")
        
        # All retries failed
        retry_time = time.time() - start_time
        self.metrics['failed_retries'] += 1
        self.metrics['total_retries'] += config.max_attempts
        self.metrics['total_retry_time'] += retry_time
        
        log.error(f"Retry failed for {config_name} after {config.max_attempts} attempts")
        raise last_exception
    
    def retry_async(self, operation: Callable, config_name: str, 
                   *args, **kwargs):
        """
        Execute operation with retry logic (async wrapper)
        
        Args:
            operation: Async function to retry
            config_name: Name of retry configuration to use
            *args: Arguments to pass to operation
            **kwargs: Keyword arguments to pass to operation
            
        Returns:
            Async function that will retry on failure
        """
        import asyncio
        
        config = self._get_config(config_name)
        
        async def retry_wrapper():
            start_time = time.time()
            last_exception = None
            
            for attempt in range(config.max_attempts):
                try:
                    result = await operation(*args, **kwargs)
                    
                    # Success - log and return result
                    if attempt > 0:
                        retry_time = time.time() - start_time
                        self.metrics['successful_retries'] += 1
                        self.metrics['total_retries'] += attempt
                        self.metrics['total_retry_time'] += retry_time
                        
                        log.info(f"✓ Async retry successful for {config_name} (attempt {attempt + 1})")
                    
                    return result
                    
                except Exception as e:
                    last_exception = e
                    
                    # Track exception types
                    exc_type = type(e).__name__
                    self.metrics['exceptions_by_type'][exc_type] = (
                        self.metrics['exceptions_by_type'].get(exc_type, 0) + 1
                    )
                    
                    # Check if should retry
                    if not config.should_retry(e, attempt):
                        break
                    
                    # Log retry attempt
                    if attempt < config.max_attempts - 1:
                        delay = self._calculate_delay(config, attempt)
                        log.debug(f"Async retry attempt {attempt + 1} failed for {config_name}: {e}")
                        log.debug(f"Waiting {delay:.2f}s before retry...")
                        await asyncio.sleep(delay)
                    else:
                        log.warning(f"All async retry attempts failed for {config_name}: {e}")
            
            # All retries failed
            retry_time = time.time() - start_time
            self.metrics['failed_retries'] += 1
            self.metrics['total_retries'] += config.max_attempts
            self.metrics['total_retry_time'] += retry_time
            
            log.error(f"Async retry failed for {config_name} after {config.max_attempts} attempts")
            raise last_exception
        
        return retry_wrapper
    
    def execute_with_result(self, operation: Callable, config_name: str, 
                         *args, **kwargs) -> RetryResult:
        """
        Execute operation and return detailed result object
        
        Args:
            operation: Function to execute
            config_name: Name of retry configuration to use
            *args: Arguments to pass to operation
            **kwargs: Keyword arguments to pass to operation
            
        Returns:
            RetryResult with detailed information
        """
        config = self._get_config(config_name)
        start_time = time.time()
        last_exception = None
        
        for attempt in range(config.max_attempts):
            try:
                result = operation(*args, **kwargs)
                
                total_time = time.time() - start_time
                
                if attempt > 0:
                    self.metrics['successful_retries'] += 1
                    self.metrics['total_retries'] += attempt
                    self.metrics['total_retry_time'] += total_time
                
                return RetryResult(
                    success=True,
                    result=result,
                    attempts=attempt + 1,
                    total_time=total_time
                )
                
            except Exception as e:
                last_exception = e
                
                # Track exception types
                exc_type = type(e).__name__
                self.metrics['exceptions_by_type'][exc_type] = (
                    self.metrics['exceptions_by_type'].get(exc_type, 0) + 1
                )
                
                # Check if should retry
                if not config.should_retry(e, attempt):
                    break
                
                # Calculate delay and wait
                if attempt < config.max_attempts - 1:
                    delay = self._calculate_delay(config, attempt)
                    time.sleep(delay)
        
        # All retries failed
        total_time = time.time() - start_time
        self.metrics['failed_retries'] += 1
        self.metrics['total_retries'] += config.max_attempts
        self.metrics['total_retry_time'] += total_time
        
        return RetryResult(
            success=False,
            error=last_exception,
            attempts=config.max_attempts,
            total_time=total_time
        )
    
    def register_config(self, name: str, config: RetryConfig):
        """
        Register a custom retry configuration
        
        Args:
            name: Configuration name
            config: Retry configuration
        """
        self.default_configs[name] = config
        log.debug(f"Registered retry config: {name}")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get retry metrics"""
        total_attempts = (self.metrics['successful_retries'] + 
                         self.metrics['failed_retries'])
        
        return {
            **self.metrics,
            'total_attempts': total_attempts,
            'success_rate': (
                (self.metrics['successful_retries'] / max(1, total_attempts)) * 100
            ),
            'average_retry_time': (
                self.metrics['total_retry_time'] / max(1, total_attempts)
            )
        }
    
    def reset_metrics(self):
        """Reset retry metrics"""
        self.metrics = {
            'total_retries': 0,
            'successful_retries': 0,
            'failed_retries': 0,
            'total_retry_time': 0.0,
            'exceptions_by_type': {},
        }
    
    def _get_config(self, name: str) -> RetryConfig:
        """Get retry configuration by name"""
        if name in self.default_configs:
            return self.default_configs[name]
        
        # Return default config if not found
        log.warning(f"Retry config '{name}' not found, using default")
        return RetryConfig()
    
    def _calculate_delay(self, config: RetryConfig, attempt: int) -> float:
        """Calculate delay between retry attempts"""
        if config.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay = config.base_delay * (config.multiplier ** attempt)
        elif config.strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = config.base_delay * (attempt + 1)
        elif config.strategy == RetryStrategy.FIXED_DELAY:
            delay = config.base_delay
        else:  # IMMEDIATE
            delay = 0.0
        
        # Apply maximum delay limit
        delay = min(delay, config.max_delay)
        
        # Add jitter if enabled
        if config.jitter and delay > 0:
            jitter_range = delay * 0.1
            delay += random.uniform(-jitter_range, jitter_range)
        
        return max(0.0, delay)
    
    def _setup_default_configs(self):
        """Setup default retry configurations"""
        self.default_configs.update({
            'device_grab': RetryConfig(
                max_attempts=5,
                base_delay=0.1,
                max_delay=2.0,
                strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
                retryable_exceptions=(OSError, PermissionError)
            ),
            
            'soundfont_load': RetryConfig(
                max_attempts=3,
                base_delay=0.5,
                max_delay=5.0,
                strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
                retryable_exceptions=(IOError, OSError)
            ),
            
            'fluidsynth_init': RetryConfig(
                max_attempts=3,
                base_delay=1.0,
                max_delay=10.0,
                strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
                retryable_exceptions=(ConnectionError, OSError)
            ),
            
            'audio_output': RetryConfig(
                max_attempts=5,
                base_delay=0.2,
                max_delay=3.0,
                strategy=RetryStrategy.LINEAR_BACKOFF,
                retryable_exceptions=(IOError, OSError)
            ),
            
            'midi_connection': RetryConfig(
                max_attempts=3,
                base_delay=0.3,
                max_delay=2.0,
                strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
                retryable_exceptions=(ConnectionError, OSError)
            ),
            
            'file_operations': RetryConfig(
                max_attempts=3,
                base_delay=0.1,
                max_delay=1.0,
                strategy=RetryStrategy.FIXED_DELAY,
                retryable_exceptions=(IOError, OSError)
            ),
        })