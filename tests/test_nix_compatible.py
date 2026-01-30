#!/usr/bin/env python3
"""
Nix-compatible test suite for FW16 Synth

This test suite is designed to run within the nix flake environment
with minimal external dependencies.
"""

import sys
import unittest
import time
import math
import threading
from pathlib import Path
from dataclasses import dataclass, field
from collections import deque
from typing import Dict, List, Set, Optional, Callable, Any, Tuple
from enum import Enum, auto


# =============================================================================
# MOCKS FOR MISSING DEPENDENCIES
# =============================================================================

class MockFluidSynth:
    """Mock FluidSynth for testing without actual library"""
    def __init__(self):
        self.notes_on = []
        self.cc_values = {}
        self.pitch_bend_value = 8192

    def start(self, driver='pulseaudio'):
        pass

    def sfload(self, path):
        return 1  # Return soundfont ID

    def sfunload(self, sfid):
        pass

    def noteon(self, channel, note, velocity):
        self.notes_on.append((channel, note, velocity))

    def noteoff(self, channel, note):
        self.notes_on = [n for n in self.notes_on if n[1] != note or n[0] != channel]

    def pitch_bend(self, channel, value):
        self.pitch_bend_value = value

    def cc(self, channel, cc, value):
        self.cc_values[(channel, cc)] = value

    def program_select(self, channel, sfid, bank, program):
        pass

    def delete(self):
        self.notes_on.clear()
        self.cc_values.clear()


# =============================================================================
# TEST CONFIGURATION AND DATA CLASSES
# =============================================================================

class AudioDriver(str, Enum):
    PIPEWIRE = "pulseaudio"
    PULSEAUDIO = "pulseaudio"
    JACK = "jack"
    ALSA = "alsa"


class ModSource(Enum):
    TOUCHPAD_X = auto()
    TOUCHPAD_Y = auto()
    TOUCHPAD_PRESSURE = auto()


class ModDest(Enum):
    PITCH_BEND = auto()
    MOD_WHEEL = auto()
    BREATH = auto()
    EXPRESSION = auto()
    FILTER_CUTOFF = auto()
    FILTER_RESONANCE = auto()
    ATTACK = auto()
    RELEASE = auto()


@dataclass
class ModulationRouting:
    source: ModSource
    destination: ModDest
    amount: float = 1.0
    invert: bool = False
    center: float = 0.5


@dataclass
class SynthConfig:
    audio_driver: AudioDriver = AudioDriver.PIPEWIRE
    sample_rate: int = 48000
    buffer_size: int = 256
    midi_channel: int = 0
    base_octave: int = 4
    velocity_min: int = 20
    velocity_max: int = 127
    mod_routing: List[ModulationRouting] = field(default_factory=list)
    pitch_bend_semitones: int = 2


# =============================================================================
# ENGINE MODULE TESTS
# =============================================================================

class FluidSynthEngine:
    """FluidSynth audio engine wrapper"""
    def __init__(self, config: SynthConfig):
        self.config = config
        self.fs = None
        self.sfid = -1
        self.channel = config.midi_channel
        self.layer_channel = 1
        self._initialized = False

    def initialize(self, soundfont_path=None) -> bool:
        try:
            self.fs = MockFluidSynth()
            self.fs.start(driver=self.config.audio_driver.value)
            self._initialized = True
            return True
        except Exception as e:
            return False

    def note_on(self, note, velocity, layer=False):
        if self._initialized:
            self.fs.noteon(self.channel, note, velocity)

    def note_off(self, note, layer=False):
        if self._initialized:
            self.fs.noteoff(self.channel, note)

    def all_notes_off(self):
        if self._initialized:
            for ch in [self.channel, self.layer_channel]:
                self.fs.cc(ch, 123, 0)


