# FW16 Synth

**Transform your Framework 16 into a synthesizer.**

Uses the laptop keyboard as a piano keyboard and the touchpad for real-time modulation. Low-latency evdev input bypasses the display server for direct hardware access.

## Features

- **Keyboard Piano**: 3+ octave range mapped across QWERTY, ASDF, and ZXCV rows
- **Black Keys**: Number row (2, 3, 5, 6, 7, 9, 0) = sharps/flats
- **Touchpad Modulation**: X-axis = pitch bend, Y-axis = filter/mod wheel, pressure = expression
- **Velocity Sensitivity**: Keypress timing determines note velocity
- **128 GM Instruments**: Full General MIDI support via FluidSynth
- **Sustain Pedal**: Space bar acts as sustain
- **Exclusive Input**: Grabs devices for zero-conflict operation

## Keyboard Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  `  1  2  3  4  5  6  7  8  9  0  -  =  ⌫                      │
│        C# D#    F# G# A#    C# D#  ▼  ▲  (octave controls)     │
├─────────────────────────────────────────────────────────────────┤
│  ⇥  Q  W  E  R  T  Y  U  I  O  P  [  ]  \                      │
│     C  D  E  F  G  A  B  C  D  E  F  G     (octave 0)          │
├─────────────────────────────────────────────────────────────────┤
│  ⇪  A  S  D  F  G  H  J  K  L  ;  '  ↵                         │
│     C  D  E  F  G  A  B  C  D  E  F        (octave -1)         │
├─────────────────────────────────────────────────────────────────┤
│  ⇧  Z  X  C  V  B  N  M  ,  .  /  ⇧                            │
│     C  D  E  F  G  A  B  C  D  E           (octave -2)         │
├─────────────────────────────────────────────────────────────────┤
│  Ctrl ❖ Alt ━━━━━━━ SUSTAIN ━━━━━━━ Alt Fn Ctrl               │
└─────────────────────────────────────────────────────────────────┘
```

## Controls

| Key | Function |
|-----|----------|
| `+` / `=` | Octave up |
| `-` | Octave down |
| `Space` | Sustain pedal |
| `Page Up` | Next instrument |
| `Page Down` | Previous instrument |
| `Esc` | Panic (all notes off) |
| `Ctrl+C` | Exit |

## Touchpad Modulation

| Axis | MIDI Control | Effect |
|------|--------------|--------|
| X (left/right) | Pitch Bend | ±2 semitones (configurable) |
| Y (up/down) | CC 74 | Filter cutoff / brightness |
| Pressure | CC 11 | Expression |

## Installation

### NixOS (Flake)

```bash
# Run directly
nix run github:ALH477/fw16-synth

# Or add to flake.nix
{
  inputs.fw16-synth.url = "github:ALH477/fw16-synth";
}

# Then in configuration.nix
programs.fw16-synth.enable = true;
```

### Development Shell

```bash
nix develop
python fw16_synth.py
```

### Manual Installation

```bash
# Dependencies
pip install evdev pyfluidsynth

# System packages (Debian/Ubuntu)
sudo apt install fluidsynth fluid-soundfont-gm

# System packages (Fedora)
sudo dnf install fluidsynth fluid-soundfont-gm

# Run
python fw16_synth.py --soundfont /path/to/soundfont.sf2
```

## Usage

```bash
# Basic usage (auto-detects soundfont)
fw16-synth

# Specify soundfont
fw16-synth --soundfont ~/Music/soundfonts/Nice-Keys-Ultimate.sf2

# Use JACK audio
fw16-synth --driver jack

# Start at different octave
fw16-synth --octave 3

# Start with different instrument (0=Piano, 25=Nylon Guitar, etc.)
fw16-synth --program 25

# Quiet mode (no note output)
fw16-synth --quiet
```

## Permissions

Requires access to `/dev/input/event*` devices. Options:

1. **Run as root** (not recommended)
2. **Add user to input group**:
   ```bash
   sudo usermod -aG input $USER
   # Log out and back in
   ```
3. **udev rules** (included in NixOS module):
   ```bash
   # /etc/udev/rules.d/99-fw16-synth.rules
   SUBSYSTEM=="input", GROUP="input", MODE="0660"
   ```

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                      FW16 Synth                              │
├──────────────┬───────────────────────────────────────────────┤
│   evdev      │  Direct kernel input (bypasses X11/Wayland)  │
├──────────────┼───────────────────────────────────────────────┤
│   asyncio    │  Non-blocking event processing               │
├──────────────┼───────────────────────────────────────────────┤
│  FluidSynth  │  Software synthesizer with SoundFont support │
├──────────────┼───────────────────────────────────────────────┤
│  PulseAudio  │  Audio output (or JACK/ALSA/PipeWire)        │
│  PipeWire    │                                               │
│  JACK        │                                               │
└──────────────┴───────────────────────────────────────────────┘
```

## Velocity Calculation

Note velocity is determined by the time between key release and next key press of the same key. This provides expressive control without pressure-sensitive keys.

- Fast keypress (< 10ms): Maximum velocity (127)
- Slow keypress (> 150ms): Minimum velocity (40)
- Linear interpolation between

## Troubleshooting

### "No keyboard found"
- Check `/dev/input/event*` permissions
- Ensure you're in the `input` group
- Try running with `sudo` to test

### No sound
- Check audio backend: `--driver pulseaudio` or `--driver pipewire`
- Verify soundfont exists: `--soundfont /path/to/file.sf2`
- Check volume levels in pavucontrol

### High latency
- Use JACK: `--driver jack` with low buffer sizes
- Check if PipeWire is running in low-latency mode
- Consider real-time kernel for professional use

### Touchpad not detected
- Framework 16 touchpad should auto-detect
- Check `evtest` for touchpad device
- Modulation works without touchpad (keyboard-only mode)

## License

MIT License - DeMoD LLC

## Credits

- [FluidSynth](https://www.fluidsynth.org/) - Software synthesizer
- [python-evdev](https://python-evdev.readthedocs.io/) - Linux input device access
- [pyfluidsynth](https://github.com/nwhitehead/pyfluidsynth) - Python FluidSynth bindings
