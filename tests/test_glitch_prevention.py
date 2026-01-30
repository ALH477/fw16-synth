#!/usr/bin/env python3
"""
Test script for glitch prevention functionality

This script demonstrates and tests the glitch prevention features
implemented for the FW16 Synth system.
"""

import logging
import time
import threading
from unittest.mock import Mock, MagicMock
import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

def test_glitch_prevention_module():
    """Test the core glitch prevention module"""
    log.info("Testing glitch prevention module...")
    
    try:
        from fw16_synth.production.glitch_prevention import (
            GlitchDetector, RateLimiter, StateValidator, 
            InputSanitizer, TouchpadProcessor
        )
        
        # Test Rate Limiter
        rate_limiter = RateLimiter(max_operations=5, time_window=1.0)
        
        # Should allow first 5 operations
        for i in range(5):
            assert rate_limiter.can_proceed(f"test_op_{i}"), f"Operation {i} should be allowed"
        
        # Should block 6th operation
        assert not rate_limiter.can_proceed("test_op_6"), "6th operation should be blocked"
        
        log.info("✓ Rate limiter test passed")
        
        # Test Input Sanitizer
        cc_num, cc_val = InputSanitizer.sanitize_midi_cc(200, -5)
        assert cc_num == 127, f"CC number should be clamped to 127, got {cc_num}"
        assert cc_val == 0, f"CC value should be clamped to 0, got {cc_val}"
        
        valid, msg = InputSanitizer.validate_audio_parameters(44100, 512, 2)
        assert valid, f"Valid audio parameters should pass validation: {msg}"
        
        valid, msg = InputSanitizer.validate_audio_parameters(-1, 512, 2)
        assert not valid, f"Invalid sample rate should fail validation"
        
        log.info("✓ Input sanitizer test passed")
        
        # Test Touchpad Processor
        processor = TouchpadProcessor()
        x, y, drift = processor.process_input(100, 150, 1000, 1000)
        assert 0 <= x <= 1000, f"X should be in range: {x}"
        assert 0 <= y <= 1000, f"Y should be in range: {y}"
        
        log.info("✓ Touchpad processor test passed")
        
        # Test Glitch Detector
        detector = GlitchDetector()
        detector.report_glitch(
            detector.GlitchType.AUDIO_DROP_OUT,
            "Test glitch",
            severity='medium'
        )
        
        recent_glitches = detector.get_recent_glitches(60.0)
        assert len(recent_glitches) == 1, "Should have one recent glitch"
        
        health_report = detector.get_health_report()
        assert 'system_health' in health_report, "Health report should contain system health"
        
        log.info("✓ Glitch detector test passed")
        
        log.info("✅ All glitch prevention module tests passed!")
        return True
        
    except Exception as e:
        log.error(f"❌ Glitch prevention module test failed: {e}")
        return False