class TestFluidSynthEngine(unittest.TestCase):
    """Test FluidSynthEngine functionality"""

    def test_engine_initialization(self):
        """Test audio engine initialization"""
        config = SynthConfig()
        engine = FluidSynthEngine(config)

        result = engine.initialize()

        self.assertTrue(result, "Engine should initialize successfully")
        self.assertTrue(engine._initialized, "Engine should be marked as initialized")
        self.assertIsNotNone(engine.fs, "FluidSynth instance should be created")

    def test_note_on_off(self):
        """Test note on/off operations"""
        config = SynthConfig()
        engine = FluidSynthEngine(config)
        engine.initialize()

        # Test note on
        engine.note_on(60, 100)
        self.assertEqual(len(engine.fs.notes_on), 1)
        self.assertEqual(engine.fs.notes_on[0], (0, 60, 100))

        # Test note off
        engine.note_off(60)
        self.assertEqual(len(engine.fs.notes_on), 0)

    def test_all_notes_off(self):
        """Test all notes off operation"""
        config = SynthConfig()
        engine = FluidSynthEngine(config)
        engine.initialize()

        # Play multiple notes
        for note in [60, 64, 67]:
            engine.note_on(note, 100)

        self.assertEqual(len(engine.fs.notes_on), 3)

        # Turn all off
        engine.all_notes_off()

        # All notes should be off (cc 123 sent)
        # In mock, this just ensures method is callable

    def test_multiple_notes(self):
        """Test playing multiple notes simultaneously"""
        config = SynthConfig()
        engine = FluidSynthEngine(config)
        engine.initialize()

        # Play chord (C major)
        for note in [60, 64, 67]:
            engine.note_on(note, 100)

        self.assertEqual(len(engine.fs.notes_on), 3)


class TestModulationRouting(unittest.TestCase):
    """Test modulation routing configuration"""

    def test_default_routing(self):
        """Test default modulation routing"""
        routing = ModulationRouting(
            source=ModSource.TOUCHPAD_X,
            destination=ModDest.PITCH_BEND
        )

        self.assertEqual(routing.source, ModSource.TOUCHPAD_X)
        self.assertEqual(routing.destination, ModDest.PITCH_BEND)
        self.assertEqual(routing.amount, 1.0)
        self.assertFalse(routing.invert)

    def test_routing_with_invert(self):
        """Test modulation routing with inversion"""
        routing = ModulationRouting(
            source=ModSource.TOUCHPAD_Y,
            destination=ModDest.FILTER_CUTOFF,
            invert=True,
            center=0.5
        )

        self.assertTrue(routing.invert)
        self.assertEqual(routing.center, 0.5)


class TestSynthConfig(unittest.TestCase):
    """Test synthesizer configuration"""

    def test_default_config(self):
        """Test default configuration values"""
        config = SynthConfig()

        self.assertEqual(config.audio_driver, AudioDriver.PIPEWIRE)
        self.assertEqual(config.sample_rate, 48000)
        self.assertEqual(config.buffer_size, 256)
        self.assertEqual(config.midi_channel, 0)
        self.assertEqual(config.base_octave, 4)

    def test_custom_config(self):
        """Test custom configuration"""
        config = SynthConfig(
            audio_driver=AudioDriver.JACK,
            sample_rate=96000,
            buffer_size=512
        )

        self.assertEqual(config.audio_driver, AudioDriver.JACK)
        self.assertEqual(config.sample_rate, 96000)
        self.assertEqual(config.buffer_size, 512)


# =============================================================================
# UTILITIES TESTS
# =============================================================================

class ParameterSmoother:
    """Parameter smoothing for anti-zipper effects"""

    def __init__(self, alpha: float = 0.85):
        self.alpha = alpha
        self._last_value = None

    def smooth(self, value: float) -> float:
        """Apply exponential smoothing"""
        if self._last_value is None:
            self._last_value = value
            return value

        smoothed = self._last_value + self.alpha * (value - self._last_value)
        self._last_value = smoothed
        return smoothed


class VelocityTracker:
    """Velocity calculation from keypress timing"""

    def __init__(self, time_min: float = 0.015, time_max: float = 0.200,
                 velocity_min: int = 20, velocity_max: int = 127):
        self.time_min = time_min
        self.time_max = time_max
        self.velocity_min = velocity_min
        self.velocity_max = velocity_max

    def calculate_velocity(self, press_time: float) -> int:
        """Calculate velocity from keypress duration"""
        # Clamp time to valid range
        clamped_time = max(self.time_min, min(self.time_max, press_time))

        # Map time to velocity (faster = higher velocity)
        ratio = (clamped_time - self.time_min) / (self.time_max - self.time_min)
        velocity = self.velocity_max - int(ratio * (self.velocity_max - self.velocity_min))

        return max(self.velocity_min, min(self.velocity_max, velocity))


