"""
Unit tests for FW16 Synth production modules
"""

import unittest
import time
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

# Add src to path
import sys
from os.path import dirname, join
sys.path.insert(0, join(dirname(dirname(__file__)), 'src'))


class TestProductionErrorHandler(unittest.TestCase):
    """Test ProductionErrorHandler functionality"""

    def test_error_context_creation(self):
        """Test error context dataclass creation"""
        from fw16_synth.production.error_handler import ErrorContext, ErrorSeverity

        context = ErrorContext(
            error=Exception("Test error"),
            context="test_context",
            severity=ErrorSeverity.MEDIUM,
            user_message="Test message",
            solutions=["Solution 1", "Solution 2"],
            details={"key": "value"},
            timestamp=time.time()
        )

        self.assertEqual(context.context, "test_context")
        self.assertEqual(context.severity, ErrorSeverity.MEDIUM)
        self.assertEqual(len(context.solutions), 2)

    def test_error_severity_enum(self):
        """Test ErrorSeverity enum values"""
        from fw16_synth.production.error_handler import ErrorSeverity

        self.assertEqual(ErrorSeverity.LOW.value, "low")
        self.assertEqual(ErrorSeverity.MEDIUM.value, "medium")
        self.assertEqual(ErrorSeverity.HIGH.value, "high")
        self.assertEqual(ErrorSeverity.CRITICAL.value, "critical")


class TestResourceManager(unittest.TestCase):
    """Test ProductionResourceManager functionality"""

    def test_resource_registration(self):
        """Test resource registration"""
        from fw16_synth.production.resource_manager import (
            ProductionResourceManager, ResourceStatus
        )

        manager = ProductionResourceManager()
        test_resource = Mock()

        # Register resource
        success = manager.register_resource(
            "test_resource",
            test_resource,
            lambda: None
        )

        self.assertTrue(success)
        status = manager.get_resource_status("test_resource")
        self.assertIsNotNone(status)
        self.assertEqual(status.status, ResourceStatus.ACTIVE)

    def test_resource_cleanup(self):
        """Test resource cleanup"""
        from fw16_synth.production.resource_manager import (
            ProductionResourceManager, ResourceStatus
        )

        manager = ProductionResourceManager()
        cleanup_called = [False]

        def cleanup_func():
            cleanup_called[0] = True

        # Register and cleanup
        manager.register_resource("test", Mock(), cleanup_func)
        manager.cleanup_resource("test")

        status = manager.get_resource_status("test")
        self.assertEqual(status.status, ResourceStatus.CLEANED)

    def test_lifo_cleanup_order(self):
        """Test LIFO cleanup order"""
        from fw16_synth.production.resource_manager import ProductionResourceManager

        manager = ProductionResourceManager()
        cleanup_order = []

        # Register multiple resources
        for i in range(3):
            def make_cleanup(n):
                def cleanup():
                    cleanup_order.append(n)
                return cleanup
            manager.register_resource(f"res_{i}", Mock(), make_cleanup(i))

        # Cleanup all - should be LIFO order
        manager.cleanup_all()

        self.assertEqual(cleanup_order, [2, 1, 0])


