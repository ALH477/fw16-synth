"""
SoundFont Management Module

Handles SoundFont discovery, loading, and downloading.
"""

import json
import glob
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Set, Optional, Callable, Tuple

from ..fw16_synth import GM_INSTRUMENTS, GM_CATEGORIES

log = logging.getLogger(__name__)


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


class SoundFontManager:
    """Manages soundfont discovery, loading, and hot-swapping."""

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
