# FW16 Synth Production Deployment Guide

## Overview

This guide covers deploying FW16 Synth in production environments with comprehensive monitoring, configuration management, and operational best practices.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Nix-based Deployment](#nix-based-deployment)
3. [Container Deployment](#container-deployment)
4. [Configuration Management](#configuration-management)
5. [Monitoring and Observability](#monitoring-and-observability)
6. [Performance Tuning](#performance-tuning)
7. [Troubleshooting](#troubleshooting)
8. [Security Considerations](#security-considerations)

## Prerequisites

### System Requirements

- **Operating System**: Linux (kernel 5.14+ recommended)
- **Architecture**: x86_64
- **Memory**: 4GB RAM minimum, 8GB recommended
- **Storage**: 2GB free space (additional space for soundfonts)
- **Audio**: PipeWire or JACK audio server
- **Input**: evdev-compatible input devices

### Dependencies

```bash
# For Nix-based deployment
curl -L https://nixos.org/nix/install | sh

# For container deployment
sudo apt install docker.io docker-compose
```

### User Permissions

```bash
# Add user to required groups
sudo usermod -aG input,audio,video $USER

# For real-time audio (optional but recommended)
sudo usermod -aG realtime $USER
```

## Nix-based Deployment

### 1. System-wide Installation (NixOS)

Add to your `configuration.nix`:

```nix
{ config, pkgs, ... }:

{
  imports = [
    # Import the FW16 Synth module
    /path/to/fw16-synth/modules/default.nix
  ];

  programs.fw16-synth = {
    enable = true;
    audioDriver = "pipewire";
    soundfont = "/var/lib/soundfonts/FluidR3_GM.sf2";
    users = [ "musician" ];
    enableRealtimeAudio = true;
  };

  # Optional: Enable real-time scheduling
  security.rtkit.enable = true;
  security.pam.loginLimits = [
    { domain = "@audio"; type = "-"; item = "rtprio"; value = "95"; }
    { domain = "@audio"; type = "-"; item = "memlock"; value = "unlimited"; }
  ];
}
```

### 2. User Installation (Home Manager)

Add to your `home.nix`:

```nix
{ config, pkgs, ... }:

{
  programs.fw16-synth = {
    enable = true;
    soundfont = "${pkgs.soundfont-fluid}/share/soundfonts/FluidR3_GM.sf2";
    audioDriver = "pipewire";
    defaultOctave = 4;
    defaultProgram = 0;
    installSoundfonts = true;
  };
}
```

### 3. Standalone Installation

```bash
# Install via Nix profile
nix profile install .#fw16-synth

# Or build and install
nix build
nix profile install ./result

# Run
fw16-synth --production
```

## Container Deployment

### Docker Compose Setup

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  fw16-synth:
    build: .
    container_name: fw16-synth
    restart: unless-stopped
    
    # Audio configuration
    devices:
      - /dev/snd:/dev/snd
      - /dev/input:/dev/input
    
    # Audio networking
    environment:
      - PULSE_SERVER=unix:/run/user/1000/pulse/native
      - PULSE_COOKIE=/run/user/1000/pulse/cookie
      - DEFAULT_SOUNDFONT=/opt/soundfonts/FluidR3_GM.sf2
      - PYTHONUNBUFFERED=1
    
    volumes:
      - /run/user/1000/pulse:/run/user/1000/pulse:ro
      - /dev/input:/dev/input:ro
      - ./config:/opt/fw16-synth/config:ro
      - ./logs:/opt/fw16-synth/logs
      - ./soundfonts:/opt/soundfonts:ro
    
    # Real-time priority
    cap_add:
      - SYS_NICE
      - SYS_RESOURCE
    
    # Low latency networking
    sysctls:
      - net.core.somaxconn=1024
      - net.ipv4.tcp_fin_timeout=30
    
    # Health check
    healthcheck:
      test: ["CMD", "fw16-synth", "--health-check"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
```

### Dockerfile

```dockerfile
FROM nixos/nix:latest

# Install FW16 Synth
COPY . /opt/fw16-synth
WORKDIR /opt/fw16-synth

RUN nix-build --no-out-link && \
    nix-env -i -f default.nix

# Create soundfont directory
RUN mkdir -p /opt/soundfonts

# Create non-root user
RUN useradd -m -s /bin/bash synthuser && \
    usermod -aG audio,input synthuser

# Set permissions
RUN chown -R synthuser:synthuser /opt

USER synthuser
WORKDIR /opt/fw16-synth

CMD ["fw16-synth", "--production", "--log-file", "/opt/fw16-synth/logs/synth.log"]
```

### Container Deployment Commands

```bash
# Build and start
docker-compose up -d

# View logs
docker-compose logs -f

# Monitor health
docker-compose ps

# Scale (for multiple instances)
docker-compose up -d --scale fw16-synth=3
```

## Configuration Management

### 1. Environment-based Configuration

```bash
# Production environment variables
export FW16_SYNTH_AUDIO_DRIVER="pipewire"
export FW16_SYNTH_SOUND_FONT="/opt/soundfonts/FluidR3_GM.sf2"
export FW16_SYNTH_BASE_OCTAVE="4"
export FW16_SYNTH_VELOCITY_SOURCE="combined"
export FW16_SYNTH_LOG_LEVEL="INFO"
export FW16_SYNTH_METRICS_ENABLED="true"
export FW16_SYNTH_HEALTH_CHECK_INTERVAL="30"
```

### 2. Configuration File

Create `/etc/fw16-synth/config.yaml`:

```yaml
# Audio settings
audio:
  driver: pipewire
  sample_rate: 48000
  buffer_size: 256
  soundfont: /opt/soundfonts/FluidR3_GM.sf2

# Performance settings
performance:
  enable_profiling: true
  metrics_collection: true
  health_monitoring: true
  log_level: INFO
  log_file: /var/log/fw16-synth/production.log

# MIDI settings
midi:
  input_enabled: true
  auto_connect: true
  port_filter: "Framework|Piano|Keyboard"

# Touchpad settings
touchpad:
  enabled: true
  smoothing: 0.85
  pressure_threshold: 0.1

# Production settings
production:
  enable_monitoring: true
  enable_profiling: true
  enable_health_checks: true
  graceful_shutdown_timeout: 30
  error_recovery_enabled: true
```

### 3. Configuration Validation

```bash
# Validate configuration
fw16-synth --config /etc/fw16-synth/config.yaml --validate-only

# Test configuration
fw16-synth --config /etc/fw16-synth/config.yaml --test-mode
```

## Monitoring and Observability

### 1. Health Checks

```bash
# Basic health check
curl -f http://localhost:8080/health || exit 1

# Detailed health check
curl http://localhost:8080/health/detailed | jq

# Metrics endpoint
curl http://localhost:8080/metrics | jq
```

### 2. Prometheus Integration

Add to Prometheus configuration:

```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'fw16-synth'
    static_configs:
      - targets: ['localhost:8080']
    metrics_path: '/metrics'
    scrape_interval: 5s
```

### 3. Grafana Dashboards

Import dashboard configuration:

```json
{
  "dashboard": {
    "title": "FW16 Synth Production Monitoring",
    "panels": [
      {
        "title": "Audio Latency",
        "type": "graph",
        "targets": [
          {
            "expr": "fw16_synth_audio_latency_ms",
            "legendFormat": "Audio Latency"
          }
        ]
      },
      {
        "title": "System Resources",
        "type": "graph",
        "targets": [
          {
            "expr": "fw16_synth_cpu_percent",
            "legendFormat": "CPU %"
          },
          {
            "expr": "fw16_synth_memory_percent",
            "legendFormat": "Memory %"
          }
        ]
      }
    ]
  }
}
```

### 4. Alerting Rules

Prometheus alerting rules:

```yaml
groups:
  - name: fw16-synth
    rules:
      - alert: HighAudioLatency
        expr: fw16_synth_audio_latency_ms > 20
        for: 1m
        labels:
          severity: warning
        annotations:
          summary: "High audio latency detected"
          description: "Audio latency is {{ $value }}ms"
      
      - alert: HighCPULoad
        expr: fw16_synth_cpu_percent > 80
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High CPU usage"
          description: "CPU usage is {{ $value }}%"
```

## Performance Tuning

### 1. Audio Optimization

```bash
# PipeWire configuration
echo 'context.properties = { audio.rate = 48000 }' | sudo tee -a /etc/pipewire/pipewire.conf

# Real-time scheduling
sudo systemctl edit pipewire
# Add:
# [Service]
# CPUSchedulingPolicy=1
# CPUSchedulingPriority=80

# Buffer size optimization
echo 'audio.buffer_size = 256' | sudo tee -a /etc/fw16-synth/config.yaml
```

### 2. System Tuning

```bash
# Increase file descriptor limits
echo '* soft nofile 65536' | sudo tee -a /etc/security/limits.conf
echo '* hard nofile 65536' | sudo tee -a /etc/security/limits.conf

# Optimize network buffers
sudo sysctl -w net.core.rmem_max=134217728
sudo sysctl -w net.core.wmem_max=134217728

# Disable CPU frequency scaling
echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
```

### 3. Memory Management

```bash
# Enable huge pages for audio
echo 2048 | sudo tee /proc/sys/vm/nr_hugepages

# Optimize swap behavior
sudo sysctl -w vm.swappiness=1
sudo sysctl -w vm.vfs_cache_pressure=50
```

## Troubleshooting

### 1. Common Issues

**No Sound Output**
```bash
# Check audio server
systemctl --user status pipewire
systemctl --user status pipewire-pulse

# Test audio
pactl list sinks short
speaker-test -c 2 -t wav

# Check permissions
groups | grep audio
```

**Input Device Not Detected**
```bash
# List input devices
evtest --query /dev/input/event0 EV_KEY KEY_A

# Check permissions
ls -la /dev/input/event*
groups | grep input

# Test device access
sudo evtest /dev/input/event0
```

**High Latency**
```bash
# Check buffer sizes
cat /proc/asound/cards
cat /proc/asound/pcm

# Monitor system load
top
iostat -x 1

# Check for interference
sudo powertop --auto-tune
```

### 2. Log Analysis

```bash
# View production logs
tail -f /var/log/fw16-synth/production.log

# Filter errors
grep ERROR /var/log/fw16-synth/production.log

# Monitor metrics
tail -f /var/log/fw16-synth/production.log | grep METRIC
```

### 3. Performance Debugging

```bash
# Profile CPU usage
perf top -p $(pgrep fw16-synth)

# Monitor memory usage
valgrind --tool=massif fw16-synth

# Check for bottlenecks
strace -p $(pgrep fw16-synth)
```

## Security Considerations

### 1. Input Device Security

```bash
# Restrict input device access
sudo chmod 640 /dev/input/event*
sudo chown root:input /dev/input/event*

# Create udev rules for specific devices
cat > /etc/udev/rules.d/99-fw16-synth.rules << EOF
KERNEL=="event*", SUBSYSTEM=="input", GROUP="input", MODE="0640"
EOF
```

### 2. Audio Security

```bash
# Restrict audio access
sudo chmod 660 /dev/snd/*
sudo chown root:audio /dev/snd/*

# Use PulseAudio per-user
echo 'enable-shm = no' | sudo tee -a /etc/pulse/client.conf
```

### 3. Container Security

```yaml
# Secure container configuration
security_opt:
  - no-new-privileges:true
  - label=type:container_t

# Read-only filesystem
read_only: true
tmpfs:
  - /tmp
  - /var/run

# Drop capabilities
cap_drop:
  - ALL
cap_add:
  - SYS_NICE
  - SYS_RESOURCE
```

### 4. Network Security

```bash
# Firewall rules
sudo ufw allow from 192.168.1.0/24 to any port 8080
sudo ufw deny 8080

# TLS for web interface
# Configure reverse proxy with TLS termination
```

## Maintenance

### 1. Regular Tasks

```bash
# Update soundfonts
fw16-synth --download-soundfonts

# Rotate logs
sudo logrotate /etc/logrotate.d/fw16-synth

# Update dependencies
nix-env -u fw16-synth
```

### 2. Backup and Recovery

```bash
# Backup configuration
tar -czf fw16-synth-backup.tar.gz \
  /etc/fw16-synth/ \
  /opt/soundfonts/ \
  /var/log/fw16-synth/

# Restore configuration
tar -xzf fw16-synth-backup.tar.gz -C /
```

### 3. Monitoring Health

```bash
# Health check script
#!/bin/bash
if ! curl -f http://localhost:8080/health; then
  echo "FW16 Synth health check failed"
  systemctl restart fw16-synth
  exit 1
fi
```

## Support

For additional support:

- **Documentation**: [GitHub Wiki](https://github.com/ALH477/fw16-synth/wiki)
- **Issues**: [GitHub Issues](https://github.com/ALH477/fw16-synth/issues)
- **Discussions**: [GitHub Discussions](https://github.com/ALH477/fw16-synth/discussions)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines and contribution process.