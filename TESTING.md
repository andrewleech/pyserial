# Testing pySerial

This document describes how to run tests for pySerial.

## Quick Start

```bash
# Install test dependencies
uv pip install -e ".[test]"

# Run tests
pytest

# Run tests with coverage
pytest --cov=serial --cov-report=html
```

## Using taskipy (optional task runner)

If you have [taskipy](https://github.com/taskipy/taskipy) installed (included with `pip install -e ".[test]"`):

```bash
# Show all available tasks
task --list

# Install dependencies
task install-dev

# Run tests
task test

# Run tests with coverage
task test-cov

# Test on all Python versions (if installed)
task test-all
```

Taskipy tasks are defined in `pyproject.toml` under `[tool.taskipy.tasks]`.

## Manual Testing

### Test with specific Python version

```bash
uv run --python 3.10 pytest
uv run --python 3.11 pytest
uv run --python 3.12 pytest
```

### Test with physical hardware

By default, tests use `loop://` (software loopback, no hardware required). To test with physical hardware:

#### Hardware Requirements

Physical hardware testing requires a **loopback adapter** with these connections:
- **TX ↔ RX** (pins 2-3 on DB9)
- **RTS ↔ CTS** (pins 7-8 on DB9)
- **DTR ↔ DSR** (pins 4-6 on DB9)

Without these jumpers, hardware tests will fail or hang.

#### Option 1: Direct pytest (explicit port)

```bash
# Using pytest --port flag
pytest --port=/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A12345-if00-port0

# Using environment variable
PYSERIAL_PORT=/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A12345-if00-port0 pytest
```

#### Option 2: Using taskipy (convenience wrappers)

```bash
# List available ports
task list-ports

# Test with specific port
task test-hardware -- --port=/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A12345-if00-port0

# Auto-detect first USB serial port
task test-hardware-first

# Interactively select port
task test-hardware-select
```

#### Option 3: Helper script

```bash
# List available serial ports
python test/list_available_ports.py --by-id

# Get first available USB port
python test/list_available_ports.py --by-id --first
```

**Important:** Always use `/dev/serial/by-id/` paths on Linux instead of `/dev/ttyUSB*` or `/dev/ttyACM*`, as device node assignments can change between boots.

#### Troubleshooting

**Tests hang or timeout:** Missing loopback jumpers. Verify all three connections (TX-RX, RTS-CTS, DTR-DSR).

**Permission denied:** Add user to `dialout` group on Linux:
```bash
sudo usermod -a -G dialout $USER
# Log out and back in for changes to take effect
```

**Quick verification test:**
```bash
# Test loopback before running full suite
python -c "
import serial
s = serial.Serial('YOUR_PORT_HERE', 115200, timeout=1)
s.write(b'test')
print('Success!' if s.read(4) == b'test' else 'Failed - check jumpers')
s.close()
"
```

## Continuous Integration

GitHub Actions automatically runs tests on:
- Python 3.10, 3.11, 3.12, 3.13, 3.14
- Linux (ubuntu-latest)
- Windows (windows-latest)

Coverage reports are uploaded to Codecov from Ubuntu Python 3.12 runs.

## Running Specific Tests

```bash
# Run a specific test file
pytest test/test_readline.py

# Run a specific test class
pytest test/test.py::Test4_Nonblocking

# Run a specific test method
pytest test/test.py::Test4_Nonblocking::test_Timeout

# Run with verbose output
pytest -v

# Run with output from print statements
pytest -s
```

## Coverage

Generate an HTML coverage report:

```bash
pytest --cov=serial --cov-report=html
# Open htmlcov/index.html in a browser
```

Generate a terminal coverage report:

```bash
pytest --cov=serial --cov-report=term
```

## Legacy Test Runner

The legacy test runner is still available:

```bash
python test/run_all_tests.py loop://
```

However, pytest is now the recommended approach.