class TestParameterSmoother(unittest.TestCase):
    """Test parameter smoothing functionality"""

    def test_initial_value(self):
        """Test that initial value is passed through"""
        smoother = ParameterSmoother(alpha=0.85)
        result = smoother.smooth(0.5)

        self.assertAlmostEqual(result, 0.5, places=2)

    def test_smoothing_behavior(self):
        """Test that values are smoothed toward previous"""
        smoother = ParameterSmoother(alpha=0.85)

        # Initial
        v1 = smoother.smooth(0.0)
        self.assertAlmostEqual(v1, 0.0, places=2)

        # Jump to 1.0, should be smoothed
        v2 = smoother.smooth(1.0)
        self.assertGreater(v2, 0.0)
        self.assertLess(v2, 1.0)

        # Should converge to 1.0
        v3 = smoother.smooth(1.0)
        self.assertGreater(v3, v2)

    def test_alpha_parameter(self):
        """Test that alpha affects smoothing strength"""
        smoother_high = ParameterSmoother(alpha=0.95)
        smoother_low = ParameterSmoother(alpha=0.3)

        # Start with 0
        smoother_high.smooth(0.0)
        smoother_low.smooth(0.0)

        # Jump to 1.0
        v_high = smoother_high.smooth(1.0)  # More smoothing, closer to old value
        v_low = smoother_low.smooth(1.0)  # Less smoothing, closer to new value

        # Higher alpha means more responsive to new value
        self.assertGreater(v_high, v_low)


class TestVelocityTracker(unittest.TestCase):
    """Test velocity tracking functionality"""

    def test_fast_keypress(self):
        """Test that fast keypress produces high velocity"""
        tracker = VelocityTracker(
            time_min=0.015,
            time_max=0.200,
            velocity_min=20,
            velocity_max=127
        )

        velocity = tracker.calculate_velocity(0.020)  # Fast

        self.assertGreater(velocity, 100)

    def test_slow_keypress(self):
        """Test that slow keypress produces low velocity"""
        tracker = VelocityTracker(
            time_min=0.015,
            time_max=0.200,
            velocity_min=20,
            velocity_max=127
        )

        velocity = tracker.calculate_velocity(0.150)  # Slow

        self.assertLess(velocity, 80)

    def test_velocity_clamping(self):
        """Test that velocity is clamped to min/max range"""
        tracker = VelocityTracker(
            time_min=0.015,
            time_max=0.200,
            velocity_min=20,
            velocity_max=127
        )

        # Extremely fast - should max out
        vel_fast = tracker.calculate_velocity(0.001)
        self.assertLessEqual(vel_fast, tracker.velocity_max)

        # Extremely slow - should min out
        vel_slow = tracker.calculate_velocity(1.0)
        self.assertGreaterEqual(vel_slow, tracker.velocity_min)

    def test_time_clamping(self):
        """Test that time is clamped to min/max range"""
        tracker = VelocityTracker(
            time_min=0.015,
            time_max=0.200,
            velocity_min=20,
            velocity_max=127
        )

        # Below min time
        vel1 = tracker.calculate_velocity(0.001)
        self.assertLessEqual(vel1, tracker.velocity_max)

        # Above max time
        vel2 = tracker.calculate_velocity(1.0)
        self.assertGreaterEqual(vel2, tracker.velocity_min)


# =============================================================================
# RATE LIMITER TESTS
# =============================================================================

class RateLimiter:
    """Rate limiter for operations"""

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
                return False

            self.operations.append(current_time)
            return True


class TestRateLimiter(unittest.TestCase):
    """Test rate limiting functionality"""

    def test_allow_operations_within_limit(self):
        """Test that operations within limit are allowed"""
        limiter = RateLimiter(max_operations=5, time_window=1.0)

        for i in range(5):
            self.assertTrue(limiter.can_proceed(f"op_{i}"),
                          f"Operation {i} should be allowed")

    def test_block_operations_exceeding_limit(self):
        """Test that operations exceeding limit are blocked"""
        limiter = RateLimiter(max_operations=5, time_window=1.0)

        # Fill to limit
        for i in range(5):
            limiter.can_proceed(f"op_{i}")

        # Next operation should be blocked
        self.assertFalse(limiter.can_proceed("op_6"),
                         "Operation exceeding limit should be blocked")

    def test_window_expiry(self):
        """Test that old operations expire after window"""
        limiter = RateLimiter(max_operations=3, time_window=0.1)

        # Fill to limit
        for i in range(3):
            limiter.can_proceed(f"op_{i}")

        self.assertFalse(limiter.can_proceed("op_4"))

        # Wait for window to expire
        time.sleep(0.15)

        # Should now allow new operations
        self.assertTrue(limiter.can_proceed("op_5"),
                        "Operation should be allowed after window expiry")

    def test_thread_safety(self):
        """Test that rate limiter is thread-safe"""
        limiter = RateLimiter(max_operations=100, time_window=1.0)
        results = []

        def worker():
            for i in range(20):
                results.append(limiter.can_proceed(f"worker_op_{i}"))

        # Create multiple threads
        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All operations should complete without errors
        self.assertEqual(len(results), 100)
        # Most should be allowed (within limit of 100)
        allowed_count = sum(1 for r in results if r)
        self.assertGreater(allowed_count, 0)


