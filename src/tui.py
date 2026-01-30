#!/usr/bin/env python3
"""
FW16 Synth TUI - Terminal User Interface with keyboard visualization
=====================================================================
Shows a real-time visual representation of the keyboard and touchpad state.
"""

import sys
import os
import time
from dataclasses import dataclass
from typing import Dict, Set, Optional, Tuple

# Try to import curses for TUI
try:
    import curses
    HAS_CURSES = True
except ImportError:
    HAS_CURSES = False


@dataclass
class Color:
    """Terminal color codes"""
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    
    # DeMoD color scheme
    TURQUOISE = '\033[38;5;44m'   # Electric turquoise
    VIOLET = '\033[38;5;135m'     # DeMoD violet
    WHITE = '\033[38;5;255m'
    GRAY = '\033[38;5;240m'
    BLACK = '\033[38;5;232m'
    
    # Note colors
    NOTE_ON = '\033[48;5;44m\033[38;5;232m'   # Turquoise bg, black text
    NOTE_OFF = '\033[48;5;235m\033[38;5;250m' # Dark gray bg
    BLACK_KEY = '\033[48;5;232m\033[38;5;255m' # Black bg
    BLACK_KEY_ON = '\033[48;5;135m\033[38;5;255m' # Violet bg when pressed


class KeyboardVisualizer:
    """ASCII keyboard visualization"""
    
    # Keyboard layout for display
    LAYOUT = [
        # Top row - number keys (black keys)
        [
            ('`', None), ('1', None), ('2', 'C#'), ('3', 'D#'), ('4', None),
            ('5', 'F#'), ('6', 'G#'), ('7', 'A#'), ('8', None), ('9', 'C#'),
            ('0', 'D#'), ('-', '▼'), ('=', '▲'), ('⌫', None)
        ],
        # QWERTY row - white keys
        [
            ('⇥', None), ('Q', 'C'), ('W', 'D'), ('E', 'E'), ('R', 'F'),
            ('T', 'G'), ('Y', 'A'), ('U', 'B'), ('I', 'C'), ('O', 'D'),
            ('P', 'E'), ('[', 'F'), (']', 'G'), ('\\', None)
        ],
        # Home row - octave -1
        [
            ('⇪', None), ('A', 'C'), ('S', 'D'), ('D', 'E'), ('F', 'F'),
            ('G', 'G'), ('H', 'A'), ('J', 'B'), ('K', 'C'), ('L', 'D'),
            (';', 'E'), ("'", 'F'), ('↵', None)
        ],
        # Bottom row - octave -2
        [
            ('⇧', None), ('Z', 'C'), ('X', 'D'), ('C', 'E'), ('V', 'F'),
            ('B', 'G'), ('N', 'A'), ('M', 'B'), (',', 'C'), ('.', 'D'),
            ('/', 'E'), ('⇧', None)
        ],
        # Space bar row
        [
            ('Ctrl', None), ('❖', None), ('Alt', None),
            ('━━━━━ SUSTAIN ━━━━━', 'SUS'),
            ('Alt', None), ('Fn', None), ('Ctrl', None)
        ]
    ]
    
    def __init__(self):
        self.active_keys: Set[str] = set()
        self.octave: int = 4
        self.program: int = 0
        self.program_name: str = "Piano"
        self.sustain: bool = False
        
        # Touchpad state
        self.touch_x: float = 0.5
        self.touch_y: float = 0.5
        self.touch_pressure: float = 0.0
        self.touching: bool = False
        
        # Last note info
        self.last_note: str = ""
        self.last_velocity: int = 0
    
    def render(self) -> str:
        """Render the full TUI"""
        lines = []
        
        # Header
        lines.append(f"{Color.TURQUOISE}{Color.BOLD}╔══════════════════════════════════════════════════════════════════╗{Color.RESET}")
        lines.append(f"{Color.TURQUOISE}{Color.BOLD}║  FW16 SYNTH{Color.RESET}{Color.TURQUOISE} - Framework 16 Synthesizer          {Color.VIOLET}DeMoD LLC{Color.TURQUOISE}  ║{Color.RESET}")
        lines.append(f"{Color.TURQUOISE}{Color.BOLD}╚══════════════════════════════════════════════════════════════════╝{Color.RESET}")
        lines.append("")
        
        # Status bar
        sus_indicator = f"{Color.TURQUOISE}●{Color.RESET}" if self.sustain else f"{Color.DIM}○{Color.RESET}"
        lines.append(f"  Octave: {Color.BOLD}{self.octave}{Color.RESET}  │  "
                    f"Program: {Color.BOLD}{self.program:03d}{Color.RESET} {self.program_name}  │  "
                    f"Sustain: {sus_indicator}")
        lines.append("")
        
        # Keyboard visualization
        lines.append(f"  {Color.DIM}┌{'─' * 62}┐{Color.RESET}")
        
        for row_idx, row in enumerate(self.LAYOUT[:-1]):  # Exclude space bar for now
            row_str = "  │ "
            for key, note in row:
                is_active = key.upper() in self.active_keys
                is_black = note and '#' in note
                
                if note:
                    if is_active:
                        if is_black:
                            row_str += f"{Color.BLACK_KEY_ON}[{key}]{Color.RESET}"
                        else:
                            row_str += f"{Color.NOTE_ON}[{key}]{Color.RESET}"
                    else:
                        if is_black:
                            row_str += f"{Color.BLACK_KEY}[{key}]{Color.RESET}"
                        else:
                            row_str += f"{Color.NOTE_OFF}[{key}]{Color.RESET}"
                else:
                    row_str += f"{Color.DIM}[{key}]{Color.RESET}"
                row_str += " "
            
            row_str += "│"
            lines.append(row_str)
        
        # Space bar (sustain)
        sus_style = Color.NOTE_ON if self.sustain else Color.DIM
        lines.append(f"  │ {Color.DIM}[Ctrl]{Color.RESET} {Color.DIM}[❖]{Color.RESET} {Color.DIM}[Alt]{Color.RESET} "
                    f"{sus_style}[━━━━━━━ SUSTAIN ━━━━━━━]{Color.RESET} "
                    f"{Color.DIM}[Alt]{Color.RESET} {Color.DIM}[Fn]{Color.RESET} {Color.DIM}[Ctrl]{Color.RESET} │")
        
        lines.append(f"  {Color.DIM}└{'─' * 62}┘{Color.RESET}")
        lines.append("")
        
        # Touchpad visualization
        lines.append(f"  {Color.VIOLET}Touchpad Modulation:{Color.RESET}")
        lines.append(self._render_touchpad())
        lines.append("")
        
        # Last note display
        if self.last_note:
            lines.append(f"  {Color.TURQUOISE}Last Note:{Color.RESET} {Color.BOLD}{self.last_note}{Color.RESET} "
                        f"velocity={self.last_velocity}")
        else:
            lines.append(f"  {Color.DIM}Play a note...{Color.RESET}")
        
        lines.append("")
        lines.append(f"  {Color.DIM}[+/-] Octave  [PgUp/Dn] Program  [Esc] Panic  [Ctrl+C] Exit{Color.RESET}")
        
        return '\n'.join(lines)
    
    def _render_touchpad(self) -> str:
        """Render touchpad state as ASCII"""
        width = 30
        height = 8
        
        # Create grid
        grid = [[' ' for _ in range(width)] for _ in range(height)]
        
        # Draw border
        for x in range(width):
            grid[0][x] = '─'
            grid[height-1][x] = '─'
        for y in range(height):
            grid[y][0] = '│'
            grid[y][width-1] = '│'
        grid[0][0] = '┌'
        grid[0][width-1] = '┐'
        grid[height-1][0] = '└'
        grid[height-1][width-1] = '┘'
        
        # Draw center cross
        mid_x, mid_y = width // 2, height // 2
        for x in range(1, width-1):
            if grid[mid_y][x] == ' ':
                grid[mid_y][x] = '·'
        for y in range(1, height-1):
            if grid[y][mid_x] == ' ':
                grid[y][mid_x] = '·'
        grid[mid_y][mid_x] = '+'
        
        # Draw finger position if touching
        if self.touching:
            fx = int(self.touch_x * (width - 3)) + 1
            fy = int(self.touch_y * (height - 3)) + 1
            fx = max(1, min(width - 2, fx))
            fy = max(1, min(height - 2, fy))
            
            # Pressure indicator
            if self.touch_pressure > 0.7:
                marker = '●'
            elif self.touch_pressure > 0.3:
                marker = '◉'
            else:
                marker = '○'
            
            grid[fy][fx] = marker
        
        # Convert to string with colors
        result = []
        for y, row in enumerate(grid):
            line = '  '
            for x, char in enumerate(row):
                if char in '●◉○':
                    line += f"{Color.TURQUOISE}{Color.BOLD}{char}{Color.RESET}"
                elif char in '─│┌┐└┘':
                    line += f"{Color.DIM}{char}{Color.RESET}"
                elif char in '·+':
                    line += f"{Color.DIM}{char}{Color.RESET}"
                else:
                    line += char
            result.append(line)
        
        # Add labels
        pitch_cents = int((self.touch_x - 0.5) * 2 * 200)  # Assuming ±2 semitones
        mod_val = int((1 - self.touch_y) * 127)
        
        result.append(f"    {Color.DIM}X: Pitch Bend ({pitch_cents:+d}¢)  Y: Mod ({mod_val}){Color.RESET}")
        
        return '\n'.join(result)
    
    def key_down(self, key: str, note: str, velocity: int):
        """Register key press"""
        self.active_keys.add(key.upper())
        self.last_note = note
        self.last_velocity = velocity
    
    def key_up(self, key: str):
        """Register key release"""
        self.active_keys.discard(key.upper())
    
    def update_touchpad(self, x: float, y: float, pressure: float, touching: bool):
        """Update touchpad state"""
        self.touch_x = x
        self.touch_y = y
        self.touch_pressure = pressure
        self.touching = touching
    
    def set_octave(self, octave: int):
        """Update octave display"""
        self.octave = octave
    
    def set_program(self, program: int, name: str):
        """Update program display"""
        self.program = program
        self.program_name = name
    
    def set_sustain(self, on: bool):
        """Update sustain state"""
        self.sustain = on


