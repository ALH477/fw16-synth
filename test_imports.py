#!/usr/bin/env python3

"""Test script to verify the import fixes work correctly"""

import sys
import os

# Add the src directory to Python path to simulate the test environment
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_imports():
    """Test that all the production modules can be imported correctly"""
    print("Testing production module imports...")

    try:
        from production.error_handler import ProductionErrorHandler, ErrorSeverity
        print("✓ Successfully imported ProductionErrorHandler and ErrorSeverity")
    except ImportError as e:
        print(f"✗ Failed to import error_handler: {e}")
        return False

    try:
        from production.resource_manager import ProductionResourceManager
        print("✓ Successfully imported ProductionResourceManager")
    except ImportError as e:
        print(f"✗ Failed to import resource_manager: {e}")
        return False

    try:
        from production.device_manager import ProductionDeviceManager
        print("✓ Successfully imported ProductionDeviceManager")
    except ImportError as e:
        print(f"✗ Failed to import device_manager: {e}")
        return False

    try:
        from production.health_monitor import ProductionHealthMonitor
        print("✓ Successfully imported ProductionHealthMonitor")
    except ImportError as e:
        print(f"✗ Failed to import health_monitor: {e}")
        return False

    try:
        from production.retry_manager import ProductionRetryManager
        print("✓ Successfully imported ProductionRetryManager")
    except ImportError as e:
        print(f"✗ Failed to import retry_manager: {e}")
        return False

    try:
        from production.config_validator import ProductionConfigValidator
        print("✓ Successfully imported ProductionConfigValidator")
    except ImportError as e:
        print(f"✗ Failed to import config_validator: {e}")
        return False

    try:
        from production.synth_controller import ProductionSynthController
        print("✓ Successfully imported ProductionSynthController")
    except ImportError as e:
        print(f"✗ Failed to import synth_controller: {e}")
        return False

    print("\n🎉 All imports successful! The fix is working correctly.")
    return True

if __name__ == "__main__":
    success = test_imports()
    sys.exit(0 if success else 1)