def test_glitch_integration():
    """Test the glitch integration wrapper"""
    log.info("Testing glitch integration wrapper...")
    
    try:
        from fw16_synth.production.glitch_integration import (
            EnhancedFluidSynthEngine, EnhancedMIDIInput
        )
        
        # Create mock base engine
        mock_engine = Mock()
        mock_engine._initialized = False
        mock_engine.sfid = -1
        mock_engine.config = Mock()
        mock_engine.config.sample_rate = 44100
        mock_engine.config.buffer_size = 512
        mock_engine.initialize = Mock(return_value=True)
        mock_engine.note_on = Mock()
        mock_engine.note_off = Mock()
        mock_engine.pitch_bend = Mock()
        mock_engine.control_change = Mock()
        mock_engine.program_change = Mock()
        mock_engine.all_notes_off = Mock()
        mock_engine.shutdown = Mock()
        
        # Test enhanced engine
        enhanced_engine = EnhancedFluidSynthEngine(mock_engine)
        
        # Test initialization
        result = enhanced_engine.initialize()
        assert result, "Enhanced initialization should succeed"
        assert mock_engine.initialize.called, "Base initialize should be called"
        
        # Test note operations with validation
        enhanced_engine.note_on(128, 200)  # Invalid values
        mock_engine.note_on.assert_called_with(127, 127)  # Should be clamped
        
        enhanced_engine.note_off(-5)  # Invalid value
        mock_engine.note_off.assert_called_with(0)  # Should be clamped
        
        enhanced_engine.pitch_bend(20000)  # Invalid value
        mock_engine.pitch_bend.assert_called_with(16383)  # Should be clamped
        
        enhanced_engine.control_change(128, -10)  # Invalid values
        mock_engine.control_change.assert_called_with(127, 0)  # Should be clamped
        
        log.info("✓ Enhanced engine validation test passed")
        
        # Test health status
        health = enhanced_engine.get_health_status()
        assert 'operations_total' in health, "Health status should include operation count"
        assert 'initialized' in health, "Health status should include initialization state"
        
        log.info("✓ Enhanced engine health status test passed")
        
        # Test enhanced MIDI input
        mock_midi = Mock()
        mock_midi._process_message = Mock()
        
        enhanced_midi = EnhancedMIDIInput(mock_midi)
        
        # Test message processing
        mock_msg = Mock()
        enhanced_midi._process_message_enhanced(mock_msg)
        mock_midi._process_message.assert_called_with(mock_msg)
        
        midi_health = enhanced_midi.get_health_status()
        assert 'messages_processed' in midi_health, "MIDI health should include message count"
        
        log.info("✓ Enhanced MIDI input test passed")
        
        log.info("✅ All glitch integration tests passed!")
        return True
        
    except Exception as e:
        log.error(f"❌ Glitch integration test failed: {e}")
        return False


def test_rate_limiting_stress():
    """Stress test rate limiting functionality"""
    log.info("Running rate limiting stress test...")
    
    try:
        from fw16_synth.production.glitch_prevention import RateLimiter
        
        rate_limiter = RateLimiter(max_operations=100, time_window=0.1)
        
        # Test rapid operations
        allowed_count = 0
        blocked_count = 0
        
        for i in range(200):
            if rate_limiter.can_proceed(f"stress_test_{i}"):
                allowed_count += 1
            else:
                blocked_count += 1
        
        # Should allow approximately 100 operations and block ~100
        assert 90 <= allowed_count <= 110, f"Should allow ~100 operations, got {allowed_count}"
        assert 90 <= blocked_count <= 110, f"Should block ~100 operations, got {blocked_count}"
        
        log.info(f"✓ Rate limiting stress test passed: {allowed_count} allowed, {blocked_count} blocked")
        return True
        
    except Exception as e:
        log.error(f"❌ Rate limiting stress test failed: {e}")
        return False


def test_concurrent_access():
    """Test thread safety and concurrent access"""
    log.info("Running concurrent access test...")
    
    try:
        from fw16_synth.production.glitch_integration import EnhancedFluidSynthEngine
        
        # Create mock base engine
        mock_engine = Mock()
        mock_engine._initialized = True
        mock_engine.sfid = 1
        mock_engine.note_on = Mock()
        mock_engine.note_off = Mock()
        
        enhanced_engine = EnhancedFluidSynthEngine(mock_engine)
        
        # Test concurrent access
        def worker_thread(thread_id):
            for i in range(50):
                enhanced_engine.note_on(i % 128, 64)
                enhanced_engine.note_off(i % 128)
                time.sleep(0.001)  # Small delay
        
        threads = []
        for i in range(5):
            thread = threading.Thread(target=worker_thread, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Check that operations were executed
        health = enhanced_engine.get_health_status()
        assert health['operations_total'] > 0, "Should have processed operations"
        
        log.info(f"✓ Concurrent access test passed: {health['operations_total']} operations processed")
        return True
        
    except Exception as e:
        log.error(f"❌ Concurrent access test failed: {e}")
        return False


def main():
    """Run all tests"""
    log.info("🚀 Starting glitch prevention tests...")
    
    tests = [
        test_glitch_prevention_module,
        test_glitch_integration,
        test_rate_limiting_stress,
        test_concurrent_access
    ]
    
    passed = 0
    failed = 0
    
    for test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            log.error(f"Test {test_func.__name__} failed with exception: {e}")
            failed += 1
    
    log.info(f"\n📊 Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        log.info("🎉 All glitch prevention tests passed!")
        return 0
    else:
        log.error("💥 Some tests failed!")
        return 1


if __name__ == "__main__":
    exit(main())