class TestHealthMonitor(unittest.TestCase):
    """Test ProductionHealthMonitor functionality"""

    def test_health_metrics_creation(self):
        """Test HealthMetrics dataclass creation"""
        from fw16_synth.production.health_monitor import HealthMetrics

        metrics = HealthMetrics()

        self.assertEqual(metrics.notes_played, 0)
        self.assertEqual(metrics.errors_count, 0)
        self.assertIsNotNone(metrics.start_time)

    def test_health_status_enum(self):
        """Test HealthStatus enum values"""
        from fw16_synth.production.health_monitor import HealthStatus

        self.assertEqual(HealthStatus.HEALTHY.value, "healthy")
        self.assertEqual(HealthStatus.WARNING.value, "warning")
        self.assertEqual(HealthStatus.CRITICAL.value, "critical")
        self.assertEqual(HealthStatus.UNKNOWN.value, "unknown")

    def test_velocity_recording(self):
        """Test velocity recording with thread safety"""
        from fw16_synth.production.health_monitor import ProductionHealthMonitor

        monitor = ProductionHealthMonitor()

        # Record velocities
        for vel in [60, 80, 100, 120]:
            monitor.record_velocity(vel, "timing")

        health = monitor.get_health_status()
        self.assertGreater(health['metrics']['application']['notes_played'], 0)

    def test_error_recording(self):
        """Test error recording"""
        from fw16_synth.production.health_monitor import ProductionHealthMonitor

        monitor = ProductionHealthMonitor()

        # Record errors
        monitor.record_error("test_error")

        health = monitor.get_health_status()
        self.assertEqual(health['metrics']['application']['errors_count'], 1)


class TestRetryManager(unittest.TestCase):
    """Test ProductionRetryManager functionality"""

    @patch('fw16_synth.production.retry_manager.time.sleep')
    def test_successful_retry(self, mock_sleep):
        """Test successful retry on first attempt"""
        from fw16_synth.production.retry_manager import ProductionRetryManager

        manager = ProductionRetryManager()

        def always_succeed():
            return "success"

        result = manager.execute_with_result(always_succeed, 'test_op')

        self.assertTrue(result.success)
        self.assertEqual(result.result, "success")
        self.assertEqual(result.attempts, 1)

    @patch('fw16_synth.production.retry_manager.time.sleep')
    def test_retry_on_failure(self, mock_sleep):
        """Test retry logic on failure"""
        from fw16_synth.production.retry_manager import ProductionRetryManager

        manager = ProductionRetryManager(max_attempts=3, backoff_factor=1.0)

        call_count = [0]

        def fail_twice_succeed_third():
            call_count[0] += 1
            if call_count[0] < 3:
                raise Exception("Temporary failure")
            return "success"

        result = manager.execute_with_result(fail_twice_succeed_third, 'test_op')

        self.assertTrue(result.success)
        self.assertEqual(result.attempts, 3)
        self.assertEqual(result.result, "success")


class TestGlitchPrevention(unittest.TestCase):
    """Test glitch prevention functionality"""

    def test_rate_limiter(self):
        """Test rate limiting"""
        from fw16_synth.production.glitch_prevention import RateLimiter

        limiter = RateLimiter(max_operations=5, time_window=1.0)

        # Should allow first 5 operations
        for i in range(5):
            self.assertTrue(limiter.can_proceed(f"op_{i}"))

        # Should block 6th operation
        self.assertFalse(limiter.can_proceed("op_6"))

    def test_input_sanitizer_midi_cc(self):
        """Test MIDI CC value sanitization"""
        from fw16_synth.production.glitch_prevention import InputSanitizer

        # Test clamping
        cc_num, cc_val = InputSanitizer.sanitize_midi_cc(200, -5)
        self.assertEqual(cc_num, 127)
        self.assertEqual(cc_val, 0)

    def test_audio_parameter_validation(self):
        """Test audio parameter validation"""
        from fw16_synth.production.glitch_prevention import InputSanitizer

        # Valid parameters
        valid, msg = InputSanitizer.validate_audio_parameters(44100, 512, 2)
        self.assertTrue(valid)

        # Invalid parameters
        valid, msg = InputSanitizer.validate_audio_parameters(-1, 512, 2)
        self.assertFalse(valid)

    def test_touchpad_sanitization(self):
        """Test touchpad coordinate sanitization"""
        from fw16_synth.production.glitch_prevention import InputSanitizer

        # Test clamping
        x, y = InputSanitizer.sanitize_touchpad_coords(1500, 2000, 1000, 1000)
        self.assertEqual(x, 1000.0)
        self.assertEqual(y, 1000.0)


if __name__ == "__main__":
    unittest.main()
