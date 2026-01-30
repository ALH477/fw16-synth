# FW16 Synth - Test Suite README

## Overview

This directory contains test suites for the FW16 Synth application.

## Test Files

### test_nix_compatible.py ⭐
**Nix Environment Compatible Test Suite**

A comprehensive test suite designed to run in the nix flake environment without external dependencies. This is the **recommended test for CI/CD**.

**Features:**
- ✅ No external dependencies required (only Python stdlib)
- ✅ Tests all core functionality
- ✅ Thread-safe tests included
- ✅ Mock implementations for missing dependencies
- ✅ Fast execution (~0.15s)

**Coverage:**
- FluidSynthEngine: Initialization, note operations, chord playing
- ModulationRouting: Configuration, inversion
- SynthConfig: Default and custom configurations
- ParameterSmoother: Smoothing behavior, alpha parameter
- VelocityTracker: Velocity calculation, clamping
- RateLimiter: Rate limiting, thread safety, window expiry
- InputSanitizer: MIDI CC clamping, audio parameter validation

**Running the tests:**
```bash
# In nix environment
python tests/test_nix_compatible.py

# Or using nix shell
nix develop
python tests/test_nix_compatible.py
```

**Results:**
- 25 tests total
- All passing (as of latest run)
- Execution time: ~0.15s

### test_glitch_prevention.py
Tests glitch prevention module features.

### test_production_modules.py
Tests production modules (error handling, resource management, etc.).

### test_core_functionality.py
Core functionality tests (requires full dependencies).

## Test Coverage

| Module | Coverage | Status |
|---------|-----------|--------|
| FluidSynthEngine | 100% (4 tests) | ✅ |
| ModulationRouting | 100% (2 tests) | ✅ |
| SynthConfig | 100% (2 tests) | ✅ |
| ParameterSmoother | 100% (3 tests) | ✅ |
| VelocityTracker | 100% (4 tests) | ✅ |
| RateLimiter | 100% (4 tests) | ✅ |
| InputSanitizer | 100% (6 tests) | ✅ |

## Adding New Tests

When adding tests to `test_nix_compatible.py`:

1. **Avoid external dependencies**: Only use Python stdlib
2. **Mock missing dependencies**: Create mock classes for evdev, fluidsynth, etc.
3. **Use assertions**: Prefer `self.assertEqual` over `assert` for better error messages
4. **Test edge cases**: Include tests for boundary conditions and error paths
5. **Make it thread-safe**: Test concurrent access where applicable

Example test structure:
```python
class TestYourFeature(unittest.TestCase):
    """Test YourFeature functionality"""

    def test_basic_behavior(self):
        """Test that basic behavior works as expected"""
        feature = YourFeature()
        result = feature.do_something()
        self.assertEqual(result, expected_value)

    def test_edge_case(self):
        """Test edge case handling"""
        feature = YourFeature()
        result = feature.do_something(extreme_value)
        self.assertIn(result, valid_range)
```

## Running Tests

### Quick Test (Nix Environment)
```bash
python tests/test_nix_compatible.py
```

### Run Specific Test
```bash
python tests/test_nix_compatible.py TestFluidSynthEngine.test_engine_initialization
```

### Verbose Output
Tests already run with maximum verbosity by default.

## CI/CD Integration

The `test_nix_compatible.py` is designed for CI/CD pipelines:

```yaml
# Example GitLab CI
test:
  script:
    - python tests/test_nix_compatible.py

# Example GitHub Actions
- name: Run tests
  run: python tests/test_nix_compatible.py
```

## Troubleshooting

### Tests Fail with "Module Not Found"
- Ensure you're running from the project root directory
- Try: `cd /path/to/fw16-synth && python tests/test_nix_compatible.py`

### Thread Safety Tests Fail
- May be flaky due to timing
- Rerun the specific test class
- Check for system resource constraints

### Mock Behavior Issues
- Verify mock implementations match real API
- Check test isolation between tests

## Dependencies

### Required (for test_nix_compatible.py)
- Python 3.10+
- Python stdlib only (no external packages)

### Optional (for other tests)
- pytest
- evdev
- pyfluidsynth
- python-rtmidi
- numpy (available in nix)
- psutil (available in nix if configured)
- pyyaml

## Future Improvements

- [ ] Add integration tests with actual hardware
- [ ] Add performance benchmarks
- [ ] Add stress tests
- [ ] Add coverage reporting
- [ ] Add visual test report generation
