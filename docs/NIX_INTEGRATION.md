# Nix Integration Guide

## Overview

The FW16 Synth project now includes comprehensive Nix integration that creates a functional development environment and properly packages the Python codebase for distribution.

## What's Included

### 1. **Updated flake.nix**
- **Python Environment**: Properly configured with all dependencies (evdev, pyfluidsynth, python-rtmidi)
- **Source Code Packaging**: Updated to work with new `src/` directory structure
- **SoundFont Bundling**: Includes high-quality soundfonts (FluidR3 GM, GeneralUser GS)
- **Development Shell**: Complete development environment with all tools
- **NixOS Module**: System-wide installation support
- **Home-Manager Module**: User-level configuration support

### 2. **Python Package Configuration**
- **pyproject.toml**: Modern Python packaging with setuptools
- **Proper Package Structure**: Source code in `src/` with proper `__init__.py` files
- **Entry Points**: Command-line script `fw16-synth`
- **Dependencies**: All runtime and development dependencies defined

### 3. **Testing Infrastructure**
- **Test Structure**: `tests/` directory with pytest configuration
- **Configuration Tests**: Basic tests for config module functionality
- **Development Tools**: Black, MyPy, pytest integration

## Usage

### Development Environment

```bash
# Enter development shell
nix develop

# Run the application
python src/fw16_synth.py

# Format code
black src/

# Run tests
pytest tests/

# Build package
nix build
```

### Installation

```bash
# Install system-wide (NixOS)
nixos-rebuild switch --flake .

# Install for user (Home Manager)
home-manager switch --flake .

# Install standalone
nix profile install .#fw16-synth
```

### Package Distribution

```bash
# Build wheel
python -m build

# Install locally
pip install dist/fw16_synth-2.1.0-py3-none-any.whl

# Run installed package
fw16-synth
```

## Key Features

### 1. **Functional Development Environment**
- All Python dependencies pre-installed
- SoundFont paths properly configured
- Input device permissions handled
- Audio system integration (PipeWire, JACK, ALSA)

### 2. **Proper Python Packaging**
- Source code in `src/` directory
- Proper package structure with `__init__.py`
- Entry point script creation
- Dependency management

### 3. **SoundFont Integration**
- Bundled high-quality soundfonts
- Automatic soundfont discovery
- Download capability for additional soundfonts
- Environment variable configuration

### 4. **Multi-Platform Support**
- NixOS system integration
- Home-Manager user configuration
- Standalone package installation
- Development environment setup

## Environment Variables

The Nix flake sets up several environment variables:

- `DEFAULT_SOUNDFONT`: Default soundfont path
- `NIX_SOUNDFONT_FLUID`: FluidR3 GM soundfont directory
- `NIX_SOUNDFONT_GENERALUSER`: GeneralUser GS soundfont directory
- `PYTHONPATH`: Updated for development shell
- `PYTHONUNBUFFERED`: Ensures proper output handling

## Troubleshooting

### Permission Issues
```bash
# Add user to input group for device access
sudo usermod -aG input $USER
sudo usermod -aG audio $USER
```

### Audio Issues
```bash
# Check audio system
systemctl --user status pipewire
systemctl --user status pipewire-pulse

# Restart audio
systemctl --user restart pipewire
```

### Development Shell Issues
```bash
# Clear Nix cache
nix-collect-garbage -d

# Rebuild shell
nix develop --refresh
```

## Benefits

1. **Reproducible Builds**: Nix ensures identical environments across systems
2. **Dependency Management**: All dependencies handled automatically
3. **SoundFont Bundling**: High-quality soundfonts included by default
4. **Development Tools**: Complete development environment with formatting and testing
5. **Multiple Installation Methods**: System, user, and standalone installation options
6. **Python Best Practices**: Modern Python packaging with proper structure

## Future Enhancements

- **CI/CD Integration**: Automated testing and building
- **Additional SoundFonts**: More bundled soundfont options
- **GUI Support**: Desktop integration improvements
- **Documentation**: API documentation generation
- **Performance**: Optimized builds for different use cases