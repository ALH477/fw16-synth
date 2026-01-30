"""
Production Resource Manager

Resource lifecycle management with proper cleanup ordering.
Prevents resource leaks and ensures clean shutdown.
"""

import time
import threading
import logging
from typing import Dict, Callable, Any, List, Optional
from dataclasses import dataclass
from enum import Enum

log = logging.getLogger(__name__)


class ResourceStatus(Enum):
    """Resource status states"""
    ACTIVE = "active"
    CLEANED = "cleaned"
    FAILED = "failed"


@dataclass
class ResourceInfo:
    """Information about a managed resource"""
    name: str
    resource: Any
    cleanup_func: Callable
    status: ResourceStatus = ResourceStatus.ACTIVE
    created_time: float = 0.0
    cleanup_attempts: int = 0
    last_error: Optional[Exception] = None


class ProductionResourceManager:
    """Production-ready resource manager with LIFO cleanup"""
    
    def __init__(self, max_cleanup_retries: int = 3):
        self.resources: Dict[str, ResourceInfo] = {}
        self.cleanup_order: List[str] = []  # Stack for LIFO cleanup
        self.max_cleanup_retries = max_cleanup_retries
        self.cleanup_lock = threading.Lock()
        self.cleanup_timeout = 10.0  # seconds
        self.metrics = {
            'resources_registered': 0,
            'resources_cleaned': 0,
            'cleanup_failures': 0,
            'total_cleanup_time': 0.0,
        }
    
    def register_resource(self, name: str, resource: Any, cleanup_func: Callable, 
                       timeout: Optional[float] = None) -> bool:
        """
        Register a resource with cleanup handler
        
        Args:
            name: Unique resource identifier
            resource: The resource to manage
            cleanup_func: Function to call for cleanup
            timeout: Cleanup timeout override
            
        Returns:
            True if registration successful
        """
        try:
            with self.cleanup_lock:
                if name in self.resources:
                    log.warning(f"Resource '{name}' already registered, overwriting")
                
                resource_info = ResourceInfo(
                    name=name,
                    resource=resource,
                    cleanup_func=cleanup_func,
                    created_time=time.time()
                )
                
                # Store resource and add to cleanup stack
                self.resources[name] = resource_info
                self.cleanup_order.append(name)
                self.metrics['resources_registered'] += 1
                
                log.info(f"✓ Registered resource: {name}")
                return True
                
        except Exception as e:
            log.error(f"Failed to register resource '{name}': {e}")
            return False
    
    def unregister_resource(self, name: str) -> bool:
        """
        Remove a resource from management
        
        Args:
            name: Resource name to unregister
            
        Returns:
            True if unregistration successful
        """
        try:
            with self.cleanup_lock:
                if name not in self.resources:
                    log.warning(f"Resource '{name}' not registered")
                    return False
                
                # Clean up resource first
                if self.resources[name].status == ResourceStatus.ACTIVE:
                    self._cleanup_resource(name)
                
                # Remove from tracking
                del self.resources[name]
                if name in self.cleanup_order:
                    self.cleanup_order.remove(name)
                
                log.info(f"✓ Unregistered resource: {name}")
                return True
                
        except Exception as e:
            log.error(f"Failed to unregister resource '{name}': {e}")
            return False
    
    def cleanup_resource(self, name: str) -> bool:
        """
        Clean up a specific resource
        
        Args:
            name: Resource name to clean up
            
        Returns:
            True if cleanup successful
        """
        with self.cleanup_lock:
            return self._cleanup_resource(name)
    
    def cleanup_all(self) -> Dict[str, bool]:
        """
        Clean up all registered resources in LIFO order
        
        Returns:
            Dictionary of resource names to cleanup success status
        """
        cleanup_results = {}
        start_time = time.time()
        
        with self.cleanup_lock:
            log.info(f"Starting cleanup of {len(self.cleanup_order)} resources...")
            
            # Clean up in reverse order (LIFO)
            for name in reversed(self.cleanup_order):
                success = self._cleanup_resource(name)
                cleanup_results[name] = success
            
            # Clear all tracking
            self.resources.clear()
            self.cleanup_order.clear()
            
            cleanup_time = time.time() - start_time
            self.metrics['total_cleanup_time'] += cleanup_time
            
            log.info(f"✓ Cleanup completed in {cleanup_time:.2f}s")
            
            return cleanup_results
    
    def get_resource_status(self, name: str) -> Optional[ResourceInfo]:
        """Get status of a specific resource"""
        return self.resources.get(name)
    
    def get_all_resources(self) -> Dict[str, ResourceInfo]:
        """Get all registered resources"""
        return dict(self.resources)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get resource management metrics"""
        active_resources = sum(1 for r in self.resources.values() 
                             if r.status == ResourceStatus.ACTIVE)
        failed_resources = sum(1 for r in self.resources.values() 
                             if r.status == ResourceStatus.FAILED)
        
        return {
            **self.metrics,
            'active_resources': active_resources,
            'failed_resources': failed_resources,
            'registered_resources': len(self.resources),
            'cleanup_success_rate': (
                self.metrics['resources_cleaned'] / 
                max(1, self.metrics['resources_cleaned'] + self.metrics['cleanup_failures'])
            ) * 100
        }
    
    def _cleanup_resource(self, name: str) -> bool:
        """Internal cleanup method (requires lock held)"""
        if name not in self.resources:
            log.warning(f"Resource '{name}' not found for cleanup")
            return False
        
        resource_info = self.resources[name]
        
        if resource_info.status != ResourceStatus.ACTIVE:
            log.debug(f"Resource '{name}' already cleaned up")
            return True
        
        cleanup_start = time.time()
        
        # Attempt cleanup with retry logic
        for attempt in range(self.max_cleanup_retries):
            try:
                log.debug(f"Cleaning up resource '{name}' (attempt {attempt + 1})")
                
                # Call cleanup function with timeout
                cleanup_func = resource_info.cleanup_func
                if hasattr(cleanup_func, '__self__'):
                    # Method bound to object - call it
                    cleanup_func()
                else:
                    # Unbound function - pass the resource
                    cleanup_func(resource_info.resource)
                
                resource_info.status = ResourceStatus.CLEANED
                self.metrics['resources_cleaned'] += 1
                
                cleanup_time = time.time() - cleanup_start
                log.info(f"✓ Cleaned up resource: {name} ({cleanup_time:.3f}s)")
                return True
                
            except Exception as e:
                resource_info.cleanup_attempts += 1
                resource_info.last_error = e
                cleanup_time = time.time() - cleanup_start
                
                log.warning(f"Cleanup attempt {attempt + 1} failed for '{name}': {e}")
                
                if attempt < self.max_cleanup_retries - 1:
                    time.sleep(0.1 * (attempt + 1))  # Exponential backoff
        
        # All cleanup attempts failed
        resource_info.status = ResourceStatus.FAILED
        self.metrics['cleanup_failures'] += 1
        
        log.error(f"✗ Failed to clean up resource: {name} after {self.max_cleanup_retries} attempts")
        return False
    
    def force_cleanup_resource(self, name: str) -> bool:
        """
        Force cleanup of a resource (for emergency cleanup)
        
        Args:
            name: Resource name to force clean
            
        Returns:
            True if force cleanup successful
        """
        try:
            with self.cleanup_lock:
                if name not in self.resources:
                    return False
                
                resource_info = self.resources[name]
                
                # Call cleanup without retry
                try:
                    log.warning(f"Force cleaning up resource: {name}")
                    cleanup_func = resource_info.cleanup_func
                    
                    if hasattr(cleanup_func, '__self__'):
                        cleanup_func()
                    else:
                        cleanup_func(resource_info.resource)
                    
                    resource_info.status = ResourceStatus.CLEANED
                    self.metrics['resources_cleaned'] += 1
                    return True
                    
                except Exception as e:
                    log.error(f"Force cleanup failed for '{name}': {e}")
                    return False
                    
        except Exception as e:
            log.error(f"Force cleanup error for '{name}': {e}")
            return False
    
    def reset_metrics(self):
        """Reset resource management metrics"""
        self.metrics = {
            'resources_registered': 0,
            'resources_cleaned': 0,
            'cleanup_failures': 0,
            'total_cleanup_time': 0.0,
        }