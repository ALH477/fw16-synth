#!/usr/bin/env python3
"""
FW16 Synth - Professional FluidSynth Controller for Framework 16
=================================================================
Transforms the Framework 16 laptop into a performance synthesizer.

Features:
  - Low-latency evdev input (bypasses display server)
  - Real-time TUI with keyboard visualization
  - Soundfont browser with hot-reload
  - Touchpad XY modulation with configurable CC mapping
  - Velocity sensitivity via keypress timing
  - Full GM instrument set with quick-access presets
  - Transpose, layer, and arpeggiator modes
  - Smooth parameter interpolation (anti-zipper)
  - Built-in help overlay

DeMoD LLC - Design ≠ Marketing
"""

from __future__ import annotations

import asyncio
import sys
import os
import time
import signal
import argparse
import logging
import threading
import json
import glob
import subprocess
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Callable, Tuple, Set, Any, Union
from enum import IntEnum, Enum, auto
from pathlib import Path
from contextlib import contextmanager
from collections import deque
import math

# =============================================================================
# DEPENDENCY HANDLING
# =============================================================================

def check_dependencies() -> Tuple[bool, List[str]]:
    """Check for required dependencies and return status"""
    missing = []
    
    try:
        import evdev
    except ImportError:
        missing.append("evdev (pip install evdev)")
    
    try:
        import fluidsynth
    except ImportError:
        missing.append("pyfluidsynth (pip install pyfluidsynth)")
    
    return len(missing) == 0, missing


_deps_ok, _missing_deps = check_dependencies()
if not _deps_ok:
    print("\n╔══════════════════════════════════════════════════════════════╗")
    print("║  FW16 Synth - Missing Dependencies                           ║")
    print("╠══════════════════════════════════════════════════════════════╣")
    for dep in _missing_deps:
        print(f"║  • {dep:<56} ║")
    print("╠══════════════════════════════════════════════════════════════╣")
    print("║  Install with: pip install evdev pyfluidsynth                ║")
    print("║  Or use: nix develop                                         ║")
    print("╚══════════════════════════════════════════════════════════════╝\n")
    sys.exit(1)

import evdev
from evdev import ecodes, InputDevice
import fluidsynth

# Optional MIDI input support (for FW16 Piano Keyboard Module and other USB MIDI devices)
try:
    import rtmidi
    RTMIDI_AVAILABLE = True
except ImportError:
    RTMIDI_AVAILABLE = False


# =============================================================================
# LOGGING
# =============================================================================

class ColorFormatter(logging.Formatter):
    """Colored log formatter"""
    COLORS = {
        'DEBUG': '\033[38;5;244m',
        'INFO': '\033[38;5;44m',
        'WARNING': '\033[38;5;214m',
        'ERROR': '\033[38;5;196m',
        'CRITICAL': '\033[38;5;196;1m',
    }
    RESET = '\033[0m'
    
    def format(self, record):
        color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        return super().format(record)


def setup_logging(verbose: bool = False, log_file: Optional[Path] = None) -> logging.Logger:
    """Configure logging"""
    logger = logging.getLogger('fw16synth')
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    
    console = logging.StreamHandler()
    console.setFormatter(ColorFormatter('%(levelname)s %(message)s'))
    logger.addHandler(console)
    
    if log_file:
        fh = logging.FileHandler(log_file)
        fh.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s'))
        logger.addHandler(fh)
    
    return logger


log = logging.getLogger('fw16synth')


# =============================================================================
# ENUMS & CONSTANTS
# =============================================================================

class AudioDriver(str, Enum):
    # Note: PipeWire provides PulseAudio compatibility, so we use "pulseaudio" driver
    PIPEWIRE = "pulseaudio"  # PipeWire via PulseAudio compatibility
    PULSEAUDIO = "pulseaudio"
    JACK = "jack"
    ALSA = "alsa"


class ModSource(Enum):
    TOUCHPAD_X = auto()
    TOUCHPAD_Y = auto()
    TOUCHPAD_PRESSURE = auto()


class ModDest(Enum):
    PITCH_BEND = auto()
    MOD_WHEEL = auto()
    BREATH = auto()
    EXPRESSION = auto()
    FILTER_CUTOFF = auto()
    FILTER_RESONANCE = auto()
    ATTACK = auto()
    RELEASE = auto()


class UIMode(Enum):
    """UI display modes"""
    NORMAL = auto()
    HELP = auto()
    SOUNDFONT_BROWSER = auto()
    DOWNLOAD_BROWSER = auto()
    PROGRAM_BROWSER = auto()
    DOWNLOADING = auto()


class ArpMode(Enum):
    """Arpeggiator modes"""
    OFF = auto()
    UP = auto()
    DOWN = auto()
    UP_DOWN = auto()
    RANDOM = auto()


MOD_DEST_CC: Dict[ModDest, int] = {
    ModDest.MOD_WHEEL: 1,
    ModDest.BREATH: 2,
    ModDest.EXPRESSION: 11,
    ModDest.FILTER_CUTOFF: 74,
    ModDest.FILTER_RESONANCE: 71,
    ModDest.ATTACK: 73,
    ModDest.RELEASE: 72,
}

# GM Instrument Names
GM_INSTRUMENTS: List[str] = [
    # Piano (0-7)
    "Acoustic Grand", "Bright Acoustic", "Electric Grand", "Honky-Tonk",
    "Electric Piano 1", "Electric Piano 2", "Harpsichord", "Clavinet",
    # Chromatic Percussion (8-15)
    "Celesta", "Glockenspiel", "Music Box", "Vibraphone",
    "Marimba", "Xylophone", "Tubular Bells", "Dulcimer",
    # Organ (16-23)
    "Drawbar Organ", "Percussive Organ", "Rock Organ", "Church Organ",
    "Reed Organ", "Accordion", "Harmonica", "Tango Accordion",
    # Guitar (24-31)
    "Nylon Guitar", "Steel Guitar", "Jazz Guitar", "Clean Guitar",
    "Muted Guitar", "Overdriven Guitar", "Distortion Guitar", "Guitar Harmonics",
    # Bass (32-39)
    "Acoustic Bass", "Finger Bass", "Pick Bass", "Fretless Bass",
    "Slap Bass 1", "Slap Bass 2", "Synth Bass 1", "Synth Bass 2",
    # Strings (40-47)
    "Violin", "Viola", "Cello", "Contrabass",
    "Tremolo Strings", "Pizzicato Strings", "Orchestral Harp", "Timpani",
    # Ensemble (48-55)
    "String Ensemble 1", "String Ensemble 2", "Synth Strings 1", "Synth Strings 2",
    "Choir Aahs", "Voice Oohs", "Synth Voice", "Orchestra Hit",
    # Brass (56-63)
    "Trumpet", "Trombone", "Tuba", "Muted Trumpet",
    "French Horn", "Brass Section", "Synth Brass 1", "Synth Brass 2",
    # Reed (64-71)
    "Soprano Sax", "Alto Sax", "Tenor Sax", "Baritone Sax",
    "Oboe", "English Horn", "Bassoon", "Clarinet",
    # Pipe (72-79)
    "Piccolo", "Flute", "Recorder", "Pan Flute",
    "Blown Bottle", "Shakuhachi", "Whistle", "Ocarina",
    # Synth Lead (80-87)
    "Lead 1 (square)", "Lead 2 (sawtooth)", "Lead 3 (calliope)", "Lead 4 (chiff)",
    "Lead 5 (charang)", "Lead 6 (voice)", "Lead 7 (fifths)", "Lead 8 (bass+lead)",
    # Synth Pad (88-95)
    "Pad 1 (new age)", "Pad 2 (warm)", "Pad 3 (polysynth)", "Pad 4 (choir)",
    "Pad 5 (bowed)", "Pad 6 (metallic)", "Pad 7 (halo)", "Pad 8 (sweep)",
    # Synth Effects (96-103)
    "FX 1 (rain)", "FX 2 (soundtrack)", "FX 3 (crystal)", "FX 4 (atmosphere)",
    "FX 5 (brightness)", "FX 6 (goblins)", "FX 7 (echoes)", "FX 8 (sci-fi)",
    # Ethnic (104-111)
    "Sitar", "Banjo", "Shamisen", "Koto",
    "Kalimba", "Bagpipe", "Fiddle", "Shanai",
    # Percussive (112-119)
    "Tinkle Bell", "Agogo", "Steel Drums", "Woodblock",
    "Taiko Drum", "Melodic Tom", "Synth Drum", "Reverse Cymbal",
    # Sound Effects (120-127)
    "Guitar Fret Noise", "Breath Noise", "Seashore", "Bird Tweet",
    "Telephone Ring", "Helicopter", "Applause", "Gunshot",
]

# GM Instrument Categories
GM_CATEGORIES = [
    ("Piano", 0, 7),
    ("Chromatic Perc", 8, 15),
    ("Organ", 16, 23),
    ("Guitar", 24, 31),
    ("Bass", 32, 39),
    ("Strings", 40, 47),
    ("Ensemble", 48, 55),
    ("Brass", 56, 63),
    ("Reed", 64, 71),
    ("Pipe", 72, 79),
    ("Synth Lead", 80, 87),
    ("Synth Pad", 88, 95),
    ("Synth FX", 96, 103),
    ("Ethnic", 104, 111),
    ("Percussive", 112, 119),
    ("Sound FX", 120, 127),
]


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class ModulationRouting:
    source: ModSource
    destination: ModDest
    amount: float = 1.0
    invert: bool = False
    center: float = 0.5


@dataclass
class PresetConfig:
    name: str
    program: int
    bank: int = 0
    hotkey: Optional[int] = None


@dataclass
class SynthConfig:
    # Audio
    audio_driver: AudioDriver = AudioDriver.PIPEWIRE
    sample_rate: int = 48000
    buffer_size: int = 256
    soundfont: Optional[str] = None
    
    # MIDI
    midi_channel: int = 0
    
    # Keyboard
    base_octave: int = 4
    velocity_curve: str = "linear"
    velocity_min: int = 20
    velocity_max: int = 127
    velocity_fixed: Optional[int] = None
    velocity_time_fast: float = 0.015
    velocity_time_slow: float = 0.200
    
    # Touchpad
    touchpad_enabled: bool = True
    touchpad_smoothing: float = 0.85
    
    # Modulation routing
    mod_routing: List[ModulationRouting] = field(default_factory=lambda: [
        ModulationRouting(ModSource.TOUCHPAD_X, ModDest.PITCH_BEND),
        ModulationRouting(ModSource.TOUCHPAD_Y, ModDest.FILTER_CUTOFF, invert=True),
        ModulationRouting(ModSource.TOUCHPAD_PRESSURE, ModDest.EXPRESSION),
    ])
    
    pitch_bend_semitones: int = 2
    
    # Presets
    presets: List[PresetConfig] = field(default_factory=lambda: [
        PresetConfig("Grand Piano", 0, hotkey=ecodes.KEY_F1),
        PresetConfig("Electric Piano", 4, hotkey=ecodes.KEY_F2),
        PresetConfig("Drawbar Organ", 16, hotkey=ecodes.KEY_F3),
        PresetConfig("Nylon Guitar", 24, hotkey=ecodes.KEY_F4),
        PresetConfig("Synth Strings", 50, hotkey=ecodes.KEY_F5),
        PresetConfig("Choir Aahs", 52, hotkey=ecodes.KEY_F6),
        PresetConfig("Brass Section", 61, hotkey=ecodes.KEY_F7),
        PresetConfig("Tenor Sax", 66, hotkey=ecodes.KEY_F8),
        PresetConfig("Flute", 73, hotkey=ecodes.KEY_F9),
        PresetConfig("Saw Lead", 81, hotkey=ecodes.KEY_F10),
        PresetConfig("Warm Pad", 89, hotkey=ecodes.KEY_F11),
        PresetConfig("Atmosphere", 99, hotkey=ecodes.KEY_F12),
    ])
    
    # Display
    show_tui: bool = True
    refresh_rate: float = 30.0
    
    # Features
    enable_arpeggiator: bool = True
    enable_transpose: bool = True
    enable_layer: bool = True
    
    # MIDI Input (for FW16 Piano Keyboard Module and other USB MIDI devices)
    midi_input_enabled: bool = False
    midi_port: Optional[str] = None  # Port name substring or None for auto-detect
    midi_auto_connect: bool = True   # Auto-connect to FW16 module if found


# =============================================================================
# SOUNDFONT MANAGER
# =============================================================================

@dataclass
class SoundFontInfo:
    """Information about a soundfont file"""
    path: Path
    name: str
    size_mb: float
    presets: int = 0
    favorite: bool = False
    last_used: Optional[float] = None
    
    @classmethod
    def from_path(cls, path: Path) -> 'SoundFontInfo':
        """Create SoundFontInfo from a file path"""
        size_mb = path.stat().st_size / (1024 * 1024)
        name = path.stem
        return cls(path=path, name=name, size_mb=size_mb)


class SoundFontManager:
    """
    Manages soundfont discovery, loading, and hot-swapping.
    """
    
    # Common soundfont search paths
    SEARCH_PATHS = [
        Path.home() / ".local/share/soundfonts",
        Path.home() / "soundfonts",
        Path.home() / "Music/soundfonts",
        Path("/usr/share/soundfonts"),
        Path("/usr/share/sounds/sf2"),
        Path("/usr/local/share/soundfonts"),
        Path("/nix/store"),  # Nix store (will glob for *soundfont*)
    ]
    
    STATE_FILE = Path.home() / ".config/fw16-synth/soundfonts.json"
    
    def __init__(self):
        self.soundfonts: List[SoundFontInfo] = []
        self.current: Optional[SoundFontInfo] = None
        self.favorites: Set[str] = set()
        self.recent: List[str] = []
        self._extra_paths: List[Path] = []
        
        # Add paths from environment variables (set by Nix wrapper)
        for env_var in ['BUNDLED_SOUNDFONTS', 'NIX_SOUNDFONT_FLUID', 
                        'NIX_SOUNDFONT_GENERALUSER', 'DEFAULT_SOUNDFONT']:
            env_path = os.environ.get(env_var)
            if env_path:
                p = Path(env_path)
                # If it's a file, use the parent directory
                if p.is_file():
                    p = p.parent
                if p.exists() and p not in self._extra_paths:
                    self._extra_paths.append(p)
                    log.debug(f"Added soundfont path from {env_var}: {p}")
        
        self._load_state()
    
    def _load_state(self):
        """Load favorites and recent from state file"""
        try:
            if self.STATE_FILE.exists():
                with open(self.STATE_FILE) as f:
                    data = json.load(f)
                    self.favorites = set(data.get('favorites', []))
                    self.recent = data.get('recent', [])[:10]
        except Exception as e:
            log.debug(f"Could not load soundfont state: {e}")
    
    def _save_state(self):
        """Save favorites and recent to state file"""
        try:
            self.STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(self.STATE_FILE, 'w') as f:
                json.dump({
                    'favorites': list(self.favorites),
                    'recent': self.recent[:10],
                }, f, indent=2)
        except Exception as e:
            log.debug(f"Could not save soundfont state: {e}")
    
    def scan(self) -> List[SoundFontInfo]:
        """Scan for available soundfonts"""
        found: Dict[str, SoundFontInfo] = {}
        
        # Combine standard paths with environment-provided paths
        all_paths = list(self.SEARCH_PATHS) + self._extra_paths
        
        for base_path in all_paths:
            try:
                if not base_path.exists():
                    continue
                
                # Special handling for Nix store
                if str(base_path) == "/nix/store":
                    patterns = [
                        "/nix/store/*soundfont*/**/*.sf2",
                        "/nix/store/*soundfont*/**/*.SF2",
                    ]
                    for pattern in patterns:
                        for sf_path in glob.glob(pattern, recursive=True):
                            path = Path(sf_path)
                            if path.is_file() and str(path) not in found:
                                try:
                                    info = SoundFontInfo.from_path(path)
                                    info.favorite = str(path) in self.favorites
                                    found[str(path)] = info
                                except Exception:
                                    pass
                else:
                    # Standard directory search
                    for pattern in ['*.sf2', '*.SF2', '**/*.sf2', '**/*.SF2']:
                        for sf_path in base_path.glob(pattern):
                            if sf_path.is_file() and str(sf_path) not in found:
                                try:
                                    info = SoundFontInfo.from_path(sf_path)
                                    info.favorite = str(sf_path) in self.favorites
                                    found[str(sf_path)] = info
                                except Exception:
                                    pass
            except Exception as e:
                log.debug(f"Error scanning {base_path}: {e}")
        
        # Sort: favorites first, then by name
        self.soundfonts = sorted(
            found.values(),
            key=lambda sf: (not sf.favorite, sf.name.lower())
        )
        
        log.info(f"Found {len(self.soundfonts)} soundfonts")
        return self.soundfonts
    
    def find_default(self) -> Optional[Path]:
        """Find the best default soundfont"""
        # Check recent first
        for path_str in self.recent:
            path = Path(path_str)
            if path.exists():
                return path
        
        # Scan if needed
        if not self.soundfonts:
            self.scan()
        
        # Prefer FluidR3
        for sf in self.soundfonts:
            if 'fluid' in sf.name.lower() and 'gm' in sf.name.lower():
                return sf.path
        
        # Any soundfont
        if self.soundfonts:
            return self.soundfonts[0].path
        
        return None
    
    def set_current(self, path: Path):
        """Set current soundfont and update recent list"""
        path_str = str(path)
        
        # Find or create info
        for sf in self.soundfonts:
            if str(sf.path) == path_str:
                self.current = sf
                break
        else:
            self.current = SoundFontInfo.from_path(path)
        
        # Update recent list
        if path_str in self.recent:
            self.recent.remove(path_str)
        self.recent.insert(0, path_str)
        self.recent = self.recent[:10]
        
        self._save_state()
    
    def toggle_favorite(self, path: Path) -> bool:
        """Toggle favorite status for a soundfont"""
        path_str = str(path)
        
        if path_str in self.favorites:
            self.favorites.discard(path_str)
            is_fav = False
        else:
            self.favorites.add(path_str)
            is_fav = True
        
        # Update info
        for sf in self.soundfonts:
            if str(sf.path) == path_str:
                sf.favorite = is_fav
                break
        
        self._save_state()
        return is_fav
    
    def get_categorized(self) -> Dict[str, List[SoundFontInfo]]:
        """Get soundfonts organized by category"""
        categories: Dict[str, List[SoundFontInfo]] = {
            '★ Favorites': [],
            '◷ Recent': [],
            '📁 All': [],
        }
        
        recent_paths = set(self.recent[:5])
        
        for sf in self.soundfonts:
            if sf.favorite:
                categories['★ Favorites'].append(sf)
            if str(sf.path) in recent_paths:
                categories['◷ Recent'].append(sf)
            categories['📁 All'].append(sf)
        
        return {k: v for k, v in categories.items() if v}


