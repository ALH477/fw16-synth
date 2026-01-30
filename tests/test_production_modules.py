"""
Production Module Tests
=======================
Comprehensive tests for production-grade components including
error handling, resource management, device management, and health monitoring.
"""

import tempfile
from unittest.mock import Mock, patch

# Test the production modules


def test_production_error_handler():
    """Test production error handling with severity levels and recovery"""
    from src.production.error_handler import ProductionErrorHandler, ErrorSeverity
    
    handler = ProductionErrorHandler()
    
    # Test error handling with different severities
    test_error = ValueError("Test error")
    
    # Low severity should not trigger critical actions
    handler.handle_error(test_error, 'test_operation', ErrorSeverity.LOW)
    stats = handler.get_error_statistics()
    assert stats['total_errors'] == 1
    assert stats['low_severity'] == 1
    
    # High severity should be tracked
    handler.handle_error(test_error, 'test_operation', ErrorSeverity.HIGH)
    stats = handler.get_error_statistics()
    assert stats['high_severity'] == 1
    
    # Critical severity should be tracked
    handler.handle_error(test_error, 'test_operation', ErrorSeverity.CRITICAL)
    stats = handler.get_error_statistics()
    assert stats['critical_errors'] == 1


def test_production_resource_manager():
    """Test resource lifecycle management and cleanup"""
    from src.production.resource_manager import ProductionResourceManager
    
    manager = ProductionResourceManager()
    
    # Test resource registration
    mock_resource = Mock()
    cleanup_func = Mock()
    
    manager.register_resource('test_resource', mock_resource, cleanup_func)
    
    # Test cleanup
    results = manager.cleanup_all()
    assert 'test_resource' in results
    assert results['test_resource'] is True
    cleanup_func.assert_called_once()


def test_production_device_manager():
    """Test device management with hot-plug support"""
    from src.production.device_manager import ProductionDeviceManager
    
    log = Mock()
    manager = ProductionDeviceManager(log)
    
    # Test device enumeration
    with patch('evdev.list_devices') as mock_list:
        mock_list.return_value = ['/dev/input/event0', '/dev/input/event1']
        
        with patch('evdev.InputDevice') as mock_device:
            mock_dev = Mock()
            mock_dev.name = "Test Keyboard"
            mock_dev.capabilities.return_value = {
                1: [(1, {})]  # EV_KEY with KEY_A
            }
            mock_device.return_value = mock_dev
            
            result = manager.enumerate_devices()
            assert result is True
            assert len(manager.get_active_devices()) > 0


def test_production_health_monitor():
    """Test health monitoring and performance metrics"""
    from src.production.health_monitor import ProductionHealthMonitor
    
    log = Mock()
    monitor = ProductionHealthMonitor(log)
    
    # Start monitoring
    assert monitor.start_monitoring() is True
    
    # Test metric recording
    monitor.record_note_on()
    monitor.record_velocity(80, 'timing')
    monitor.record_latency(5.0)
    
    # Get health status
    status = monitor.get_health_status()
    assert 'status' in status
    assert 'uptime' in status
    assert 'metrics' in status
    
    # Stop monitoring
    monitor.stop_monitoring()


def test_production_retry_manager():
    """Test intelligent retry logic with exponential backoff"""
    from src.production.retry_manager import ProductionRetryManager
    
    manager = ProductionRetryManager()
    
    # Test successful operation
    def success_func():
        return "success"
    
    result = manager.execute_with_result(success_func, 'test_op')
    assert result.failed is False
    assert result.result == "success"
    
    # Test retry logic
    call_count = 0
    def flaky_func():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise Exception("Temporary failure")
        return "eventual_success"
    
    result = manager.execute_with_result(flaky_func, 'flaky_op')
    assert result.failed is False
    assert result.result == "eventual_success"
    assert call_count == 3


def test_production_config_validator():
    """Test configuration validation with detailed error reporting"""
    from src.production.config_validator import ProductionConfigValidator
    
    validator = ProductionConfigValidator()
    
    # Test valid config
    valid_config = Mock()
    valid_config.audio_driver = "pipewire"
    valid_config.velocity_source = "timing"
    valid_config.base_octave = 4
    
    is_valid, errors = validator.validate_and_report(valid_config)
    assert is_valid is True
    assert len(errors) == 0
    
    # Test invalid config
    invalid_config = Mock()
    invalid_config.audio_driver = "invalid_driver"
    invalid_config.velocity_source = "invalid_source"
    invalid_config.base_octave = 15  # Out of range
    
    is_valid, errors = validator.validate_and_report(invalid_config)
    assert is_valid is False
    assert len(errors) > 0


def test_production_synth_controller():
    """Test production synth controller integration"""
    from src.production.synth_controller import ProductionSynthController
    
    # Mock base synth
    mock_base = Mock()
    mock_base.initialize.return_value = True
    mock_base._devices = []
    
    config = Mock()
    
    controller = ProductionSynthController(mock_base, config)
    
    # Test initialization
    result = controller.initialize()
    assert result is True
    mock_base.initialize.assert_called_once()
    
    # Test health reporting
    health = controller.get_health_report()
    assert 'status' in health
    assert 'uptime' in health
    
    # Test error statistics
    errors = controller.get_error_statistics()
    assert 'total_errors' in errors


