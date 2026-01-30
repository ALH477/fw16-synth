# FW16 Synth v2.1 - Production-Grade Implementation

## Overview

Transform your Framework 16 into a professional-grade synthesizer with production-ready error handling, resource management, health monitoring, and comprehensive recovery mechanisms. Built for reliability and maintainability in production environments.

## Features

### Core Functionality
- Real-time FluidSynth audio engine with low-latency output
- Multi-device input support (keyboard, touchpad, MIDI controllers)
- Advanced velocity system with pressure/position/timing detection
- Professional TUI with real-time visualization and control
- SoundFont browser with integrated downloader
- Arpeggiator with multiple modes and patterns
- Layer mode for dual-instrument playback

### Production Enhancements
- **Error Recovery**: Automatic recovery from audio engine failures, device disconnection, and resource exhaustion
- **Resource Management**: LIFO resource lifecycle management with automatic cleanup and leak prevention
- **Health Monitoring**: Real-time system health tracking with performance metrics and automated alerts
- **Device Management**: Hot-plug support with device health monitoring and automatic reconnection
- **Retry Logic**: Intelligent retry mechanisms with exponential backoff and jitter for transient failures
- **Configuration Validation**: Comprehensive validation with user-friendly error messages and solutions
- **Structured Logging**: Enhanced logging with rotation, performance tracking, and structured output

## Installation

### Dependencies
```bash
# Core dependencies
sudo apt install python3-dev python3-pip build-essential libasound2-dev
sudo apt install libfluidsynth-dev portaudio19-dev jackd2

# Python packages
pip install evdev pyfluidsynth python-rtmidi numpy psutil

# Optional for production monitoring
pip install prometheus-client grafana-api
```

### Development Installation
```bash
# Clone and install with development dependencies
git clone https://github.com/your-repo/fw16-synth.git
cd fw16-synth
pip install -e ".[dev]"

# Or use nix
nix develop
```

### Quick Install
```bash
git clone https://github.com/your-repo/fw16-synth.git
cd fw16-synth
pip install -e .
```

## Usage

### Basic Usage
```bash
# Start with all features
./fw16-synth

# Production mode with monitoring
./fw16-synth --production

# Production with file logging
./fw16-synth --production --log-file /var/log/fw16-synth.log

# MIDI input support
./fw16-synth --midi --midi-port "Framework 16"

# Custom velocity source
./fw16-synth --velocity-source pressure

# Fixed velocity for testing
./fw16-synth --velocity 100
```

### Configuration Options
```bash
--driver DRIVER      Audio driver (pipewire, pulseaudio, jack, alsa)
--soundfont PATH     Custom SoundFont file
--octave N          Starting octave (0-8)
--program N           Starting program (0-127)
--velocity SOURCE     Velocity mode (timing, pressure, position, combined)
--velocity N          Fixed velocity (1-127)
--production          Enable production-ready features
--log-file PATH       Enable file logging with rotation
--verbose            Enable verbose logging
--midi               Enable MIDI input
--midi-port NAME     Specific MIDI device
```

### Velocity System

The FW16 Synth features an advanced multi-source velocity system:

#### Velocity Sources
- **Pressure-based**: Touchpad pressure sensitivity (most expressive)
- **Position-based**: Keyboard row mapping (predictable control)
- **Timing-based**: Inter-key timing (traditional method)
- **Combined**: Intelligent fallback (pressure → position → timing)

#### Position Mapping
- Bottom row (Z-X-C-V...): Soft velocity (40)
- Home row (A-S-D-F...): Medium velocity (80)  
- Top rows (Q-W-E-R...): Loud velocity (110)

#### Visual Indicators
- Real-time velocity meter with source indicators
- Color-coded velocity source symbols
- Velocity distribution tracking

## Production Features

### Error Handling
- **Automatic Recovery**: FluidSynth restart, device reconnection, audio driver switching
- **Circuit Breakers**: Prevent repeated failures with automatic disable
- **User-Friendly Messages**: Clear error descriptions with actionable solutions
- **Error Analytics**: Pattern analysis and failure rate tracking

### Resource Management
- **LIFO Cleanup**: Resources released in reverse registration order
- **Leak Prevention**: Automatic detection and prevention of resource leaks
- **Retry Logic**: Multiple retry attempts with intelligent backoff
- **Performance Tracking**: Resource usage metrics and cleanup success rates