# =============================================================================
# SOUNDFONT DOWNLOAD CATALOG
# =============================================================================

@dataclass
class SoundFontDownload:
    """Information about a downloadable soundfont"""
    name: str
    url: str
    filename: str
    size_mb: float
    description: str
    license: str
    quality: int  # 1-5 stars
    category: str  # "General MIDI", "Piano", "Orchestra", etc.


# Catalog of free, high-quality soundfonts
SOUNDFONT_CATALOG: List[SoundFontDownload] = [
    # ═══════════════════════════════════════════════════════════════════════════
    # General MIDI (Full GM sets)
    # ═══════════════════════════════════════════════════════════════════════════
    SoundFontDownload(
        name="FluidR3 GM",
        url="https://keymusician01.s3.amazonaws.com/FluidR3_GM.sf2",
        filename="FluidR3_GM.sf2",
        size_mb=141.0,
        description="Industry standard General MIDI soundfont. Excellent quality across all instruments.",
        license="MIT",
        quality=5,
        category="General MIDI",
    ),
    SoundFontDownload(
        name="GeneralUser GS",
        url="https://www.schristiancollins.com/soundfonts/GeneralUser_GS.sf2",
        filename="GeneralUser_GS.sf2",
        size_mb=29.8,
        description="Compact, high-quality GM/GS set. Great balance of size and quality.",
        license="Free (GeneralUser License)",
        quality=5,
        category="General MIDI",
    ),
    SoundFontDownload(
        name="TimGM6mb",
        url="https://sourceforge.net/p/mscore/code/HEAD/tree/trunk/mscore/share/sound/TimGM6mb.sf2?format=raw",
        filename="TimGM6mb.sf2",
        size_mb=5.7,
        description="Tiny but surprisingly good. Perfect for low-resource systems.",
        license="GPL",
        quality=3,
        category="General MIDI",
    ),
    SoundFontDownload(
        name="Arachno SoundFont",
        url="https://www.arachnosoft.com/main/download.php?id=soundfont-sf2",
        filename="Arachno.sf2",
        size_mb=150.0,
        description="Professional-grade GM set with enhanced instruments.",
        license="Freeware",
        quality=5,
        category="General MIDI",
    ),
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Piano / Keys
    # ═══════════════════════════════════════════════════════════════════════════
    SoundFontDownload(
        name="Salamander Grand Piano",
        url="https://freepats.zenvoid.org/Piano/SalamanderGrandPiano/SalamanderGrandPianoV3+20161209_48khz24bit.tar.xz",
        filename="SalamanderGrandPiano.tar.xz",
        size_mb=440.0,
        description="Concert Yamaha C5 grand piano. Stunning realism with velocity layers.",
        license="CC BY 3.0",
        quality=5,
        category="Piano",
    ),
    SoundFontDownload(
        name="Yamaha C5 Grand (Compact)",
        url="https://musical-artifacts.com/artifacts/433/YDP-GrandPiano-20160804.sf2",
        filename="YDP-GrandPiano.sf2",
        size_mb=37.0,
        description="Compact Yamaha grand piano with good velocity response.",
        license="CC0",
        quality=4,
        category="Piano",
    ),
    SoundFontDownload(
        name="Nice Keys Suite",
        url="https://musical-artifacts.com/artifacts/671/Nice-Keys-Suite-V1.sf2",
        filename="Nice-Keys-Suite.sf2",
        size_mb=69.0,
        description="Collection of high-quality piano, electric piano, and organ sounds.",
        license="CC BY 4.0",
        quality=4,
        category="Piano",
    ),
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Orchestra / Strings
    # ═══════════════════════════════════════════════════════════════════════════
    SoundFontDownload(
        name="Sonatina Symphonic Orchestra",
        url="https://ftp.osuosl.org/pub/musescore/soundfont/Sonatina_Symphonic_Orchestra_SF2.zip",
        filename="Sonatina_Symphonic_Orchestra.zip",
        size_mb=503.0,
        description="Full symphony orchestra with multiple articulations.",
        license="CC BY 3.0",
        quality=5,
        category="Orchestra",
    ),
    SoundFontDownload(
        name="Strings Section",
        url="https://musical-artifacts.com/artifacts/1205/StringEnsemble.sf2",
        filename="StringEnsemble.sf2",
        size_mb=12.0,
        description="Beautiful string ensemble for layering.",
        license="Public Domain",
        quality=4,
        category="Orchestra",
    ),
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Synth / Electronic
    # ═══════════════════════════════════════════════════════════════════════════
    SoundFontDownload(
        name="Vintage Dreams Waves",
        url="https://musical-artifacts.com/artifacts/23/Vintage_Dreams_Waves_v2.sf2",
        filename="Vintage_Dreams_Waves.sf2",
        size_mb=19.0,
        description="Classic analog synth sounds: pads, leads, basses.",
        license="CC BY 4.0",
        quality=4,
        category="Synth",
    ),
    SoundFontDownload(
        name="SynthPad Collection",
        url="https://musical-artifacts.com/artifacts/1371/Pads.sf2",
        filename="Pads.sf2",
        size_mb=8.5,
        description="Atmospheric pads and textures.",
        license="Public Domain",
        quality=3,
        category="Synth",
    ),
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Guitar / Bass
    # ═══════════════════════════════════════════════════════════════════════════
    SoundFontDownload(
        name="Acoustic Guitar",
        url="https://musical-artifacts.com/artifacts/1089/Acoustic_Guitar.sf2",
        filename="Acoustic_Guitar.sf2",
        size_mb=24.0,
        description="Nylon and steel string acoustic guitars.",
        license="CC BY 4.0",
        quality=4,
        category="Guitar",
    ),
    SoundFontDownload(
        name="Electric Bass Collection",
        url="https://musical-artifacts.com/artifacts/682/Electric_Bass.sf2",
        filename="Electric_Bass.sf2",
        size_mb=15.0,
        description="Fingered, picked, and slap bass sounds.",
        license="CC BY 4.0",
        quality=4,
        category="Bass",
    ),
]


class SoundFontDownloader:
    """
    Manages downloading soundfonts from the internet.
    Downloads to ~/.local/share/soundfonts/
    """
    
    DOWNLOAD_DIR = Path.home() / ".local/share/soundfonts"
    CATALOG_CACHE = Path.home() / ".config/fw16-synth/download_cache.json"
    
    def __init__(self):
        self.catalog = SOUNDFONT_CATALOG
        self.download_dir = self.DOWNLOAD_DIR
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self._in_progress: Dict[str, float] = {}  # filename -> progress
    
    def get_catalog(self, category: Optional[str] = None) -> List[SoundFontDownload]:
        """Get available soundfonts, optionally filtered by category"""
        if category:
            return [sf for sf in self.catalog if sf.category == category]
        return self.catalog
    
    def get_categories(self) -> List[str]:
        """Get list of available categories"""
        return sorted(set(sf.category for sf in self.catalog))
    
    def is_downloaded(self, sf: SoundFontDownload) -> bool:
        """Check if a soundfont is already downloaded"""
        # Check for the file or extracted version
        target = self.download_dir / sf.filename
        if target.exists():
            return True
        
        # Check for extracted .sf2 if it's an archive
        if sf.filename.endswith(('.zip', '.tar.xz', '.tar.gz')):
            base = sf.filename.rsplit('.', 2)[0]
            for ext in ['.sf2', '.SF2']:
                if (self.download_dir / (base + ext)).exists():
                    return True
                # Also check without extension modifications
                for f in self.download_dir.glob(f"*{base}*{ext}"):
                    return True
        
        return False
    
    def get_downloaded_path(self, sf: SoundFontDownload) -> Optional[Path]:
        """Get the path to a downloaded soundfont"""
        target = self.download_dir / sf.filename
        
        # Direct .sf2 file
        if target.exists() and target.suffix.lower() == '.sf2':
            return target
        
        # Look for extracted files
        base = sf.filename.rsplit('.', 2)[0] if '.' in sf.filename else sf.filename
        for pattern in [f"{base}*.sf2", f"{base}*.SF2", f"*{base}*.sf2"]:
            matches = list(self.download_dir.glob(pattern))
            if matches:
                return matches[0]
        
        return None
    
    def download(self, sf: SoundFontDownload, 
                 progress_callback: Optional[Callable[[float, str], None]] = None) -> Optional[Path]:
        """
        Download a soundfont. Returns path on success.
        
        progress_callback(percent, status_message)
        """
        import urllib.request
        import urllib.error
        import shutil
        import tarfile
        import zipfile
        
        target = self.download_dir / sf.filename
        
        def report_progress(pct: float, msg: str):
            if progress_callback:
                progress_callback(pct, msg)
            else:
                log.info(f"Download {sf.name}: {pct:.0f}% - {msg}")
        
        try:
            report_progress(0, f"Connecting to server...")
            
            # Download with progress
            req = urllib.request.Request(sf.url, headers={
                'User-Agent': 'FW16-Synth/2.0 (SoundFont Downloader)'
            })
            
            with urllib.request.urlopen(req, timeout=30) as response:
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                chunk_size = 8192
                
                report_progress(5, f"Downloading {sf.size_mb:.1f} MB...")
                
                with open(target, 'wb') as f:
                    while True:
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        if total_size > 0:
                            pct = 5 + (downloaded / total_size) * 85
                            report_progress(pct, f"Downloaded {downloaded / 1024 / 1024:.1f} MB")
            
            report_progress(90, "Download complete, processing...")
            
            # Extract if needed
            final_path = target
            
            if sf.filename.endswith('.zip'):
                report_progress(92, "Extracting ZIP archive...")
                with zipfile.ZipFile(target, 'r') as zf:
                    # Find .sf2 files
                    sf2_files = [n for n in zf.namelist() if n.lower().endswith('.sf2')]
                    if sf2_files:
                        zf.extractall(self.download_dir)
                        final_path = self.download_dir / sf2_files[0]
                target.unlink()  # Remove archive
                
            elif sf.filename.endswith(('.tar.xz', '.tar.gz', '.tar.bz2')):
                report_progress(92, "Extracting TAR archive...")
                mode = 'r:xz' if sf.filename.endswith('.xz') else \
                       'r:gz' if sf.filename.endswith('.gz') else 'r:bz2'
                with tarfile.open(target, mode) as tf:
                    sf2_files = [m for m in tf.getmembers() if m.name.lower().endswith('.sf2')]
                    if sf2_files:
                        tf.extractall(self.download_dir)
                        final_path = self.download_dir / sf2_files[0].name
                target.unlink()  # Remove archive
            
            report_progress(100, "Complete!")
            log.info(f"Downloaded soundfont: {final_path}")
            return final_path
            
        except urllib.error.URLError as e:
            report_progress(0, f"Network error: {e.reason}")
            log.error(f"Failed to download {sf.name}: {e}")
            if target.exists():
                target.unlink()
            return None
            
        except Exception as e:
            report_progress(0, f"Error: {str(e)}")
            log.error(f"Failed to download {sf.name}: {e}")
            if target.exists():
                target.unlink()
            return None
    
    def download_essential(self, 
                          progress_callback: Optional[Callable[[str, float, str], None]] = None) -> List[Path]:
        """
        Download a curated set of essential soundfonts.
        
        progress_callback(soundfont_name, percent, status)
        Returns list of downloaded paths.
        """
        essential = [
            "GeneralUser GS",  # Best balance of size/quality
            "Nice Keys Suite",  # Good piano/keys
        ]
        
        downloaded = []
        for name in essential:
            sf = next((s for s in self.catalog if s.name == name), None)
            if sf and not self.is_downloaded(sf):
                def cb(pct, msg):
                    if progress_callback:
                        progress_callback(sf.name, pct, msg)
                
                path = self.download(sf, cb)
                if path:
                    downloaded.append(path)
        
        return downloaded


# =============================================================================
# TERMINAL COLORS
# =============================================================================

class Color:
    """ANSI color codes - DeMoD turquoise/violet theme"""
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    ITALIC = '\033[3m'
    UNDERLINE = '\033[4m'
    BLINK = '\033[5m'
    REVERSE = '\033[7m'
    
    # DeMoD palette
    TURQUOISE = '\033[38;5;44m'
    TURQUOISE_BRIGHT = '\033[38;5;51m'
    VIOLET = '\033[38;5;135m'
    VIOLET_BRIGHT = '\033[38;5;177m'
    MAGENTA = '\033[38;5;199m'
    
    # Functional
    WHITE = '\033[38;5;255m'
    GRAY = '\033[38;5;245m'
    DARK_GRAY = '\033[38;5;238m'
    BLACK = '\033[38;5;232m'
    
    GREEN = '\033[38;5;46m'
    YELLOW = '\033[38;5;226m'
    ORANGE = '\033[38;5;214m'
    RED = '\033[38;5;196m'
    
    # Backgrounds
    BG_TURQUOISE = '\033[48;5;44m'
    BG_VIOLET = '\033[48;5;135m'
    BG_DARK = '\033[48;5;235m'
    BG_BLACK = '\033[48;5;232m'
    BG_GREEN = '\033[48;5;22m'
    BG_RED = '\033[48;5;52m'


# =============================================================================
# DEMOD ASCII ART & BRANDING
# =============================================================================

# ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
# ┃  DeMoD LLC - Design ≠ Marketing                                           ┃
# ┃  Turquoise (#00D7AF) / Violet (#AF5FFF) color palette                     ┃
# ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

VERSION = "2.0.0"
TAGLINE = "Design ≠ Marketing"

# Main FW16 Synth logo - 80 columns wide
LOGO_FW16 = """
███████╗██╗    ██╗ ██╗ ██████╗     ███████╗██╗   ██╗███╗   ██╗████████╗██╗  ██╗
██╔════╝██║    ██║███║██╔════╝     ██╔════╝╚██╗ ██╔╝████╗  ██║╚══██╔══╝██║  ██║
█████╗  ██║ █╗ ██║╚██║███████╗     ███████╗ ╚████╔╝ ██╔██╗ ██║   ██║   ███████║
██╔══╝  ██║███╗██║ ██║██╔═══██╗    ╚════██║  ╚██╔╝  ██║╚██╗██║   ██║   ██╔══██║
██║     ╚███╔███╔╝ ██║╚██████╔╝    ███████║   ██║   ██║ ╚████║   ██║   ██║  ██║
╚═╝      ╚══╝╚══╝  ╚═╝ ╚═════╝     ╚══════╝   ╚═╝   ╚═╝  ╚═══╝   ╚═╝   ╚═╝  ╚═╝
"""