def test_production_monitoring_integration():
    """Test integration of monitoring components"""
    from src.production.health_monitor import ProductionHealthMonitor
    from src.production.error_handler import ProductionErrorHandler
    
    log = Mock()
    monitor = ProductionHealthMonitor(log)
    handler = ProductionErrorHandler()
    
    # Simulate normal operation
    monitor.record_note_on()
    monitor.record_velocity(100, 'pressure')
    monitor.record_latency(2.5)
    
    # Simulate some errors
    handler.handle_error(Exception("Test error"), 'test_op', 'medium')
    
    # Get comprehensive metrics
    health = monitor.get_health_status()
    errors = handler.get_error_statistics()
    
    assert health['metrics']['application']['notes_played'] > 0
    assert errors['total_errors'] > 0


def test_production_resource_cleanup():
    """Test comprehensive resource cleanup under failure conditions"""
    from src.production.resource_manager import ProductionResourceManager
    
    manager = ProductionResourceManager()
    
    # Register multiple resources
    resources = []
    for i in range(3):
        mock_resource = Mock()
        cleanup_func = Mock()
        manager.register_resource(f'resource_{i}', mock_resource, cleanup_func)
        resources.append(cleanup_func)
    
    # Simulate partial cleanup failure
    resources[1].side_effect = Exception("Cleanup failed")
    
    results = manager.cleanup_all()
    
    # Should attempt all cleanups even if some fail
    for cleanup_func in resources:
        cleanup_func.assert_called_once()
    
    # Should report which ones failed
    assert results['resource_1'] is False
    assert results['resource_0'] is True
    assert results['resource_2'] is True


def test_production_device_hotplug():
    """Test device hot-plug detection and management"""
    from src.production.device_manager import ProductionDeviceManager
    
    log = Mock()
    manager = ProductionDeviceManager(log)
    
    # Mock device discovery
    with patch.object(manager, '_enumerate_devices') as mock_enum:
        mock_enum.return_value = True
        
        # Start monitoring
        manager.start_hotplug_monitoring()
        
        # Simulate device addition/removal
        manager._handle_device_change('/dev/input/event99', True)
        manager._handle_device_change('/dev/input/event99', False)
        
        # Stop monitoring
        manager.stop_monitoring()


def test_production_error_recovery():
    """Test error recovery strategies and resilience"""
    from src.production.error_handler import ProductionErrorHandler, ErrorSeverity
    
    handler = ProductionErrorHandler()
    
    # Test error context tracking
    context = {
        'operation': 'audio_init',
        'device': '/dev/snd',
        'attempt': 1
    }
    
    handler.handle_error_with_context(
        Exception("Audio device busy"),
        context,
        ErrorSeverity.HIGH
    )
    
    # Test recovery suggestion
    recovery = handler.get_recovery_suggestions('audio_init')
    assert isinstance(recovery, list)


def test_production_performance_monitoring():
    """Test performance monitoring and bottleneck detection"""
    from src.production.health_monitor import ProductionHealthMonitor
    
    log = Mock()
    monitor = ProductionHealthMonitor(log)
    
    # Record performance metrics
    monitor.record_latency(10.0)  # Audio processing
    monitor.record_latency(2.0)   # Input processing
    monitor.record_latency(15.0)  # UI update
    
    # Check for performance issues
    health = monitor.get_health_status()
    metrics = health['metrics']
    
    # Should detect high latency
    assert metrics['performance']['avg_latency'] > 0
    assert metrics['performance']['max_latency'] >= 15.0


class TestProductionIntegration:
    """Integration tests for production system components"""
    
    def setup_method(self):
        """Setup for integration tests"""
        self.temp_dir = tempfile.mkdtemp()
        
    def teardown_method(self):
        """Cleanup after integration tests"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_full_production_workflow(self):
        """Test complete production workflow with error handling"""
        from src.production.synth_controller import ProductionSynthController
        from src.production.error_handler import ProductionErrorHandler
        
        # Mock components
        mock_base = Mock()
        mock_base.initialize.return_value = True
        mock_base._devices = []
        
        config = Mock()
        
        # Create production controller
        controller = ProductionSynthController(mock_base, config)
        
        # Test full workflow
        assert controller.initialize() is True
        
        # Simulate operation
        controller.health_monitor.record_note_on()
        controller.health_monitor.record_velocity(80, 'timing')
        
        # Test error handling during operation
        controller.error_handler.handle_error(
            Exception("Simulated error"),
            'test_operation',
            'medium'
        )
        
        # Get comprehensive reports
        health = controller.get_health_report()
        errors = controller.get_error_statistics()
        resources = controller.get_resource_metrics()
        
        assert health['status'] in ['HEALTHY', 'DEGRADED']
        assert errors['total_errors'] >= 1
        assert 'resources_cleaned' in resources
    
    def test_production_graceful_shutdown(self):
        """Test graceful shutdown under various conditions"""
        from src.production.synth_controller import ProductionSynthController
        
        mock_base = Mock()
        mock_base.initialize.return_value = True
        mock_base._devices = []
        
        config = Mock()
        
        controller = ProductionSynthController(mock_base, config)
        controller.initialize()
        
        # Simulate shutdown
        controller.stop()
        
        # Verify cleanup was called
        assert controller.shutdown_requested is True
        # Health monitoring should be stopped
        assert controller.health_monitor._running is False