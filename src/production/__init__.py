"""
FW16 Synth Production Module

Production-ready enhancements for the FW16 Synth including:
- Centralized error handling with recovery strategies
- Resource lifecycle management with proper cleanup
- Device management with hot-plug support
- Health monitoring and performance metrics
- Intelligent retry logic with exponential backoff

This module transforms the functional prototype into a production-grade
application while preserving all existing functionality including the
excellent velocity system.
"""

# Import production components
try:
    from .error_handler import ProductionErrorHandler
    from .resource_manager import ProductionResourceManager
    from .device_manager import ProductionDeviceManager
    from .retry_manager import ProductionRetryManager
    from .health_monitor import ProductionHealthMonitor
    from .synth_controller import ProductionSynthController
    from .config_validator import ProductionConfigValidator
    
    __all__ = [
        'ProductionErrorHandler',
        'ProductionResourceManager', 
        'ProductionDeviceManager',
        'ProductionRetryManager',
        'ProductionHealthMonitor',
        'ProductionSynthController',
        'ProductionConfigValidator',
    ]
    
except ImportError as e:
    import logging
    logging.getLogger(__name__).warning(
        f"Failed to import production components: {e}"
    )
    
    __all__ = []