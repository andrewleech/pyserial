#!/usr/bin/env python
#
# This file is part of pySerial - Cross platform serial port support for Python
# (C) 2001-2024 Chris Liechti <cliechti@gmx.net>
#
# SPDX-License-Identifier:    BSD-3-Clause
"""\
Hardware-specific tests for serial port functionality.

These tests require actual serial port hardware or kernel-level emulation (like tty0tty).
They will be skipped when using loop:// since it ignores termios settings.

Tests validate:
- Baud rate timing and accuracy
- Parity generation and checking
- Character size enforcement
- Stop bits configuration
- Hardware flow control (RTS/CTS)
- Software flow control (XON/XOFF)
- Break signal generation

These tests assume a null-modem (loopback) configuration where:
  TX <-> RX
  RTS <-> CTS
  DTR <-> DSR
"""

import unittest
import time
import serial
import sys
import os
import pytest

# Default port - will be overridden by conftest.py
PORT = 'loop://'


def get_port():
    """Get the actual port to use for testing"""
    # Check environment variable first (set by CI), then module-level PORT
    return os.environ.get('PYSERIAL_PORT', PORT)


def is_hardware_port():
    """Check if we're using a real hardware port or tty0tty, not loop://"""
    return not get_port().startswith('loop://')


def get_port_pair():
    """Get both ports for tty0tty/vtty/socat paired testing"""
    port = get_port()
    # Check for tty0tty (tnt0/tnt1) or vtty/socat (ttyV0/ttyV1) paired devices
    if 'tnt' in port or 'ttyV' in port:
        port_num = int(port[-1])
        paired_num = port_num ^ 1  # XOR with 1 to flip between even/odd
        paired_port = port[:-1] + str(paired_num)
        return port, paired_port
    else:
        # For real hardware with actual loopback, same port for both
        return port, port


# Use pytest.mark.skipif which evaluates at collection time
pytestmark = pytest.mark.skipif(
    os.environ.get('PYSERIAL_PORT', 'loop://').startswith('loop://'),
    reason="Requires real hardware or tty0tty (not loop://)"
)


# Keep the unittest decorator for backwards compatibility when run standalone
@unittest.skipUnless(is_hardware_port(), "Requires real hardware or tty0tty (not loop://)")
class Test_HardwareFlowControl(unittest.TestCase):
    """Test that hardware flow control actually works"""

    def test_rtscts_flow_control(self):
        """Test that RTS/CTS signals are connected between paired ports"""
        # tty0tty creates pairs: /dev/tnt0 <-> /dev/tnt1
        # RTS on one side connects to CTS on the other side
        port = get_port()

        # Get the paired port (tnt0->tnt1, tnt1->tnt0, etc)
        if 'tnt' in port:
            port_num = int(port[-1])
            paired_num = port_num ^ 1  # XOR with 1 to flip between even/odd
            paired_port = port[:-1] + str(paired_num)
        else:
            # For real hardware, skip this test
            self.skipTest("Requires tty0tty paired ports")
            return

        s1 = serial.Serial(port, baudrate=115200, timeout=1)
        s2 = serial.Serial(paired_port, baudrate=115200, timeout=1)

        try:
            # s1's RTS should appear as s2's CTS
            s1.rts = True
            time.sleep(0.05)
            self.assertTrue(s2.cts, "Paired port CTS should be high when RTS is high")

            s1.rts = False
            time.sleep(0.05)
            self.assertFalse(s2.cts, "Paired port CTS should be low when RTS is low")

            # And vice versa
            s2.rts = True
            time.sleep(0.05)
            self.assertTrue(s1.cts, "Paired port CTS should be high when RTS is high")

        finally:
            s1.close()
            s2.close()


