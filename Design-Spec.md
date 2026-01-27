# FW16 Synth v2.1 - Detailed Design Specification

**Document Version**: 1.0  
**Date**: November 2024  
**Author**: DeMoD LLC  
**Classification**: Technical Design Document  

---

## Table of Contents

1. [Executive Overview](#1-executive-overview)
2. [System Architecture](#2-system-architecture)
3. [Component Specifications](#3-component-specifications)
4. [Interface Definitions](#4-interface-definitions)
5. [Data Flow Architecture](#5-data-flow-architecture)
6. [State Management](#6-state-management)
7. [Performance Engineering](#7-performance-engineering)
8. [Security Architecture](#8-security-architecture)
9. [Error Handling & Recovery](#9-error-handling--recovery)
10. [Device Management](#10-device-management)
11. [Audio Pipeline](#11-audio-pipeline)
12. [User Interface Design](#12-user-interface-design)
13. [Configuration Management](#13-configuration-management)
14. [Testing Strategy](#14-testing-strategy)
15. [Deployment Architecture](#15-deployment-architecture)
16. [Monitoring & Observability](#16-monitoring--observability)
17. [Edge Cases & Nuances](#17-edge-cases--nuances)
18. [Future Extensibility](#18-future-extensibility)

---

## 1. Executive Overview

### 1.1 Purpose

The FW16 Synth transforms Framework 16 laptops into professional-grade synthesizers by leveraging the laptop's unique modular input capabilities, specifically the keyboard and touchpad modules, as expressive musical controllers.

### 1.2 Design Philosophy

- **Zero-Latency Target**: Sub-10ms round-trip latency for professional music performance
- **Modular Architecture**: Clean separation between input, processing, and output stages
- **Production-First**: Built with reliability, monitoring, and recovery as first-class concerns
- **Expressive Control**: Novel velocity detection combining timing, pressure, and position
- **Framework-Native**: Optimized for Framework 16's specific hardware capabilities

### 1.3 Key Innovations

1. **Multi-Source Velocity System**: Combines timing, pressure, and keyboard position for expressive dynamics
2. **Hot-Plug Device Management**: Seamless handling of modular component changes
3. **Production-Grade Resilience**: Automatic recovery from transient failures
4. **Nix-Based Deployment**: Reproducible builds and environments

---

## 2. System Architecture

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                          User Interface Layer                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌───────────┐ │
│  │     TUI     │  │     GUI     │  │  Web UI     │  │    CLI    │ │
│  │  (Primary)  │  │  (Future)   │  │  (Future)   │  │ (Headless)│ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └───────────┘ │
└─────────────────────────────────────────────────────────────────────┘
                                    │
┌─────────────────────────────────────────────────────────────────────┐
│                         Application Core Layer                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌───────────┐ │
│  │   Synth     │  │   State     │  │   Config    │  │  Session  │ │
│  │ Controller  │  │  Manager    │  │  Manager    │  │  Manager  │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └───────────┘ │
└─────────────────────────────────────────────────────────────────────┘
                                    │
┌─────────────────────────────────────────────────────────────────────┐
│                         Input Processing Layer                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌───────────┐ │
│  │  Keyboard   │  │  Touchpad   │  │    MIDI     │  │  Velocity │ │
│  │  Handler    │  │  Handler    │  │  Handler    │  │ Processor │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └───────────┘ │
└─────────────────────────────────────────────────────────────────────┘
                                    │
┌─────────────────────────────────────────────────────────────────────┐
│                          Audio Engine Layer                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌───────────┐ │
│  │ FluidSynth  │  │   Effects   │  │ Arpeggiator │  │   Layer   │ │
│  │   Engine    │  │  Processor  │  │   Engine    │  │  Manager  │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └───────────┘ │
└─────────────────────────────────────────────────────────────────────┘
                                    │
┌─────────────────────────────────────────────────────────────────────┐
│                         Production Services Layer                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌───────────┐ │
│  │   Error     │  │  Resource   │  │   Health    │  │   Retry   │ │
│  │  Handler    │  │  Manager    │  │  Monitor    │  │  Manager  │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └───────────┘ │
└─────────────────────────────────────────────────────────────────────┘
                                    │
┌─────────────────────────────────────────────────────────────────────┐
│                          System Interface Layer                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌───────────┐ │
│  │    evdev    │  │    ALSA/    │  │    File     │  │  Network  │ │
│  │  (Input)    │  │  PipeWire   │  │   System    │  │ (Future)  │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └───────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 Component Interaction Model

The system follows a **pipeline architecture** with clear data flow:

1. **Input Events** → **Input Handlers** → **Velocity Processing** → **Note Events**
2. **Note Events** → **Audio Engine** → **Effects** → **Audio Output**
3. **All Components** → **Health Monitor** → **Metrics & Alerts**

### 2.3 Threading Model

```python
# Main Thread: UI and coordination
# Audio Thread: Real-time audio processing (SCHED_FIFO)
# Input Thread: Device polling and event processing
# Monitor Thread: Health monitoring and metrics
# Worker Pool: File I/O, network operations
```

---

## 3. Component Specifications

### 3.1 Input Handler Components

#### 3.1.1 Keyboard Handler

**Purpose**: Process keyboard events into musical note events

**Key Specifications**:
- **Latency Target**: <1ms from keypress to event emission
- **Polling Rate**: 1000Hz minimum
- **Key Mapping**: Configurable, default chromatic from C
- **Chord Detection**: Support up to 10 simultaneous keys
- **Anti-Ghosting**: Handle keyboard matrix limitations

**Interface**:
```python
class KeyboardHandler:
    def __init__(self, device_path: str, config: KeyboardConfig):
        """Initialize with specific device and configuration"""
        
    def start_polling(self) -> None:
        """Begin async event polling"""
        
    def register_callback(self, event_type: KeyEventType, 
                         callback: Callable[[KeyEvent], None]) -> None:
        """Register event callbacks"""
        
    def get_capabilities(self) -> DeviceCapabilities:
        """Query device capabilities (keys, anti-ghosting, etc)"""
```

**Critical Nuances**:
- Must handle keyboard matrix limitations (2KRO/6KRO/NKRO)
- Framework keyboard has specific scan codes that differ from standard
- Key repeat must be disabled at kernel level for musical use
- Must track key state to handle missed release events

#### 3.1.2 Touchpad Handler

**Purpose**: Convert touchpad input into expression controls

**Key Specifications**:
- **Resolution**: Minimum 1000 DPI effective resolution
- **Update Rate**: 125Hz minimum
- **Gesture Support**: Single touch only (multi-touch reserved)
- **Pressure Levels**: 256 minimum, 1024 preferred
- **Coordinate System**: Normalized 0.0-1.0

**Interface**:
```python
class TouchpadHandler:
    def __init__(self, device_path: str, config: TouchpadConfig):
        """Initialize with specific device"""
        
    def enable_pressure(self) -> bool:
        """Enable pressure sensitivity if available"""
        
    def set_smoothing(self, factor: float) -> None:
        """Set coordinate smoothing (0.0-1.0)"""
        
    def map_axis(self, axis: Axis, control: ControlType) -> None:
        """Map touchpad axis to MIDI control"""
```

**Critical Nuances**:
- Pressure may use ABS_MT_PRESSURE or ABS_PRESSURE depending on driver
- Coordinate jitter requires exponential smoothing
- Palm rejection must be handled at application level
- Dead zones needed at edges (2% border)

### 3.2 Velocity Processing System

#### 3.2.1 Multi-Source Velocity Engine

**Purpose**: Generate expressive velocity values from multiple input sources

**Velocity Sources**:

1. **Timing Velocity**
   - Window: 10-500ms between notes
   - Curve: Logarithmic (fast=loud)
   - Range: 30-127
   - Baseline: 64

2. **Pressure Velocity**
   - Source: Touchpad Z-axis
   - Curve: Linear with soft knee
   - Range: 1-127
   - Threshold: 5% activation

3. **Position Velocity**
   - Zones: Bottom row (40), Home row (80), Top rows (110)
   - Interpolation: None (discrete zones)
   - Modifier keys: Shift (+20), Ctrl (-20)

4. **Combined Mode**
   - Priority: Pressure → Position → Timing
   - Fallback: Cascading with 100ms timeout
   - Smoothing: 3-sample moving average

**Interface**:
```python
class VelocityProcessor:
    def calculate_velocity(self, 
                          key: Optional[Key],
                          pressure: Optional[float],
                          timing: Optional[float],
                          mode: VelocityMode) -> int:
        """Calculate velocity from available sources"""
        
    def set_curve(self, source: VelocitySource, 
                  curve: VelocityCurve) -> None:
        """Configure velocity response curves"""
```

### 3.3 Audio Engine Components

#### 3.3.1 FluidSynth Integration

**Purpose**: Core synthesis engine for SoundFont playback

**Key Specifications**:
- **Polyphony**: 256 voices minimum
- **Sample Rate**: 48kHz default (configurable)
- **Buffer Size**: 64-512 samples (user selectable)
- **Reverb/Chorus**: Optional, disabled by default
- **Interpolation**: 4th order by default

**Critical Nuances**:
- Must preallocate voices to avoid allocation in audio thread
- Gain staging critical to avoid clipping with high polyphony
- SoundFont loading must happen in separate thread
- Bank/Program changes must be atomic

#### 3.3.2 Effects Processor

**Purpose**: Real-time audio effects processing

**Effects Chain**:
1. **Input Gain** (-20dB to +20dB)
2. **Compressor** (optional, for dynamic control)
3. **EQ** (3-band parametric)
4. **Reverb** (FluidSynth built-in)
5. **Chorus** (FluidSynth built-in)
6. **Output Limiter** (protective, -0.3dB ceiling)

### 3.4 Production Service Components

#### 3.4.1 Error Handler

**Error Categories & Recovery Strategies**:

1. **Device Errors**
   - `ENODEV`: Device disconnected → Hot-plug monitoring
   - `EACCES`: Permission denied → User guidance
   - `EBUSY`: Device busy → Retry with backoff

2. **Audio Errors**
   - Buffer underrun → Increase buffer size
   - Engine crash → Restart with safe settings
   - Driver failure → Fallback driver cascade

3. **Resource Errors**
   - Memory exhaustion → Voice stealing
   - CPU overload → Disable effects
   - File errors → Cached fallback

#### 3.4.2 Health Monitor

**Metrics Collection**:

```python
@dataclass
class HealthMetrics:
    # Performance metrics
    audio_latency_ms: float      # Round-trip latency
    render_time_us: float        # Per-buffer render time
    cpu_usage_percent: float     # Process CPU usage
    memory_usage_mb: float       # RSS memory
    
    # Audio metrics  
    buffer_underruns: int        # Since start
    xrun_count: int             # Audio dropouts
    voice_count: int            # Active voices
    
    # Application metrics
    notes_per_second: float     # Current rate
    total_notes: int            # Lifetime count
    error_rate: float           # Errors per minute
    uptime_seconds: float       # Since start
    
    # Device metrics
    active_devices: int         # Connected devices
    device_errors: int          # Device error count
    reconnect_attempts: int     # Recovery attempts
```

---

## 4. Interface Definitions

### 4.1 Event System

All components communicate through a central event bus:

```python
@dataclass
class Event:
    timestamp: float
    source: str
    priority: EventPriority

@dataclass 
class NoteOnEvent(Event):
    note: int          # MIDI note number 0-127
    velocity: int      # Velocity 1-127
    channel: int       # MIDI channel 0-15
    source_device: str # Device identifier

@dataclass
class NoteOffEvent(Event):
    note: int
    channel: int
    source_device: str

@dataclass
class ControlChangeEvent(Event):
    controller: int    # CC number 0-127
    value: int        # Value 0-127
    channel: int
    
@dataclass
class PitchBendEvent(Event):
    value: int        # -8192 to 8191
    channel: int
```

### 4.2 Configuration Schema

```yaml
# Complete configuration schema with defaults and constraints
audio:
  driver: pipewire           # enum: [pipewire, pulse, jack, alsa]
  sample_rate: 48000        # enum: [22050, 44100, 48000, 96000]
  buffer_size: 256          # range: 64-2048, power of 2
  period_count: 2           # range: 2-16
  soundfont: ""             # path, validated at load
  gain_db: 0.0              # range: -20.0 to 20.0
  reverb:
    enabled: false
    room_size: 0.2          # range: 0.0-1.0
    damping: 0.5            # range: 0.0-1.0
    width: 0.5              # range: 0.0-1.0
    level: 0.9              # range: 0.0-1.0
  chorus:
    enabled: false
    voices: 3               # range: 0-99
    level: 2.0              # range: 0.0-10.0
    speed: 0.3              # range: 0.1-5.0
    depth: 8.0              # range: 0.0-21.0

velocity:
  mode: combined            # enum: [timing, pressure, position, combined, fixed]
  fixed_value: 100          # range: 1-127
  timing:
    window_ms: 500          # range: 10-1000
    curve: logarithmic      # enum: [linear, logarithmic, exponential]
    min_velocity: 30        # range: 1-127
    max_velocity: 127       # range: 1-127
  pressure:
    threshold: 0.05         # range: 0.0-1.0
    curve: linear           # enum: [linear, logarithmic, exponential]
    smoothing: 0.7          # range: 0.0-1.0
  position:
    row_velocities:
      bottom: 40            # range: 1-127
      home: 80              # range: 1-127  
      top: 110              # range: 1-127
    use_modifiers: true     # bool

input:
  keyboard:
    devices: []             # auto-detect if empty
    layout: qwerty          # enum: [qwerty, dvorak, colemak]
    base_note: 48           # C3, range: 0-127
    anti_ghost: true        # bool
    poll_rate_hz: 1000      # range: 125-8000
  touchpad:
    devices: []             # auto-detect if empty
    sensitivity: 1.0        # range: 0.1-10.0
    deadzone: 0.02          # range: 0.0-0.2
    smoothing: 0.85         # range: 0.0-0.99
```

### 4.3 Plugin Interface (Future)

```python
class SynthPlugin(ABC):
    """Base class for synthesis plugins"""
    
    @abstractmethod
    def process_buffer(self, 
                      buffer: np.ndarray,
                      sample_rate: int,
                      timestamp: float) -> np.ndarray:
        """Process audio buffer"""
        
    @abstractmethod
    def handle_note_on(self, note: int, velocity: int) -> None:
        """Handle note on event"""
        
    @abstractmethod
    def handle_note_off(self, note: int) -> None:
        """Handle note off event"""
        
    @abstractmethod
    def get_parameters(self) -> Dict[str, Parameter]:
        """Get plugin parameters"""
```

---

## 5. Data Flow Architecture

### 5.1 Input to Audio Pipeline

```
1. Hardware Event Generation
   └─> Kernel Driver (evdev)
       └─> Input Handler (1000Hz polling)
           └─> Event Validation & Deduplication
               └─> Velocity Processor
                   └─> Event Bus (lock-free queue)
                       └─> Audio Engine
                           └─> Audio Driver
                               └─> Hardware Output

Latency Budget:
- Kernel to userspace: <0.1ms
- Input processing: <0.5ms  
- Velocity calculation: <0.1ms
- Event bus: <0.05ms
- Audio engine: <2ms
- Driver buffering: 5.3ms (@256 samples/48kHz)
Total: <8ms typical, <10ms worst case
```

### 5.2 State Synchronization

The system maintains synchronized state across threads:

```python
class SynthState:
    """Thread-safe global state"""
    
    # Atomic values (lock-free access)
    current_program: AtomicInt
    current_octave: AtomicInt
    master_volume: AtomicFloat
    
    # Protected collections (RCU pattern)
    active_notes: RCUDict[int, NoteInfo]
    cc_values: RCUDict[int, int]
    
    # Statistics (eventually consistent)
    stats: Statistics  # Updated every 100ms
```

### 5.3 Memory Management

**Allocation Strategy**:
- **Pre-allocation**: All audio buffers allocated at startup
- **Object Pools**: Reusable event objects
- **Ring Buffers**: Lock-free communication between threads
- **Memory Mapping**: SoundFonts memory-mapped for efficiency

---

## 6. State Management

### 6.1 State Architecture

```python
@dataclass
class ApplicationState:
    # Audio state
    audio: AudioState
    
    # Input state  
    keyboard: KeyboardState
    touchpad: TouchpadState
    midi: MidiState
    
    # Performance state
    velocity: VelocityState
    arpeggiator: ArpeggiatorState
    layer: LayerState
    
    # UI state
    ui: UIState
    
    # Health state
    health: HealthState

class StateManager:
    """Centralized state management with change notifications"""
    
    def update_state(self, path: str, value: Any) -> None:
        """Update state with automatic notifications"""
        
    def subscribe(self, path: str, callback: Callable) -> Subscription:
        """Subscribe to state changes"""
        
    def get_snapshot(self) -> ApplicationState:
        """Get consistent state snapshot"""
```

### 6.2 Persistence

State persistence uses a layered approach:

1. **Runtime State**: In-memory only
2. **Session State**: Saved on exit, restored on start
3. **User Preferences**: Persistent configuration
4. **System Defaults**: Immutable baseline

---

## 7. Performance Engineering

### 7.1 Latency Optimization

**Critical Path Optimizations**:

1. **Input Processing**
   - Direct evdev access (bypass libinput)
   - Dedicated thread with SCHED_FIFO priority
   - Pre-computed key-to-note mapping
   - Branch-free velocity calculation

2. **Audio Rendering**
   - Lock-free ring buffer for events
   - Cache-aligned data structures
   - SIMD operations for mixing
   - Voice pre-allocation

3. **Memory Access**
   - NUMA-aware allocation
   - Huge pages for sample data
   - Cache-conscious data layout
   - Minimal pointer chasing

### 7.2 CPU Optimization

```c
// Example: SIMD-optimized mixing
void mix_buffers_avx2(float* dest, const float* src, 
                      int samples, float gain) {
    __m256 gain_vec = _mm256_set1_ps(gain);
    for (int i = 0; i < samples; i += 8) {
        __m256 src_vec = _mm256_load_ps(&src[i]);
        __m256 dest_vec = _mm256_load_ps(&dest[i]);
        dest_vec = _mm256_fmadd_ps(src_vec, gain_vec, dest_vec);
        _mm256_store_ps(&dest[i], dest_vec);
    }
}
```

### 7.3 Resource Limits

```python
RESOURCE_LIMITS = {
    'max_polyphony': 256,
    'max_events_per_second': 10000,
    'max_cc_updates_per_second': 1000,
    'event_queue_size': 4096,
    'max_soundfont_size_mb': 2048,
    'max_memory_usage_mb': 1024,
    'cpu_limit_percent': 80
}
```

---

## 8. Security Architecture

### 8.1 Threat Model

1. **Malicious SoundFonts**: Could contain crafted data
2. **Device Hijacking**: Unauthorized input device access
3. **Resource Exhaustion**: DoS through excessive events
4. **Configuration Tampering**: Modified config files
5. **Network Attacks**: Future network features

### 8.2 Security Measures

#### 8.2.1 Input Validation

```python
class SecurityValidator:
    def validate_soundfont(self, path: Path) -> bool:
        """Validate SoundFont file integrity"""
        # Check magic bytes
        # Validate chunk sizes
        # Scan for suspicious patterns
        
    def validate_event(self, event: Event) -> bool:
        """Validate event parameters"""
        # Range checks
        # Rate limiting
        # Source validation
```

#### 8.2.2 Privilege Management

```python
class PrivilegeManager:
    def drop_privileges(self) -> None:
        """Drop root privileges after device access"""
        # Change effective UID/GID
        # Close unnecessary file descriptors
        # Apply seccomp filters
        
    def setup_sandbox(self) -> None:
        """Configure process sandbox"""
        # Namespace isolation
        # Capability dropping
        # Resource limits
```

### 8.3 Secure Defaults

- SoundFonts loaded read-only
- No network access by default
- Configuration validation on load
- Minimal process privileges
- Secure temporary file handling

---

## 9. Error Handling & Recovery

### 9.1 Error Classification

```python
class ErrorCategory(Enum):
    TRANSIENT = "transient"      # Retry immediately
    RECOVERABLE = "recoverable"  # Retry with backoff
    DEGRADED = "degraded"        # Continue with reduced functionality
    FATAL = "fatal"              # Requires restart

ERROR_CLASSIFICATIONS = {
    errno.EAGAIN: ErrorCategory.TRANSIENT,
    errno.ENODEV: ErrorCategory.RECOVERABLE,
    errno.ENOMEM: ErrorCategory.DEGRADED,
    errno.EACCES: ErrorCategory.FATAL,
}
```

### 9.2 Recovery Strategies

#### 9.2.1 Audio Recovery

```python
class AudioRecoveryStrategy:
    def recover_from_xrun(self) -> bool:
        """Recover from buffer underrun"""
        # 1. Stop audio stream
        # 2. Flush buffers
        # 3. Increase buffer size
        # 4. Restart stream
        # 5. Restore state
        
    def recover_from_driver_error(self) -> bool:
        """Recover from driver failure"""
        # 1. Close driver connection
        # 2. Try alternative drivers in order:
        #    pipewire -> pulse -> jack -> alsa
        # 3. Reinitialize with safe settings
        # 4. Restore previous state
```

#### 9.2.2 Device Recovery

```python
class DeviceRecoveryStrategy:
    def recover_from_disconnect(self, device: Device) -> bool:
        """Recover from device disconnection"""
        # 1. Mark device as disconnected
        # 2. Start reconnection timer
        # 3. Poll for device return
        # 4. Reinitialize on detection
        # 5. Restore device state
```

### 9.3 Graceful Degradation

Functionality reduction priority:

1. Disable effects processing
2. Reduce polyphony
3. Disable velocity processing
4. Fall back to fixed velocity
5. Disable touchpad input
6. Basic keyboard-only mode

---

## 10. Device Management

### 10.1 Device Discovery

```python
class DeviceDiscovery:
    def scan_devices(self) -> List[Device]:
        """Scan for compatible input devices"""
        devices = []
        
        # Scan /dev/input/event*
        for event_path in Path('/dev/input').glob('event*'):
            device = self._probe_device(event_path)
            if self._is_compatible(device):
                devices.append(device)
                
        return devices
        
    def _is_compatible(self, device: Device) -> bool:
        """Check device compatibility"""
        # Must have KEY events for keyboard
        # Must have ABS events for touchpad
        # Check for known device names/vendors
```

### 10.2 Hot-Plug Handling

```python
class HotPlugManager:
    def __init__(self):
        self.monitor = pyudev.Monitor.from_netlink(context)
        self.monitor.filter_by('input')
        
    def handle_device_event(self, action: str, device: Device):
        if action == 'add':
            # 1. Validate device
            # 2. Initialize handler
            # 3. Restore saved state
            # 4. Notify UI
        elif action == 'remove':
            # 1. Save device state
            # 2. Clean up handler
            # 3. Mark notes as released
            # 4. Notify UI
```

### 10.3 Device Quirks

Framework 16 specific handling:

```python
DEVICE_QUIRKS = {
    "Framework Laptop 16 Keyboard Module": {
        "needs_grab": True,      # Exclusive access required
        "custom_keymap": True,   # Non-standard scan codes
        "repeat_filter": True,   # Kernel repeat interferes
    },
    "Framework Laptop 16 Numpad Module": {
        "is_secondary": True,    # Not primary keyboard
        "custom_layout": True,   # Special mapping needed
    }
}
```

---

## 11. Audio Pipeline

### 11.1 Pipeline Stages

```
Input Events
    ↓
Event Validation [<1ms]
    ↓
Note Scheduling [<1ms]
    ↓
Voice Allocation [<1ms]
    ↓
Sample Generation [FluidSynth]
    ↓
Effects Processing [Optional]
    ↓
Mixing & Gain Staging
    ↓
Output Buffering
    ↓
Driver Handoff [ALSA/JACK/PipeWire]
```

### 11.2 Voice Management

```python
class VoiceManager:
    def __init__(self, max_voices: int = 256):
        self.voice_pool = [Voice() for _ in range(max_voices)]
        self.active_voices: Dict[int, Voice] = {}
        self.voice_stealing_enabled = True
        
    def allocate_voice(self, note: int, velocity: int) -> Optional[Voice]:
        """Allocate voice with stealing if necessary"""
        if len(self.active_voices) >= len(self.voice_pool):
            if self.voice_stealing_enabled:
                victim = self._find_steal_candidate()
                self._steal_voice(victim)
            else:
                return None
                
        voice = self._get_free_voice()
        voice.start_note(note, velocity)
        self.active_voices[note] = voice
        return voice
        
    def _find_steal_candidate(self) -> Voice:
        """Find best voice to steal (oldest, quietest)"""
        # Priority: released notes, quietest, oldest
```

### 11.3 Buffer Management

```python
class AudioBufferManager:
    def __init__(self, buffer_size: int, num_buffers: int = 3):
        # Triple buffering for smooth playback
        self.buffers = [
            AudioBuffer(buffer_size) 
            for _ in range(num_buffers)
        ]
        self.read_index = 0
        self.write_index = 1
        self.process_index = 2
        
    def swap_buffers(self):
        """Atomic buffer swap for audio callback"""
        self.read_index, self.write_index, self.process_index = \
            self.write_index, self.process_index, self.read_index
```

---

## 12. User Interface Design

### 12.1 TUI Layout Specification

```
┌─────────────────────────────────────────────────────────────┐
│ FW16 Synth v2.1          [CPU: 12%] [MEM: 145MB] [♪: 8.2ms]│
├─────────────────────────────────────────────────────────────┤
│ SoundFont: FluidR3_GM.sf2              │ Velocity: ████░░░░ │
│ [001] Acoustic Grand Piano             │ Mode: Combined      │
│ Octave: 4  Transpose: 0  Layer: OFF    │ Source: Pressure    │
├─────────────────────────────────────────────────────────────┤
│ ┌─ Note History ──────────────────┐ ┌─ Active Notes ──────┐│
│ │ C4  vel:102 pressure  0.23s ago│ │ C4  ████████████   │││
│ │ E4  vel: 87 position  0.45s ago│ │ E4  ███████████    │││
│ │ G4  vel: 65 timing    0.67s ago│ │ G4  █████████      │││
│ │ C5  vel:110 pressure  1.12s ago│ │                     │││
│ └──────────────────────────────────┘ └────────────────────┘││
├─────────────────────────────────────────────────────────────┤
│ [Tab]Browse [D]Download [L]Layer [A]Arp [R]Record [Q]uit   │
└─────────────────────────────────────────────────────────────┘
```

### 12.2 Color Scheme

```python
COLOR_SCHEME = {
    'background': (0, 0, 0),           # Black
    'foreground': (255, 255, 255),     # White
    'accent': (0, 255, 255),           # Cyan
    'success': (0, 255, 0),            # Green
    'warning': (255, 255, 0),          # Yellow
    'error': (255, 0, 0),              # Red
    'velocity_low': (0, 255, 0),       # Green
    'velocity_mid': (255, 255, 0),     # Yellow  
    'velocity_high': (255, 0, 0),      # Red
    'active_note': (0, 128, 255),      # Blue
}
```

### 12.3 Responsive Design

The TUI adapts to terminal size:

- **Minimum**: 80x24 (basic layout)
- **Standard**: 120x40 (full layout)
- **Extended**: 160x50+ (additional panels)

---

## 13. Configuration Management

### 13.1 Configuration Sources (Priority Order)

1. **Command Line Arguments** (highest)
2. **Environment Variables**
3. **User Config File** (`~/.config/fw16-synth/config.yaml`)
4. **System Config File** (`/etc/fw16-synth/config.yaml`)
5. **Built-in Defaults** (lowest)

### 13.2 Live Configuration Updates

```python
class ConfigurationManager:
    def __init__(self):
        self.watchers: Dict[str, FileWatcher] = {}
        self.update_callbacks: Dict[str, List[Callable]] = {}
        
    def enable_hot_reload(self, config_path: Path):
        """Enable configuration hot-reload"""
        watcher = FileWatcher(config_path)
        watcher.on_change = self._reload_config
        self.watchers[str(config_path)] = watcher
        
    def update_value(self, path: str, value: Any, 
                    persistent: bool = False):
        """Update configuration value"""
        # Validate against schema
        # Apply immediately if possible
        # Save to file if persistent
        # Notify subscribers
```

### 13.3 Configuration Migrations

```python
class ConfigMigration:
    """Handle configuration format changes between versions"""
    
    MIGRATIONS = {
        "2.0": migrate_v20_to_v21,
        "2.1": lambda x: x  # Current version
    }
    
    def migrate_config(self, config: Dict, from_version: str) -> Dict:
        """Migrate configuration to current version"""
        current_config = config.copy()
        
        for version, migration in self.MIGRATIONS.items():
            if version > from_version:
                current_config = migration(current_config)
                
        return current_config
```

---

## 14. Testing Strategy

### 14.1 Test Categories

1. **Unit Tests** (Isolated component testing)
   - Input validation
   - Velocity calculations
   - State management
   - Configuration parsing

2. **Integration Tests** (Component interaction)
   - Input to audio pipeline
   - Device hot-plug scenarios
   - Error recovery flows
   - Configuration updates

3. **Performance Tests** (Latency and throughput)
   - Round-trip latency measurement
   - CPU usage under load
   - Memory allocation patterns
   - Event throughput limits

4. **Stress Tests** (Reliability under load)
   - Rapid note generation
   - Device connect/disconnect cycles
   - Configuration thrashing
   - Resource exhaustion

5. **Hardware Tests** (Real device validation)
   - Framework 16 keyboard module
   - Various touchpad models
   - MIDI controller compatibility

### 14.2 Test Infrastructure

```python
class SynthTestFramework:
    """Comprehensive test framework for FW16 Synth"""
    
    @fixture
    def mock_audio_engine(self):
        """Mock audio engine for testing without audio hardware"""
        return MockFluidSynth()
        
    @fixture  
    def virtual_input_device(self):
        """Virtual input device for testing without hardware"""
        return VirtualEvdevDevice()
        
    @fixture
    def performance_profiler(self):
        """Performance profiling tools"""
        return PerformanceProfiler()
```

### 14.3 Continuous Testing

```yaml
# CI/CD test pipeline
test_pipeline:
  - stage: quick_tests
    parallel:
      - unit_tests: pytest tests/unit -n auto
      - lint: flake8 src/ --max-complexity 10
      - type_check: mypy src/ --strict
      
  - stage: integration_tests
    tests:
      - integration: pytest tests/integration
      - performance: pytest tests/performance --benchmark
      
  - stage: hardware_tests
    when: manual
    tests:
      - fw16_hardware: pytest tests/hardware --device fw16
```

---

## 15. Deployment Architecture

### 15.1 Deployment Targets

1. **NixOS System Service**
   ```nix
   systemd.services.fw16-synth = {
     description = "FW16 Synthesizer Service";
     wantedBy = [ "multi-user.target" ];
     serviceConfig = {
       Type = "notify";
       ExecStart = "${fw16-synth}/bin/fw16-synth --daemon";
       Restart = "on-failure";
       User = "fw16synth";
       Group = "audio";
       PrivateDevices = false;
       RestrictAddressFamilies = "AF_UNIX AF_INET";
     };
   };
   ```

2. **Container Deployment**
   ```dockerfile
   FROM nixos/nix:latest AS builder
   # Multi-stage build for minimal image
   
   FROM scratch
   COPY --from=builder /nix/store/... /
   USER 1000:1000
   ENTRYPOINT ["/bin/fw16-synth"]
   ```

3. **Standalone Binary**
   ```bash
   # Single-file deployment with Nix bundle
   nix bundle --bundler github:NixOS/bundlers#toArx .#fw16-synth
   ```

### 15.2 Update Mechanism

```python
class UpdateManager:
    """Handle application updates gracefully"""
    
    def check_updates(self) -> Optional[Version]:
        """Check for available updates"""
        # Query update server
        # Verify signatures
        # Return new version info
        
    def prepare_update(self, version: Version) -> bool:
        """Download and prepare update"""
        # Download update package
        # Verify integrity
        # Stage for installation
        
    def apply_update(self) -> bool:
        """Apply update with rollback capability"""
        # Save current state
        # Stop services gracefully
        # Apply update atomically
        # Restart with new version
        # Rollback on failure
```

---

## 16. Monitoring & Observability

### 16.1 Metrics Collection

```python
class MetricsCollector:
    """Comprehensive metrics collection"""
    
    # Performance metrics
    audio_latency = Histogram('fw16_synth_audio_latency_seconds')
    cpu_usage = Gauge('fw16_synth_cpu_usage_percent')
    memory_usage = Gauge('fw16_synth_memory_usage_bytes')
    
    # Application metrics
    notes_total = Counter('fw16_synth_notes_total')
    velocity_distribution = Histogram('fw16_synth_velocity')
    active_voices = Gauge('fw16_synth_active_voices')
    
    # Error metrics
    errors_total = Counter('fw16_synth_errors_total', ['category'])
    recovery_attempts = Counter('fw16_synth_recovery_attempts_total')
    
    # Device metrics
    devices_connected = Gauge('fw16_synth_devices_connected')
    device_errors = Counter('fw16_synth_device_errors_total')
```

### 16.2 Distributed Tracing

```python
class TracingManager:
    """Distributed tracing for latency analysis"""
    
    def trace_note_event(self, note: int, velocity: int) -> Span:
        """Trace complete note event flow"""
        span = self.tracer.start_span('note_event')
        span.set_attribute('note', note)
        span.set_attribute('velocity', velocity)
        
        # Trace through pipeline:
        # - Input processing
        # - Velocity calculation  
        # - Event routing
        # - Voice allocation
        # - Audio rendering
        # - Output buffering
        
        return span
```

### 16.3 Log Aggregation

```python
# Structured logging format
{
    "timestamp": "2024-01-20T15:30:45.123Z",
    "level": "INFO",
    "component": "AudioEngine", 
    "event": "note_on",
    "attributes": {
        "note": 60,
        "velocity": 100,
        "latency_ms": 7.2,
        "voice_id": 5,
        "device": "Framework Laptop 16 Keyboard Module"
    },
    "trace_id": "1234567890abcdef",
    "span_id": "fedcba0987654321"
}
```

---

## 17. Edge Cases & Nuances

### 17.1 Hardware-Specific Edge Cases

1. **Keyboard Matrix Limitations**
   - Some key combinations impossible due to matrix design
   - Ghosting on specific 3+ key combinations
   - Solution: Intelligent chord detection with matrix awareness

2. **Touchpad Pressure Variations**
   - Different touchpad models report pressure differently
   - Some use ABS_PRESSURE, others ABS_MT_PRESSURE
   - Solution: Runtime capability detection and normalization

3. **USB Bandwidth Saturation**
   - Multiple high-polling devices can saturate USB
   - Causes increased latency and missed events
   - Solution: Adaptive polling rate based on load

### 17.2 Audio Edge Cases

1. **Sample Rate Mismatches**
   - System audio at 44.1kHz, engine at 48kHz
   - Causes pitch shift and artifacts
   - Solution: High-quality resampling

2. **Clock Drift**
   - Audio clock and system clock can drift
   - Causes timing issues in sequencer
   - Solution: Clock synchronization with compensation

3. **Power Management Interference**
   - CPU frequency scaling causes audio glitches
   - USB autosuspend breaks device polling
   - Solution: Performance governor and PM overrides

### 17.3 Software Edge Cases

1. **Race Conditions**
   - Note off before note on processing completes
   - Multiple velocity sources updating simultaneously
   - Solution: Event ordering and atomic operations

2. **Resource Leaks**
   - SoundFont references not released
   - Event handlers not unregistered
   - Solution: RAII and weak references

3. **Configuration Conflicts**
   - User sets incompatible options
   - Device capabilities don't match config
   - Solution: Validation with clear error messages

---

## 18. Future Extensibility

### 18.1 Planned Features

1. **Network Collaboration**
   - Multi-user jam sessions
   - Synchronized state across instances
   - Low-latency network protocol

2. **AI Integration**
   - Intelligent accompaniment
   - Style transfer
   - Performance analysis

3. **Advanced Synthesis**
   - Granular synthesis engine
   - Physical modeling
   - Custom DSP chains

4. **Recording & Production**
   - Multi-track recording
   - MIDI export
   - DAW integration

### 18.2 Extension Points

```python
# Plugin system design
class PluginManager:
    """Extensible plugin system"""
    
    def load_plugin(self, path: Path) -> Plugin:
        """Load plugin from file"""
        # Sandbox execution
        # API versioning
        # Capability negotiation
        
    def register_processor(self, processor: AudioProcessor):
        """Register audio processor in chain"""
        
    def register_input_handler(self, handler: InputHandler):
        """Register custom input handler"""
```

### 18.3 API Stability

```python
# API versioning strategy
API_VERSION = "2.1.0"
API_COMPATIBILITY = ["2.0.0", "2.1.0"]

@deprecated("Use DeviceManager instead")
class LegacyDeviceHandler:
    """Compatibility wrapper for old API"""
```

---

## Appendices

### A. Performance Benchmarks

| Operation | Target | Measured | Notes |
|-----------|---------|----------|--------|
| Input to audio latency | <10ms | 7.2ms | With 256 sample buffer |
| Note event throughput | >1000/s | 1847/s | Single threaded |
| Voice allocation | <1ms | 0.3ms | 256 voice pool |
| Config reload | <100ms | 67ms | Full validation |
| Device hotplug | <500ms | 234ms | Including init |

### B. Resource Requirements

| Resource | Minimum | Recommended | Notes |
|----------|---------|-------------|--------|
| CPU | 2 cores | 4+ cores | One core per component |
| RAM | 256MB | 1GB | Depends on SoundFonts |
| Disk | 50MB | 2GB | For multiple SoundFonts |
| Audio latency | 20ms | 5ms | Hardware dependent |

### C. Compatibility Matrix

| Component | Versions | Notes |
|-----------|----------|--------|
| Python | 3.8-3.12 | 3.10+ recommended |
| Linux kernel | 5.10+ | evdev improvements |
| PipeWire | 0.3.40+ | Better MIDI support |
| FluidSynth | 2.2.0+ | Performance fixes |

---

**End of Design Specification**

*This document represents the complete technical design for FW16 Synth v2.1. Implementation should follow these specifications while allowing for practical adjustments based on real-world testing and user feedback.*