### Device Management
- **Hot-Plug Support**: Automatic detection of device connection/disconnection
- **Health Monitoring**: Device performance tracking and status monitoring
- **Capability Detection**: Automatic identification of device features and limitations
- **Automatic Reconnection**: Seamless recovery from device disconnection

### Health Monitoring
- **System Metrics**: CPU usage, memory usage, system load
- **Audio Metrics**: Latency tracking, buffer monitoring, throughput analysis
- **Application Metrics**: Notes played, error rates, velocity distribution
- **Automated Alerts**: Proactive notification of performance issues

### Configuration Management
- **Runtime Validation**: Comprehensive validation of all configuration parameters
- **Safety Checks**: Prevention of invalid or dangerous configurations
- **Default Management**: Sensible defaults with automatic fallback options
- **Documentation**: Complete configuration reference with examples

## Performance

### System Requirements
- **CPU**: Minimal overhead, optimized for real-time audio
- **Memory**: Efficient resource usage with automatic cleanup
- **Latency**: Sub-10ms audio latency with proper configuration
- **Storage**: SoundFont caching and efficient resource management

### Monitoring Integration
```bash
# Health status monitoring
./fw16-synth --production --health-check

# Export metrics for monitoring systems
./fw16-synth --production --export-metrics

# Performance benchmark mode
./fw16-synth --production --benchmark
```

## Troubleshooting

### Common Issues

#### Permission Errors
```
Error: Device access permission denied
Solution: 
1. Add user to input group:
   sudo usermod -aG input $USER
2. Log out and log back in
3. Verify membership:
   groups | grep input
```

#### Audio Engine Issues
```
Error: Audio engine failed to initialize
Solution:
1. Check audio system:
   systemctl --user status pipewire
2. Restart audio if needed:
   systemctl --user restart pipewire
3. Try different driver:
   ./fw16-synth --driver alsa
```

#### Device Connection Problems
```
Error: No input devices found
Solution:
1. Check device connectivity:
   ls -la /dev/input/
2. Verify device permissions:
   sudo chmod 666 /dev/input/event*
3. Test with specific device:
   ./fw16-synth --device /dev/input/event3
```

### Production Mode Issues

#### Health Monitoring Problems
```
Error: Health monitoring failed to start
Solution:
1. Check psutil installation:
   python -c "import psutil; print('OK')"
2. Verify system resources:
   free -h
3. Check log permissions:
   ls -la /var/log/
```

#### Resource Cleanup Failures
```
Error: Resource cleanup failed
Solution:
1. Check system logs:
   journalctl -xe | grep fw16-synth
2. Force cleanup if needed:
   killall -9 fw16-synth
3. Restart clean session:
   ./fw16-synth --production --clean-start
```

## Development

### Building from Source
```bash
# Clone repository
git clone https://github.com/your-repo/fw16-synth.git
cd fw16-synth

# Development setup
python3 -m venv venv
source venv/bin/activate
pip install -e ".[dev]"

# Run in development mode
./fw16-synth --development --debug
```

### Testing
```bash
# Run nix-compatible tests (recommended for CI/CD)
python tests/test_nix_compatible.py

# Run unit tests (requires full dependencies)
pytest tests/ -v

# Run specific test class
python tests/test_nix_compatible.py TestFluidSynthEngine

# Run glitch prevention tests
python tests/test_glitch_prevention.py

# Integration tests
pytest tests/integration/ -v

# Production simulation
pytest tests/production/ -v --simulate-failures
```

#### Test Coverage
- **test_nix_compatible.py**: 25 tests covering core functionality (no external deps)
- **test_glitch_prevention.py**: Glitch detection and prevention
- **test_production_modules.py**: Production module tests
- All tests use Python standard library for maximum compatibility

