"""
Unit tests for FW16 Synth core functionality

Uses unittest framework for compatibility.
"""

import unittest
import time
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

# Add src to path
import sys
from os.path import dirname, join
sys.path.insert(0, join(dirname(dirname(__file__)), 'src'))

import fw16_synth
SynthConfig = fw16_synth.SynthConfig
AudioDriver = fw16_synth.AudioDriver
ModSource = fw16_synth.ModSource
ModDest = fw16_synth.ModDest
ModulationRouting = fw16_synth.ModulationRouting


class TestSynthConfig(unittest.TestCase):
    """Test SynthConfig dataclass"""

    def test_default_config(self):
        """Test default configuration values"""
        config = SynthConfig()

        self.assertEqual(config.audio_driver, AudioDriver.PIPEWIRE)
        self.assertEqual(config.sample_rate, 48000)
        self.assertEqual(config.buffer_size, 256)
        self.assertEqual(config.midi_channel, 0)
        self.assertEqual(config.base_octave, 4)
        self.assertTrue(config.show_tui)

    def test_modulation_routing_default(self):
        """Test default modulation routing"""
        config = SynthConfig()

        self.assertEqual(len(config.mod_routing), 3)
        self.assertEqual(config.mod_routing[0].source, ModSource.TOUCHPAD_X)
        self.assertEqual(config.mod_routing[0].destination, ModDest.PITCH_BEND)
        self.assertEqual(config.mod_routing[1].destination, ModDest.FILTER_CUTOFF)
        self.assertTrue(config.mod_routing[1].invert)
        self.assertEqual(config.mod_routing[2].destination, ModDest.EXPRESSION)

    def test_velocity_settings(self):
        """Test velocity configuration settings"""
        config = SynthConfig(
            velocity_fixed=100,
            velocity_min=30,
            velocity_max=120
        )

        self.assertEqual(config.velocity_fixed, 100)
        self.assertEqual(config.velocity_min, 30)
        self.assertEqual(config.velocity_max, 120)


class TestModulationRouting(unittest.TestCase):
    """Test modulation routing configuration"""

    def test_modulation_routing(self):
        """Test modulation routing configuration"""
        routing = ModulationRouting(
            source=ModSource.TOUCHPAD_X,
            destination=ModDest.PITCH_BEND,
            amount=1.0,
            invert=False,
            center=0.5
        )

        self.assertEqual(routing.source, ModSource.TOUCHPAD_X)
        self.assertEqual(routing.destination, ModDest.PITCH_BEND)
        self.assertEqual(routing.amount, 1.0)
        self.assertFalse(routing.invert)


class TestAudioDriverEnum(unittest.TestCase):
    """Test AudioDriver enum values"""

    def test_audio_driver_enum(self):
        """Test AudioDriver enum values"""
        self.assertEqual(AudioDriver.PIPEWIRE.value, "pulseaudio")
        self.assertEqual(AudioDriver.PULSEAUDIO.value, "pulseaudio")
        self.assertEqual(AudioDriver.JACK.value, "jack")
        self.assertEqual(AudioDriver.ALSA.value, "alsa")


class TestModSourceEnum(unittest.TestCase):
    """Test ModSource enum"""

    def test_mod_source_enum(self):
        """Test ModSource enum"""
        sources = [ModSource.TOUCHPAD_X, ModSource.TOUCHPAD_Y,
                    ModSource.TOUCHPAD_PRESSURE]
        self.assertEqual(len(sources), 3)


class TestModDestEnum(unittest.TestCase):
    """Test ModDest enum"""

    def test_mod_dest_enum(self):
        """Test ModDest enum"""
        self.assertIn(ModDest.PITCH_BEND, ModDest)
        self.assertIn(ModDest.MOD_WHEEL, ModDest)
        self.assertIn(ModDest.FILTER_CUTOFF, ModDest)


class TestParameterSmoother(unittest.TestCase):
    """Test parameter smoothing for anti-zipper effects"""

    def test_parameter_smoothing(self):
        """Test parameter smoothing calculation"""
        from fw16_synth import ParameterSmoother

        smoother = ParameterSmoother(alpha=0.85)

        # Initial value
        result = smoother.smooth(0.5)
        self.assertAlmostEqual(result, 0.5, places=2)

        # New value should be smoothed toward previous
        result = smoother.smooth(1.0)
        self.assertTrue(result > 0.5 and result < 1.0)

    def test_parameter_range(self):
        """Test parameter stays in valid range"""
        from fw16_synth import ParameterSmoother

        smoother = ParameterSmoother(alpha=0.85)

        # Test boundaries
        result = smoother.smooth(0.0)
        self.assertGreaterEqual(result, 0.0)

        result = smoother.smooth(1.0)
        self.assertLessEqual(result, 1.0)


class TestVelocityTracker(unittest.TestCase):
    """Test velocity tracking system"""

    def test_velocity_from_timing(self):
        """Test velocity calculation from keypress timing"""
        from fw16_synth import VelocityTracker

        tracker = VelocityTracker(
            time_min=0.015,
            time_max=0.200,
            velocity_min=20,
            velocity_max=127
        )

        # Fast keypress should give high velocity
        velocity = tracker.calculate_velocity(0.010)  # Very fast
        self.assertGreaterEqual(velocity, 100)

        # Slow keypress should give low velocity
        velocity = tracker.calculate_velocity(0.250)  # Very slow
        self.assertLessEqual(velocity, 50)

    def test_velocity_clamping(self):
        """Test velocity value clamping"""
        from fw16_synth import VelocityTracker

        tracker = VelocityTracker(
            time_min=0.015,
            time_max=0.200,
            velocity_min=20,
            velocity_max=127
        )

        # Test minimum
        velocity = tracker.calculate_velocity(1.0)  # Extremely slow
        self.assertGreaterEqual(velocity, tracker.velocity_min)

        # Test maximum
        velocity = tracker.calculate_velocity(0.001)  # Extremely fast
        self.assertLessEqual(velocity, tracker.velocity_max)


if __name__ == "__main__":
    unittest.main()
