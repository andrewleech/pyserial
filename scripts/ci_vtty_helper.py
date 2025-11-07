#!/usr/bin/env python3
"""
Helper script to create and manage vtty virtual serial port pairs for CI testing.
Allocates two vtty devices and starts a background process to keep them alive.
"""
import os
import fcntl
import struct
import sys
import subprocess
import signal
import time

# ioctl command for getting the allocated vtty device number
# From vtty source: #define VTMX_GET_VTTY_NUM (TIOCGPTN)
# TIOCGPTN = 0x80045430 on Linux x86_64
VTMX_GET_VTTY_NUM = 0x80045430


def check_prerequisites():
    """Check that vtty module is loaded and /dev/vtmx exists."""
    print("[VTTY] Checking prerequisites...", file=sys.stderr)

    # Check if module is loaded
    try:
        result = subprocess.run(['lsmod'], capture_output=True, text=True, check=True)
        if 'vtty' not in result.stdout:
            print("[VTTY] ERROR: vtty module not loaded", file=sys.stderr)
            return False
        print("[VTTY] Module loaded: OK", file=sys.stderr)
    except subprocess.CalledProcessError as e:
        print(f"[VTTY] ERROR: Failed to check lsmod: {e}", file=sys.stderr)
        return False

    # Check /dev/vtmx exists
    if not os.path.exists("/dev/vtmx"):
        print("[VTTY] ERROR: /dev/vtmx does not exist", file=sys.stderr)
        return False
    print("[VTTY] /dev/vtmx exists: OK", file=sys.stderr)

    # Check permissions
    if not os.access("/dev/vtmx", os.R_OK | os.W_OK):
        print("[VTTY] ERROR: /dev/vtmx not readable/writable", file=sys.stderr)
        return False
    print("[VTTY] /dev/vtmx permissions: OK", file=sys.stderr)

    return True


def get_vtty_device_number(fd, fd_num):
    """Get the device number for an open /dev/vtmx file descriptor."""
    try:
        print(f"[VTTY] Calling ioctl for fd{fd_num} (ioctl=0x{VTMX_GET_VTTY_NUM:08x})...", file=sys.stderr)
        buf = struct.pack('i', 0)
        result = fcntl.ioctl(fd, VTMX_GET_VTTY_NUM, buf)
        device_num = struct.unpack('i', result)[0]
        print(f"[VTTY] fd{fd_num} allocated device number: {device_num}", file=sys.stderr)
        return device_num
    except OSError as e:
        print(f"[VTTY] ERROR: ioctl failed on fd{fd_num}: errno={e.errno} ({e.strerror})", file=sys.stderr)
        print(f"[VTTY] Details: {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"[VTTY] ERROR: Unexpected error on fd{fd_num}: {e}", file=sys.stderr)
        return None


def verify_device_exists(device_num, timeout=5):
    """
    Verify that /dev/ttyV<N> device node exists and is accessible.
    Retries for up to timeout seconds in case device creation is delayed.
    """
    device_path = f"/dev/ttyV{device_num}"
    print(f"[VTTY] Verifying device {device_path} (timeout: {timeout}s)...", file=sys.stderr)

    start_time = time.time()
    while time.time() - start_time < timeout:
        if os.path.exists(device_path):
            print(f"[VTTY] Device node exists: OK", file=sys.stderr)

            # Check if now readable/writable (permissions should be set by udev rule)
            if os.access(device_path, os.R_OK | os.W_OK):
                print(f"[VTTY] Device permissions verified: OK", file=sys.stderr)
                return True
            else:
                print(f"[VTTY] Device exists but not readable/writable yet, retrying...", file=sys.stderr)
                time.sleep(0.1)
                continue

        elapsed = time.time() - start_time
        remaining = timeout - elapsed
        if remaining > 0:
            print(f"[VTTY] Device not yet created, retrying... ({remaining:.1f}s remaining)", file=sys.stderr)
            time.sleep(0.1)

    print(f"[VTTY] ERROR: Device {device_path} failed to become available after {timeout}s", file=sys.stderr)
    return False


def keeper_process(fd1, fd2):
    """
    Background process that keeps file descriptors open.
    This prevents the vtty devices from being deallocated.
    """
    # Ignore signals so we only exit when parent closes descriptors
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    signal.signal(signal.SIGINT, signal.SIG_IGN)

    # Just sleep indefinitely, keeping descriptors open
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass


def create_vtty_pair_with_keeper():
    """
    Create a pair of vtty devices and start a background keeper process.
    Returns tuple of (port1_path, port2_path, keeper_pid) if successful, None otherwise.
    """
    print("[VTTY] Starting vtty pair creation...", file=sys.stderr)

    if not check_prerequisites():
        return None

    try:
        # Open /dev/vtmx twice to allocate two virtual devices
        # Opening /dev/vtmx automatically creates the corresponding /dev/ttyV# device
        print("[VTTY] Opening /dev/vtmx (first descriptor)...", file=sys.stderr)
        fd1 = os.open("/dev/vtmx", os.O_RDWR | os.O_NOCTTY)
        print(f"[VTTY] Opened fd1: {fd1}", file=sys.stderr)

        print("[VTTY] Opening /dev/vtmx (second descriptor)...", file=sys.stderr)
        fd2 = os.open("/dev/vtmx", os.O_RDWR | os.O_NOCTTY)
        print(f"[VTTY] Opened fd2: {fd2}", file=sys.stderr)

        # Get the device numbers allocated by the kernel
        num1 = get_vtty_device_number(fd1, 1)
        num2 = get_vtty_device_number(fd2, 2)

        if num1 is None or num2 is None:
            print("[VTTY] ERROR: Failed to get device numbers", file=sys.stderr)
            os.close(fd1)
            os.close(fd2)
            return None

        port1 = f"/dev/ttyV{num1}"
        port2 = f"/dev/ttyV{num2}"

        print(f"[VTTY] Allocated devices: {port1} and {port2}", file=sys.stderr)

        # Verify devices are accessible
        if not verify_device_exists(num1) or not verify_device_exists(num2):
            print(f"[VTTY] ERROR: Devices created but not accessible", file=sys.stderr)
            os.close(fd1)
            os.close(fd2)
            return None

        # Start background process to keep descriptors open
        # Fork and let parent exit while child keeps descriptors
        pid = os.fork()
        if pid == 0:
            # Child process: keep descriptors open
            keeper_process(fd1, fd2)
            os._exit(0)
        else:
            # Parent process: close our copies and exit, child keeps them open
            # Don't actually close - let child keep them via fork's descriptor inheritance
            print(f"[VTTY] Started keeper process (PID {pid}) to maintain device allocation", file=sys.stderr)
            print(f"[VTTY] SUCCESS: Created vtty pair {port1} <-> {port2}", file=sys.stderr)
            return (port1, port2, pid)

    except OSError as e:
        print(f"[VTTY] ERROR: OS error: errno={e.errno} ({e.strerror})", file=sys.stderr)
        print(f"[VTTY] Details: {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"[VTTY] ERROR: Unexpected error: {e}", file=sys.stderr)
        return None


def main():
    """Create vtty pair and output environment variables for use in shell."""
    result = create_vtty_pair_with_keeper()

    if result is None:
        print("[VTTY] FATAL: Failed to create vtty pair - aborting", file=sys.stderr)
        sys.exit(1)

    port1, port2, keeper_pid = result

    # Output bash-compatible export statements
    print(f"export PYSERIAL_PORT={port1}")
    print(f"export PYSERIAL_PORT_PAIR={port2}")
    print(f"export VTTY_KEEPER_PID={keeper_pid}")


if __name__ == "__main__":
    main()