# DeMoD company logo
LOGO_DEMOD = """
██████╗ ███████╗███╗   ███╗ ██████╗ ██████╗ 
██╔══██╗██╔════╝████╗ ████║██╔═══██╗██╔══██╗
██║  ██║█████╗  ██╔████╔██║██║   ██║██║  ██║
██║  ██║██╔══╝  ██║╚██╔╝██║██║   ██║██║  ██║
██████╔╝███████╗██║ ╚═╝ ██║╚██████╔╝██████╔╝
╚═════╝ ╚══════╝╚═╝     ╚═╝ ╚═════╝ ╚═════╝ 
"""

# Decorative elements
WAVE_CHAR = "∿"
PIANO_KEYS = "┃█┃█┃┃█┃█┃█┃┃█┃█┃┃█┃█┃█┃┃█┃█┃┃█┃█┃█┃"
OSCILLOSCOPE = "╭─────╮╭╮╭──╮╭╮╭─────╮"

# Box characters for consistent styling
class Box:
    """Unicode box drawing characters"""
    # Single line
    H = '─'
    V = '│'
    TL = '╭'
    TR = '╮'
    BL = '╰'
    BR = '╯'
    # Double line
    DH = '═'
    DV = '║'
    DTL = '╔'
    DTR = '╗'
    DBL = '╚'
    DBR = '╝'
    # Mixed
    VR = '├'
    VL = '┤'
    HD = '┬'
    HU = '┴'
    X = '┼'


def print_splash_screen():
    """
    Display the animated startup splash screen.
    Features: FW16 logo, DeMoD branding, loading animation.
    """
    import time
    
    C = Color.TURQUOISE
    CB = Color.TURQUOISE_BRIGHT
    V = Color.VIOLET
    VB = Color.VIOLET_BRIGHT
    W = Color.WHITE
    G = Color.GRAY
    D = Color.DARK_GRAY
    B = Color.BOLD
    R = Color.RESET
    
    # Clear screen and hide cursor
    sys.stdout.write('\033[2J\033[H\033[?25l')
    sys.stdout.flush()
    
    width = 80
    
    # Build the splash frame
    def wave_line(w):
        return WAVE_CHAR * w
    
    def center(text, w):
        return text.center(w)
    
    lines = []
    
    # ═══════════════════════════════════════════════════════════════════════════
    # TOP BORDER
    # ═══════════════════════════════════════════════════════════════════════════
    lines.append(f"{C}{Box.DTL}{Box.DH * (width - 2)}{Box.DTR}{R}")
    lines.append(f"{C}{Box.DV}{R}{D}{wave_line(width - 2)}{R}{C}{Box.DV}{R}")
    lines.append(f"{C}{Box.DV}{R}{' ' * (width - 2)}{C}{Box.DV}{R}")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # FW16 SYNTH LOGO
    # ═══════════════════════════════════════════════════════════════════════════
    for i, line in enumerate(LOGO_FW16.strip().split('\n')):
        # Gradient from turquoise to violet
        color = CB if i < 3 else V
        padded = center(line, width - 2)
        lines.append(f"{C}{Box.DV}{R}{color}{padded}{R}{C}{Box.DV}{R}")
    
    lines.append(f"{C}{Box.DV}{R}{' ' * (width - 2)}{C}{Box.DV}{R}")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # SEPARATOR WITH OSCILLOSCOPE
    # ═══════════════════════════════════════════════════════════════════════════
    osc_line = f"──────── {OSCILLOSCOPE} ────────"
    lines.append(f"{C}{Box.DV}{R}{D}{center(osc_line, width - 2)}{R}{C}{Box.DV}{R}")
    lines.append(f"{C}{Box.DV}{R}{' ' * (width - 2)}{C}{Box.DV}{R}")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # DEMOD LOGO
    # ═══════════════════════════════════════════════════════════════════════════
    for line in LOGO_DEMOD.strip().split('\n'):
        padded = center(line, width - 2)
        lines.append(f"{C}{Box.DV}{R}{VB}{padded}{R}{C}{Box.DV}{R}")
    
    lines.append(f"{C}{Box.DV}{R}{' ' * (width - 2)}{C}{Box.DV}{R}")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # TAGLINE
    # ═══════════════════════════════════════════════════════════════════════════
    tagline = f"« {TAGLINE} »"
    lines.append(f"{C}{Box.DV}{R}{W}{B}{center(tagline, width - 2)}{R}{C}{Box.DV}{R}")
    
    version_line = f"v{VERSION}"
    lines.append(f"{C}{Box.DV}{R}{D}{center(version_line, width - 2)}{R}{C}{Box.DV}{R}")
    
    lines.append(f"{C}{Box.DV}{R}{' ' * (width - 2)}{C}{Box.DV}{R}")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PIANO KEYS DECORATION
    # ═══════════════════════════════════════════════════════════════════════════
    piano_extended = (PIANO_KEYS * 3)[:width - 4]
    lines.append(f"{C}{Box.DV}{R} {C}{piano_extended}{R} {C}{Box.DV}{R}")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # BOTTOM BORDER
    # ═══════════════════════════════════════════════════════════════════════════
    lines.append(f"{C}{Box.DV}{R}{D}{wave_line(width - 2)}{R}{C}{Box.DV}{R}")
    lines.append(f"{C}{Box.DBL}{Box.DH * (width - 2)}{Box.DBR}{R}")
    
    # Print with animation
    for i, line in enumerate(lines):
        print(line)
        if i < 4:
            time.sleep(0.015)
    
    # Loading animation
    print()
    msg = "  Initializing synthesizer"
    frames = ["◐", "◓", "◑", "◒"]
    
    for cycle in range(8):
        frame = frames[cycle % 4]
        dots = "." * ((cycle % 3) + 1)
        sys.stdout.write(f"\r{C}{msg}{dots:<3} {V}{frame}{R}  ")
        sys.stdout.flush()
        time.sleep(0.12)
    
    sys.stdout.write(f"\r{Color.GREEN}  Synthesizer ready!{' ' * 20}{R}\n")
    sys.stdout.flush()
    
    # Show cursor
    sys.stdout.write('\033[?25h')
    time.sleep(0.4)


def print_exit_screen():
    """Display exit message with branding"""
    C = Color.TURQUOISE
    V = Color.VIOLET
    D = Color.DARK_GRAY
    R = Color.RESET
    
    print()
    print(f"{D}{'─' * 60}{R}")
    print(f"{V}  DeMoD LLC{R} {D}│{R} {C}FW16 Synth v{VERSION}{R}")
    print(f"{D}  « {TAGLINE} »{R}")
    print(f"{D}{'─' * 60}{R}")
    print()


# =============================================================================
# TERMINAL UI
# =============================================================================

