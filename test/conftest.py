"""pytest configuration for pySerial tests.

Allows specifying hardware port via:
1. Command line: pytest --port=/dev/serial/by-id/...
2. Environment variable: PYSERIAL_PORT=/dev/serial/by-id/... pytest
3. Default: loop:// (software loopback, no hardware required)
"""
import os
import sys
import pytest


def pytest_addoption(parser):
    """Add custom command-line options."""
    parser.addoption(
        "--port",
        action="store",
        default=None,
        help="Serial port to use for testing (default: loop://)"
    )


@pytest.fixture(scope="session", autouse=True)
def configure_test_port(request):
    """Configure the PORT variable for all test modules.
    
    Priority:
    1. --port command-line argument
    2. PYSERIAL_PORT environment variable
    3. Default: loop://
    """
    # Get port from command line or environment
    port = request.config.getoption("--port")
    if port is None:
        port = os.environ.get("PYSERIAL_PORT")
    if port is None:
        port = "loop://"
    
    # Update PORT in all test modules
    # This mirrors the behavior of the old run_all_tests.py
    for module_name in list(sys.modules.keys()):
        if module_name.startswith('test.test_') or module_name == 'test':
            module = sys.modules[module_name]
            if hasattr(module, 'PORT'):
                module.PORT = port
    
    # Print port being used
    print(f"\n{'='*70}")
    print(f"Testing with port: {port!r}")
    if port == "loop://":
        print("Using software loopback (no hardware required)")
    else:
        print("Using physical hardware - ensure loopback jumpers are installed:")
        print("  TX <-> RX  (pins 2-3 on DB9)")
        print("  RTS <-> CTS (pins 7-8 on DB9)")
        print("  DTR <-> DSR (pins 4-6 on DB9)")
    print(f"{'='*70}\n")
    
    return port


def pytest_configure(config):
    """Configure pytest with custom markers and settings."""
    config.addinivalue_line(
        "markers",
        "hardware: mark test as requiring physical hardware"
    )
