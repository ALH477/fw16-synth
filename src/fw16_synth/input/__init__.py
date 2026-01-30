"""
Input Module

Provides keyboard and touchpad input handling for FW16 Synth.
"""

from .keyboard_input import (
    KeyboardMapper,
    ParameterSmoother,
    VelocityTracker,
    KeyboardInputHandler,
)
from .touchpad_input import (
    TouchpadState,
    TouchpadController,
)

__all__ = [
    'KeyboardMapper',
    'ParameterSmoother',
    'VelocityTracker',
    'KeyboardInputHandler',
    'TouchpadState',
    'TouchpadController',
]