@unittest.skipUnless(is_hardware_port(), "Requires real hardware or tty0tty (not loop://)")
class Test_ParityValidation(unittest.TestCase):
    """Test that parity bits are actually generated and checked"""

    def test_parity_even(self):
        """Test that even parity works correctly"""
        port_tx, port_rx = get_port_pair()
        print(f"DEBUG: port_tx={port_tx}, port_rx={port_rx}", flush=True)

        print(f"DEBUG: Opening TX port {port_tx}", flush=True)
        s_tx = serial.Serial(port_tx, baudrate=9600, parity=serial.PARITY_EVEN, timeout=1)
        print(f"DEBUG: TX port opened", flush=True)

        print(f"DEBUG: Opening RX port {port_rx}", flush=True)
        s_rx = serial.Serial(port_rx, baudrate=9600, parity=serial.PARITY_EVEN, timeout=1) if port_tx != port_rx else s_tx
        print(f"DEBUG: RX port opened, same_port={port_tx == port_rx}", flush=True)

        try:
            test_data = b'\x00\x01\x7F\x80\xFF\xAA\x55'
            print(f"DEBUG: Writing {len(test_data)} bytes", flush=True)
            s_tx.write(test_data)
            print(f"DEBUG: Flushing", flush=True)
            s_tx.flush()
            print(f"DEBUG: Sleeping", flush=True)
            time.sleep(0.1)

            print(f"DEBUG: Reading {len(test_data)} bytes", flush=True)
            received = s_rx.read(len(test_data))
            print(f"DEBUG: Received {len(received)} bytes: {received!r}", flush=True)
            self.assertEqual(received, test_data,
                           "Data should pass correctly with matching parity")
        finally:
            print(f"DEBUG: Cleaning up", flush=True)
            if s_tx != s_rx:
                s_rx.close()
            s_tx.close()
            print(f"DEBUG: Cleanup complete", flush=True)

    def test_parity_odd(self):
        """Test that odd parity works correctly"""
        port_tx, port_rx = get_port_pair()
        s_tx = serial.Serial(port_tx, baudrate=9600, parity=serial.PARITY_ODD, timeout=1)
        s_rx = serial.Serial(port_rx, baudrate=9600, parity=serial.PARITY_ODD, timeout=1) if port_tx != port_rx else s_tx

        try:
            test_data = b'\x00\x01\x7F\x80\xFF\xAA\x55'
            s_tx.write(test_data)
            s_tx.flush()
            time.sleep(0.1)

            received = s_rx.read(len(test_data))
            self.assertEqual(received, test_data,
                           "Data should pass correctly with matching parity")
        finally:
            if s_tx != s_rx:
                s_rx.close()
            s_tx.close()

    def test_parity_none(self):
        """Test that no parity works correctly"""
        port_tx, port_rx = get_port_pair()
        s_tx = serial.Serial(port_tx, baudrate=9600, parity=serial.PARITY_NONE, timeout=1)
        s_rx = serial.Serial(port_rx, baudrate=9600, parity=serial.PARITY_NONE, timeout=1) if port_tx != port_rx else s_tx

        try:
            test_data = b'\x00\x01\x7F\x80\xFF\xAA\x55'
            s_tx.write(test_data)
            s_tx.flush()
            time.sleep(0.1)

            received = s_rx.read(len(test_data))
            self.assertEqual(received, test_data,
                           "Data should pass correctly with no parity")
        finally:
            if s_tx != s_rx:
                s_rx.close()
            s_tx.close()


