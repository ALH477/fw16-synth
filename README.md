# FW16 Synth v2.0

```
╔══════════════════════════════════════════════════════════════════════════════╗
║ ∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿ ║
║                                                                              ║
║  ███████╗██╗    ██╗ ██╗ ██████╗     ███████╗██╗   ██╗███╗   ██╗████████╗██╗  ██╗  ║
║  ██╔════╝██║    ██║███║██╔════╝     ██╔════╝╚██╗ ██╔╝████╗  ██║╚══██╔══╝██║  ██║  ║
║  █████╗  ██║ █╗ ██║╚██║███████╗     ███████╗ ╚████╔╝ ██╔██╗ ██║   ██║   ███████║  ║
║  ██╔══╝  ██║███╗██║ ██║██╔═══██╗    ╚════██║  ╚██╔╝  ██║╚██╗██║   ██║   ██╔══██║  ║
║  ██║     ╚███╔███╔╝ ██║╚██████╔╝    ███████║   ██║   ██║ ╚████║   ██║   ██║  ██║  ║
║  ╚═╝      ╚══╝╚══╝  ╚═╝ ╚═════╝     ╚══════╝   ╚═╝   ╚═╝  ╚═══╝   ╚═╝   ╚═╝  ╚═╝  ║
║                                                                              ║
║                     ──────── ╭─────╮╭╮╭──╮╭╮╭─────╮ ────────                 ║
║                                                                              ║
║          ██████╗ ███████╗███╗   ███╗ ██████╗ ██████╗                         ║
║          ██╔══██╗██╔════╝████╗ ████║██╔═══██╗██╔══██╗                        ║
║          ██║  ██║█████╗  ██╔████╔██║██║   ██║██║  ██║                        ║
║          ██║  ██║██╔══╝  ██║╚██╔╝██║██║   ██║██║  ██║                        ║
║          ██████╔╝███████╗██║ ╚═╝ ██║╚██████╔╝██████╔╝                        ║
║          ╚═════╝ ╚══════╝╚═╝     ╚═╝ ╚═════╝ ╚═════╝                         ║
║                                                                              ║
║                        « Design ≠ Marketing »                                ║
║                                                                              ║
║  ┃█┃█┃┃█┃█┃█┃┃█┃█┃┃█┃█┃█┃┃█┃█┃┃█┃█┃█┃┃█┃█┃┃█┃█┃█┃┃█┃█┃┃█┃█┃█┃┃█┃█┃┃█┃█┃█┃  ║
║ ∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿ ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

**Transform your Framework 16 into a professional synthesizer.**

A low-latency FluidSynth controller with real-time TUI, SoundFont browser, arpeggiator, layer mode, and touchpad modulation. Built for performance.

![Version](https://img.shields.io/badge/version-2.0-00D7AF)
![NixOS](https://img.shields.io/badge/NixOS-ready-5277C3)
![License](https://img.shields.io/badge/license-MIT-AF5FFF)

## What's New in v2.0

- **SoundFont Browser** — Press `Tab` to browse, preview, and load soundfonts
- **Help Overlay** — Press `?` for quick reference
- **Arpeggiator** — Press `A` to cycle through Up/Down/UpDown/Random modes
- **Layer Mode** — Press `L` to play two instruments simultaneously  
- **Transpose** — Press `Shift + </>` to transpose ±12 semitones
- **Velocity Meter** — Real-time velocity visualization
- **Chord Display** — See currently held notes
- **Favorites** — Star your favorite soundfonts

## Quick Start

```bash
# NixOS / Nix
nix run github:your-repo/fw16-synth

# Development
nix develop
python fw16_synth.py