### Code Structure
```
fw16-synth/
├── fw16_synth.py          # Main application (being refactored)
├── production/             # Production features
│   ├── error_handler.py     # Centralized error handling
│   ├── resource_manager.py  # Resource lifecycle management
│   ├── device_manager.py    # Device hot-plug support
│   ├── retry_manager.py     # Intelligent retry logic
│   ├── health_monitor.py    # System health monitoring (thread-safe)
│   ├── synth_controller.py  # Production wrapper
│   └── config_validator.py  # Configuration validation
├── engine/                # Audio engine module
│   ├── __init__.py
│   └── fluidsynth_engine.py
├── soundfont/             # SoundFont management module
│   ├── __init__.py
│   └── manager.py
├── input/                 # Input handling module
│   ├── __init__.py
│   ├── keyboard_input.py    # Keyboard mapper, velocity tracker (240 lines)
│   └── touchpad_input.py    # Touchpad controller, calibration (131 lines)
├── midi/                  # MIDI handling module
│   ├── __init__.py
│   └── midi_handler.py     # MIDI input controller, message parser (291 lines)
├── ui/                    # UI components module
│   └── __init__.py
├── tests/                  # Test suite
│   ├── README.md          # Test documentation
│   ├── test_nix_compatible.py  # Nix-compatible tests (25 tests)
│   ├── test_extended_coverage.py  # Extended tests (26 tests)
│   ├── test_core_functionality.py  # Core functionality tests
│   ├── test_production_modules.py  # Production module tests
│   └── test_glitch_prevention.py  # Glitch prevention tests
├── docs/                   # Documentation
└── scripts/                # Utility scripts
```

## Configuration

### System Configuration
Production settings can be configured via:

1. **Command Line Arguments**: All options available via CLI
2. **Configuration Files**: YAML configuration support
3. **Environment Variables**: Override options via environment
4. **Runtime Changes**: Most settings adjustable during operation

### Production Configuration
```yaml
# ~/.config/fw16-synth/config.yml
production:
  enabled: true
  health_monitoring:
    interval: 1.0
    alerts:
      latency_threshold: 50.0
      error_threshold: 0.1
  logging:
    level: INFO
    file: /var/log/fw16-synth.log
    rotation:
      max_size: 50MB
      backup_count: 10
  error_handling:
    retry_attempts: 3
    circuit_breaker_threshold: 3
    recovery_timeout: 30.0
```

## License

MIT License - See LICENSE file for details

## Support

- **Documentation**: Full documentation at /docs/
- **Issues**: Report bugs via GitHub Issues
- **Community**: Discussions and support available
- **Contributing**: Pull requests welcome for improvements

## Recent Improvements

### v2.1.1 - Code Quality & Testing Enhancement

**Bug Fixes:**
- Fixed thread safety issue in `HealthMetrics.velocity_distribution` (added lock protection)
- Fixed error rate calculation in `HealthMonitor.record_error()`
- Fixed `alerts_sent` type from `set` to `Dict[str, float]` for cooldown tracking

**Code Quality:**
- Added `numpy` and `psutil` to core dependencies
- Implemented actual recovery strategies in `ProductionErrorHandler`:
  - `_recover_fluidsynth()`: Attempts PipeWire restart, tries alternative audio drivers
  - `_recover_device_access()`: Checks permissions, scans for available devices
  - `_recover_audio_output()`: Unmutes audio, restarts audio server
  - `_recover_soundfont_load()`: Searches for .sf2 files in standard paths
  - `_recover_midi_connection()`: Waits for USB enumeration, checks MIDI ports
- Modularized `fw16_synth.py` into smaller, maintainable modules:
  - `engine/fluidsynth_engine.py`: Audio engine wrapper
  - `soundfont/manager.py`: SoundFont discovery and management

**Testing:**
- Added `tests/test_nix_compatible.py`: 25 tests running in pure Python (no external deps)
  - FluidSynthEngine: Initialization, note operations, chord playing
  - ModulationRouting: Configuration, inversion
  - SynthConfig: Default and custom configurations
  - ParameterSmoother: Smoothing behavior, alpha parameter
  - VelocityTracker: Velocity calculation, clamping
  - RateLimiter: Rate limiting, thread safety, window expiry
  - InputSanitizer: MIDI CC clamping, audio parameter validation
- Added `tests/test_production_modules_improved.py`: Production module tests
- Added `tests/README.md`: Comprehensive test documentation
- All 25 nix-compatible tests passing (~0.15s execution time)

**Documentation:**
- Updated README.md with new testing information
- Updated README.md with refactored module structure
- Added test coverage documentation

**Dependencies:**
- Updated `pyproject.toml` to include `numpy` and `psutil` as core dependencies
- Added `pytest` to dev dependencies

**Stats:**
- Total Python files: 32
- Total Python lines: 11,913
- New modularized code: 402 lines extracted from monolithic main file
- Test coverage: 25 comprehensive tests for core functionality

---

FW16 Synth v2.1.1 - Professional audio synthesis with production-grade reliability and maintainability.