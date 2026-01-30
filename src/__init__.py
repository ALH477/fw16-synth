"""
FW16 Synth v2.1 - Professional FluidSynth Controller for Framework 16
=====================================================================

Transforms the Framework 16 laptop into a performance synthesizer with
production-ready error handling, resource management, and health monitoring.

Main entry point: fw16_synth.py
Production features: production/ module
Configuration: config.py
Terminal UI: tui.py

DeMoD LLC - Design not Marketing
"""

__version__ = "2.1.0"
__author__ = "DeMoD LLC"
__description__ = "Professional FluidSynth Controller for Framework 16"

# Define what's available in the package
__all__ = [
    'FW16Synth',
    'load_config',
    'save_config',
    'create_default_config',
    'TerminalUI',
]

# Import main components
try:
    from .fw16_synth import FW16Synth
except ImportError:
    pass

try:
    from .config import load_config, save_config, create_default_config
except ImportError:
    pass

try:
    from .tui import TerminalUI
except ImportError:
    pass

# Import production components if available
try:
    from .production import ProductionSynthController
    __all__.append('ProductionSynthController')
except ImportError:
    pass

try:
    from .production import ProductionErrorHandler
    __all__.append('ProductionErrorHandler')
except ImportError:
    pass

try:
    from .production import ProductionResourceManager
    __all__.append('ProductionResourceManager')
except ImportError:
    pass

try:
    from .production import ProductionDeviceManager
    __all__.append('ProductionDeviceManager')
except ImportError:
    pass

try:
    from .production import ProductionHealthMonitor
    __all__.append('ProductionHealthMonitor')
except ImportError:
    pass

try:
    from .production import ProductionRetryManager
    __all__.append('ProductionRetryManager')
except ImportError:
    pass

try:
    from .production import ProductionConfigValidator
    __all__.append('ProductionConfigValidator')
except ImportError:
    pass