class TerminalUI:
    """Full terminal UI manager"""
    
    def __init__(self):
        self.visualizer = KeyboardVisualizer()
        self._last_render = ""
    
    def clear(self):
        """Clear terminal"""
        os.system('clear' if os.name == 'posix' else 'cls')
    
    def home(self):
        """Move cursor to home position"""
        print('\033[H', end='')
    
    def hide_cursor(self):
        """Hide terminal cursor"""
        print('\033[?25l', end='')
    
    def show_cursor(self):
        """Show terminal cursor"""
        print('\033[?25h', end='')
    
    def render(self):
        """Render the UI"""
        output = self.visualizer.render()
        
        # Only redraw if changed
        if output != self._last_render:
            self.home()
            print(output)
            self._last_render = output
    
    def start(self):
        """Start the TUI"""
        self.clear()
        self.hide_cursor()
        self.render()
    
    def stop(self):
        """Stop the TUI"""
        self.show_cursor()
        print()  # Ensure we're on a new line


# Demo mode for testing
if __name__ == "__main__":
    import time
    import random
    
    ui = TerminalUI()
    ui.start()
    
    try:
        # Demo animation
        keys = ['Q', 'W', 'E', 'R', 'T', 'Y', 'U', 'I']
        notes = ['C4', 'D4', 'E4', 'F4', 'G4', 'A4', 'B4', 'C5']
        
        for i in range(100):
            # Random key presses
            if random.random() > 0.7:
                idx = random.randint(0, len(keys) - 1)
                ui.visualizer.key_down(keys[idx], notes[idx], random.randint(60, 127))
            
            if random.random() > 0.7:
                idx = random.randint(0, len(keys) - 1)
                ui.visualizer.key_up(keys[idx])
            
            # Random touchpad movement
            if random.random() > 0.5:
                ui.visualizer.update_touchpad(
                    random.random(),
                    random.random(),
                    random.random(),
                    True
                )
            
            # Toggle sustain sometimes
            if random.random() > 0.95:
                ui.visualizer.set_sustain(not ui.visualizer.sustain)
            
            ui.render()
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        pass
    finally:
        ui.stop()
        print("TUI Demo complete")