# Manual
pip install evdev pyfluidsynth
python fw16_synth.py
```

## Screenshot

```
╔═══ FW16 SYNTH ═══════════════════════════════════ FluidR3_GM ═══╗
║ Oct:4 T:+0 │ Prog:000 Acoustic Grand     │  SUS   LYR  ARP:---  TCH ║
╟──────────────────────────────────────────────────────────────────────╢
║ [`][1][2][3][4][5][6][7][8][9][0][-][=][⌫]                          ║
║ [⇥][Q][W][E][R][T][Y][U][I][O][P][[][]][\\]                          ║
║ [⇪][A][S][D][F][G][H][J][K][L][;]['][↵]                             ║
║ [⇧][Z][X][C][V][B][N][M][,][.][/][⇧]                                ║
║ [Ctrl] [❖] [Alt]  [━━━━━ SUSTAIN ━━━━━]  [Alt] [Fn] [Ctrl]          ║
╟──────────────────────────────────────────────────────────────────────╢
║  ·····+·····│·····  │ ├─ Meters ─┤                                  ║
║  ·····│·····│·····  │ Vel  ████████ 98                              ║
║  ─────●─────│─────  │ Bend ████░░░░ +25%                            ║
║  ·····│·····│·····  │ Filt ██████░░  89                             ║
║  ·····+·····│·····  │ Expr ████████ 112                             ║
║   Touchpad (X=Bend) │ Chord: C4 E4 G4                               ║
╟──────────────────────────────────────────────────────────────────────╢
║ 14:32:05 Program → 0: Acoustic Grand                                ║
║ 14:32:08 ♪ C4 ON  vel=98                                            ║
╟──────────────────────────────────────────────────────────────────────╢
║ [?] Help  [Tab] SoundFonts  [+/-] Oct  [</>] Transpose  [L] Layer   ║
╚══════════════════════════════════════════════════════════════════════╝
```

## Controls

### Keyboard Layout

```
┌───────────────────────────────────────────────────────────────────┐
│  `   1   2   3   4   5   6   7   8   9   0   -   =   ⌫           │
│          C#  D#      F#  G#  A#      C#  D#  Oct Oct              │
├───────────────────────────────────────────────────────────────────┤
│  ⇥   Q   W   E   R   T   Y   U   I   O   P   [   ]   \           │
│      C   D   E   F   G   A   B   C   D   E   F   G                │
│                    Main Octave                                    │
├───────────────────────────────────────────────────────────────────┤
│  ⇪   A   S   D   F   G   H   J   K   L   ;   '   ↵               │
│      C   D   E   F   G   A   B   C   D   E   F                    │
│                    Lower Octave (-1)                              │
├───────────────────────────────────────────────────────────────────┤
│  ⇧   Z   X   C   V   B   N   M   ,   .   /   ⇧                   │
│      C   D   E   F   G   A   B   C   D   E                        │
│                    Bass Octave (-2)                               │
├───────────────────────────────────────────────────────────────────┤
│  Ctrl  ❖  Alt  ━━━━━━━━ SUSTAIN ━━━━━━━━  Alt  Fn  Ctrl          │
└───────────────────────────────────────────────────────────────────┘
```

### Control Keys

| Key | Function |
|-----|----------|
| `Space` | Sustain pedal |
| `+` / `-` | Octave up/down |
| `Shift + <` | Transpose down |
| `Shift + >` | Transpose up |
| `Page Up/Down` | Previous/next instrument |
| `F1-F12` | Quick presets |
| `Tab` | Open SoundFont browser |
| `L` | Toggle layer mode |
| `A` | Cycle arpeggiator modes |
| `?` | Show help overlay |
| `Esc` | Panic (all notes off) |
| `Ctrl+C` | Exit |

### Presets (F1-F12)

| Key | Instrument | Key | Instrument |
|-----|------------|-----|------------|
| F1 | Acoustic Grand | F7 | Brass Section |
| F2 | Electric Piano 1 | F8 | Tenor Sax |
| F3 | Drawbar Organ | F9 | Flute |
| F4 | Nylon Guitar | F10 | Saw Lead |
| F5 | Synth Strings | F11 | Warm Pad |
| F6 | Choir Aahs | F12 | Atmosphere |

## Features

### SoundFont Browser

Press `Tab` to open the browser:

```
╔══════════════════════════════════════════════════════════════════╗
║                      SOUNDFONT BROWSER                           ║
║     [↑/↓] Select  [Enter] Load  [F] Favorite  [Tab/Esc] Close    ║
╟──────────────────────────────────────────────────────────────────╢
║ ▶ ★ FluidR3_GM                                           140.2MB ║
║   ★ GeneralUser_GS                                        29.8MB ║
║     Arachno_SoundFont                                    148.1MB ║
║     Nice-Keys-Ultimate                                    52.3MB ║
║     SGM-V2.01                                            235.8MB ║
╟──────────────────────────────────────────────────────────────────╢
║ /usr/share/soundfonts/FluidR3_GM.sf2                             ║
╚══════════════════════════════════════════════════════════════════╝
```

Features:
- Auto-scans common locations (`~/.local/share/soundfonts`, `/usr/share/soundfonts`, Nix store)
- Favorites persist across sessions (★ indicator)
- Recent files remembered
- Hot-reload without stopping playback
- File size display

### Arpeggiator

Press `A` to cycle modes:
- **OFF** — Normal playing
- **UP** — Ascending arpeggio
- **DOWN** — Descending arpeggio  
- **UP_DOWN** — Alternating direction
- **RANDOM** — Random note selection

Hold notes and they'll be arpeggiated automatically.

### Layer Mode

Press `L` to enable layering. Plays two instruments simultaneously:
- Main: Current program
- Layer: Strings (program 48)

Great for creating rich, full sounds.

### Touchpad Modulation

| Axis | MIDI Control | Effect |
|------|--------------|--------|
| **X** (horizontal) | Pitch Bend | ±2 semitones |
| **Y** (vertical) | CC 74 | Filter cutoff |
| **Pressure** | CC 11 | Expression |

Visual feedback in the TUI shows current position and values.

## Installation

### NixOS

```nix
# flake.nix
{
  inputs.fw16-synth.url = "github:your-repo/fw16-synth";
}

# configuration.nix
{ inputs, ... }: {
  imports = [ inputs.fw16-synth.nixosModules.default ];
  
  programs.fw16-synth = {
    enable = true;
    users = [ "your-username" ];
    audioDriver = "pipewire";
  };
}
```

### Home-Manager

```nix
programs.fw16-synth = {
  enable = true;
  defaultOctave = 4;
};
```

### Manual

```bash
# Debian/Ubuntu
sudo apt install fluidsynth fluid-soundfont-gm
pip install evdev pyfluidsynth

# Arch
sudo pacman -S fluidsynth soundfont-fluid
pip install evdev pyfluidsynth

# Run
python fw16_synth.py
```

### Device Access

```bash
# Add to input group
sudo usermod -aG input $USER
# Log out and back in
```

## Command Line

```
usage: fw16_synth.py [-h] [--soundfont PATH] [--driver DRIVER]
                     [--octave N] [--program N] [--velocity N]
                     [--no-tui] [--verbose] [--log-file PATH]

Options:
  --soundfont, -s   SoundFont file (.sf2)
  --driver, -d      Audio: pipewire, pulseaudio, jack, alsa
  --octave, -o      Starting octave (0-8, default: 4)
  --program, -p     Starting program (0-127, default: 0)
  --velocity        Fixed velocity (disables dynamic)
  --no-tui          Text-only mode
  --verbose, -v     Debug logging
```

## SoundFont Locations

The browser searches:
- `~/.local/share/soundfonts/`
- `~/soundfonts/`
- `~/Music/soundfonts/`
- `/usr/share/soundfonts/`
- `/usr/share/sounds/sf2/`
- `/nix/store/*soundfont*/` (Nix)

State saved to `~/.config/fw16-synth/soundfonts.json`

## Performance

| Component | Latency |
|-----------|---------|
| Keyboard → evdev | <1ms |
| Processing | <1ms |
| FluidSynth | 1-2ms |
| PipeWire (128 samples) | ~2.7ms |
| **Total** | **~5ms** |

## Troubleshooting

### No input devices

```bash
# Check permissions
ls -la /dev/input/event*

# Test device access
evtest

# Verify group membership
groups | grep input
```

### No sound

```bash
# Test audio
pactl info  # PulseAudio/PipeWire
jack_lsp    # JACK

# Test FluidSynth directly
fluidsynth -a pulseaudio /usr/share/soundfonts/FluidR3_GM.sf2
```

### SoundFonts not found

```bash
# Check search paths
ls ~/.local/share/soundfonts/
ls /usr/share/soundfonts/

# Specify directly
fw16-synth --soundfont /path/to/soundfont.sf2
```

## Development

```bash
nix develop

# Run with debug
python fw16_synth.py --verbose

# Format
black fw16_synth.py

# Type check
mypy fw16_synth.py
```

## License

MIT License — DeMoD LLC

---

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║          ██████╗ ███████╗███╗   ███╗ ██████╗ ██████╗                         ║
║          ██╔══██╗██╔════╝████╗ ████║██╔═══██╗██╔══██╗                        ║
║          ██║  ██║█████╗  ██╔████╔██║██║   ██║██║  ██║                        ║
║          ██║  ██║██╔══╝  ██║╚██╔╝██║██║   ██║██║  ██║                        ║
║          ██████╔╝███████╗██║ ╚═╝ ██║╚██████╔╝██████╔╝                        ║
║          ╚═════╝ ╚══════╝╚═╝     ╚═╝ ╚═════╝ ╚═════╝                         ║
║                                                                              ║
║                    ╭──────────────────────────────╮                          ║
║                    │    « Design ≠ Marketing »    │                          ║
║                    ╰──────────────────────────────╯                          ║
║                                                                              ║
║  ┃█┃█┃┃█┃█┃█┃┃█┃█┃┃█┃█┃█┃┃█┃█┃┃█┃█┃█┃┃█┃█┃┃█┃█┃█┃┃█┃█┃┃█┃█┃█┃┃█┃█┃┃█┃█┃█┃  ║
║                                                                              ║
║  ∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿  ║
╚══════════════════════════════════════════════════════════════════════════════╝
```