class TerminalUI:
    """
    Real-time Terminal User Interface with multiple display modes.
    """
    
    # Box drawing
    BOX_H = '─'
    BOX_V = '│'
    BOX_TL = '╭'
    BOX_TR = '╮'
    BOX_BL = '╰'
    BOX_BR = '╯'
    
    DBL_H = '═'
    DBL_V = '║'
    DBL_TL = '╔'
    DBL_TR = '╗'
    DBL_BL = '╚'
    DBL_BR = '╝'
    
    # Blocks for meters
    BLOCKS = ' ▁▂▃▄▅▆▇█'
    
    def __init__(self, config: SynthConfig):
        self.config = config
        self._width = 76
        self._height = 32
        self._lock = threading.Lock()
        self._last_frame = ""
        
        # UI state
        self.mode = UIMode.NORMAL
        self.active_keys: Set[str] = set()
        self.octave: int = config.base_octave
        self.transpose: int = 0
        self.program: int = 0
        self.program_name: str = GM_INSTRUMENTS[0]
        self.sustain: bool = False
        self.layer_enabled: bool = False
        self.layer_program: int = 48  # Strings
        self.arp_mode: ArpMode = ArpMode.OFF
        
        # Soundfont
        self.soundfont_name: str = "Loading..."
        self.soundfont_path: str = ""
        
        # Touchpad
        self.touch_x: float = 0.5
        self.touch_y: float = 0.5
        self.touch_pressure: float = 0.0
        self.touching: bool = False
        
        # Meters
        self.pitch_bend: float = 0.0
        self.mod_values: Dict[ModDest, float] = {d: 0.0 for d in ModDest}
        self.velocity_last: int = 0
        self.volume_level: float = 0.0
        
        # Activity
        self.activity_log: deque = deque(maxlen=4)
        self.last_chord: List[str] = []
        
        # Browser state
        self.browser_items: List[Any] = []
        self.browser_index: int = 0
        self.browser_scroll: int = 0
        self.browser_category: int = 0
        
        # Download browser state
        self.download_items: List[Any] = []
        self.download_index: int = 0
        self.download_scroll: int = 0
        self.download_progress: float = 0.0
        self.download_status: str = ""
        self.download_active: bool = False
        
        # MIDI input state (FW16 Piano Keyboard Module)
        self.midi_connected: bool = False
        self.midi_port_name: str = ""
        self.last_velocity: int = 0  # From MIDI input
        
        # Performance
        self.latency_ms: float = 0.0
        self.note_count: int = 0
    
    # ─────────────────────────────────────────────────────────────────────────
    # Terminal control
    # ─────────────────────────────────────────────────────────────────────────
    
    def _clear(self):
        sys.stdout.write('\033[2J')
        sys.stdout.flush()
    
    def _home(self):
        sys.stdout.write('\033[H')
    
    def _hide_cursor(self):
        sys.stdout.write('\033[?25l')
        sys.stdout.flush()
    
    def _show_cursor(self):
        sys.stdout.write('\033[?25h')
        sys.stdout.flush()
    
    def start(self):
        self._clear()
        self._hide_cursor()
    
    def stop(self):
        self._show_cursor()
        self._clear()
        self._home()
    
    # ─────────────────────────────────────────────────────────────────────────
    # Rendering helpers
    # ─────────────────────────────────────────────────────────────────────────
    
    def _meter_bar(self, value: float, width: int, color: str) -> str:
        """Create a horizontal meter bar"""
        filled = int(value * width)
        bar = '█' * filled + '░' * (width - filled)
        return f"{color}{bar}{Color.RESET}"
    
    def _velocity_color(self, vel: int) -> str:
        """Get color based on velocity"""
        if vel > 100:
            return Color.RED
        elif vel > 70:
            return Color.ORANGE
        elif vel > 40:
            return Color.YELLOW
        else:
            return Color.GREEN
    
    # ─────────────────────────────────────────────────────────────────────────
    # Header
    # ─────────────────────────────────────────────────────────────────────────
    
    def _render_header(self) -> List[str]:
        lines = []
        
        # Top border with waveform
        wave = WAVE_CHAR * (self._width - 2)
        lines.append(
            f"{Color.TURQUOISE}{self.DBL_TL}{Color.DARK_GRAY}{wave}{Color.TURQUOISE}{self.DBL_TR}{Color.RESET}"
        )
        
        # Title line with soundfont info and branding
        sf_display = f"♪ {self.soundfont_name[:22]}" if self.soundfont_name else "No SoundFont"
        
        lines.append(
            f"{Color.TURQUOISE}{self.DBL_V}{Color.RESET} "
            f"{Color.TURQUOISE_BRIGHT}{Color.BOLD}FW16 SYNTH{Color.RESET}"
            f" {Color.DARK_GRAY}│{Color.RESET} "
            f"{Color.VIOLET}{sf_display:<24}{Color.RESET}"
            f"{Color.DARK_GRAY}│{Color.RESET} "
            f"{Color.DARK_GRAY}DeMoD «{Color.RESET}{Color.VIOLET} Design{Color.DARK_GRAY}≠{Color.TURQUOISE}Marketing{Color.RESET}{Color.DARK_GRAY} »{Color.RESET}"
            f"  {Color.TURQUOISE}{self.DBL_V}{Color.RESET}"
        )
        
        return lines
    
    # ─────────────────────────────────────────────────────────────────────────
    # Status bar
    # ─────────────────────────────────────────────────────────────────────────
    
    def _render_status(self) -> List[str]:
        lines = []
        
        # Main status line
        oct_str = f"Oct:{Color.BOLD}{self.octave}{Color.RESET}"
        
        trans_color = Color.YELLOW if self.transpose != 0 else Color.DARK_GRAY
        trans_str = f"{trans_color}T:{self.transpose:+d}{Color.RESET}"
        
        prog_str = f"Prog:{Color.BOLD}{self.program:03d}{Color.RESET} {Color.TURQUOISE}{self.program_name[:18]}{Color.RESET}"
        
        # Indicators
        sus_ind = f"{Color.BG_TURQUOISE}{Color.BLACK} SUS {Color.RESET}" if self.sustain else f"{Color.DARK_GRAY} SUS {Color.RESET}"
        
        layer_ind = f"{Color.BG_VIOLET}{Color.WHITE} LYR {Color.RESET}" if self.layer_enabled else f"{Color.DARK_GRAY} LYR {Color.RESET}"
        
        arp_names = {ArpMode.OFF: "---", ArpMode.UP: " ↑ ", ArpMode.DOWN: " ↓ ", 
                     ArpMode.UP_DOWN: "↑↓", ArpMode.RANDOM: " ? "}
        arp_color = Color.BG_GREEN if self.arp_mode != ArpMode.OFF else ""
        arp_ind = f"{arp_color}{Color.WHITE}ARP:{arp_names[self.arp_mode]}{Color.RESET}"
        
        touch_ind = f"{Color.BG_VIOLET}{Color.WHITE} TCH {Color.RESET}" if self.touching else f"{Color.DARK_GRAY} TCH {Color.RESET}"
        
        # MIDI input indicator (FW16 Piano Keyboard Module)
        midi_ind = f"{Color.BG_GREEN}{Color.WHITE} MIDI {Color.RESET}" if self.midi_connected else f"{Color.DARK_GRAY} MIDI {Color.RESET}"
        
        line = (
            f"{Color.TURQUOISE}{self.DBL_V}{Color.RESET} "
            f"{oct_str} {trans_str} │ {prog_str} │ "
            f"{sus_ind} {layer_ind} {arp_ind} {touch_ind} {midi_ind}"
        )
        
        # Pad to width (approximate)
        line += " " * 4 + f"{Color.TURQUOISE}{self.DBL_V}{Color.RESET}"
        lines.append(line)
        
        # Separator
        lines.append(
            f"{Color.TURQUOISE}{self.DBL_V}{Color.RESET}"
            f"{Color.DARK_GRAY}{self.BOX_H * (self._width - 2)}{Color.RESET}"
            f"{Color.TURQUOISE}{self.DBL_V}{Color.RESET}"
        )
        
        return lines
    
    # ─────────────────────────────────────────────────────────────────────────
    # Keyboard visualization
    # ─────────────────────────────────────────────────────────────────────────
    
    def _render_keyboard(self) -> List[str]:
        lines = []
        
        # Shorthand for readability
        T, F = True, False
        
        # Define keyboard rows: (char, is_note, note_name, is_black)
        rows = [
            [('`',F,None,F),('1',F,None,F),('2',T,'C#',T),('3',T,'D#',T),('4',F,None,F),
             ('5',T,'F#',T),('6',T,'G#',T),('7',T,'A#',T),('8',F,None,F),('9',T,'C#',T),
             ('0',T,'D#',T),('-',F,'▼',F),('=',F,'▲',F),('⌫',F,None,F)],
            [('⇥',F,None,F),('Q',T,'C',F),('W',T,'D',F),('E',T,'E',F),('R',T,'F',F),
             ('T',T,'G',F),('Y',T,'A',F),('U',T,'B',F),('I',T,'C',F),('O',T,'D',F),
             ('P',T,'E',F),('[',T,'F',F),(']',T,'G',F),('\\',F,None,F)],
            [('⇪',F,None,F),('A',T,'C',F),('S',T,'D',F),('D',T,'E',F),('F',T,'F',F),
             ('G',T,'G',F),('H',T,'A',F),('J',T,'B',F),('K',T,'C',F),('L',T,'D',F),
             (';',T,'E',F),("'",T,'F',F),('↵',F,None,F)],
            [('⇧',F,None,F),('Z',T,'C',F),('X',T,'D',F),('C',T,'E',F),('V',T,'F',F),
             ('B',T,'G',F),('N',T,'A',F),('M',T,'B',F),(',',T,'C',F),('.',T,'D',F),
             ('/',T,'E',F),('⇧',F,None,F)],
        ]
        
        for row in rows:
            line = f"{Color.TURQUOISE}{self.DBL_V}{Color.RESET} "
            
            for char, is_note, note, is_black in row:
                key_upper = char.upper() if len(char) == 1 else char
                is_active = key_upper in self.active_keys
                
                if is_note:
                    if is_active:
                        style = f"{Color.BG_VIOLET}{Color.WHITE}{Color.BOLD}" if is_black else f"{Color.BG_TURQUOISE}{Color.BLACK}{Color.BOLD}"
                    else:
                        style = f"{Color.BG_BLACK}{Color.GRAY}" if is_black else f"{Color.BG_DARK}{Color.WHITE}"
                else:
                    style = Color.DARK_GRAY
                
                line += f"{style}[{char}]{Color.RESET} "
            
            line = line.rstrip()
            pad = self._width - self._visible_len(line) - 2
            line += " " * pad + f"{Color.TURQUOISE}{self.DBL_V}{Color.RESET}"
            lines.append(line)
        
        # Space bar
        sus_style = f"{Color.BG_TURQUOISE}{Color.BLACK}" if self.sustain else f"{Color.BG_DARK}{Color.GRAY}"
        lines.append(
            f"{Color.TURQUOISE}{self.DBL_V}{Color.RESET} "
            f"{Color.DARK_GRAY}[Ctrl] [❖] [Alt]{Color.RESET}  "
            f"{sus_style}[{'━' * 16} SUSTAIN {'━' * 16}]{Color.RESET}  "
            f"{Color.DARK_GRAY}[Alt] [Fn] [Ctrl]{Color.RESET}"
            f"  {Color.TURQUOISE}{self.DBL_V}{Color.RESET}"
        )
        
        return lines
    
    def _visible_len(self, s: str) -> int:
        """Calculate visible length ignoring ANSI codes"""
        import re
        return len(re.sub(r'\033\[[0-9;]*m', '', s))
    
    # ─────────────────────────────────────────────────────────────────────────
    # Touchpad & meters
    # ─────────────────────────────────────────────────────────────────────────
    
    def _render_touchpad_section(self) -> List[str]:
        lines = []
        
        # Section separator
        lines.append(
            f"{Color.TURQUOISE}{self.DBL_V}{Color.RESET}"
            f"{Color.DARK_GRAY}{self.BOX_H * (self._width - 2)}{Color.RESET}"
            f"{Color.TURQUOISE}{self.DBL_V}{Color.RESET}"
        )
        
        # Touchpad grid (20x6)
        tp_w, tp_h = 20, 6
        
        # Build touchpad display
        tp_lines = []
        for y in range(tp_h):
            row = ""
            for x in range(tp_w):
                gx = x / (tp_w - 1)
                gy = y / (tp_h - 1)
                
                if self.touching:
                    dist = math.sqrt((gx - self.touch_x)**2 + (gy - self.touch_y)**2)
                    if dist < 0.12:
                        intensity = min(1.0, self.touch_pressure * 1.5)
                        if intensity > 0.6:
                            row += f"{Color.TURQUOISE_BRIGHT}●{Color.RESET}"
                        else:
                            row += f"{Color.VIOLET}○{Color.RESET}"
                        continue
                
                # Grid
                cx = abs(gx - 0.5) < 0.03
                cy = abs(gy - 0.5) < 0.1
                
                if cx and cy:
                    row += f"{Color.DARK_GRAY}+{Color.RESET}"
                elif cx:
                    row += f"{Color.DARK_GRAY}│{Color.RESET}"
                elif cy:
                    row += f"{Color.DARK_GRAY}─{Color.RESET}"
                else:
                    row += f"{Color.DARK_GRAY}·{Color.RESET}"
            tp_lines.append(row)
        
        # Meters section
        meter_lines = []
        
        # Velocity meter
        vel_pct = self.velocity_last / 127
        vel_color = self._velocity_color(self.velocity_last)
        vel_bar = self._meter_bar(vel_pct, 8, vel_color)
        
        # Pitch bend meter (bipolar)
        bend_val = (self.pitch_bend + 1) / 2
        bend_bar = self._meter_bar(bend_val, 8, Color.TURQUOISE)
        
        # Filter meter
        filt_val = self.mod_values.get(ModDest.FILTER_CUTOFF, 0.5)
        filt_bar = self._meter_bar(filt_val, 8, Color.VIOLET)
        
        # Expression meter
        expr_val = self.mod_values.get(ModDest.EXPRESSION, 0.5)
        expr_bar = self._meter_bar(expr_val, 8, Color.MAGENTA)
        
        meter_lines = [
            f"{Color.GRAY}Vel  {Color.RESET}{vel_bar} {Color.BOLD}{self.velocity_last:3d}{Color.RESET}",
            f"{Color.GRAY}Bend {Color.RESET}{bend_bar} {int(self.pitch_bend * 100):+4d}%",
            f"{Color.GRAY}Filt {Color.RESET}{filt_bar} {int(filt_val * 127):3d}",
            f"{Color.GRAY}Expr {Color.RESET}{expr_bar} {int(expr_val * 127):3d}",
        ]
        
        # Chord display
        chord_str = " ".join(self.last_chord[-6:]) if self.last_chord else "---"
        
        # Combine touchpad and meters
        for i in range(max(len(tp_lines), len(meter_lines) + 2)):
            tp_part = tp_lines[i] if i < len(tp_lines) else " " * tp_w
            
            if i == 0:
                meter_part = f"{Color.GRAY}├─ Meters ─┤{Color.RESET}"
            elif i - 1 < len(meter_lines):
                meter_part = meter_lines[i - 1]
            elif i == len(meter_lines) + 1:
                meter_part = f"{Color.GRAY}Chord: {Color.WHITE}{chord_str[:20]}{Color.RESET}"
            else:
                meter_part = ""
            
            line = (
                f"{Color.TURQUOISE}{self.DBL_V}{Color.RESET}  "
                f"{tp_part}  {Color.DARK_GRAY}│{Color.RESET}  "
                f"{meter_part}"
            )
            
            pad = self._width - self._visible_len(line) - 1
            line += " " * max(0, pad) + f"{Color.TURQUOISE}{self.DBL_V}{Color.RESET}"
            lines.append(line)
        
        # Touchpad label
        lines.append(
            f"{Color.TURQUOISE}{self.DBL_V}{Color.RESET}  "
            f"{Color.GRAY}{'Touchpad (X=Bend Y=Filt)':^20}{Color.RESET}  "
            f"{Color.DARK_GRAY}│{Color.RESET}"
            f"{'':43}"
            f"{Color.TURQUOISE}{self.DBL_V}{Color.RESET}"
        )
        
        return lines
    
    # ─────────────────────────────────────────────────────────────────────────
    # Activity log
    # ─────────────────────────────────────────────────────────────────────────
    
    def _render_activity(self) -> List[str]:
        lines = []
        
        lines.append(
            f"{Color.TURQUOISE}{self.DBL_V}{Color.RESET}"
            f"{Color.DARK_GRAY}{self.BOX_H * (self._width - 2)}{Color.RESET}"
            f"{Color.TURQUOISE}{self.DBL_V}{Color.RESET}"
        )
        
        for entry in list(self.activity_log):
            truncated = entry[:self._width - 6]
            lines.append(
                f"{Color.TURQUOISE}{self.DBL_V}{Color.RESET} "
                f"{Color.GRAY}{truncated:<{self._width - 4}}{Color.RESET}"
                f"{Color.TURQUOISE}{self.DBL_V}{Color.RESET}"
            )
        
        # Pad
        while len(lines) < 5:
            lines.append(
                f"{Color.TURQUOISE}{self.DBL_V}{Color.RESET}"
                f"{' ' * (self._width - 2)}"
                f"{Color.TURQUOISE}{self.DBL_V}{Color.RESET}"
            )
        
        return lines
    
    # ─────────────────────────────────────────────────────────────────────────
    # Footer / help
    # ─────────────────────────────────────────────────────────────────────────
    
    def _render_footer(self) -> List[str]:
        lines = []
        
        # Help hints
        help_text = "[?] Help  [Tab] Browse  [D] Download  [L] Layer  [A] Arp  [+/-] Oct"
        
        lines.append(
            f"{Color.TURQUOISE}{self.DBL_V}{Color.RESET} "
            f"{Color.DARK_GRAY}{help_text:^{self._width - 4}}{Color.RESET}"
            f" {Color.TURQUOISE}{self.DBL_V}{Color.RESET}"
        )
        
        # DeMoD branding footer
        piano = PIANO_KEYS[:self._width - 4]
        lines.append(
            f"{Color.TURQUOISE}{self.DBL_V}{Color.RESET} "
            f"{Color.DARK_GRAY}{piano:^{self._width - 4}}{Color.RESET}"
            f" {Color.TURQUOISE}{self.DBL_V}{Color.RESET}"
        )
        
        # Bottom border with waveform
        wave = WAVE_CHAR * (self._width - 2)
        lines.append(
            f"{Color.TURQUOISE}{self.DBL_BL}{Color.DARK_GRAY}{wave}{Color.TURQUOISE}{self.DBL_BR}{Color.RESET}"
        )
        
        return lines
    
    # ─────────────────────────────────────────────────────────────────────────
    # Help overlay
    # ─────────────────────────────────────────────────────────────────────────
    
    def _render_help(self) -> List[str]:
        lines = []
        w = self._width
        
        # Header with waveform border
        wave = WAVE_CHAR * (w - 2)
        lines.append(f"{Color.TURQUOISE}{self.DBL_TL}{Color.DARK_GRAY}{wave}{Color.TURQUOISE}{self.DBL_TR}{Color.RESET}")
        
        # ASCII art title
        help_art = [
            "╦ ╦╔═╗╦  ╔═╗",
            "╠═╣║╣ ║  ╠═╝",
            "╩ ╩╚═╝╩═╝╩  ",
        ]
        
        for art_line in help_art:
            centered = art_line.center(w - 2)
            lines.append(
                f"{Color.TURQUOISE}{self.DBL_V}{Color.RESET}"
                f"{Color.TURQUOISE_BRIGHT}{centered}{Color.RESET}"
                f"{Color.TURQUOISE}{self.DBL_V}{Color.RESET}"
            )
        
        lines.append(f"{Color.TURQUOISE}{self.DBL_V}{Color.RESET}{' ' * (w - 2)}{Color.TURQUOISE}{self.DBL_V}{Color.RESET}")
        
        # Piano decoration
        piano = PIANO_KEYS[:w - 4]
        piano_centered = piano.center(w - 2)
        lines.append(
            f"{Color.TURQUOISE}{self.DBL_V}{Color.RESET}"
            f"{Color.DARK_GRAY}{piano_centered}{Color.RESET}"
            f"{Color.TURQUOISE}{self.DBL_V}{Color.RESET}"
        )
        
        lines.append(f"{Color.TURQUOISE}{self.DBL_V}{Color.RESET}{' ' * (w - 2)}{Color.TURQUOISE}{self.DBL_V}{Color.RESET}")
        
        help_sections = [
            (f"{Color.VIOLET}▸ Keyboard Controls{Color.RESET}", [
                ("QWERTY / ASDF / ZXCV", "Play notes (3 octaves)"),
                ("2 3 5 6 7 9 0", "Black keys (sharps/flats)"),
                ("Space", "Sustain pedal (hold)"),
            ]),
            (f"{Color.VIOLET}▸ Navigation{Color.RESET}", [
                ("+ / -", "Octave up / down"),
                ("Shift + < / >", "Transpose ±1 semitone"),
                ("Page Up / Down", "Change instrument"),
                ("F1 - F12", "Quick preset instruments"),
            ]),
            (f"{Color.VIOLET}▸ Features{Color.RESET}", [
                ("Tab", "SoundFont browser"),
                ("D", "Download soundfonts"),
                ("M", "Toggle MIDI input (FW16 module)"),
                ("L", "Layer mode (dual voice)"),
                ("A", "Arpeggiator (↑/↓/↑↓/?)"),
                ("Esc", "Panic (all notes off)"),
            ]),
            (f"{Color.VIOLET}▸ Touchpad Modulation{Color.RESET}", [
                ("X axis ←→", "Pitch bend ±2 semitones"),
                ("Y axis ↑↓", "Filter cutoff"),
                ("Pressure", "Expression/dynamics"),
            ]),
        ]
        
        for section_title, items in help_sections:
            lines.append(
                f"{Color.TURQUOISE}{self.DBL_V}{Color.RESET}  {section_title}"
                f"{' ' * (w - self._visible_len(section_title) - 4)}"
                f"{Color.TURQUOISE}{self.DBL_V}{Color.RESET}"
            )
            for key, desc in items:
                line = f"    {Color.WHITE}{key:<24}{Color.RESET} {Color.GRAY}{desc}{Color.RESET}"
                pad = w - self._visible_len(line) - 4
                lines.append(
                    f"{Color.TURQUOISE}{self.DBL_V}{Color.RESET}  {line}{' ' * max(0, pad)}  {Color.TURQUOISE}{self.DBL_V}{Color.RESET}"
                )
            lines.append(f"{Color.TURQUOISE}{self.DBL_V}{Color.RESET}{' ' * (w - 2)}{Color.TURQUOISE}{self.DBL_V}{Color.RESET}")
        
        # DeMoD branding
        lines.append(
            f"{Color.TURQUOISE}{self.DBL_V}{Color.RESET}"
            f"{Color.DARK_GRAY}{'─' * (w - 2)}{Color.RESET}"
            f"{Color.TURQUOISE}{self.DBL_V}{Color.RESET}"
        )
        
        brand_line = f"DeMoD LLC │ Design{Color.VIOLET}≠{Color.DARK_GRAY}Marketing │ v{VERSION}"
        lines.append(
            f"{Color.TURQUOISE}{self.DBL_V}{Color.RESET}"
            f"{Color.DARK_GRAY}{brand_line:^{w - 2}}{Color.RESET}"
            f"{Color.TURQUOISE}{self.DBL_V}{Color.RESET}"
        )
        
        # Close prompt
        lines.append(
            f"{Color.TURQUOISE}{self.DBL_V}{Color.RESET}"
            f"{Color.GRAY}{'[ Press any key to close ]':^{w - 2}}{Color.RESET}"
            f"{Color.TURQUOISE}{self.DBL_V}{Color.RESET}"
        )
        
        # Bottom border with waveform
        lines.append(f"{Color.TURQUOISE}{self.DBL_BL}{Color.DARK_GRAY}{wave}{Color.TURQUOISE}{self.DBL_BR}{Color.RESET}")
        
        return lines
        
        return lines
    
    # ─────────────────────────────────────────────────────────────────────────
    # Soundfont browser
    # ─────────────────────────────────────────────────────────────────────────
    
    def _render_soundfont_browser(self) -> List[str]:
        lines = []
        
        # Header
        lines.append(f"{Color.VIOLET}{self.DBL_TL}{self.DBL_H * (self._width - 2)}{self.DBL_TR}{Color.RESET}")
        lines.append(
            f"{Color.VIOLET}{self.DBL_V}{Color.RESET}"
            f"{Color.VIOLET_BRIGHT}{Color.BOLD}{'SOUNDFONT BROWSER':^{self._width - 2}}{Color.RESET}"
            f"{Color.VIOLET}{self.DBL_V}{Color.RESET}"
        )
        
        lines.append(
            f"{Color.VIOLET}{self.DBL_V}{Color.RESET}"
            f"{Color.DARK_GRAY}{'[↑/↓] Select  [Enter] Load  [F] Favorite  [Tab/Esc] Close':^{self._width - 2}}{Color.RESET}"
            f"{Color.VIOLET}{self.DBL_V}{Color.RESET}"
        )
        
        lines.append(
            f"{Color.VIOLET}{self.DBL_V}{Color.RESET}"
            f"{Color.DARK_GRAY}{self.BOX_H * (self._width - 2)}{Color.RESET}"
            f"{Color.VIOLET}{self.DBL_V}{Color.RESET}"
        )
        
        # Soundfont list
        visible_count = 15
        
        if not self.browser_items:
            lines.append(
                f"{Color.VIOLET}{self.DBL_V}{Color.RESET}"
                f"{Color.GRAY}{'No soundfonts found. Check search paths.':^{self._width - 2}}{Color.RESET}"
                f"{Color.VIOLET}{self.DBL_V}{Color.RESET}"
            )
        else:
            # Adjust scroll
            if self.browser_index < self.browser_scroll:
                self.browser_scroll = self.browser_index
            elif self.browser_index >= self.browser_scroll + visible_count:
                self.browser_scroll = self.browser_index - visible_count + 1
            
            visible = self.browser_items[self.browser_scroll:self.browser_scroll + visible_count]
            
            for i, sf in enumerate(visible):
                idx = self.browser_scroll + i
                is_selected = idx == self.browser_index
                is_current = sf.path == Path(self.soundfont_path) if self.soundfont_path else False
                
                # Build line
                fav_icon = "★" if sf.favorite else " "
                cur_icon = "▶" if is_current else " "
                size_str = f"{sf.size_mb:.1f}MB"
                name = sf.name[:45]
                
                if is_selected:
                    style = f"{Color.BG_VIOLET}{Color.WHITE}"
                elif is_current:
                    style = f"{Color.TURQUOISE}"
                else:
                    style = Color.GRAY
                
                line_content = f" {cur_icon} {fav_icon} {name:<45} {size_str:>8} "
                
                lines.append(
                    f"{Color.VIOLET}{self.DBL_V}{Color.RESET}"
                    f"{style}{line_content:<{self._width - 2}}{Color.RESET}"
                    f"{Color.VIOLET}{self.DBL_V}{Color.RESET}"
                )
        
        # Pad remaining space
        while len(lines) < visible_count + 5:
            lines.append(
                f"{Color.VIOLET}{self.DBL_V}{Color.RESET}"
                f"{' ' * (self._width - 2)}"
                f"{Color.VIOLET}{self.DBL_V}{Color.RESET}"
            )
        
        # Footer with current path
        if self.browser_items and 0 <= self.browser_index < len(self.browser_items):
            sf = self.browser_items[self.browser_index]
            path_str = str(sf.path)[-60:]
            lines.append(
                f"{Color.VIOLET}{self.DBL_V}{Color.RESET}"
                f"{Color.DARK_GRAY} {path_str:<{self._width - 4}} {Color.RESET}"
                f"{Color.VIOLET}{self.DBL_V}{Color.RESET}"
            )
        else:
            lines.append(
                f"{Color.VIOLET}{self.DBL_V}{Color.RESET}"
                f"{' ' * (self._width - 2)}"
                f"{Color.VIOLET}{self.DBL_V}{Color.RESET}"
            )
        
        lines.append(f"{Color.VIOLET}{self.DBL_BL}{self.DBL_H * (self._width - 2)}{self.DBL_BR}{Color.RESET}")
        
        return lines
    
    # ─────────────────────────────────────────────────────────────────────────
    # Download browser
    # ─────────────────────────────────────────────────────────────────────────
    
    def _render_download_browser(self) -> List[str]:
        lines = []
        w = self._width
        
        # Header
        wave = WAVE_CHAR * (w - 2)
        lines.append(f"{Color.TURQUOISE}{self.DBL_TL}{Color.DARK_GRAY}{wave}{Color.TURQUOISE}{self.DBL_TR}{Color.RESET}")
        
        lines.append(
            f"{Color.TURQUOISE}{self.DBL_V}{Color.RESET}"
            f"{Color.TURQUOISE_BRIGHT}{Color.BOLD}{'SOUNDFONT DOWNLOADER':^{w - 2}}{Color.RESET}"
            f"{Color.TURQUOISE}{self.DBL_V}{Color.RESET}"
        )
        
        lines.append(
            f"{Color.TURQUOISE}{self.DBL_V}{Color.RESET}"
            f"{Color.DARK_GRAY}{'[↑/↓] Select  [Enter] Download  [D] Close':^{w - 2}}{Color.RESET}"
            f"{Color.TURQUOISE}{self.DBL_V}{Color.RESET}"
        )
        
        lines.append(
            f"{Color.TURQUOISE}{self.DBL_V}{Color.RESET}"
            f"{Color.DARK_GRAY}{self.BOX_H * (w - 2)}{Color.RESET}"
            f"{Color.TURQUOISE}{self.DBL_V}{Color.RESET}"
        )
        
        # Download list
        visible_count = 12
        
        if not self.download_items:
            lines.append(
                f"{Color.TURQUOISE}{self.DBL_V}{Color.RESET}"
                f"{Color.GRAY}{'Loading catalog...':^{w - 2}}{Color.RESET}"
                f"{Color.TURQUOISE}{self.DBL_V}{Color.RESET}"
            )
        else:
            # Ensure scroll keeps selection visible
            if self.download_index < self.download_scroll:
                self.download_scroll = self.download_index
            elif self.download_index >= self.download_scroll + visible_count:
                self.download_scroll = self.download_index - visible_count + 1
            
            for i in range(visible_count):
                idx = self.download_scroll + i
                if idx >= len(self.download_items):
                    lines.append(
                        f"{Color.TURQUOISE}{self.DBL_V}{Color.RESET}"
                        f"{' ' * (w - 2)}"
                        f"{Color.TURQUOISE}{self.DBL_V}{Color.RESET}"
                    )
                    continue
                
                sf = self.download_items[idx]
                is_selected = (idx == self.download_index)
                
                # Check if downloaded
                downloaded = hasattr(sf, '_downloaded') and sf._downloaded
                
                # Build line
                if downloaded:
                    status = f"{Color.GREEN}✓{Color.RESET}"
                else:
                    status = f"{Color.DARK_GRAY}○{Color.RESET}"
                
                quality = "★" * sf.quality + "☆" * (5 - sf.quality)
                
                # Category color
                cat_colors = {
                    "General MIDI": Color.TURQUOISE,
                    "Piano": Color.VIOLET,
                    "Orchestra": Color.MAGENTA,
                    "Synth": Color.GREEN,
                    "Guitar": Color.ORANGE,
                    "Bass": Color.YELLOW,
                }
                cat_color = cat_colors.get(sf.category, Color.GRAY)
                
                name_part = f"{sf.name[:28]:<28}"
                size_part = f"{sf.size_mb:>6.1f}MB"
                cat_part = f"{sf.category[:10]:<10}"
                
                if is_selected:
                    line = (
                        f"{Color.BG_VIOLET}{Color.WHITE} {status} "
                        f"{name_part} "
                        f"{Color.GRAY}{quality}{Color.RESET}{Color.BG_VIOLET} "
                        f"{size_part} "
                        f"{cat_color}{cat_part}{Color.RESET}"
                    )
                else:
                    line = (
                        f" {status} "
                        f"{Color.WHITE}{name_part}{Color.RESET} "
                        f"{Color.YELLOW}{quality}{Color.RESET} "
                        f"{Color.GRAY}{size_part}{Color.RESET} "
                        f"{cat_color}{cat_part}{Color.RESET}"
                    )
                
                # Pad and add borders
                pad = w - self._visible_len(line) - 2
                lines.append(
                    f"{Color.TURQUOISE}{self.DBL_V}{Color.RESET}"
                    f"{line}{' ' * max(0, pad)}"
                    f"{Color.TURQUOISE}{self.DBL_V}{Color.RESET}"
                )
        
        # Description of selected item
        lines.append(
            f"{Color.TURQUOISE}{self.DBL_V}{Color.RESET}"
            f"{Color.DARK_GRAY}{self.BOX_H * (w - 2)}{Color.RESET}"
            f"{Color.TURQUOISE}{self.DBL_V}{Color.RESET}"
        )
        
        if self.download_items and 0 <= self.download_index < len(self.download_items):
            sf = self.download_items[self.download_index]
            desc = sf.description[:w - 6]
            lines.append(
                f"{Color.TURQUOISE}{self.DBL_V}{Color.RESET} "
                f"{Color.GRAY}{desc:<{w - 4}}{Color.RESET}"
                f" {Color.TURQUOISE}{self.DBL_V}{Color.RESET}"
            )
            license_info = f"License: {sf.license}"
            lines.append(
                f"{Color.TURQUOISE}{self.DBL_V}{Color.RESET} "
                f"{Color.DARK_GRAY}{license_info:<{w - 4}}{Color.RESET}"
                f" {Color.TURQUOISE}{self.DBL_V}{Color.RESET}"
            )
        else:
            lines.append(
                f"{Color.TURQUOISE}{self.DBL_V}{Color.RESET}"
                f"{' ' * (w - 2)}"
                f"{Color.TURQUOISE}{self.DBL_V}{Color.RESET}"
            )
            lines.append(
                f"{Color.TURQUOISE}{self.DBL_V}{Color.RESET}"
                f"{' ' * (w - 2)}"
                f"{Color.TURQUOISE}{self.DBL_V}{Color.RESET}"
            )
        
        # Download progress (if active)
        if self.download_active:
            prog_w = w - 20
            filled = int(self.download_progress / 100 * prog_w)
            bar = f"{Color.GREEN}{'█' * filled}{Color.DARK_GRAY}{'░' * (prog_w - filled)}{Color.RESET}"
            pct = f"{self.download_progress:5.1f}%"
            lines.append(
                f"{Color.TURQUOISE}{self.DBL_V}{Color.RESET} "
                f"{Color.WHITE}Downloading:{Color.RESET} {bar} {pct} "
                f"{Color.TURQUOISE}{self.DBL_V}{Color.RESET}"
            )
            status_line = self.download_status[:w - 6]
            lines.append(
                f"{Color.TURQUOISE}{self.DBL_V}{Color.RESET} "
                f"{Color.GRAY}{status_line:<{w - 4}}{Color.RESET}"
                f" {Color.TURQUOISE}{self.DBL_V}{Color.RESET}"
            )
        else:
            lines.append(
                f"{Color.TURQUOISE}{self.DBL_V}{Color.RESET}"
                f"{' ' * (w - 2)}"
                f"{Color.TURQUOISE}{self.DBL_V}{Color.RESET}"
            )
            lines.append(
                f"{Color.TURQUOISE}{self.DBL_V}{Color.RESET}"
                f"{' ' * (w - 2)}"
                f"{Color.TURQUOISE}{self.DBL_V}{Color.RESET}"
            )
        
        # Footer with branding
        lines.append(
            f"{Color.TURQUOISE}{self.DBL_V}{Color.RESET}"
            f"{Color.DARK_GRAY}{'Downloads to ~/.local/share/soundfonts/':^{w - 2}}{Color.RESET}"
            f"{Color.TURQUOISE}{self.DBL_V}{Color.RESET}"
        )
        
        lines.append(f"{Color.TURQUOISE}{self.DBL_BL}{Color.DARK_GRAY}{wave}{Color.TURQUOISE}{self.DBL_BR}{Color.RESET}")
        
        return lines
    
    # ─────────────────────────────────────────────────────────────────────────
    # Main render
    # ─────────────────────────────────────────────────────────────────────────
    
    def render(self) -> str:
        with self._lock:
            if self.mode == UIMode.HELP:
                return '\n'.join(self._render_help())
            elif self.mode == UIMode.SOUNDFONT_BROWSER:
                return '\n'.join(self._render_soundfont_browser())
            elif self.mode == UIMode.DOWNLOAD_BROWSER:
                return '\n'.join(self._render_download_browser())
            else:
                lines = []
                lines.extend(self._render_header())
                lines.extend(self._render_status())
                lines.extend(self._render_keyboard())
                lines.extend(self._render_touchpad_section())
                lines.extend(self._render_activity())
                lines.extend(self._render_footer())
                return '\n'.join(lines)
    
    def update(self):
        frame = self.render()
        if frame != self._last_frame:
            self._home()
            sys.stdout.write(frame)
            sys.stdout.flush()
            self._last_frame = frame
    
    # ─────────────────────────────────────────────────────────────────────────
    # State updates
    # ─────────────────────────────────────────────────────────────────────────
    
    def log(self, message: str):
        timestamp = time.strftime("%H:%M:%S")
        self.activity_log.append(f"{timestamp} {message}")
    
    def note_on(self, key: str, note_name: str, velocity: int):
        self.active_keys.add(key.upper())
        self.velocity_last = velocity
        self.last_chord.append(note_name)
        if len(self.last_chord) > 8:
            self.last_chord.pop(0)
        self.note_count += 1
    
    def note_off(self, key: str, note_name: str):
        self.active_keys.discard(key.upper())
        if note_name in self.last_chord:
            self.last_chord.remove(note_name)
    
    def set_octave(self, octave: int):
        self.octave = octave
        self.log(f"Octave → {octave}")
    
    def set_transpose(self, transpose: int):
        self.transpose = transpose
        if transpose != 0:
            self.log(f"Transpose → {transpose:+d} semitones")
        else:
            self.log("Transpose → OFF")
    
    def set_program(self, program: int, name: str):
        self.program = program
        self.program_name = name
        self.log(f"Program → {program}: {name}")
    
    def set_soundfont(self, name: str, path: str):
        self.soundfont_name = name
        self.soundfont_path = path
        self.log(f"SoundFont → {name}")
    
    def set_sustain(self, on: bool):
        self.sustain = on
    
    def set_layer(self, enabled: bool, program: int = 0):
        self.layer_enabled = enabled
        self.layer_program = program
        if enabled:
            self.log(f"Layer ON → {GM_INSTRUMENTS[program]}")
        else:
            self.log("Layer OFF")
    
    def set_arp_mode(self, mode: ArpMode):
        self.arp_mode = mode
        if mode != ArpMode.OFF:
            self.log(f"Arpeggiator → {mode.name}")
        else:
            self.log("Arpeggiator OFF")
    
    def set_touchpad(self, x: float, y: float, pressure: float, touching: bool):
        self.touch_x = x
        self.touch_y = y
        self.touch_pressure = pressure
        self.touching = touching
    
    def set_pitch_bend(self, value: float):
        self.pitch_bend = value
    
    def set_mod(self, dest: ModDest, value: float):
        self.mod_values[dest] = value