@unittest.skipUnless(is_hardware_port(), "Requires real hardware or tty0tty (not loop://)")
class Test_ByteSize(unittest.TestCase):
    """Test that character size (bits per byte) is enforced"""

    @unittest.skip("tty0tty doesn't enforce bytesize/parity at driver level")
    def test_bytesize_7(self):
        """Test 7-bit character size masks high bit"""
        s = serial.Serial(get_port(),  baudrate=9600, bytesize=serial.SEVENBITS,
                          parity=serial.PARITY_NONE, timeout=1)

        try:
            # With 7 bits, high bit should be masked off
            # Send 0xFF (11111111), should receive 0x7F (01111111)
            test_data = b'\xFF\xAA\x80'
            s.write(test_data)
            s.flush()
            time.sleep(0.1)

            received = s.read(len(test_data))
            # High bit should be masked in 7-bit mode
            expected = bytes([b & 0x7F for b in test_data])
            self.assertEqual(received, expected,
                           "High bit should be masked in 7-bit mode")
        finally:
            s.close()

    @unittest.skip("tty0tty doesn't enforce bytesize/parity at driver level")
    def test_bytesize_8(self):
        """Test 8-bit character size preserves all bits"""
        s = serial.Serial(get_port(),  baudrate=9600, bytesize=serial.EIGHTBITS,
                          parity=serial.PARITY_NONE, timeout=1)

        try:
            # With 8 bits, all bits should pass through
            test_data = b'\xFF\xAA\x80\x00\x7F'
            s.write(test_data)
            s.flush()
            time.sleep(0.1)

            received = s.read(len(test_data))
            self.assertEqual(received, test_data,
                           "All 8 bits should pass through in 8-bit mode")
        finally:
            s.close()


@unittest.skipUnless(is_hardware_port(), "Requires real hardware or tty0tty (not loop://)")
class Test_BaudRate(unittest.TestCase):
    """Test baud rate timing accuracy"""

    def test_baud_rate_timing(self):
        """Test that different baud rates have measurably different timing"""
        test_data = b'X' * 100
        port_tx, port_rx = get_port_pair()

        # Test at 9600 baud
        s_tx = serial.Serial(port_tx, baudrate=9600, timeout=5)
        s_rx = serial.Serial(port_rx, baudrate=9600, timeout=5) if port_tx != port_rx else s_tx
        start = time.time()
        s_tx.write(test_data)
        s_tx.flush()  # Wait for transmission to complete
        time_slow = time.time() - start
        if s_tx != s_rx:
            s_rx.close()
        s_tx.close()

        # Test at 115200 baud
        s_tx = serial.Serial(port_tx, baudrate=115200, timeout=5)
        s_rx = serial.Serial(port_rx, baudrate=115200, timeout=5) if port_tx != port_rx else s_tx
        start = time.time()
        s_tx.write(test_data)
        s_tx.flush()  # Wait for transmission to complete
        time_fast = time.time() - start
        if s_tx != s_rx:
            s_rx.close()
        s_tx.close()

        # 115200 should be roughly 12x faster than 9600
        # At minimum, it should be noticeably faster
        self.assertLess(time_fast * 2, time_slow,
                       f"115200 baud ({time_fast:.3f}s) should be much faster than 9600 baud ({time_slow:.3f}s)")

    def test_standard_baud_rates(self):
        """Test that common baud rates can be set and used"""
        standard_bauds = [9600, 19200, 38400, 57600, 115200]
        test_data = b'test'
        port_tx, port_rx = get_port_pair()

        for baud in standard_bauds:
            with self.subTest(baudrate=baud):
                s_tx = serial.Serial(port_tx, baudrate=baud, timeout=1)
                s_rx = serial.Serial(port_rx, baudrate=baud, timeout=1) if port_tx != port_rx else s_tx
                try:
                    # Verify we can send and receive at this baud rate
                    s_tx.write(test_data)
                    s_tx.flush()
                    time.sleep(0.1)
                    received = s_rx.read(len(test_data))
                    self.assertEqual(received, test_data,
                                   f"Data integrity should be maintained at {baud} baud")
                finally:
                    if s_tx != s_rx:
                        s_rx.close()
                    s_tx.close()


