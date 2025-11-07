#!/usr/bin/env python
#
# This file is part of pySerial - Cross platform serial port support for Python
# (C) 2001-2024 Chris Liechti <cliechti@gmx.net>
#
# SPDX-License-Identifier:    BSD-3-Clause
"""\
Hardware-specific tests for serial port functionality.

These tests require actual serial port hardware or kernel-level emulation (like vtty).
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


def is_hardware_port():
    """Check if we're using a real hardware port or vtty, not loop://"""
    # Check environment variable first (set by CI), then module-level PORT
    port = os.environ.get('PYSERIAL_PORT', PORT)
    return not port.startswith('loop://')


# Use pytest.mark.skipif which evaluates at collection time
pytestmark = pytest.mark.skipif(
    os.environ.get('PYSERIAL_PORT', 'loop://').startswith('loop://'),
    reason="Requires real hardware or vtty (not loop://)"
)


# Keep the unittest decorator for backwards compatibility when run standalone
@unittest.skipUnless(is_hardware_port(), "Requires real hardware or vtty (not loop://)")
class Test_HardwareFlowControl(unittest.TestCase):
    """Test that hardware flow control actually works"""

    def setUp(self):
        self.s = serial.Serial(PORT, baudrate=115200, timeout=1, write_timeout=1)

    def tearDown(self):
        self.s.close()

    def test_rtscts_flow_control(self):
        """Test that RTS/CTS flow control actually stops transmission"""
        # This test uses a single port in loopback mode
        # When we lower RTS (ready to send), CTS (clear to send) should go low
        # and writes should block/timeout

        self.s.rtscts = True

        # With RTS high, CTS should be high and we can send
        self.s.rts = True
        time.sleep(0.05)  # Allow signal to propagate
        self.assertTrue(self.s.cts, "CTS should be high when RTS is high")

        # Send some data - should work
        self.s.write(b'test')
        self.s.flush()

        # With RTS low, CTS should be low and sends should timeout
        self.s.rts = False
        time.sleep(0.05)  # Allow signal to propagate
        self.assertFalse(self.s.cts, "CTS should be low when RTS is low")

        # Try to send data - should timeout since CTS is low
        # Note: This might not work perfectly in loopback since we're controlling
        # our own RTS, but it tests the mechanism
        self.s.write_timeout = 0.5
        start = time.time()
        try:
            # Write large data that would exceed buffer
            self.s.write(b'X' * 10000)
            elapsed = time.time() - start
            # Should have taken at least close to the timeout
            self.assertGreater(elapsed, 0.3, "Write should have been delayed by flow control")
        except serial.SerialTimeoutException:
            # Timeout is also acceptable - means flow control blocked it
            pass


@unittest.skipUnless(is_hardware_port(), "Requires real hardware or vtty (not loop://)")
class Test_ParityValidation(unittest.TestCase):
    """Test that parity bits are actually generated and checked"""

    def test_parity_even(self):
        """Test that even parity works correctly"""
        # Open two instances of the same port with loopback
        # Both should use same parity for data integrity
        s1 = serial.Serial(PORT, baudrate=9600, parity=serial.PARITY_EVEN, timeout=1)

        try:
            # With matching parity, data should pass through correctly
            test_data = b'\x00\x01\x7F\x80\xFF\xAA\x55'
            s1.write(test_data)
            s1.flush()
            time.sleep(0.1)

            received = s1.read(len(test_data))
            self.assertEqual(received, test_data,
                           "Data should pass correctly with matching parity")
        finally:
            s1.close()

    def test_parity_odd(self):
        """Test that odd parity works correctly"""
        s1 = serial.Serial(PORT, baudrate=9600, parity=serial.PARITY_ODD, timeout=1)

        try:
            # With matching parity, data should pass through correctly
            test_data = b'\x00\x01\x7F\x80\xFF\xAA\x55'
            s1.write(test_data)
            s1.flush()
            time.sleep(0.1)

            received = s1.read(len(test_data))
            self.assertEqual(received, test_data,
                           "Data should pass correctly with matching parity")
        finally:
            s1.close()

    def test_parity_none(self):
        """Test that no parity works correctly"""
        s1 = serial.Serial(PORT, baudrate=9600, parity=serial.PARITY_NONE, timeout=1)

        try:
            # With no parity, all 8 bits should pass through
            test_data = b'\x00\x01\x7F\x80\xFF\xAA\x55'
            s1.write(test_data)
            s1.flush()
            time.sleep(0.1)

            received = s1.read(len(test_data))
            self.assertEqual(received, test_data,
                           "Data should pass correctly with no parity")
        finally:
            s1.close()