# =============================================================================
# KEYBOARD MAPPER
# =============================================================================

class KeyboardMapper:
    """Maps QWERTY keyboard to MIDI notes"""
    
    NOTE_MAP: Dict[int, int] = {
        # Number row - black keys
        ecodes.KEY_2: 1, ecodes.KEY_3: 3, ecodes.KEY_5: 6,
        ecodes.KEY_6: 8, ecodes.KEY_7: 10, ecodes.KEY_9: 13, ecodes.KEY_0: 15,
        # QWERTY row
        ecodes.KEY_Q: 0, ecodes.KEY_W: 2, ecodes.KEY_E: 4, ecodes.KEY_R: 5,
        ecodes.KEY_T: 7, ecodes.KEY_Y: 9, ecodes.KEY_U: 11, ecodes.KEY_I: 12,
        ecodes.KEY_O: 14, ecodes.KEY_P: 16, ecodes.KEY_LEFTBRACE: 17,
        ecodes.KEY_RIGHTBRACE: 19,
        # Home row (-1 octave)
        ecodes.KEY_A: -12, ecodes.KEY_S: -10, ecodes.KEY_D: -8, ecodes.KEY_F: -7,
        ecodes.KEY_G: -5, ecodes.KEY_H: -3, ecodes.KEY_J: -1, ecodes.KEY_K: 0,
        ecodes.KEY_L: 2, ecodes.KEY_SEMICOLON: 4, ecodes.KEY_APOSTROPHE: 5,
        # Bottom row (-2 octaves)
        ecodes.KEY_Z: -24, ecodes.KEY_X: -22, ecodes.KEY_C: -20, ecodes.KEY_V: -19,
        ecodes.KEY_B: -17, ecodes.KEY_N: -15, ecodes.KEY_M: -13, ecodes.KEY_COMMA: -12,
        ecodes.KEY_DOT: -10, ecodes.KEY_SLASH: -8,
    }
    
    KEY_CHARS: Dict[int, str] = {
        ecodes.KEY_2: '2', ecodes.KEY_3: '3', ecodes.KEY_5: '5',
        ecodes.KEY_6: '6', ecodes.KEY_7: '7', ecodes.KEY_9: '9', ecodes.KEY_0: '0',
        ecodes.KEY_Q: 'Q', ecodes.KEY_W: 'W', ecodes.KEY_E: 'E', ecodes.KEY_R: 'R',
        ecodes.KEY_T: 'T', ecodes.KEY_Y: 'Y', ecodes.KEY_U: 'U', ecodes.KEY_I: 'I',
        ecodes.KEY_O: 'O', ecodes.KEY_P: 'P', ecodes.KEY_LEFTBRACE: '[',
        ecodes.KEY_RIGHTBRACE: ']',
        ecodes.KEY_A: 'A', ecodes.KEY_S: 'S', ecodes.KEY_D: 'D', ecodes.KEY_F: 'F',
        ecodes.KEY_G: 'G', ecodes.KEY_H: 'H', ecodes.KEY_J: 'J', ecodes.KEY_K: 'K',
        ecodes.KEY_L: 'L', ecodes.KEY_SEMICOLON: ';', ecodes.KEY_APOSTROPHE: "'",
        ecodes.KEY_Z: 'Z', ecodes.KEY_X: 'X', ecodes.KEY_C: 'C', ecodes.KEY_V: 'V',
        ecodes.KEY_B: 'B', ecodes.KEY_N: 'N', ecodes.KEY_M: 'M', ecodes.KEY_COMMA: ',',
        ecodes.KEY_DOT: '.', ecodes.KEY_SLASH: '/',
    }
    
    # Control keys
    CTRL_OCTAVE_UP = ecodes.KEY_EQUAL
    CTRL_OCTAVE_DOWN = ecodes.KEY_MINUS
    CTRL_SUSTAIN = ecodes.KEY_SPACE
    CTRL_PROG_UP = ecodes.KEY_PAGEUP
    CTRL_PROG_DOWN = ecodes.KEY_PAGEDOWN
    CTRL_PANIC = ecodes.KEY_ESC
    CTRL_HELP = ecodes.KEY_SLASH  # ? key (with shift)
    CTRL_TRANSPOSE_UP = ecodes.KEY_DOT     # > key
    CTRL_TRANSPOSE_DOWN = ecodes.KEY_COMMA  # < key
    CTRL_LAYER = ecodes.KEY_L
    CTRL_ARP = ecodes.KEY_A
    CTRL_SOUNDFONT = ecodes.KEY_TAB
    CTRL_DOWNLOAD = ecodes.KEY_D
    CTRL_MIDI = ecodes.KEY_M  # Toggle MIDI input (FW16 Piano Keyboard Module)
    CTRL_FAVORITE = ecodes.KEY_F
    
    NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    
    PRESET_KEYS = [
        ecodes.KEY_F1, ecodes.KEY_F2, ecodes.KEY_F3, ecodes.KEY_F4,
        ecodes.KEY_F5, ecodes.KEY_F6, ecodes.KEY_F7, ecodes.KEY_F8,
        ecodes.KEY_F9, ecodes.KEY_F10, ecodes.KEY_F11, ecodes.KEY_F12,
    ]
    
    @classmethod
    def get_note(cls, keycode: int, base_octave: int, transpose: int = 0) -> Optional[int]:
        if keycode not in cls.NOTE_MAP:
            return None
        offset = cls.NOTE_MAP[keycode]
        note = (base_octave * 12) + offset + transpose
        return max(0, min(127, note))
    
    @classmethod
    def get_key_char(cls, keycode: int) -> Optional[str]:
        return cls.KEY_CHARS.get(keycode)
    
    @classmethod
    def note_name(cls, note: int) -> str:
        octave = (note // 12) - 1
        name = cls.NOTE_NAMES[note % 12]
        return f"{name}{octave}"


# =============================================================================
# PARAMETER SMOOTHER
# =============================================================================

class ParameterSmoother:
    def __init__(self, smoothing: float = 0.9, threshold: float = 0.001):
        self.smoothing = smoothing
        self.threshold = threshold
        self._current: Dict[str, float] = {}
        self._target: Dict[str, float] = {}
    
    def set_target(self, name: str, value: float):
        self._target[name] = value
        if name not in self._current:
            self._current[name] = value
    
    def get(self, name: str, default: float = 0.0) -> float:
        return self._current.get(name, default)
    
    def update(self) -> Dict[str, float]:
        changed = {}
        for name, target in self._target.items():
            current = self._current.get(name, target)
            new_val = current * self.smoothing + target * (1 - self.smoothing)
            if abs(new_val - current) > self.threshold:
                self._current[name] = new_val
                changed[name] = new_val
            elif abs(target - current) > self.threshold:
                self._current[name] = target
                changed[name] = target
        return changed


# =============================================================================
# VELOCITY TRACKER
# =============================================================================

class VelocityTracker:
    def __init__(self, config: SynthConfig):
        self.config = config
        self._last_release: Dict[int, float] = {}
    
    def key_pressed(self, keycode: int) -> int:
        if self.config.velocity_fixed is not None:
            return self.config.velocity_fixed
        
        now = time.perf_counter()
        if keycode in self._last_release:
            elapsed = now - self._last_release[keycode]
        else:
            elapsed = (self.config.velocity_time_fast + self.config.velocity_time_slow) / 2
        
        return self._time_to_velocity(elapsed)
    
    def key_released(self, keycode: int):
        self._last_release[keycode] = time.perf_counter()
    
    def _time_to_velocity(self, elapsed: float) -> int:
        t_fast = self.config.velocity_time_fast
        t_slow = self.config.velocity_time_slow
        v_min = self.config.velocity_min
        v_max = self.config.velocity_max
        
        elapsed = max(t_fast, min(t_slow, elapsed))
        normalized = (elapsed - t_fast) / (t_slow - t_fast)
        
        if self.config.velocity_curve == "soft":
            normalized = math.sqrt(normalized)
        elif self.config.velocity_curve == "hard":
            normalized = normalized ** 2
        
        velocity = int(v_max - normalized * (v_max - v_min))
        return max(1, min(127, velocity))


# =============================================================================
# TOUCHPAD CONTROLLER
# =============================================================================

@dataclass
class TouchpadState:
    x: float = 0.5
    y: float = 0.5
    pressure: float = 0.0
    touching: bool = False
    x_min: int = 0
    x_max: int = 1
    y_min: int = 0
    y_max: int = 1
    pressure_min: int = 0
    pressure_max: int = 1


class TouchpadController:
    def __init__(self, config: SynthConfig, smoother: ParameterSmoother):
        self.config = config
        self.smoother = smoother
        self.state = TouchpadState()
    
    def calibrate(self, device: InputDevice):
        caps = device.capabilities()
        for item in caps.get(ecodes.EV_ABS, []):
            if not isinstance(item, tuple):
                continue
            code, info = item
            if code in (ecodes.ABS_X, ecodes.ABS_MT_POSITION_X):
                self.state.x_min, self.state.x_max = info.min, info.max
            elif code in (ecodes.ABS_Y, ecodes.ABS_MT_POSITION_Y):
                self.state.y_min, self.state.y_max = info.min, info.max
            elif code in (ecodes.ABS_PRESSURE, ecodes.ABS_MT_PRESSURE):
                self.state.pressure_min, self.state.pressure_max = info.min, info.max
        
        log.info(f"Touchpad: X={self.state.x_min}-{self.state.x_max} Y={self.state.y_min}-{self.state.y_max}")
    
    def handle_event(self, event) -> bool:
        changed = False
        
        if event.type == ecodes.EV_ABS:
            code, value = event.code, event.value
            
            if code in (ecodes.ABS_X, ecodes.ABS_MT_POSITION_X):
                self.state.x = self._normalize(value, self.state.x_min, self.state.x_max)
                self.smoother.set_target('touch_x', self.state.x)
                changed = True
            elif code in (ecodes.ABS_Y, ecodes.ABS_MT_POSITION_Y):
                self.state.y = self._normalize(value, self.state.y_min, self.state.y_max)
                self.smoother.set_target('touch_y', self.state.y)
                changed = True
            elif code in (ecodes.ABS_PRESSURE, ecodes.ABS_MT_PRESSURE):
                self.state.pressure = self._normalize(value, self.state.pressure_min, self.state.pressure_max)
                self.smoother.set_target('touch_pressure', self.state.pressure)
                changed = True
        
        elif event.type == ecodes.EV_KEY and event.code == ecodes.BTN_TOUCH:
            self.state.touching = bool(event.value)
            if not self.state.touching:
                self.smoother.set_target('touch_x', 0.5)
                self.smoother.set_target('touch_pressure', 0.0)
            changed = True
        
        return changed
    
    def _normalize(self, value: int, min_val: int, max_val: int) -> float:
        if max_val == min_val:
            return 0.5
        return max(0.0, min(1.0, (value - min_val) / (max_val - min_val)))


# =============================================================================
# FLUIDSYNTH ENGINE
# =============================================================================

class FluidSynthEngine:
    def __init__(self, config: SynthConfig):
        self.config = config
        self.fs: Optional[fluidsynth.Synth] = None
        self.sfid: int = -1
        self.channel: int = config.midi_channel
        self.layer_channel: int = 1
        self._initialized = False
    
    def initialize(self, soundfont_path: Optional[Path] = None) -> bool:
        try:
            self.fs = fluidsynth.Synth()
            driver = self.config.audio_driver.value
            log.info(f"Starting FluidSynth ({driver})")
            self.fs.start(driver=driver)
            
            if soundfont_path and soundfont_path.exists():
                return self.load_soundfont(soundfont_path)
            
            self._initialized = True
            return True
        except Exception as e:
            log.error(f"FluidSynth init failed: {e}")
            return False
    
    def load_soundfont(self, path: Path) -> bool:
        """Load a soundfont (can be called at runtime)"""
        try:
            # Unload previous
            if self.sfid >= 0:
                self.all_notes_off()
                self.fs.sfunload(self.sfid)
            
            log.info(f"Loading: {path.name}")
            self.sfid = self.fs.sfload(str(path))
            
            if self.sfid < 0:
                log.error("Failed to load soundfont")
                return False
            
            # Initialize channels
            self.fs.program_select(self.channel, self.sfid, 0, 0)
            self.fs.program_select(self.layer_channel, self.sfid, 0, 48)
            
            # Set pitch bend range
            self._set_pitch_bend_range(self.config.pitch_bend_semitones)
            
            self._initialized = True
            return True
        except Exception as e:
            log.error(f"Load soundfont failed: {e}")
            return False
    
    def _set_pitch_bend_range(self, semitones: int):
        for ch in [self.channel, self.layer_channel]:
            self.fs.cc(ch, 101, 0)
            self.fs.cc(ch, 100, 0)
            self.fs.cc(ch, 6, semitones)
            self.fs.cc(ch, 38, 0)
            self.fs.cc(ch, 101, 127)
            self.fs.cc(ch, 100, 127)
    
    def note_on(self, note: int, velocity: int, layer: bool = False):
        if self._initialized:
            self.fs.noteon(self.channel, note, velocity)
            if layer:
                self.fs.noteon(self.layer_channel, note, max(1, velocity - 20))
    
    def note_off(self, note: int, layer: bool = False):
        if self._initialized:
            self.fs.noteoff(self.channel, note)
            if layer:
                self.fs.noteoff(self.layer_channel, note)
    
    def pitch_bend(self, value: int, layer: bool = False):
        if self._initialized:
            value = max(0, min(16383, value))
            self.fs.pitch_bend(self.channel, value)
            if layer:
                self.fs.pitch_bend(self.layer_channel, value)
    
    def control_change(self, cc: int, value: int, layer: bool = False):
        if self._initialized:
            value = max(0, min(127, value))
            self.fs.cc(self.channel, cc, value)
            if layer:
                self.fs.cc(self.layer_channel, cc, value)
    
    def program_change(self, program: int, bank: int = 0, channel: Optional[int] = None):
        if self._initialized:
            ch = channel if channel is not None else self.channel
            self.fs.program_select(ch, self.sfid, bank, program % 128)
    
    def all_notes_off(self):
        if self._initialized:
            for ch in [self.channel, self.layer_channel]:
                self.fs.cc(ch, 123, 0)
                self.fs.cc(ch, 121, 0)
    
    def shutdown(self):
        if self.fs:
            self.all_notes_off()
            self.fs.delete()
            self.fs = None
            self._initialized = False


# =============================================================================
# ARPEGGIATOR
# =============================================================================

class Arpeggiator:
    """Simple arpeggiator for held notes"""
    
    def __init__(self, engine: FluidSynthEngine):
        self.engine = engine
        self.mode = ArpMode.OFF
        self.tempo_bpm: float = 120.0
        self.note_div: float = 0.25  # Quarter notes
        
        self._held_notes: List[int] = []
        self._current_idx: int = 0
        self._last_note: Optional[int] = None
        self._direction: int = 1
        self._running = False
        self._task: Optional[asyncio.Task] = None
    
    def set_mode(self, mode: ArpMode):
        self.mode = mode
        self._current_idx = 0
        self._direction = 1
    
    def note_on(self, note: int):
        if note not in self._held_notes:
            self._held_notes.append(note)
            self._held_notes.sort()
    
    def note_off(self, note: int):
        if note in self._held_notes:
            self._held_notes.remove(note)
    
    def clear(self):
        self._held_notes.clear()
        self._current_idx = 0
    
    async def run(self, velocity_callback: Callable[[], int], layer: bool = False):
        """Arpeggiator loop"""
        self._running = True
        
        while self._running:
            if self.mode == ArpMode.OFF or not self._held_notes:
                await asyncio.sleep(0.05)
                continue
            
            # Calculate timing
            beat_ms = 60000 / self.tempo_bpm
            note_ms = beat_ms * self.note_div
            
            # Turn off last note
            if self._last_note is not None:
                self.engine.note_off(self._last_note, layer)
            
            # Get next note
            note = self._get_next_note()
            if note is not None:
                vel = velocity_callback()
                self.engine.note_on(note, vel, layer)
                self._last_note = note
            
            await asyncio.sleep(note_ms / 1000 * 0.9)  # Slightly shorter for articulation
    
    def _get_next_note(self) -> Optional[int]:
        if not self._held_notes:
            return None
        
        import random
        
        if self.mode == ArpMode.UP:
            note = self._held_notes[self._current_idx % len(self._held_notes)]
            self._current_idx = (self._current_idx + 1) % len(self._held_notes)
        
        elif self.mode == ArpMode.DOWN:
            note = self._held_notes[-(self._current_idx % len(self._held_notes)) - 1]
            self._current_idx = (self._current_idx + 1) % len(self._held_notes)
        
        elif self.mode == ArpMode.UP_DOWN:
            idx = self._current_idx % len(self._held_notes)
            note = self._held_notes[idx] if self._direction > 0 else self._held_notes[-(idx + 1)]
            self._current_idx += 1
            if self._current_idx >= len(self._held_notes):
                self._current_idx = 0
                self._direction *= -1
        
        elif self.mode == ArpMode.RANDOM:
            note = random.choice(self._held_notes)
        
        else:
            note = None
        
        return note
    
    def stop(self):
        self._running = False
        if self._last_note is not None:
            self.engine.note_off(self._last_note)
            self._last_note = None


# =============================================================================
# MIDI INPUT CONTROLLER (Framework 16 Piano Keyboard Module Support)
# =============================================================================

class MIDIInputController:
    """
    MIDI input handler for external MIDI devices.
    
    Supports the Framework 16 Piano Keyboard Module (pitstop_tech) and other
    USB MIDI controllers. Features:
    - Auto-detection of MIDI input devices
    - Velocity-sensitive note input
    - Aftertouch (channel pressure) support
    - Pitch bend and CC passthrough
    - Hot-plug detection
    
    The FW16 Piano Keyboard Module appears as a standard USB MIDI device
    with velocity and aftertouch support.
    """
    
    # Known Framework 16 MIDI module identifiers
    FW16_MIDI_KEYWORDS = ['framework', 'fw16', 'piano', 'pitstop']
    
    def __init__(self, engine: FluidSynthEngine, callback: Optional[Callable] = None):
        self.engine = engine
        self.callback = callback  # For UI updates
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._midi_in = None
        self._port_name: str = ""
        self._connected = False
        self._last_activity = 0.0
        
        # State tracking
        self._active_notes: Set[int] = set()
        self._aftertouch_value: int = 0
        self._pitch_bend: int = 8192  # Center
        
        if not RTMIDI_AVAILABLE:
            log.warning("python-rtmidi not available - MIDI input disabled")
            log.info("Install with: pip install python-rtmidi")
    
    @property
    def available(self) -> bool:
        return RTMIDI_AVAILABLE
    
    @property
    def connected(self) -> bool:
        return self._connected
    
    @property
    def port_name(self) -> str:
        return self._port_name
    
    def list_ports(self) -> List[str]:
        """List available MIDI input ports"""
        if not RTMIDI_AVAILABLE:
            return []
        
        try:
            midi_in = rtmidi.RtMidiIn()
            ports = []
            for i in range(midi_in.getPortCount()):
                ports.append(midi_in.getPortName(i))
            return ports
        except Exception as e:
            log.error(f"Error listing MIDI ports: {e}")
            return []
    
    def find_fw16_module(self) -> Optional[int]:
        """
        Find the Framework 16 Piano Keyboard Module by name.
        Returns port index or None if not found.
        """
        ports = self.list_ports()
        for i, name in enumerate(ports):
            name_lower = name.lower()
            if any(kw in name_lower for kw in self.FW16_MIDI_KEYWORDS):
                log.info(f"Found FW16 MIDI module: {name}")
                return i
        return None
    
    def connect(self, port: Optional[int] = None, port_name: Optional[str] = None) -> bool:
        """
        Connect to a MIDI input port.
        
        Args:
            port: Port index (0-based)
            port_name: Substring of port name to match
            
        If neither specified, auto-detects FW16 module or uses first available.
        """
        if not RTMIDI_AVAILABLE:
            return False
        
        try:
            self._midi_in = rtmidi.RtMidiIn()
            ports = self.list_ports()
            
            if not ports:
                log.warning("No MIDI input ports available")
                return False
            
            # Determine which port to open
            target_port = None
            
            if port is not None:
                if 0 <= port < len(ports):
                    target_port = port
                else:
                    log.error(f"Invalid port index: {port}")
                    return False
            elif port_name:
                # Match by name substring
                for i, name in enumerate(ports):
                    if port_name.lower() in name.lower():
                        target_port = i
                        break
                if target_port is None:
                    log.error(f"No port matching '{port_name}' found")
                    return False
            else:
                # Auto-detect: prefer FW16 module, fallback to first
                target_port = self.find_fw16_module()
                if target_port is None and ports:
                    target_port = 0
            
            if target_port is None:
                return False
            
            # Open the port
            self._midi_in.openPort(target_port)
            self._port_name = ports[target_port]
            self._connected = True
            
            log.info(f"Connected to MIDI input: {self._port_name}")
            return True
            
        except Exception as e:
            log.error(f"Failed to connect to MIDI port: {e}")
            self._connected = False
            return False
    
    def disconnect(self):
        """Disconnect from MIDI port"""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        
        if self._midi_in:
            try:
                self._midi_in.closePort()
            except:
                pass
            self._midi_in = None
        
        self._connected = False
        self._port_name = ""
        log.info("MIDI input disconnected")
    
    def start(self):
        """Start MIDI input processing in background thread"""
        if not self._connected:
            log.warning("Cannot start MIDI input - not connected")
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._midi_loop, daemon=True)
        self._thread.start()
        log.info("MIDI input processing started")
    
    def stop(self):
        """Stop MIDI input processing"""
        self._running = False
        # Send note-offs for any stuck notes
        for note in list(self._active_notes):
            self.engine.note_off(note)
        self._active_notes.clear()
    
    def _midi_loop(self):
        """Background thread for MIDI message processing"""
        while self._running and self._midi_in:
            try:
                msg = self._midi_in.getMessage(50)  # 50ms timeout
                if msg:
                    self._process_message(msg)
            except Exception as e:
                log.error(f"MIDI input error: {e}")
                time.sleep(0.1)
    
    def _process_message(self, msg):
        """Process incoming MIDI message"""
        self._last_activity = time.time()
        
        # rtmidi returns MidiMessage object with various methods
        if msg.isNoteOn():
            note = msg.getNoteNumber()
            velocity = msg.getVelocity()
            
            if velocity > 0:
                self._active_notes.add(note)
                self.engine.note_on(note, velocity)
                
                if self.callback:
                    note_name = self._note_name(note)
                    self.callback('note_on', note, note_name, velocity)
            else:
                # Note on with velocity 0 = note off
                self._active_notes.discard(note)
                self.engine.note_off(note)
                
                if self.callback:
                    note_name = self._note_name(note)
                    self.callback('note_off', note, note_name, 0)
        
        elif msg.isNoteOff():
            note = msg.getNoteNumber()
            self._active_notes.discard(note)
            self.engine.note_off(note)
            
            if self.callback:
                note_name = self._note_name(note)
                self.callback('note_off', note, note_name, 0)
        
        elif msg.isAftertouch():
            # Channel aftertouch - send as expression
            value = msg.getAfterTouchValue()
            self._aftertouch_value = value
            # Map aftertouch to expression (CC 11)
            self.engine.control_change(11, value)
            
            if self.callback:
                self.callback('aftertouch', value, '', 0)
        
        elif msg.isController():
            cc = msg.getControllerNumber()
            value = msg.getControllerValue()
            self.engine.control_change(cc, value)
            
            if self.callback:
                self.callback('cc', cc, f'CC{cc}', value)
        
        elif msg.isPitchWheel():
            # Pitch bend: 0-16383, center at 8192
            value = msg.getPitchWheelValue()
            self._pitch_bend = value
            self.engine.pitch_bend(value)
            
            if self.callback:
                normalized = (value - 8192) / 8192.0
                self.callback('pitch_bend', value, '', int(normalized * 100))
        
        elif msg.isProgramChange():
            program = msg.getProgramChangeNumber()
            self.engine.program_change(program)
            
            if self.callback:
                self.callback('program', program, GM_INSTRUMENTS[program], 0)
    
    def _note_name(self, note: int) -> str:
        """Convert MIDI note to name (e.g., 60 -> 'C4')"""
        names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        octave = (note // 12) - 1
        name = names[note % 12]
        return f"{name}{octave}"


# =============================================================================
# MAIN SYNTHESIZER
# =============================================================================

class FW16Synth:
    """Main synthesizer controller"""
    
    def __init__(self, config: SynthConfig):
        self.config = config
        
        # Components
        self.sf_manager = SoundFontManager()
        self.sf_downloader = SoundFontDownloader()
        self.engine = FluidSynthEngine(config)
        self.smoother = ParameterSmoother(config.touchpad_smoothing)
        self.touchpad = TouchpadController(config, self.smoother)
        self.velocity = VelocityTracker(config)
        self.arpeggiator = Arpeggiator(self.engine)
        self.ui = TerminalUI(config) if config.show_tui else None
        
        # MIDI input (for FW16 Piano Keyboard Module and other USB MIDI devices)
        self.midi_input: Optional[MIDIInputController] = None
        self._midi_enabled = config.midi_input_enabled if hasattr(config, 'midi_input_enabled') else False
        self._midi_port = config.midi_port if hasattr(config, 'midi_port') else None
        
        # State
        self.octave = config.base_octave
        self.transpose = 0
        self.program = 0
        self.sustain = False
        self.layer_enabled = False
        self.layer_program = 48
        
        self._active_notes: Dict[int, int] = {}
        self._running = False
        self._devices: List[InputDevice] = []
        self._grabbed: List[InputDevice] = []
        
        # Shift key state for special commands
        self._shift_held = False
        
        # Presets
        self._preset_map = {p.hotkey: p for p in config.presets if p.hotkey}
    
    def initialize(self) -> bool:
        log.info("Initializing FW16 Synth...")
        
        # Scan for soundfonts
        self.sf_manager.scan()
        
        # Find soundfont
        sf_path = None
        if self.config.soundfont:
            sf_path = Path(self.config.soundfont)
        if not sf_path or not sf_path.exists():
            sf_path = self.sf_manager.find_default()
        
        if not sf_path:
            log.error("No soundfont found!")
            return False
        
        # Initialize engine
        if not self.engine.initialize(sf_path):
            return False
        
        self.sf_manager.set_current(sf_path)
        
        if self.ui:
            self.ui.set_soundfont(sf_path.stem, str(sf_path))
            self.ui.browser_items = self.sf_manager.soundfonts
        
        # Find input devices
        if not self._find_devices():
            log.error("No input devices found")
            return False
        
        # Initialize MIDI input (FW16 Piano Keyboard Module support)
        if self._midi_enabled or RTMIDI_AVAILABLE:
            self._setup_midi_input()
        
        log.info("Initialization complete")
        return True
    
    def _setup_midi_input(self):
        """Setup MIDI input controller for FW16 Piano Keyboard Module"""
        if not RTMIDI_AVAILABLE:
            log.info("MIDI input not available (install python-rtmidi)")
            return
        
        self.midi_input = MIDIInputController(self.engine, self._midi_callback)
        
        # List available MIDI ports
        ports = self.midi_input.list_ports()
        if ports:
            log.info(f"Available MIDI ports: {len(ports)}")
            for i, port in enumerate(ports):
                log.debug(f"  [{i}] {port}")
        
        # Auto-connect if enabled
        if self._midi_enabled:
            if self.midi_input.connect(port_name=self._midi_port):
                self.midi_input.start()
                if self.ui:
                    self.ui.midi_connected = True
                    self.ui.midi_port_name = self.midi_input.port_name
            else:
                log.warning("MIDI input: no device connected")
    
    def _midi_callback(self, event_type: str, value: int, name: str, extra: int):
        """Callback from MIDI input for UI updates"""
        if not self.ui:
            return
        
        if event_type == 'note_on':
            self.ui.last_velocity = extra
            self.ui.add_activity(f"MIDI: {name} ON vel={extra}")
        elif event_type == 'note_off':
            self.ui.add_activity(f"MIDI: {name} OFF")
        elif event_type == 'aftertouch':
            self.ui.add_activity(f"MIDI: Aftertouch {value}")
        elif event_type == 'pitch_bend':
            bend_pct = extra
            self.ui.add_activity(f"MIDI: Pitch Bend {bend_pct:+d}%")
        elif event_type == 'program':
            self.ui.set_program(value, name)
            self.ui.add_activity(f"MIDI: Program → {name}")
    
    def _toggle_midi_input(self):
        """Toggle MIDI input on/off (FW16 Piano Keyboard Module support)"""
        if not RTMIDI_AVAILABLE:
            if self.ui:
                self.ui.add_activity("MIDI: Not available (install python-rtmidi)")
            log.warning("MIDI input not available - install python-rtmidi")
            return
        
        if self.midi_input and self.midi_input.connected:
            # Disconnect
            self.midi_input.stop()
            self.midi_input.disconnect()
            if self.ui:
                self.ui.midi_connected = False
                self.ui.midi_port_name = ""
                self.ui.add_activity("MIDI: Disconnected")
            log.info("MIDI input disabled")
        else:
            # Connect
            if self.midi_input is None:
                self.midi_input = MIDIInputController(self.engine, self._midi_callback)
            
            # Try to connect (auto-detect FW16 module or use first available)
            if self.midi_input.connect(port_name=self._midi_port):
                self.midi_input.start()
                if self.ui:
                    self.ui.midi_connected = True
                    self.ui.midi_port_name = self.midi_input.port_name
                    self.ui.add_activity(f"MIDI: {self.midi_input.port_name[:30]}")
                log.info(f"MIDI input enabled: {self.midi_input.port_name}")
            else:
                if self.ui:
                    self.ui.add_activity("MIDI: No devices found")
                log.warning("No MIDI devices found")
    
    def _find_devices(self) -> bool:
        try:
            device_paths = evdev.list_devices()
            if not device_paths:
                log.error("No input devices found. Check permissions:")
                log.error("  1. Add yourself to 'input' group: sudo usermod -aG input $USER")
                log.error("  2. Log out and back in (or reboot)")
                log.error("  3. Verify with: groups | grep input")
                return False
            devices = [InputDevice(p) for p in device_paths]
        except PermissionError as e:
            log.error(f"Permission denied accessing input devices: {e}")
            log.error("Fix: sudo usermod -aG input $USER && logout")
            return False
        except Exception as e:
            log.error(f"Device enumeration failed: {e}")
            return False
        
        kb_found = tp_found = False
        
        for dev in devices:
            try:
                caps = dev.capabilities()
                name = dev.name.lower()
                
                if ecodes.EV_KEY in caps:
                    if ecodes.KEY_Q in caps[ecodes.EV_KEY]:
                        log.info(f"Keyboard: {dev.name}")
                        self._devices.append(dev)
                        kb_found = True
                
                if self.config.touchpad_enabled and ecodes.EV_ABS in caps:
                    abs_caps = [c[0] if isinstance(c, tuple) else c for c in caps[ecodes.EV_ABS]]
                    if ecodes.ABS_X in abs_caps or ecodes.ABS_MT_POSITION_X in abs_caps:
                        if any(t in name for t in ['touchpad', 'trackpad', 'touch']):
                            log.info(f"Touchpad: {dev.name}")
                            self._devices.append(dev)
                            self.touchpad.calibrate(dev)
                            tp_found = True
            except Exception as e:
                log.debug(f"Device check error: {e}")
        
        if not kb_found:
            log.error("No keyboard found among available devices.")
            log.error("Available devices:")
            for dev in devices:
                log.error(f"  - {dev.name} ({dev.path})")
        
        return kb_found
    
    def _handle_key_event(self, event):
        keycode = event.code
        
        # Track shift state
        if keycode in (ecodes.KEY_LEFTSHIFT, ecodes.KEY_RIGHTSHIFT):
            self._shift_held = event.value != 0
            return
        
        # Key down
        if event.value == 1:
            # Browser mode navigation
            if self.ui and self.ui.mode == UIMode.SOUNDFONT_BROWSER:
                self._handle_browser_key(keycode)
                return
            
            # Download browser mode
            if self.ui and self.ui.mode == UIMode.DOWNLOAD_BROWSER:
                self._handle_download_browser_key(keycode)
                return
            
            # Help mode - any key closes
            if self.ui and self.ui.mode == UIMode.HELP:
                self.ui.mode = UIMode.NORMAL
                return
            
            # Special keys with shift
            if self._shift_held:
                if keycode == ecodes.KEY_SLASH:  # ? = help
                    if self.ui:
                        self.ui.mode = UIMode.HELP
                    return
            
            # Control keys
            if keycode == KeyboardMapper.CTRL_OCTAVE_UP:
                self.octave = min(8, self.octave + 1)
                if self.ui:
                    self.ui.set_octave(self.octave)
                return
            
            elif keycode == KeyboardMapper.CTRL_OCTAVE_DOWN:
                self.octave = max(0, self.octave - 1)
                if self.ui:
                    self.ui.set_octave(self.octave)
                return
            
            elif keycode == KeyboardMapper.CTRL_TRANSPOSE_UP and self._shift_held:
                self.transpose = min(12, self.transpose + 1)
                if self.ui:
                    self.ui.set_transpose(self.transpose)
                return
            
            elif keycode == KeyboardMapper.CTRL_TRANSPOSE_DOWN and self._shift_held:
                self.transpose = max(-12, self.transpose - 1)
                if self.ui:
                    self.ui.set_transpose(self.transpose)
                return
            
            elif keycode == KeyboardMapper.CTRL_PROG_UP:
                self._change_program(self.program + 1)
                return
            
            elif keycode == KeyboardMapper.CTRL_PROG_DOWN:
                self._change_program(self.program - 1)
                return
            
            elif keycode == KeyboardMapper.CTRL_PANIC:
                self._panic()
                return
            
            elif keycode == KeyboardMapper.CTRL_SUSTAIN:
                self.sustain = True
                self.engine.control_change(64, 127, self.layer_enabled)
                if self.ui:
                    self.ui.set_sustain(True)
                return
            
            elif keycode == KeyboardMapper.CTRL_SOUNDFONT:
                if self.ui:
                    if self.ui.mode == UIMode.SOUNDFONT_BROWSER:
                        self.ui.mode = UIMode.NORMAL
                    else:
                        self.ui.mode = UIMode.SOUNDFONT_BROWSER
                return
            
            elif keycode == KeyboardMapper.CTRL_DOWNLOAD:
                if self.ui:
                    if self.ui.mode == UIMode.DOWNLOAD_BROWSER:
                        self.ui.mode = UIMode.NORMAL
                    else:
                        # Populate download catalog
                        catalog = self.sf_downloader.get_catalog()
                        for sf in catalog:
                            sf._downloaded = self.sf_downloader.is_downloaded(sf)
                        self.ui.download_items = catalog
                        self.ui.download_index = 0
                        self.ui.download_scroll = 0
                        self.ui.mode = UIMode.DOWNLOAD_BROWSER
                return
            
            elif keycode == KeyboardMapper.CTRL_MIDI:
                # Toggle MIDI input (FW16 Piano Keyboard Module)
                self._toggle_midi_input()
                return
            
            elif keycode == KeyboardMapper.CTRL_LAYER:
                self.layer_enabled = not self.layer_enabled
                if self.ui:
                    self.ui.set_layer(self.layer_enabled, self.layer_program)
                return
            
            elif keycode == KeyboardMapper.CTRL_ARP:
                modes = list(ArpMode)
                current_idx = modes.index(self.arpeggiator.mode)
                new_mode = modes[(current_idx + 1) % len(modes)]
                self.arpeggiator.set_mode(new_mode)
                if self.ui:
                    self.ui.set_arp_mode(new_mode)
                return
            
            # Presets
            elif keycode in self._preset_map:
                preset = self._preset_map[keycode]
                self._change_program(preset.program, preset.bank)
                return
            
            # Note keys
            note = KeyboardMapper.get_note(keycode, self.octave, self.transpose)
            if note is not None and keycode not in self._active_notes:
                velocity = self.velocity.key_pressed(keycode)
                self._active_notes[keycode] = note
                
                if self.arpeggiator.mode != ArpMode.OFF:
                    self.arpeggiator.note_on(note)
                else:
                    self.engine.note_on(note, velocity, self.layer_enabled)
                
                if self.ui:
                    key_char = KeyboardMapper.get_key_char(keycode) or '?'
                    note_name = KeyboardMapper.note_name(note)
                    self.ui.note_on(key_char, note_name, velocity)
        
        # Key up
        elif event.value == 0:
            if keycode == KeyboardMapper.CTRL_SUSTAIN:
                self.sustain = False
                self.engine.control_change(64, 0, self.layer_enabled)
                if self.ui:
                    self.ui.set_sustain(False)
                return
            
            if keycode in self._active_notes:
                note = self._active_notes.pop(keycode)
                self.velocity.key_released(keycode)
                
                if self.arpeggiator.mode != ArpMode.OFF:
                    self.arpeggiator.note_off(note)
                else:
                    self.engine.note_off(note, self.layer_enabled)
                
                if self.ui:
                    key_char = KeyboardMapper.get_key_char(keycode) or '?'
                    note_name = KeyboardMapper.note_name(note)
                    self.ui.note_off(key_char, note_name)
    
    def _handle_browser_key(self, keycode: int):
        """Handle key in soundfont browser"""
        if not self.ui:
            return
        
        items = self.ui.browser_items
        
        if keycode == ecodes.KEY_UP:
            self.ui.browser_index = max(0, self.ui.browser_index - 1)
        
        elif keycode == ecodes.KEY_DOWN:
            self.ui.browser_index = min(len(items) - 1, self.ui.browser_index + 1)
        
        elif keycode == ecodes.KEY_PAGEUP:
            self.ui.browser_index = max(0, self.ui.browser_index - 10)
        
        elif keycode == ecodes.KEY_PAGEDOWN:
            self.ui.browser_index = min(len(items) - 1, self.ui.browser_index + 10)
        
        elif keycode == ecodes.KEY_ENTER:
            if 0 <= self.ui.browser_index < len(items):
                sf = items[self.ui.browser_index]
                if self.engine.load_soundfont(sf.path):
                    self.sf_manager.set_current(sf.path)
                    self.ui.set_soundfont(sf.name, str(sf.path))
                    self.ui.mode = UIMode.NORMAL
        
        elif keycode == KeyboardMapper.CTRL_FAVORITE:
            if 0 <= self.ui.browser_index < len(items):
                sf = items[self.ui.browser_index]
                self.sf_manager.toggle_favorite(sf.path)
                self.ui.browser_items = self.sf_manager.soundfonts
        
        elif keycode in (ecodes.KEY_ESC, ecodes.KEY_TAB):
            self.ui.mode = UIMode.NORMAL
    
    def _handle_download_browser_key(self, keycode: int):
        """Handle key in download browser"""
        if not self.ui:
            return
        
        items = self.ui.download_items
        
        if keycode == ecodes.KEY_UP:
            self.ui.download_index = max(0, self.ui.download_index - 1)
        
        elif keycode == ecodes.KEY_DOWN:
            self.ui.download_index = min(len(items) - 1, self.ui.download_index + 1)
        
        elif keycode == ecodes.KEY_PAGEUP:
            self.ui.download_index = max(0, self.ui.download_index - 10)
        
        elif keycode == ecodes.KEY_PAGEDOWN:
            self.ui.download_index = min(len(items) - 1, self.ui.download_index + 10)
        
        elif keycode == ecodes.KEY_ENTER:
            if 0 <= self.ui.download_index < len(items):
                sf = items[self.ui.download_index]
                
                # Check if already downloaded
                if self.sf_downloader.is_downloaded(sf):
                    # Load the already-downloaded soundfont
                    path = self.sf_downloader.get_downloaded_path(sf)
                    if path and self.engine.load_soundfont(path):
                        self.sf_manager.scan()  # Rescan to include new font
                        self.sf_manager.set_current(path)
                        self.ui.set_soundfont(path.stem, str(path))
                        self.ui.browser_items = self.sf_manager.soundfonts
                        self.ui.mode = UIMode.NORMAL
                        self.ui.log(f"Loaded: {sf.name}")
                else:
                    # Start download in background
                    self.ui.download_active = True
                    self.ui.download_progress = 0
                    self.ui.download_status = "Starting download..."
                    
                    def progress_callback(pct, msg):
                        self.ui.download_progress = pct
                        self.ui.download_status = msg
                    
                    # Run download in thread to not block UI
                    import threading
                    def do_download():
                        try:
                            path = self.sf_downloader.download(sf, progress_callback)
                            if path:
                                sf._downloaded = True
                                self.ui.download_status = f"Downloaded: {sf.name}"
                                # Rescan soundfonts
                                self.sf_manager.scan()
                                self.ui.browser_items = self.sf_manager.soundfonts
                                self.ui.log(f"Downloaded: {sf.name}")
                            else:
                                self.ui.download_status = "Download failed!"
                        finally:
                            self.ui.download_active = False
                    
                    thread = threading.Thread(target=do_download, daemon=True)
                    thread.start()
        
        elif keycode in (ecodes.KEY_ESC, ecodes.KEY_D):
            self.ui.mode = UIMode.NORMAL
    
    def _handle_touchpad_event(self, event):
        if self.touchpad.handle_event(event):
            self._update_modulation()
    
    def _update_modulation(self):
        state = self.touchpad.state
        
        for routing in self.config.mod_routing:
            if routing.source == ModSource.TOUCHPAD_X:
                value = state.x
            elif routing.source == ModSource.TOUCHPAD_Y:
                value = state.y
            elif routing.source == ModSource.TOUCHPAD_PRESSURE:
                value = state.pressure
            else:
                continue
            
            if routing.invert:
                value = 1.0 - value
            value *= routing.amount
            
            if routing.destination == ModDest.PITCH_BEND:
                bipolar = (value - routing.center) * 2
                midi_val = int(8192 + bipolar * 8191)
                self.engine.pitch_bend(midi_val, self.layer_enabled)
                if self.ui:
                    self.ui.set_pitch_bend(bipolar)
            else:
                cc = MOD_DEST_CC.get(routing.destination)
                if cc:
                    midi_val = int(value * 127)
                    self.engine.control_change(cc, midi_val, self.layer_enabled)
                    if self.ui:
                        self.ui.set_mod(routing.destination, value)
        
        if self.ui:
            self.ui.set_touchpad(state.x, state.y, state.pressure, state.touching)
    
    def _change_program(self, program: int, bank: int = 0):
        self.program = program % 128
        self.engine.program_change(self.program, bank)
        name = GM_INSTRUMENTS[self.program]
        if self.ui:
            self.ui.set_program(self.program, name)
        else:
            log.info(f"Program: {self.program} - {name}")
    
    def _panic(self):
        self.engine.all_notes_off()
        self._active_notes.clear()
        self.arpeggiator.clear()
        if self.ui:
            self.ui.active_keys.clear()
            self.ui.last_chord.clear()
            self.ui.log("PANIC - All notes off")
    
    async def _device_loop(self, device: InputDevice):
        try:
            async for event in device.async_read_loop():
                if not self._running:
                    break
                if event.type == ecodes.EV_KEY:
                    self._handle_key_event(event)
                elif event.type == ecodes.EV_ABS:
                    self._handle_touchpad_event(event)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            log.error(f"Device loop error: {e}")
    
    async def _ui_loop(self):
        if not self.ui:
            return
        interval = 1.0 / self.config.refresh_rate
        try:
            while self._running:
                self.ui.update()
                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            pass
    
    async def _smoother_loop(self):
        try:
            while self._running:
                changed = self.smoother.update()
                if changed and self.touchpad.state.touching:
                    self._update_modulation()
                await asyncio.sleep(0.01)
        except asyncio.CancelledError:
            pass
    
    async def _arp_loop(self):
        try:
            await self.arpeggiator.run(
                lambda: self.config.velocity_fixed or 80,
                self.layer_enabled
            )
        except asyncio.CancelledError:
            pass
    
    async def run(self):
        self._running = True
        
        if self.ui:
            self.ui.start()
            self.ui.set_octave(self.octave)
            self.ui.set_program(self.program, GM_INSTRUMENTS[self.program])
        else:
            self._print_banner()
        
        # Grab devices
        for dev in self._devices:
            try:
                dev.grab()
                self._grabbed.append(dev)
            except Exception as e:
                log.warning(f"Could not grab {dev.name}: {e}")
        
        try:
            tasks = [asyncio.create_task(self._device_loop(d)) for d in self._devices]
            if self.ui:
                tasks.append(asyncio.create_task(self._ui_loop()))
            tasks.append(asyncio.create_task(self._smoother_loop()))
            tasks.append(asyncio.create_task(self._arp_loop()))
            
            await asyncio.gather(*tasks, return_exceptions=True)
        finally:
            for dev in self._grabbed:
                try:
                    dev.ungrab()
                except:
                    pass
    
    def _print_banner(self):
        """Print branded banner for non-TUI mode"""
        C = Color.TURQUOISE
        V = Color.VIOLET
        W = Color.WHITE
        G = Color.GRAY
        D = Color.DARK_GRAY
        B = Color.BOLD
        R = Color.RESET
        
        print()
        print(f"{C}{'═' * 72}{R}")
        print(f"{D}{'∿' * 72}{R}")
        print()
        
        # ASCII art logo
        logo = [
            "  ███████╗██╗    ██╗ ██╗ ██████╗     ███████╗██╗   ██╗███╗   ██╗████████╗██╗  ██╗",
            "  ██╔════╝██║    ██║███║██╔════╝     ██╔════╝╚██╗ ██╔╝████╗  ██║╚══██╔══╝██║  ██║",
            "  █████╗  ██║ █╗ ██║╚██║███████╗     ███████╗ ╚████╔╝ ██╔██╗ ██║   ██║   ███████║",
            "  ██╔══╝  ██║███╗██║ ██║██╔═══██╗    ╚════██║  ╚██╔╝  ██║╚██╗██║   ██║   ██╔══██║",
            "  ██║     ╚███╔███╔╝ ██║╚██████╔╝    ███████║   ██║   ██║ ╚████║   ██║   ██║  ██║",
            "  ╚═╝      ╚══╝╚══╝  ╚═╝ ╚═════╝     ╚══════╝   ╚═╝   ╚═╝  ╚═══╝   ╚═╝   ╚═╝  ╚═╝",
        ]
        for line in logo:
            print(f"{C}{line}{R}")
        
        print()
        print(f"{D}{'─' * 72}{R}")
        print(f"{V}{'DeMoD LLC':^72}{R}")
        print(f"{G}{'« Design ≠ Marketing »':^72}{R}")
        print(f"{D}{'─' * 72}{R}")
        print()
        
        # Controls
        print(f"{W}{B}  Controls:{R}")
        print(f"{G}    Keyboard     {W}QWERTY/ASDF/ZXCV = Notes  │  2,3,5,6,7,9,0 = Sharps{R}")
        print(f"{G}    Navigation   {W}+/- = Octave  │  PgUp/Dn = Program  │  F1-F12 = Presets{R}")
        print(f"{G}    Features     {W}Space = Sustain  │  L = Layer  │  A = Arpeggiator{R}")
        print(f"{G}    System       {W}Esc = Panic  │  Ctrl+C = Exit{R}")
        print()
        
        print(f"{D}{'∿' * 72}{R}")
        print(f"{C}{'═' * 72}{R}")
        print()
    
    def stop(self):
        self._running = False
        self.arpeggiator.stop()
        
        # Stop MIDI input
        if self.midi_input:
            self.midi_input.stop()
            self.midi_input.disconnect()
        
        if self.ui:
            self.ui.stop()
        self.engine.shutdown()
        for dev in self._devices:
            try:
                dev.close()
            except:
                pass
        
        # Show exit branding (only in non-TUI mode)
        if not self.config.show_tui:
            print_exit_screen()
        
        log.info("FW16 Synth stopped")


# =============================================================================
# ENTRY POINT
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="FW16 Synth - Transform your Framework 16 into a synthesizer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
{Color.TURQUOISE}Examples:{Color.RESET}
  %(prog)s                           # Start with defaults
  %(prog)s --soundfont /path/to.sf2  # Custom soundfont
  %(prog)s --driver jack             # Use JACK audio
  %(prog)s --no-tui                  # Disable fancy UI

{Color.VIOLET}Press Tab to open the SoundFont browser, ? for help.{Color.RESET}

{Color.GRAY}DeMoD LLC « Design ≠ Marketing »{Color.RESET}
        """
    )
    
    audio = parser.add_argument_group('Audio')
    audio.add_argument('--soundfont', '-s', metavar='PATH', help='SoundFont file (.sf2)')
    audio.add_argument('--driver', '-d', choices=['pipewire', 'pulseaudio', 'jack', 'alsa'],
                       default='pipewire', help='Audio driver')
    
    play = parser.add_argument_group('Playing')
    play.add_argument('--octave', '-o', type=int, default=4, help='Starting octave 0-8')
    play.add_argument('--program', '-p', type=int, default=0, help='Starting program 0-127')
    play.add_argument('--velocity', type=int, help='Fixed velocity 1-127')
    
    # MIDI input for FW16 Piano Keyboard Module
    midi = parser.add_argument_group('MIDI Input (FW16 Piano Keyboard Module)')
    midi.add_argument('--midi', '-m', action='store_true', 
                      help='Enable MIDI input (auto-detect FW16 module)')
    midi.add_argument('--midi-port', metavar='NAME',
                      help='MIDI port name (substring match)')
    midi.add_argument('--midi-list', action='store_true',
                      help='List available MIDI ports and exit')
    
    ui = parser.add_argument_group('Display')
    ui.add_argument('--no-tui', action='store_true', help='Disable terminal UI')
    ui.add_argument('--no-splash', action='store_true', help='Skip startup splash screen')
    
    debug = parser.add_argument_group('Debug')
    debug.add_argument('--verbose', '-v', action='store_true', help='Verbose logging')
    debug.add_argument('--log-file', metavar='PATH', help='Log to file')
    debug.add_argument('--production', action='store_true', help='Enable production mode with glitch prevention and monitoring')
    
    args = parser.parse_args()
    
    # Handle --midi-list
    if args.midi_list:
        print("\n╔══════════════════════════════════════════════════════════════╗")
        print("║  FW16 Synth - Available MIDI Input Ports                     ║")
        print("╠══════════════════════════════════════════════════════════════╣")
        if RTMIDI_AVAILABLE:
            try:
                midi_in = rtmidi.RtMidiIn()
                count = midi_in.getPortCount()
                if count == 0:
                    print("║  No MIDI input ports found.                                  ║")
                else:
                    for i in range(count):
                        name = midi_in.getPortName(i)
                        # Check if it looks like a FW16 module
                        is_fw16 = any(kw in name.lower() for kw in ['framework', 'fw16', 'piano', 'pitstop'])
                        marker = " ← FW16 Module?" if is_fw16 else ""
                        line = f"  [{i}] {name}{marker}"
                        print(f"║{line:<62}║")
            except Exception as e:
                print(f"║  Error: {e:<54}║")
        else:
            print("║  MIDI input not available - install python-rtmidi           ║")
        print("╠══════════════════════════════════════════════════════════════╣")
        print("║  Use: fw16-synth --midi --midi-port 'PortName'               ║")
        print("╚══════════════════════════════════════════════════════════════╝\n")
        sys.exit(0)
    
    # Show splash screen (unless disabled)
    if not args.no_splash and not args.no_tui:
        print_splash_screen()
    
    log_path = Path(args.log_file) if args.log_file else None
    setup_logging(args.verbose, log_path)
    
    config = SynthConfig(
        # Map driver names: pipewire uses pulseaudio API
        audio_driver=AudioDriver.PULSEAUDIO if args.driver in ('pipewire', 'pulseaudio') 
                     else AudioDriver.JACK if args.driver == 'jack' 
                     else AudioDriver.ALSA,
        soundfont=args.soundfont,
        base_octave=args.octave,
        velocity_fixed=args.velocity,
        show_tui=not args.no_tui,
        midi_input_enabled=args.midi,
        midi_port=args.midi_port,
    )
    
    synth = FW16Synth(config)
    
    # Wrap in production controller if production mode enabled
    if args.production:
        try:
            from .production.synth_controller import ProductionSynthController
            from .production.glitch_integration import enhance_fw16_synth
            
            # Try to use production controller first
            try:
                synth = ProductionSynthController(synth, config)
                log.info("Production mode enabled with comprehensive error handling")
            except Exception as e:
                log.warning(f"Production controller failed, using enhanced mode: {e}")
                # Fall back to enhanced mode
                enhance_fw16_synth(synth)
                log.info("Enhanced mode enabled with glitch prevention")
                
        except ImportError:
            log.warning("Production features not available, continuing with standard mode")
    
    def signal_handler(sig, frame):
        synth.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    if not synth.initialize():
        sys.exit(1)
    
    if args.program != 0:
        synth._change_program(args.program)
    
    try:
        asyncio.run(synth.run())
    except KeyboardInterrupt:
        pass
    finally:
        synth.stop()


if __name__ == "__main__":
    main()
