"""
Touchpad Input Module

Handles touchpad state, calibration, and modulation signal processing.
"""

import logging
from dataclasses import dataclass
from typing import Optional

try:
    import evdev
    from evdev import ecodes, InputDevice
except ImportError:
    evdev = None
    ecodes = None
    InputDevice = None

from ..fw16_synth import SynthConfig, ParameterSmoother

log = logging.getLogger(__name__)


@dataclass
class TouchpadState:
    """Touchpad state and calibration data"""
    x: float = 0.5
    y: float = 0.5
    pressure: float = 0.0
    touching: bool = False
    x_min: int = 0
    x_max: int = 1
    y_min: int = 0
    y_max: int = 1
    pressure_min: int = 0
    pressure_max: int = 1


class TouchpadController:
    """Touchpad controller with calibration and event handling"""

    def __init__(self, config: SynthConfig, smoother: ParameterSmoother):
        self.config = config
        self.smoother = smoother
        self.state = TouchpadState()

    def calibrate(self, device: Optional[InputDevice] = None):
        """Calibrate touchpad range"""
        if evdev is None or device is None:
            log.warning("evdev not available - using default calibration")
            return

        caps = device.capabilities()
        for item in caps.get(ecodes.EV_ABS, []):
            if not isinstance(item, tuple):
                continue
            code, info = item

            if code in (ecodes.ABS_X, ecodes.ABS_MT_POSITION_X):
                self.state.x_min, self.state.x_max = info.min, info.max
            elif code in (ecodes.ABS_Y, ecodes.ABS_MT_POSITION_Y):
                self.state.y_min, self.state.y_max = info.min, info.max
            elif code in (ecodes.ABS_PRESSURE, ecodes.ABS_MT_PRESSURE):
                self.state.pressure_min, self.state.pressure_max = info.min, info.max

        log.info(f"Touchpad calibrated: X={self.state.x_min}-{self.state.x_max} Y={self.state.y_min}-{self.state.y_max}")

    def handle_event(self, event) -> bool:
        """
        Handle touchpad event

        Returns:
            True if state changed, False otherwise
        """
        if evdev is None:
            return False

        changed = False

        if event.type == ecodes.EV_ABS:
            code, value = event.code, event.value

            if code in (ecodes.ABS_X, ecodes.ABS_MT_POSITION_X):
                self.state.x = self._normalize(value, self.state.x_min, self.state.x_max)
                self.smoother.set_target('touch_x', self.state.x)
                changed = True

            elif code in (ecodes.ABS_Y, ecodes.ABS_MT_POSITION_Y):
                self.state.y = self._normalize(value, self.state.y_min, self.state.y_max)
                self.smoother.set_target('touch_y', self.state.y)
                changed = True

            elif code in (ecodes.ABS_PRESSURE, ecodes.ABS_MT_PRESSURE):
                self.state.pressure = self._normalize(value, self.state.pressure_min, self.state.pressure_max)
                self.smoother.set_target('touch_pressure', self.state.pressure)
                changed = True

        elif event.type == ecodes.EV_KEY and event.code == ecodes.BTN_TOUCH:
            self.state.touching = bool(event.value)
            if not self.state.touching:
                # Reset to center when released
                self.smoother.set_target('touch_x', 0.5)
                self.smoother.set_target('touch_y', 0.5)
                self.smoother.set_target('touch_pressure', 0.0)
                changed = True

        return changed

    def get_smoothed_values(self) -> dict:
        """Get current smoothed values"""
        return {
            'x': self.smoother.get('touch_x', 0.5),
            'y': self.smoother.get('touch_y', 0.5),
            'pressure': self.smoother.get('touch_pressure', 0.0),
        }

    def _normalize(self, value: int, min_val: int, max_val: int) -> float:
        """Normalize raw device value to 0.0-1.0 range"""
        if max_val == min_val:
            return 0.5
        return max(0.0, min(1.0, (value - min_val) / (max_val - min_val)))

    def reset(self):
        """Reset touchpad state to center"""
        self.state.x = 0.5
        self.state.y = 0.5
        self.state.pressure = 0.0
        self.state.touching = False
        self.smoother.set_target('touch_x', 0.5)
        self.smoother.set_target('touch_y', 0.5)
        self.smoother.set_target('touch_pressure', 0.0)