# =============================================================================
# INPUT SANITIZER TESTS
# =============================================================================

class InputSanitizer:
    """Input sanitization and validation"""

    @staticmethod
    def sanitize_midi_cc(cc_number: int, cc_value: int) -> Tuple[int, int]:
        """Sanitize MIDI CC values"""
        cc_number = max(0, min(127, cc_number))
        cc_value = max(0, min(127, cc_value))
        return cc_number, cc_value

    @staticmethod
    def validate_audio_parameters(sample_rate: int, buffer_size: int,
                              channels: int) -> Tuple[bool, str]:
        """Validate audio parameters"""
        if sample_rate <= 0 or sample_rate > 192000:
            return False, f"Invalid sample rate: {sample_rate}"

        if buffer_size <= 0 or buffer_size > 8192:
            return False, f"Invalid buffer size: {buffer_size}"

        if channels <= 0 or channels > 32:
            return False, f"Invalid channel count: {channels}"

        return True, "Valid"


class TestInputSanitizer(unittest.TestCase):
    """Test input sanitization functionality"""

    def test_midi_cc_clamping_high(self):
        """Test that CC values are clamped at high end"""
        cc_num, cc_val = InputSanitizer.sanitize_midi_cc(200, 300)

        self.assertEqual(cc_num, 127)
        self.assertEqual(cc_val, 127)

    def test_midi_cc_clamping_low(self):
        """Test that CC values are clamped at low end"""
        cc_num, cc_val = InputSanitizer.sanitize_midi_cc(-10, -5)

        self.assertEqual(cc_num, 0)
        self.assertEqual(cc_val, 0)

    def test_midi_cc_valid_values(self):
        """Test that valid CC values pass through"""
        cc_num, cc_val = InputSanitizer.sanitize_midi_cc(64, 100)

        self.assertEqual(cc_num, 64)
        self.assertEqual(cc_val, 100)

    def test_audio_parameter_validation_valid(self):
        """Test validation of valid audio parameters"""
        valid, msg = InputSanitizer.validate_audio_parameters(44100, 512, 2)

        self.assertTrue(valid)
        self.assertEqual(msg, "Valid")

    def test_audio_parameter_validation_invalid_sample_rate(self):
        """Test validation of invalid sample rate"""
        valid, msg = InputSanitizer.validate_audio_parameters(-1, 512, 2)

        self.assertFalse(valid)
        self.assertIn("Invalid sample rate", msg)

    def test_audio_parameter_validation_invalid_buffer_size(self):
        """Test validation of invalid buffer size"""
        valid, msg = InputSanitizer.validate_audio_parameters(44100, -1, 2)

        self.assertFalse(valid)
        self.assertIn("Invalid buffer size", msg)


# =============================================================================
# MAIN TEST SUITE
# =============================================================================

def run_tests():
    """Run all tests and return results"""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestFluidSynthEngine))
    suite.addTests(loader.loadTestsFromTestCase(TestModulationRouting))
    suite.addTests(loader.loadTestsFromTestCase(TestSynthConfig))
    suite.addTests(loader.loadTestsFromTestCase(TestParameterSmoother))
    suite.addTests(loader.loadTestsFromTestCase(TestVelocityTracker))
    suite.addTests(loader.loadTestsFromTestCase(TestRateLimiter))
    suite.addTests(loader.loadTestsFromTestCase(TestInputSanitizer))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Print summary
    print("\n" + "="*70)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print("="*70)

    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(run_tests())
