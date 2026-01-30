#!/usr/bin/env bash
#
# FW16 Synth v2.0 Launcher
# ========================
# Pre-flight checks and launch
#
# DeMoD LLC - Design ≠ Marketing

set -euo pipefail

# Colors
C='\033[38;5;44m'   # Turquoise
V='\033[38;5;135m'  # Violet  
G='\033[38;5;46m'   # Green
Y='\033[38;5;226m'  # Yellow
R='\033[38;5;196m'  # Red
D='\033[38;5;245m'  # Dim
W='\033[38;5;255m'  # White
B='\033[1m'         # Bold
X='\033[0m'         # Reset

# Clear and show banner
clear
echo -e "${C}"
cat << 'LOGO'
═══════════════════════════════════════════════════════════════════════════════
∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿

  ███████╗██╗    ██╗ ██╗ ██████╗     ███████╗██╗   ██╗███╗   ██╗████████╗██╗  ██╗
  ██╔════╝██║    ██║███║██╔════╝     ██╔════╝╚██╗ ██╔╝████╗  ██║╚══██╔══╝██║  ██║
  █████╗  ██║ █╗ ██║╚██║███████╗     ███████╗ ╚████╔╝ ██╔██╗ ██║   ██║   ███████║
  ██╔══╝  ██║███╗██║ ██║██╔═══██╗    ╚════██║  ╚██╔╝  ██║╚██╗██║   ██║   ██╔══██║
  ██║     ╚███╔███╔╝ ██║╚██████╔╝    ███████║   ██║   ██║ ╚████║   ██║   ██║  ██║
  ╚═╝      ╚══╝╚══╝  ╚═╝ ╚═════╝     ╚══════╝   ╚═╝   ╚═╝  ╚═══╝   ╚═╝   ╚═╝  ╚═╝

LOGO
echo -e "${X}"

echo -e "${V}    ██████╗ ███████╗███╗   ███╗ ██████╗ ██████╗ ${X}"
echo -e "${V}    ██╔══██╗██╔════╝████╗ ████║██╔═══██╗██╔══██╗${X}"
echo -e "${V}    ██║  ██║█████╗  ██╔████╔██║██║   ██║██║  ██║${X}"
echo -e "${V}    ██║  ██║██╔══╝  ██║╚██╔╝██║██║   ██║██║  ██║${X}"
echo -e "${V}    ██████╔╝███████╗██║ ╚═╝ ██║╚██████╔╝██████╔╝${X}"
echo -e "${V}    ╚═════╝ ╚══════╝╚═╝     ╚═╝ ╚═════╝ ╚═════╝ ${X}"
echo
echo -e "${D}                    « Design ≠ Marketing »${X}"
echo -e "${C}───────────────────────────────────────────────────────────────────────────────${X}"
echo

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_SCRIPT="${SCRIPT_DIR}/fw16_synth.py"

ok()   { echo -e "  ${G}✓${X} $1"; }
warn() { echo -e "  ${Y}⚠${X} $1"; }
fail() { echo -e "  ${R}✗${X} $1"; }
info() { echo -e "  ${D}→${X} $1"; }

echo -e "${W}${B}Pre-flight Checks${X}"
echo

ERRORS=0

# Python
if command -v python3 &>/dev/null; then
    ok "Python $(python3 --version 2>&1 | cut -d' ' -f2)"
else
    fail "Python 3 not found"
    ERRORS=$((ERRORS + 1))
fi

# evdev
if python3 -c "import evdev" 2>/dev/null; then
    ok "evdev module"
else
    fail "evdev not found (pip install evdev)"
    ERRORS=$((ERRORS + 1))
fi

# pyfluidsynth
if python3 -c "import fluidsynth" 2>/dev/null; then
    ok "pyfluidsynth module"
else
    fail "pyfluidsynth not found (pip install pyfluidsynth)"
    ERRORS=$((ERRORS + 1))
fi

# Input group
if groups | grep -q '\binput\b'; then
    ok "User in 'input' group"
