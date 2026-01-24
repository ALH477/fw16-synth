#!/usr/bin/env python3
"""
FW16 Synth Configuration Module
================================
Handles YAML configuration for custom key mappings and modulation assignments.
"""

import os
import sys
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
import json

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


# Default configuration as YAML template
DEFAULT_CONFIG_YAML = """# FW16 Synth Configuration
# ========================
# Place in ~/.config/fw16-synth/config.yaml

# Audio settings
audio:
  driver: pipewire  # pulseaudio, jack, alsa, pipewire
  sample_rate: 48000
  soundfont: null   # null = auto-detect, or path to .sf2

# Keyboard settings
keyboard:
  base_octave: 4    # Middle C octave (0-8)
  velocity:
    min: 40         # Minimum velocity (slowest keypress)
    max: 127        # Maximum velocity (fastest keypress)
    time_min: 0.01  # Seconds - fastest keypress threshold
    time_max: 0.15  # Seconds - slowest keypress threshold

# Touchpad modulation mapping
touchpad:
  # X-axis (horizontal)
  x:
    type: pitch_bend  # pitch_bend or cc
    cc: null          # CC number if type=cc
    range: 2          # Semitones for pitch bend
    invert: false
  
  # Y-axis (vertical)  
  y:
    type: cc
    cc: 74            # Filter cutoff (CC74 = brightness)
    range: null
    invert: true      # Top of touchpad = max value
  
  # Pressure
  pressure:
    type: cc
    cc: 11            # Expression
    invert: false

# Custom key mapping (optional override)
# Format: key_name: semitone_offset (from octave C)
# Uncomment to customize
# keymap:
#   Q: 0    # C
#   W: 2    # D
#   E: 4    # E
#   # ... etc

# Display settings
display:
  show_notes: true
  show_touchpad: true
  use_tui: false      # Full terminal UI (experimental)

# MIDI settings (for external output)
midi:
  output_device: null  # null = internal FluidSynth only
  channel: 0           # MIDI channel (0-15)

# Presets - quick program changes
presets:
  - name: "Piano"
    program: 0
    shortcut: F1
  - name: "Rhodes"
    program: 4
    shortcut: F2
  - name: "Strings"
    program: 48
    shortcut: F3
  - name: "Pad"
    program: 89
    shortcut: F4
"""


@dataclass
class AudioConfig:
    driver: str = "pipewire"
    sample_rate: int = 48000
    soundfont: Optional[str] = None


@dataclass 
class VelocityConfig:
    min: int = 40
    max: int = 127
    time_min: float = 0.01
    time_max: float = 0.15


@dataclass
class KeyboardConfig:
    base_octave: int = 4
    velocity: VelocityConfig = field(default_factory=VelocityConfig)


@dataclass
class ModAxisConfig:
    type: str = "cc"  # "cc" or "pitch_bend"
    cc: Optional[int] = None
    range: Optional[int] = None
    invert: bool = False


@dataclass
class TouchpadConfig:
    x: ModAxisConfig = field(default_factory=lambda: ModAxisConfig(type="pitch_bend", range=2))
    y: ModAxisConfig = field(default_factory=lambda: ModAxisConfig(type="cc", cc=74, invert=True))
    pressure: ModAxisConfig = field(default_factory=lambda: ModAxisConfig(type="cc", cc=11))


@dataclass
class DisplayConfig:
    show_notes: bool = True
    show_touchpad: bool = True
    use_tui: bool = False


@dataclass
class MidiConfig:
    output_device: Optional[str] = None
    channel: int = 0


@dataclass
class PresetConfig:
    name: str
    program: int
    shortcut: Optional[str] = None


@dataclass
class FullConfig:
    audio: AudioConfig = field(default_factory=AudioConfig)
    keyboard: KeyboardConfig = field(default_factory=KeyboardConfig)
    touchpad: TouchpadConfig = field(default_factory=TouchpadConfig)
    display: DisplayConfig = field(default_factory=DisplayConfig)
    midi: MidiConfig = field(default_factory=MidiConfig)
    presets: List[PresetConfig] = field(default_factory=list)
    keymap: Optional[Dict[str, int]] = None


def get_config_path() -> Path:
    """Get the configuration file path"""
    xdg_config = os.environ.get('XDG_CONFIG_HOME', os.path.expanduser('~/.config'))
    return Path(xdg_config) / 'fw16-synth' / 'config.yaml'


def create_default_config():
    """Create default configuration file"""
    config_path = get_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    if not config_path.exists():
        config_path.write_text(DEFAULT_CONFIG_YAML)
        print(f"Created default config: {config_path}")
    else:
        print(f"Config already exists: {config_path}")


