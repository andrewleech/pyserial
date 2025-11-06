#!/usr/bin/env python3
"""
Helper script to create and manage vtty virtual serial port pairs for CI testing.
Allocates two connected vtty devices and exports them for pytest to use.
"""
import os
import fcntl
import struct
import sys

# ioctl command for getting the allocated vtty device number
# From vtty source: #define VTMX_GET_VTTY_NUM _IOR('V', 0, int)
VTMX_GET_VTTY_NUM = 0x80045600


def get_vtty_device_number(fd):
    """Get the device number for an open /dev/vtmx file descriptor."""
    try:
        buf = struct.pack('i', 0)
        result = fcntl.ioctl(fd, VTMX_GET_VTTY_NUM, buf)
        return struct.unpack('i', result)[0]
    except OSError as e:
        print(f"ERROR: Failed to get vtty device number: {e}", file=sys.stderr)
        return None


def verify_device_exists(device_num):
    """Verify that /dev/ttyV<N> device node exists and is accessible."""
    device_path = f"/dev/ttyV{device_num}"
    if not os.path.exists(device_path):
        return False
    if not os.access(device_path, os.R_OK | os.W_OK):
        return False
    return True


def create_vtty_pair():
    """
    Create a pair of connected vtty devices.
    Returns tuple of (port1_path, port2_path) if successful, None otherwise.
    """
    try:
        # Open /dev/vtmx twice to allocate two connected virtual devices
        fd1 = os.open("/dev/vtmx", os.O_RDWR | os.O_NOCTTY)
        fd2 = os.open("/dev/vtmx", os.O_RDWR | os.O_NOCTTY)

        # Get the device numbers
        num1 = get_vtty_device_number(fd1)
        num2 = get_vtty_device_number(fd2)

        if num1 is None or num2 is None:
            os.close(fd1)
            os.close(fd2)
            return None

        # Write each device number to the other to establish connection
        # Format: tag byte (0xFF) followed by port number (single byte)
        os.write(fd1, struct.pack('BB', 0xFF, num2))
        os.write(fd2, struct.pack('BB', 0xFF, num1))

        os.close(fd1)
        os.close(fd2)

        port1 = f"/dev/ttyV{num1}"
        port2 = f"/dev/ttyV{num2}"

        # Verify devices are accessible
        if not verify_device_exists(num1) or not verify_device_exists(num2):
            print(f"ERROR: Created devices but cannot access them", file=sys.stderr)
            return None

        return (port1, port2)

    except OSError as e:
        print(f"ERROR: Failed to create vtty pair: {e}", file=sys.stderr)
        return None


def main():
    """Create vtty pair and output environment variables for use in shell."""
    result = create_vtty_pair()

    if result is None:
        print("ERROR: Failed to create vtty pair", file=sys.stderr)
        sys.exit(1)

    port1, port2 = result

    # Output bash-compatible export statements
    print(f"export PYSERIAL_PORT={port1}")
    print(f"export PYSERIAL_PORT_PAIR={port2}")

    # Also output for debugging
    print(f"echo 'Created vtty pair: {port1} <-> {port2}' >&2", file=sys.stderr)


if __name__ == "__main__":
    main()
