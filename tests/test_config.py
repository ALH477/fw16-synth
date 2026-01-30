"""
FW16 Synth Configuration Tests
"""

import pytest
import tempfile
from pathlib import Path


def test_config_import():
    """Test that config module can be imported"""
    try:
        from src.config import load_config
        assert True
    except ImportError as e:
        pytest.fail(f"Failed to import config module: {e}")


def test_default_config_creation():
    """Test creating default configuration"""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.yaml"
        
        # Mock the get_config_path function
        import src.config as config_module
        original_get_config_path = config_module.get_config_path
        config_module.get_config_path = lambda: config_path
        
        try:
            config_module.create_default_config()
            assert config_path.exists()
            
            # Test loading the config
            config = config_module.load_config()
            assert config.audio.driver == "pipewire"
            assert config.keyboard.base_octave == 4
            
        finally:
            config_module.get_config_path = original_get_config_path


def test_config_validation():
    """Test configuration validation"""
    from src.config import FullConfig, AudioConfig, KeyboardConfig
    
    # Test default config
    config = FullConfig()
    assert config.audio.driver == "pipewire"
    assert config.keyboard.base_octave == 4
    
    # Test custom config
    custom_config = FullConfig(
        audio=AudioConfig(driver="alsa", sample_rate=44100),
        keyboard=KeyboardConfig(base_octave=5)
    )
    assert custom_config.audio.driver == "alsa"
    assert custom_config.audio.sample_rate == 44100
    assert custom_config.keyboard.base_octave == 5