@unittest.skipUnless(is_hardware_port(), "Requires real hardware or vtty (not loop://)")
class Test_ByteSize(unittest.TestCase):
    """Test that character size (bits per byte) is enforced"""

    def test_bytesize_7(self):
        """Test 7-bit character size masks high bit"""
        s1 = serial.Serial(PORT, baudrate=9600, bytesize=serial.SEVENBITS,
                          parity=serial.PARITY_NONE, timeout=1)

        try:
            # With 7 bits, high bit should be masked off
            # Send 0xFF (11111111), should receive 0x7F (01111111)
            test_data = b'\xFF\xAA\x80'
            s1.write(test_data)
            s1.flush()
            time.sleep(0.1)

            received = s1.read(len(test_data))
            # High bit should be masked in 7-bit mode
            expected = bytes([b & 0x7F for b in test_data])
            self.assertEqual(received, expected,
                           "High bit should be masked in 7-bit mode")
        finally:
            s1.close()

    def test_bytesize_8(self):
        """Test 8-bit character size preserves all bits"""
        s1 = serial.Serial(PORT, baudrate=9600, bytesize=serial.EIGHTBITS,
                          parity=serial.PARITY_NONE, timeout=1)

        try:
            # With 8 bits, all bits should pass through
            test_data = b'\xFF\xAA\x80\x00\x7F'
            s1.write(test_data)
            s1.flush()
            time.sleep(0.1)

            received = s1.read(len(test_data))
            self.assertEqual(received, test_data,
                           "All 8 bits should pass through in 8-bit mode")
        finally:
            s1.close()


@unittest.skipUnless(is_hardware_port(), "Requires real hardware or vtty (not loop://)")
class Test_BaudRate(unittest.TestCase):
    """Test baud rate timing accuracy"""

    def test_baud_rate_timing(self):
        """Test that different baud rates have measurably different timing"""
        test_data = b'X' * 100

        # Test at 9600 baud
        s_slow = serial.Serial(PORT, baudrate=9600, timeout=5)
        start = time.time()
        s_slow.write(test_data)
        s_slow.flush()  # Wait for transmission to complete
        time_slow = time.time() - start
        s_slow.close()

        # Test at 115200 baud
        s_fast = serial.Serial(PORT, baudrate=115200, timeout=5)
        start = time.time()
        s_fast.write(test_data)
        s_fast.flush()  # Wait for transmission to complete
        time_fast = time.time() - start
        s_fast.close()

        # 115200 should be roughly 12x faster than 9600
        # At minimum, it should be noticeably faster
        self.assertLess(time_fast * 2, time_slow,
                       f"115200 baud ({time_fast:.3f}s) should be much faster than 9600 baud ({time_slow:.3f}s)")

    def test_standard_baud_rates(self):
        """Test that common baud rates can be set and used"""
        standard_bauds = [9600, 19200, 38400, 57600, 115200]
        test_data = b'test'

        for baud in standard_bauds:
            with self.subTest(baudrate=baud):
                s = serial.Serial(PORT, baudrate=baud, timeout=1)
                try:
                    # Verify we can send and receive at this baud rate
                    s.write(test_data)
                    s.flush()
                    time.sleep(0.1)
                    received = s.read(len(test_data))
                    self.assertEqual(received, test_data,
                                   f"Data integrity should be maintained at {baud} baud")
                finally:
                    s.close()


@unittest.skipUnless(is_hardware_port(), "Requires real hardware or vtty (not loop://)")
class Test_StopBits(unittest.TestCase):
    """Test stop bits configuration"""

    def test_stopbits_one(self):
        """Test 1 stop bit configuration"""
        s = serial.Serial(PORT, baudrate=9600, stopbits=serial.STOPBITS_ONE, timeout=1)
        try:
            test_data = b'test with 1 stop bit'
            s.write(test_data)
            s.flush()
            time.sleep(0.1)
            received = s.read(len(test_data))
            self.assertEqual(received, test_data,
                           "Data should pass correctly with 1 stop bit")
        finally:
            s.close()

    def test_stopbits_two(self):
        """Test 2 stop bits configuration"""
        s = serial.Serial(PORT, baudrate=9600, stopbits=serial.STOPBITS_TWO, timeout=1)
        try:
            test_data = b'test with 2 stop bits'
            s.write(test_data)
            s.flush()
            time.sleep(0.1)
            received = s.read(len(test_data))
            self.assertEqual(received, test_data,
                           "Data should pass correctly with 2 stop bits")
        finally:
            s.close()


@unittest.skipUnless(is_hardware_port(), "Requires real hardware or vtty (not loop://)")
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

        for baud, bits, parity, stop in configs:
            with self.subTest(baudrate=baud, bytesize=bits, parity=parity, stopbits=stop):
                s = serial.Serial(PORT, baudrate=baud, bytesize=bits,
                                parity=parity, stopbits=stop, timeout=1)
                try:
                    s.write(test_data)
                    s.flush()
                    time.sleep(0.1)

                    received = s.read(len(test_data))

                    # For 7-bit modes, mask the expected data
                    if bits == 7:
                        expected = bytes([b & 0x7F for b in test_data])
                    else:
                        expected = test_data

                    self.assertEqual(received, expected,
                                   f"Config {baud}-{bits}-{parity}-{stop} should work")
                finally:
                    s.close()


@unittest.skipUnless(is_hardware_port(), "Requires real hardware or vtty (not loop://)")
@unittest.skipIf(not hasattr(serial.Serial, 'send_break'), "send_break not supported on platform")
class Test_BreakSignal(unittest.TestCase):
    """Test break signal generation"""

    def test_send_break(self):
        """Test that send_break() can be called without error"""
        s = serial.Serial(PORT, baudrate=9600, timeout=1)
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
    sys.stdout.write(f"Testing on port: {PORT}\n")
    sys.argv[1:] = ['-v']
    unittest.main()
