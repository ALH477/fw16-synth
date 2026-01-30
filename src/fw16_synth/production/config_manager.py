"""
Production Configuration Manager

Advanced configuration management with validation, migration, and hot-reloading
for production environments. Provides centralized configuration handling with
comprehensive error reporting and recovery strategies.
"""

import os
import json
import yaml
import logging
import time
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable, Union
from dataclasses import dataclass, asdict, field
from enum import Enum
from threading import Lock
import asyncio
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


class ConfigSource(Enum):
    """Configuration source types"""
    ENVIRONMENT = "environment"
    FILE = "file"
    DEFAULT = "default"
    RUNTIME = "runtime"


@dataclass
class ConfigValidationResult:
    """Result of configuration validation"""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    source: Optional[ConfigSource] = None


@dataclass
class ConfigChange:
    """Configuration change notification"""
    key: str
    old_value: Any
    new_value: Any
    source: ConfigSource
    timestamp: float


class ConfigValidationError(Exception):
    """Configuration validation error"""
    pass


class ConfigMigrationError(Exception):
    """Configuration migration error"""
    pass


class ProductionConfigManager:
    """
    Production-ready configuration manager with:
    - Multi-source configuration (environment, file, defaults)
    - Schema validation with detailed error reporting
    - Configuration migration support
    - Hot-reloading with change notifications
    - Configuration backup and recovery
    - Performance monitoring
    """
    
    def __init__(self, config_dir: Optional[Path] = None, enable_hot_reload: bool = True):
        self.config_dir = config_dir or Path.home() / ".config" / "fw16-synth"
        self.config_file = self.config_dir / "config.yaml"
        self.backup_dir = self.config_dir / "backups"
        
        # Configuration state
        self._config: Dict[str, Any] = {}
        self._defaults: Dict[str, Any] = self._get_default_config()
        self._schema: Dict[str, Dict[str, Any]] = self._get_config_schema()
        self._source_map: Dict[str, ConfigSource] = {}
        self._callbacks: List[Callable[[ConfigChange], None]] = []
        
        # Threading
        self._lock = Lock()
        self._hot_reload_enabled = enable_hot_reload
        self._observer: Optional[Observer] = None
        self._running = False
        
        # Logging
        self.logger = logging.getLogger('fw16synth.production.config')
        
        # Performance tracking
        self._load_times: List[float] = []
        self._validation_times: List[float] = []
        
        # Initialize
        self._setup_directories()
        if self._hot_reload_enabled:
            self._setup_file_watcher()
    
    def _setup_directories(self):
        """Create necessary directories"""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
    
    def _setup_file_watcher(self):
        """Setup file system watcher for hot-reloading"""
        if not self._hot_reload_enabled:
            return
        
        class ConfigFileHandler(FileSystemEventHandler):
            def __init__(self, manager):
                self.manager = manager
            
            def on_modified(self, event):
                if event.src_path == str(self.manager.config_file):
                    self.manager._handle_config_change()
        
        self._observer = Observer()
        handler = ConfigFileHandler(self)
        self._observer.schedule(handler, str(self.config_dir), recursive=False)
        self._observer.start()
        self._running = True
    
    def _handle_config_change(self):
        """Handle configuration file changes"""
        try:
            # Debounce rapid changes
            time.sleep(0.1)
            
            if not self.config_file.exists():
                return
            
            # Load and validate new config
            new_config = self._load_config_file()
            validation = self._validate_config(new_config)
            
            if validation.is_valid:
                old_config = self._config.copy()
                self._config = new_config
                self._notify_changes(old_config, new_config)
                self.logger.info("Configuration reloaded from file")
            else:
                self.logger.error(f"Configuration reload failed: {validation.errors}")
                
        except Exception as e:
            self.logger.error(f"Error handling config change: {e}")
    
    def _notify_changes(self, old_config: Dict, new_config: Dict):
        """Notify callbacks of configuration changes"""
        changes = self._diff_configs(old_config, new_config)
        for change in changes:
            for callback in self._callbacks:
                try:
                    callback(change)
                except Exception as e:
                    self.logger.error(f"Error in config change callback: {e}")
    
    def _diff_configs(self, old: Dict, new: Dict) -> List[ConfigChange]:
        """Calculate differences between old and new configs"""
        changes = []
        
        def _diff_recursive(old_dict, new_dict, prefix=""):
            for key in set(old_dict.keys()) | set(new_dict.keys()):
                old_val = old_dict.get(key)
                new_val = new_dict.get(key)
                full_key = f"{prefix}.{key}" if prefix else key
                
                if old_val != new_val:
                    if isinstance(old_val, dict) and isinstance(new_val, dict):
                        _diff_recursive(old_val, new_val, full_key)
                    else:
                        changes.append(ConfigChange(
                            key=full_key,
                            old_value=old_val,
                            new_value=new_val,
                            source=ConfigSource.FILE,
                            timestamp=time.time()
                        ))
        
        _diff_recursive(old, new)
        return changes
    
    def load_config(self) -> ConfigValidationResult:
        """Load configuration from all sources with validation"""
        start_time = time.perf_counter()
        
        try:
            # Load from file
            file_config = self._load_config_file()
            
            # Load from environment
            env_config = self._load_config_environment()
            
            # Merge configurations (environment overrides file)
            merged = self._merge_configs(self._defaults, file_config, env_config)
            
            # Validate
            validation = self._validate_config(merged)
            
            if validation.is_valid:
                with self._lock:
                    self._config = merged
                    self._update_source_map(file_config, env_config)
                
                # Backup successful config
                self._backup_config()
                
                # Record performance
                load_time = (time.perf_counter() - start_time) * 1000
                self._load_times.append(load_time)
                if len(self._load_times) > 100:
                    self._load_times.pop(0)
                
                self.logger.info(f"Configuration loaded successfully in {load_time:.2f}ms")
                return validation
            else:
                self.logger.error(f"Configuration validation failed: {validation.errors}")
                return validation
                
        except Exception as e:
            self.logger.error(f"Configuration loading failed: {e}")
            return ConfigValidationResult(
                is_valid=False,
                errors=[f"Loading failed: {str(e)}"],
                source=ConfigSource.DEFAULT
            )
    
    def _load_config_file(self) -> Dict[str, Any]:
        """Load configuration from file"""
        if not self.config_file.exists():
            return {}
        
        try:
            with open(self.config_file) as f:
                config = yaml.safe_load(f) or {}
            
            # Handle configuration migration
            config = self._migrate_config(config)
            
            self._source_map.update({k: ConfigSource.FILE for k in config.keys()})
            return config
            
        except yaml.YAMLError as e:
            self.logger.error(f"YAML parsing error in {self.config_file}: {e}")
            return {}
        except Exception as e:
            self.logger.error(f"Error reading config file: {e}")
            return {}
    
    def _load_config_environment(self) -> Dict[str, Any]:
        """Load configuration from environment variables"""
        env_config = {}
        
        # Map environment variables to config keys
        env_mappings = {
            'FW16_SYNTH_AUDIO_DRIVER': ('audio', 'driver'),
            'FW16_SYNTH_SAMPLE_RATE': ('audio', 'sample_rate'),
            'FW16_SYNTH_BUFFER_SIZE': ('audio', 'buffer_size'),
            'FW16_SYNTH_SOUND_FONT': ('audio', 'soundfont'),
            'FW16_SYNTH_BASE_OCTAVE': ('keyboard', 'base_octave'),
            'FW16_SYNTH_VELOCITY_SOURCE': ('keyboard', 'velocity_source'),
            'FW16_SYNTH_LOG_LEVEL': ('logging', 'level'),
            'FW16_SYNTH_METRICS_ENABLED': ('monitoring', 'enabled'),
            'FW16_SYNTH_HEALTH_CHECK_INTERVAL': ('monitoring', 'check_interval'),
        }
        
        for env_var, config_path in env_mappings.items():
            value = os.environ.get(env_var)
            if value is not None:
                env_config = self._set_nested_value(env_config, config_path, self._parse_env_value(value))
                self._source_map[config_path[-1]] = ConfigSource.ENVIRONMENT
        
        return env_config
    
    def _parse_env_value(self, value: str) -> Any:
        """Parse environment variable value"""
        # Boolean values
        if value.lower() in ('true', 'false'):
            return value.lower() == 'true'
        
        # Numeric values
        try:
            if '.' in value:
                return float(value)
            else:
                return int(value)
        except ValueError:
            pass
        
        return value
    
    def _merge_configs(self, *configs: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge multiple configuration dictionaries"""
        result = {}
        
        for config in configs:
            result = self._deep_merge(result, config)
        
        return result
    
    def _deep_merge(self, base: Dict, update: Dict) -> Dict:
        """Deep merge two dictionaries"""
        result = base.copy()
        
        for key, value in update.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def _update_source_map(self, file_config: Dict, env_config: Dict):
        """Update source mapping for configuration keys"""
        for key in self._defaults.keys():
            if key in env_config:
                self._source_map[key] = ConfigSource.ENVIRONMENT
            elif key in file_config:
                self._source_map[key] = ConfigSource.FILE
            else:
                self._source_map[key] = ConfigSource.DEFAULT
    
    def _validate_config(self, config: Dict[str, Any]) -> ConfigValidationResult:
        """Validate configuration against schema"""
        start_time = time.perf_counter()
        
        errors = []
        warnings = []
        
        try:
            # Validate required sections
            for section in ['audio', 'keyboard', 'monitoring']:
                if section not in config:
                    errors.append(f"Missing required section: {section}")
            
            # Validate audio section
            if 'audio' in config:
                audio = config['audio']
                if audio.get('driver') not in ['pipewire', 'pulseaudio', 'jack', 'alsa']:
                    errors.append("Invalid audio driver")
                
                sample_rate = audio.get('sample_rate', 48000)
                if not (8000 <= sample_rate <= 192000):
                    errors.append("Sample rate must be between 8000 and 192000")
                
                buffer_size = audio.get('buffer_size', 256)
                if buffer_size not in [64, 128, 256, 512, 1024]:
                    warnings.append("Buffer size should be a power of 2 for optimal performance")
            
            # Validate keyboard section
            if 'keyboard' in config:
                octave = config['keyboard'].get('base_octave', 4)
                if not (0 <= octave <= 8):
                    errors.append("Base octave must be between 0 and 8")
                
                velocity_source = config['keyboard'].get('velocity_source', 'timing')
                if velocity_source not in ['timing', 'pressure', 'position', 'combined']:
                    errors.append("Invalid velocity source")
            
            # Validate monitoring section
            if 'monitoring' in config:
                interval = config['monitoring'].get('check_interval', 30)
                if not (5 <= interval <= 300):
                    warnings.append("Health check interval should be between 5 and 300 seconds")
        
        except Exception as e:
            errors.append(f"Validation error: {str(e)}")
        
        # Record performance
        validation_time = (time.perf_counter() - start_time) * 1000
        self._validation_times.append(validation_time)
        if len(self._validation_times) > 100:
            self._validation_times.pop(0)
        
        return ConfigValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
    
    def _migrate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Migrate configuration from old versions"""
        if not config:
            return config
        
        version = config.get('version', '1.0')
        
        if version == '1.0':
            # Migration from v1.0 to v2.0
            if 'audio_driver' in config:
                config['audio'] = config.get('audio', {})
                config['audio']['driver'] = config.pop('audio_driver')
            
            if 'base_octave' in config:
                config['keyboard'] = config.get('keyboard', {})
                config['keyboard']['base_octave'] = config.pop('base_octave')
            
            config['version'] = '2.0'
            self.logger.info("Configuration migrated from v1.0 to v2.0")
        
        return config
    
    def _backup_config(self):
        """Create backup of current configuration"""
        try:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            backup_file = self.backup_dir / f"config_{timestamp}.yaml"
            
            with open(backup_file, 'w') as f:
                yaml.dump(self._config, f, default_flow_style=False)
            
            # Keep only last 10 backups
            backups = sorted(self.backup_dir.glob("config_*.yaml"))
            for old_backup in backups[:-10]:
                old_backup.unlink()
                
        except Exception as e:
            self.logger.error(f"Failed to create config backup: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        with self._lock:
            return self._get_nested_value(self._config, key.split('.'), default)
    
    def set(self, key: str, value: Any, source: ConfigSource = ConfigSource.RUNTIME):
        """Set configuration value"""
        with self._lock:
            self._config = self._set_nested_value(self._config, key.split('.'), value)
            self._source_map[key.split('.')[-1]] = source
            
            # Validate the change
            validation = self._validate_config(self._config)
            if not validation.is_valid:
                # Revert on validation failure
                self._config = self._set_nested_value(self._config, key.split('.'), default)
                raise ConfigValidationError(f"Invalid value: {validation.errors}")
            
            # Notify changes
            self._notify_changes(self._config, self._config)
            
            # Save to file if not runtime-only
            if source != ConfigSource.RUNTIME:
                self._save_config_file()
    
    def _get_nested_value(self, config: Dict, keys: List[str], default: Any) -> Any:
        """Get nested configuration value"""
        current = config
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default
        return current
    
    def _set_nested_value(self, config: Dict, keys: List[str], value: Any) -> Dict:
        """Set nested configuration value"""
        if not keys:
            return value
        
        result = config.copy()
        current = result
        
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        
        current[keys[-1]] = value
        return result
    
    def _save_config_file(self):
        """Save configuration to file"""
        try:
            with open(self.config_file, 'w') as f:
                yaml.dump(self._config, f, default_flow_style=False)
            self.logger.debug("Configuration saved to file")
        except Exception as e:
            self.logger.error(f"Failed to save configuration: {e}")
    
    def add_change_callback(self, callback: Callable[[ConfigChange], None]):
        """Add callback for configuration changes"""
        self._callbacks.append(callback)
    
    def remove_change_callback(self, callback: Callable[[ConfigChange], None]):
        """Remove configuration change callback"""
        if callback in self._callbacks:
            self._callbacks.remove(callback)
    
    def get_config_report(self) -> Dict[str, Any]:
        """Get comprehensive configuration report"""
        with self._lock:
            return {
                'config': self._config,
                'source_map': {k: v.value for k, v in self._source_map.items()},
                'validation_errors': self._validate_config(self._config).errors,
                'performance': {
                    'avg_load_time_ms': sum(self._load_times) / len(self._load_times) if self._load_times else 0,
                    'avg_validation_time_ms': sum(self._validation_times) / len(self._validation_times) if self._validation_times else 0,
                    'config_size': len(json.dumps(self._config))
                },
                'backups': [f.name for f in self.backup_dir.glob("*.yaml")],
                'schema': self._schema
            }
    
    def reset_to_defaults(self):
        """Reset configuration to defaults"""
        with self._lock:
            self._config = self._defaults.copy()
            self._source_map = {k: ConfigSource.DEFAULT for k in self._defaults.keys()}
            self._save_config_file()
            self.logger.info("Configuration reset to defaults")
    
    def shutdown(self):
        """Shutdown configuration manager"""
        self._running = False
        if self._observer:
            self._observer.stop()
            self._observer.join()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration"""
        return {
            'version': '2.0',
            'audio': {
                'driver': 'pipewire',
                'sample_rate': 48000,
                'buffer_size': 256,
                'soundfont': None
            },
            'keyboard': {
                'base_octave': 4,
                'velocity_source': 'combined',
                'velocity_min': 20,
                'velocity_max': 127
            },
            'monitoring': {
                'enabled': True,
                'check_interval': 30,
                'log_level': 'INFO'
            },
            'performance': {
                'enable_profiling': True,
                'metrics_collection': True,
                'health_monitoring': True
            }
        }
    
    def _get_config_schema(self) -> Dict[str, Dict[str, Any]]:
        """Get configuration schema for validation"""
        return {
            'audio': {
                'driver': {'type': 'string', 'choices': ['pipewire', 'pulseaudio', 'jack', 'alsa']},
                'sample_rate': {'type': 'integer', 'min': 8000, 'max': 192000},
                'buffer_size': {'type': 'integer', 'choices': [64, 128, 256, 512, 1024]},
                'soundfont': {'type': 'string', 'nullable': True}
            },
            'keyboard': {
                'base_octave': {'type': 'integer', 'min': 0, 'max': 8},
                'velocity_source': {'type': 'string', 'choices': ['timing', 'pressure', 'position', 'combined']},
                'velocity_min': {'type': 'integer', 'min': 1, 'max': 127},
                'velocity_max': {'type': 'integer', 'min': 1, 'max': 127}
            },
            'monitoring': {
                'enabled': {'type': 'boolean'},
                'check_interval': {'type': 'integer', 'min': 5, 'max': 300},
                'log_level': {'type': 'string', 'choices': ['DEBUG', 'INFO', 'WARNING', 'ERROR']}
            }
        }


# Global configuration manager instance
_config_manager: Optional[ProductionConfigManager] = None
_config_lock = Lock()


def get_config_manager() -> ProductionConfigManager:
    """Get global configuration manager instance"""
    global _config_manager
    
    if _config_manager is None:
        with _config_lock:
            if _config_manager is None:
                _config_manager = ProductionConfigManager()
                _config_manager.load_config()
    
    return _config_manager


def get_config(key: str, default: Any = None) -> Any:
    """Get configuration value from global manager"""
    return get_config_manager().get(key, default)


def set_config(key: str, value: Any):
    """Set configuration value in global manager"""
    get_config_manager().set(key, value)


def validate_config() -> ConfigValidationResult:
    """Validate current configuration"""
    return get_config_manager()._validate_config(get_config_manager()._config)