else
    warn "Not in 'input' group"
    info "Run: sudo usermod -aG input \$USER && logout"
fi

# Keyboard devices
KB_COUNT=$(find /dev/input -name 'event*' -readable 2>/dev/null | \
    xargs -I{} sh -c 'udevadm info -q property -n {} 2>/dev/null | grep -q ID_INPUT_KEYBOARD && echo {}' | \
    wc -l)
if [ "$KB_COUNT" -gt 0 ]; then
    ok "Found $KB_COUNT keyboard(s)"
else
    warn "No readable keyboards found"
fi

# Touchpad
TP_COUNT=$(find /dev/input -name 'event*' -readable 2>/dev/null | \
    xargs -I{} sh -c 'udevadm info -q property -n {} 2>/dev/null | grep -q ID_INPUT_TOUCHPAD && echo {}' | \
    wc -l)
if [ "$TP_COUNT" -gt 0 ]; then
    ok "Found $TP_COUNT touchpad(s)"
else
    warn "No touchpad found (modulation disabled)"
fi

# Audio
AUDIO_DRIVER="pipewire"
if command -v pw-cli &>/dev/null && pw-cli info 0 &>/dev/null; then
    ok "PipeWire running"
    AUDIO_DRIVER="pipewire"
elif command -v pactl &>/dev/null && pactl info &>/dev/null; then
    ok "PulseAudio running"
    AUDIO_DRIVER="pulseaudio"
elif command -v jack_lsp &>/dev/null && jack_lsp &>/dev/null 2>&1; then
    ok "JACK running"
    AUDIO_DRIVER="jack"
else
    warn "No audio server detected"
fi

# SoundFont
SOUNDFONT=""
SF_PATHS=(
    "${DEFAULT_SOUNDFONT:-}"
    "$HOME/.local/share/soundfonts/default.sf2"
    "/usr/share/soundfonts/FluidR3_GM.sf2"
    "/usr/share/soundfonts/default.sf2"
    "/usr/share/sounds/sf2/FluidR3_GM.sf2"
)

for sf in "${SF_PATHS[@]}"; do
    if [ -n "$sf" ] && [ -f "$sf" ]; then
        SOUNDFONT="$sf"
        break
    fi
done

# Try Nix store
if [ -z "$SOUNDFONT" ]; then
    NIX_SF=$(find /nix/store -name "*.sf2" -path "*soundfont*" 2>/dev/null | head -1)
    if [ -n "$NIX_SF" ]; then
        SOUNDFONT="$NIX_SF"
    fi
fi

if [ -n "$SOUNDFONT" ]; then
    ok "SoundFont: $(basename "$SOUNDFONT")"
else
    warn "No SoundFont found (will scan at startup)"
fi

echo

# Check for errors
if [ "$ERRORS" -gt 0 ]; then
    echo -e "${R}${B}Cannot start: $ERRORS critical error(s)${X}"
    exit 1
fi

# Build arguments
ARGS=("$@")

# Skip splash since we already showed branding
ARGS+=("--no-splash")

if [[ ! " ${ARGS[*]} " =~ " --driver " ]] && [[ ! " ${ARGS[*]} " =~ " -d " ]]; then
    ARGS+=("--driver" "$AUDIO_DRIVER")
fi

if [[ ! " ${ARGS[*]} " =~ " --soundfont " ]] && [[ ! " ${ARGS[*]} " =~ " -s " ]] && [ -n "$SOUNDFONT" ]; then
    ARGS+=("--soundfont" "$SOUNDFONT")
fi

echo -e "${C}┃█┃█┃┃█┃█┃█┃┃█┃█┃┃█┃█┃█┃┃█┃█┃┃█┃█┃█┃┃█┃█┃┃█┃█┃█┃┃█┃█┃┃█┃█┃█┃${X}"
echo
echo -e "${W}${B}Starting FW16 Synth...${X}"
echo -e "${D}Press ? for help, Tab for SoundFont browser, Ctrl+C to exit${X}"
echo

exec python3 "$PYTHON_SCRIPT" "${ARGS[@]}"