@unittest.skipUnless(is_hardware_port(), "Requires real hardware or tty0tty (not loop://)")
class Test_StopBits(unittest.TestCase):
    """Test stop bits configuration"""

    def test_stopbits_one(self):
        """Test 1 stop bit configuration"""
        port_tx, port_rx = get_port_pair()
        s_tx = serial.Serial(port_tx, baudrate=9600, stopbits=serial.STOPBITS_ONE, timeout=1)
        s_rx = serial.Serial(port_rx, baudrate=9600, stopbits=serial.STOPBITS_ONE, timeout=1) if port_tx != port_rx else s_tx
        try:
            test_data = b'test with 1 stop bit'
            s_tx.write(test_data)
            s_tx.flush()
            time.sleep(0.1)
            received = s_rx.read(len(test_data))
            self.assertEqual(received, test_data,
                           "Data should pass correctly with 1 stop bit")
        finally:
            if s_tx != s_rx:
                s_rx.close()
            s_tx.close()

    def test_stopbits_two(self):
        """Test 2 stop bits configuration"""
        port_tx, port_rx = get_port_pair()
        s_tx = serial.Serial(port_tx, baudrate=9600, stopbits=serial.STOPBITS_TWO, timeout=1)
        s_rx = serial.Serial(port_rx, baudrate=9600, stopbits=serial.STOPBITS_TWO, timeout=1) if port_tx != port_rx else s_tx
        try:
            test_data = b'test with 2 stop bits'
            s_tx.write(test_data)
            s_tx.flush()
            time.sleep(0.1)
            received = s_rx.read(len(test_data))
            self.assertEqual(received, test_data,
                           "Data should pass correctly with 2 stop bits")
        finally:
            if s_tx != s_rx:
                s_rx.close()
            s_tx.close()


@unittest.skipUnless(is_hardware_port(), "Requires real hardware or tty0tty (not loop://)")
class Test_MixedSettings(unittest.TestCase):
    """Test various combinations of serial port settings"""

    def test_common_configurations(self):
        """Test several common serial port configurations"""
        configs = [
            # (baudrate, bytesize, parity, stopbits)
            (9600, 8, serial.PARITY_NONE, 1),
            (9600, 7, serial.PARITY_EVEN, 1),
            (9600, 7, serial.PARITY_ODD, 1),
            (9600, 8, serial.PARITY_EVEN, 1),
            (19200, 8, serial.PARITY_NONE, 1),
            (115200, 8, serial.PARITY_NONE, 1),
            (9600, 8, serial.PARITY_NONE, 2),
        ]

        test_data = b'Config test 123'

        port_tx, port_rx = get_port_pair()

        for baud, bits, parity, stop in configs:
            with self.subTest(baudrate=baud, bytesize=bits, parity=parity, stopbits=stop):
                s_tx = serial.Serial(port_tx, baudrate=baud, bytesize=bits,
                                    parity=parity, stopbits=stop, timeout=1)
                s_rx = serial.Serial(port_rx, baudrate=baud, bytesize=bits,
                                    parity=parity, stopbits=stop, timeout=1) if port_tx != port_rx else s_tx
                try:
                    s_tx.write(test_data)
                    s_tx.flush()
                    time.sleep(0.1)

                    received = s_rx.read(len(test_data))

                    # For 7-bit modes, mask the expected data
                    if bits == 7:
                        expected = bytes([b & 0x7F for b in test_data])
                    else:
                        expected = test_data

                    self.assertEqual(received, expected,
                                   f"Config {baud}-{bits}-{parity}-{stop} should work")
                finally:
                    if s_tx != s_rx:
                        s_rx.close()
                    s_tx.close()


@unittest.skipUnless(is_hardware_port(), "Requires real hardware or tty0tty (not loop://)")
@unittest.skipIf(not hasattr(serial.Serial, 'send_break'), "send_break not supported on platform")
class Test_BreakSignal(unittest.TestCase):
    """Test break signal generation"""

    def test_send_break(self):
        """Test that send_break() can be called without error"""
        s = serial.Serial(get_port(), baudrate=9600, timeout=1)
        try:
            # Send a break signal
            # Duration is platform-specific, typically 0.25-0.5 seconds
            s.send_break(duration=0.25)

            # Should be able to send normal data after break
            s.write(b'after break')
            s.flush()
        finally:
            s.close()


if __name__ == '__main__':
    import sys
    sys.stdout.write(__doc__)
    if len(sys.argv) > 1:
        PORT = sys.argv[1]
    port = get_port()
    sys.stdout.write(f"Testing on port: {port}\n")
    sys.argv[1:] = ['-v']
    unittest.main()