def load_config(path: Optional[str] = None) -> FullConfig:
    """Load configuration from YAML file"""
    if path:
        config_path = Path(path)
    else:
        config_path = get_config_path()
    
    config = FullConfig()
    
    if not config_path.exists():
        return config
    
    if not HAS_YAML:
        print("[WARN] PyYAML not installed, using defaults")
        return config
    
    try:
        with open(config_path) as f:
            data = yaml.safe_load(f)
        
        if not data:
            return config
        
        # Parse audio config
        if 'audio' in data:
            audio = data['audio']
            config.audio = AudioConfig(
                driver=audio.get('driver', 'pipewire'),
                sample_rate=audio.get('sample_rate', 48000),
                soundfont=audio.get('soundfont')
            )
        
        # Parse keyboard config
        if 'keyboard' in data:
            kb = data['keyboard']
            vel = kb.get('velocity', {})
            config.keyboard = KeyboardConfig(
                base_octave=kb.get('base_octave', 4),
                velocity=VelocityConfig(
                    min=vel.get('min', 40),
                    max=vel.get('max', 127),
                    time_min=vel.get('time_min', 0.01),
                    time_max=vel.get('time_max', 0.15)
                )
            )
        
        # Parse touchpad config
        if 'touchpad' in data:
            tp = data['touchpad']
            
            def parse_axis(axis_data: dict) -> ModAxisConfig:
                return ModAxisConfig(
                    type=axis_data.get('type', 'cc'),
                    cc=axis_data.get('cc'),
                    range=axis_data.get('range'),
                    invert=axis_data.get('invert', False)
                )
            
            if 'x' in tp:
                config.touchpad.x = parse_axis(tp['x'])
            if 'y' in tp:
                config.touchpad.y = parse_axis(tp['y'])
            if 'pressure' in tp:
                config.touchpad.pressure = parse_axis(tp['pressure'])
        
        # Parse display config
        if 'display' in data:
            disp = data['display']
            config.display = DisplayConfig(
                show_notes=disp.get('show_notes', True),
                show_touchpad=disp.get('show_touchpad', True),
                use_tui=disp.get('use_tui', False)
            )
        
        # Parse MIDI config
        if 'midi' in data:
            midi = data['midi']
            config.midi = MidiConfig(
                output_device=midi.get('output_device'),
                channel=midi.get('channel', 0)
            )
        
        # Parse presets
        if 'presets' in data:
            config.presets = [
                PresetConfig(
                    name=p.get('name', f"Preset {i}"),
                    program=p.get('program', 0),
                    shortcut=p.get('shortcut')
                )
                for i, p in enumerate(data['presets'])
            ]
        
        # Parse custom keymap
        if 'keymap' in data and data['keymap']:
            config.keymap = data['keymap']
        
        print(f"[CONFIG] Loaded: {config_path}")
        return config
        
    except Exception as e:
        print(f"[WARN] Failed to load config: {e}")
        return FullConfig()


def save_config(config: FullConfig, path: Optional[str] = None):
    """Save configuration to YAML file"""
    if not HAS_YAML:
        print("[ERROR] PyYAML required to save config")
        return
    
    if path:
        config_path = Path(path)
    else:
        config_path = get_config_path()
    
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Convert to dict
    data = {
        'audio': asdict(config.audio),
        'keyboard': {
            'base_octave': config.keyboard.base_octave,
            'velocity': asdict(config.keyboard.velocity)
        },
        'touchpad': {
            'x': asdict(config.touchpad.x),
            'y': asdict(config.touchpad.y),
            'pressure': asdict(config.touchpad.pressure)
        },
        'display': asdict(config.display),
        'midi': asdict(config.midi),
        'presets': [asdict(p) for p in config.presets]
    }
    
    if config.keymap:
        data['keymap'] = config.keymap
    
    with open(config_path, 'w') as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)
    
    print(f"[CONFIG] Saved: {config_path}")


# CLI for config management
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="FW16 Synth Configuration Manager")
    parser.add_argument('command', choices=['init', 'show', 'path'],
                       help="Command: init (create default), show (display current), path (show config path)")
    
    args = parser.parse_args()
    
    if args.command == 'init':
        create_default_config()
    elif args.command == 'path':
        print(get_config_path())
    elif args.command == 'show':
        config = load_config()
        if HAS_YAML:
            print(yaml.dump(asdict(config), default_flow_style=False))
        else:
            print(json.dumps(asdict(config), indent=2))
