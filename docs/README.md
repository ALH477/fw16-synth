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
pip install evdev pyfluidsynth python-rtmidi psutil

# Optional for production monitoring
pip install prometheus-client grafana-api
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
# Run unit tests
pytest tests/ -v

# Integration tests
pytest tests/integration/ -v

# Performance tests
pytest tests/performance/ -v --benchmark

# Production simulation
pytest tests/production/ -v --simulate-failures
```

### Code Structure
```
fw16-synth/
├── fw16_synth.py          # Main application
├── production/             # Production features
│   ├── error_handler.py     # Centralized error handling
│   ├── resource_manager.py  # Resource lifecycle management
│   ├── device_manager.py    # Device hot-plug support
│   ├── retry_manager.py     # Intelligent retry logic
│   ├── health_monitor.py    # System health monitoring
│   ├── synth_controller.py  # Production wrapper
│   └── config_validator.py  # Configuration validation
├── tests/                  # Test suite
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

---

FW16 Synth v2.1 - Professional audio synthesis with production-grade reliability and maintainability.