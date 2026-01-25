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
- **SoundFont Downloader** — Press `D` to download popular soundfonts from the internet
- **Bundled SoundFonts** — FluidR3_GM and GeneralUser_GS included out of the box
- **Help Overlay** — Press `?` for quick reference
- **Arpeggiator** — Press `A` to cycle through Up/Down/UpDown/Random modes
- **Layer Mode** — Press `L` to play two instruments simultaneously  
- **Transpose** — Press `Shift + </>` to transpose ±12 semitones
- **Velocity Meter** — Real-time velocity visualization
- **Chord Display** — See currently held notes
- **Favorites** — Star your favorite soundfonts

## Bundled SoundFonts

The Nix package includes high-quality soundfonts ready to use:

| SoundFont | Size | Description |
|-----------|------|-------------|
| **FluidR3_GM** | 141 MB | Industry standard General MIDI |
| **GeneralUser_GS** | 30 MB | Excellent quality, compact GM/GS set |

Press `D` in-app to download additional soundfonts including pianos, orchestras, and synths!

## Quick Start

```bash
# Run directly from GitHub (requires Nix with flakes enabled)
nix run github:ALH477/fw16-synth

# Or clone and run locally
git clone https://github.com/ALH477/fw16-synth.git
cd fw16-synth
nix flake update  # Generate/update flake.lock
nix run .

# Development shell
nix develop
python fw16_synth.py
```

### Manual Installation (without Nix)

```bash
# Install dependencies
pip install evdev pyfluidsynth

# Install FluidSynth and a SoundFont
# Debian/Ubuntu: sudo apt install fluidsynth fluid-soundfont-gm
# Fedora: sudo dnf install fluidsynth fluid-soundfont-gm
# Arch: sudo pacman -S fluidsynth soundfont-fluid

# Run
python fw16_synth.py

# Or use the launcher (does pre-flight checks)
./launch.sh
```

### Prerequisites

1. **Input group membership** (required for keyboard/touchpad access):
   ```bash
   sudo usermod -aG input $USER
   # Log out and back in
   ```

2. **Audio server**: PipeWire, PulseAudio, or JACK

3. **SoundFont**: The app auto-discovers soundfonts, or specify with `--soundfont`

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
| `D` | Open SoundFont downloader |
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

### NixOS Module

```nix
# flake.nix
{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    fw16-synth.url = "github:ALH477/fw16-synth";
  };
  
  outputs = { nixpkgs, fw16-synth, ... }: {
    nixosConfigurations.myhost = nixpkgs.lib.nixosSystem {
      modules = [
        fw16-synth.nixosModules.default
        {
          programs.fw16-synth = {
            enable = true;
            users = [ "your-username" ];
            audioDriver = "pipewire";  # or "pulseaudio", "jack", "alsa"
            enableRealtimeAudio = true;
          };
        }
      ];
    };
  };
}
```

### Home-Manager Module

```nix
# In your home.nix or home-manager flake config
{ inputs, ... }: {
  imports = [ inputs.fw16-synth.homeManagerModules.default ];
  
  programs.fw16-synth = {
    enable = true;
    audioDriver = "pipewire";
    defaultOctave = 4;
    defaultProgram = 0;  # Acoustic Grand Piano
  };
}
```

### Manual Installation

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
- `~/.local/share/soundfonts/` (download destination)
- `~/soundfonts/`
- `~/Music/soundfonts/`
- `/usr/share/soundfonts/`
- `/usr/share/sounds/sf2/`
- `/nix/store/*soundfont*/` (Nix bundled)
- Environment paths (BUNDLED_SOUNDFONTS, etc.)

State saved to `~/.config/fw16-synth/soundfonts.json`

## Downloadable SoundFonts

Press `D` to open the download browser. Available soundfonts:

### General MIDI
| Name | Size | Quality | Description |
|------|------|---------|-------------|
| FluidR3 GM | 141 MB | ★★★★★ | Industry standard, excellent across all instruments |
| GeneralUser GS | 30 MB | ★★★★★ | Compact yet high-quality GM/GS set |
| TimGM6mb | 6 MB | ★★★☆☆ | Tiny but surprisingly good for low-resource systems |

### Piano / Keys
| Name | Size | Quality | Description |
|------|------|---------|-------------|
| Salamander Grand | 440 MB | ★★★★★ | Concert Yamaha C5 with velocity layers |
| YDP Grand Piano | 37 MB | ★★★★☆ | Compact Yamaha grand piano |
| Nice Keys Suite | 69 MB | ★★★★☆ | Piano, electric piano, and organ collection |

### Orchestra / Synth
| Name | Size | Quality | Description |
|------|------|---------|-------------|
| Sonatina Orchestra | 503 MB | ★★★★★ | Full symphony with multiple articulations |
| Vintage Dreams Waves | 19 MB | ★★★★☆ | Classic analog synth sounds |

Downloads are saved to `~/.local/share/soundfonts/`

## Performance

| Component | Latency |
|-----------|---------|
| Keyboard → evdev | <1ms |
| Processing | <1ms |
| FluidSynth | 1-2ms |
| PipeWire (128 samples) | ~2.7ms |
| **Total** | **~5ms** |

## Troubleshooting

### Nix flake errors

```bash
# If you get HTTP 404 or lock file errors:
rm flake.lock
nix flake update
nix run .

# For "cannot write lock file" errors:
nix run . --no-write-lock-file
```

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
