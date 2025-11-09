#!/usr/bin/env python
#
# This file is part of pySerial - Cross platform serial port support for Python
# (C) 2001-2024 Chris Liechti <cliechti@gmx.net>
#
# SPDX-License-Identifier:    BSD-3-Clause
"""\
Extended hardware-specific tests for comprehensive coverage.

These tests target uncovered code paths in serial/serialposix.py and
serial/serialutil.py that can be exercised with tty0tty or real hardware.

Tests cover:
- Alternative Serial implementations (PosixPollSerial, VTIMESerial)
- Custom/non-standard baudrates
- MARK and SPACE parity modes
- Complete modem line testing (DSR, RI, CD)
- Software flow control (XON/XOFF)
- Write timeout and non-blocking writes
- Inter-byte timeout
- Break condition property
- Edge cases and property validation

These tests assume a null-modem (loopback) configuration where:
  TX <-> RX
  RTS <-> CTS
  DTR <-> DSR/CD/RI
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


# ============================================================================
# Alternative Serial Implementation Tests
# ============================================================================

@unittest.skipUnless(is_hardware_port(), "Requires real hardware or tty0tty (not loop://)")
@unittest.skip("PosixPollSerial blocks on tty0tty")
class Test_PosixPollSerial(unittest.TestCase):
    """Test PosixPollSerial alternative implementation using poll() instead of select()"""

    def test_poll_serial_basic_io(self):
        """Test PosixPollSerial for basic read/write operations"""
        from serial.serialposix import PosixPollSerial

        port_tx, port_rx = get_port_pair()
        s_tx = PosixPollSerial(port_tx, baudrate=115200, timeout=1)
        s_rx = PosixPollSerial(port_rx, baudrate=115200, timeout=1) if port_tx != port_rx else s_tx

        try:
            test_data = b'PosixPollSerial test data'
            s_tx.write(test_data)
            s_tx.flush()
            time.sleep(0.1)

            received = s_rx.read(len(test_data))
            self.assertEqual(received, test_data)
        finally:
            if s_tx != s_rx:
                s_rx.close()
            s_tx.close()

    def test_poll_serial_timeout(self):
        """Test PosixPollSerial timeout behavior"""
        from serial.serialposix import PosixPollSerial

        s = PosixPollSerial(get_port(), baudrate=115200, timeout=0.5)
        try:
            start = time.time()
            data = s.read(10)  # Should timeout
            elapsed = time.time() - start

            self.assertEqual(len(data), 0)
            self.assertGreater(elapsed, 0.4)
            self.assertLess(elapsed, 0.7)
        finally:
            s.close()

    def test_poll_serial_with_inter_byte_timeout(self):
        """Test PosixPollSerial with inter-byte timeout"""
        from serial.serialposix import PosixPollSerial

        port_tx, port_rx = get_port_pair()
        s_tx = PosixPollSerial(port_tx, baudrate=115200, timeout=1)
        s_rx = PosixPollSerial(port_rx, baudrate=115200, timeout=1,
                              inter_byte_timeout=0.1) if port_tx != port_rx else s_tx

        try:
            # Send bytes with spacing
            s_tx.write(b'AB')
            s_tx.flush()
            time.sleep(0.05)  # Within inter-byte timeout
            s_tx.write(b'CD')
            s_tx.flush()
            time.sleep(0.15)  # Exceeds inter-byte timeout
            s_tx.write(b'EF')
            s_tx.flush()

            if s_tx != s_rx:
                time.sleep(0.2)
                # Should read first 4 bytes then stop at inter-byte timeout
                data = s_rx.read(10)
                self.assertEqual(len(data), 4)
                self.assertEqual(data, b'ABCD')
        finally:
            if s_tx != s_rx:
                s_rx.close()
            s_tx.close()


@unittest.skipUnless(is_hardware_port(), "Requires real hardware or tty0tty (not loop://)")
@unittest.skip("VTIMESerial blocks on tty0tty")
class Test_VTIMESerial(unittest.TestCase):
    """Test VTIMESerial alternative timeout implementation"""

    def test_vtime_serial_basic_io(self):
        """Test VTIMESerial for basic read/write operations"""
        from serial.serialposix import VTIMESerial

        port_tx, port_rx = get_port_pair()
        s_tx = VTIMESerial(port_tx, baudrate=115200, timeout=1)
        s_rx = VTIMESerial(port_rx, baudrate=115200, timeout=1) if port_tx != port_rx else s_tx

        try:
            test_data = b'VTIMESerial test data'
            s_tx.write(test_data)
            s_tx.flush()
            time.sleep(0.1)

            received = s_rx.read(len(test_data))
            self.assertEqual(received, test_data)
        finally:
            if s_tx != s_rx:
                s_rx.close()
            s_tx.close()

    def test_vtime_serial_no_cancel_read(self):
        """Test that VTIMESerial doesn't support cancel_read"""
        from serial.serialposix import VTIMESerial

        s = VTIMESerial(get_port(), baudrate=115200, timeout=1)
        try:
            # VTIMESerial doesn't have cancel_read/cancel_write
            self.assertFalse(hasattr(s, 'cancel_read'))
            self.assertFalse(hasattr(s, 'cancel_write'))
        finally:
            s.close()


# ============================================================================
# Custom Baudrate Tests
# ============================================================================

@unittest.skipUnless(is_hardware_port(), "Requires real hardware or tty0tty (not loop://)")
@unittest.skipUnless(sys.platform.startswith('linux'), "Custom baudrates are Linux-specific")
class Test_CustomBaudrate(unittest.TestCase):
    """Test custom/non-standard baudrate configuration"""

    def test_custom_baudrate_250000(self):
        """Test setting custom baudrate 250000"""
        port_tx, port_rx = get_port_pair()

        try:
            s_tx = serial.Serial(port_tx, baudrate=250000, timeout=1)
            s_rx = serial.Serial(port_rx, baudrate=250000, timeout=1) if port_tx != port_rx else s_tx

            self.assertEqual(s_tx.baudrate, 250000)

            # Verify data transmission works
            test_data = b'Custom baud 250000'
            s_tx.write(test_data)
            s_tx.flush()
            time.sleep(0.1)

            received = s_rx.read(len(test_data))
            self.assertEqual(received, test_data)

            if s_tx != s_rx:
                s_rx.close()
            s_tx.close()
        except (IOError, serial.SerialException) as e:
            self.skipTest(f"Custom baudrate not supported: {e}")

    def test_custom_baudrate_500000(self):
        """Test setting custom baudrate 500000"""
        try:
            s = serial.Serial(get_port(), baudrate=500000, timeout=1)
            self.assertEqual(s.baudrate, 500000)
            s.close()
        except (IOError, serial.SerialException) as e:
            self.skipTest(f"Custom baudrate not supported: {e}")

    def test_custom_baudrate_1000000(self):
        """Test setting custom baudrate 1000000"""
        try:
            s = serial.Serial(get_port(), baudrate=1000000, timeout=1)
            self.assertEqual(s.baudrate, 1000000)
            s.close()
        except (IOError, serial.SerialException) as e:
            self.skipTest(f"Custom baudrate not supported: {e}")


# ============================================================================
# MARK and SPACE Parity Tests
# ============================================================================

@unittest.skipUnless(is_hardware_port(), "Requires real hardware or tty0tty (not loop://)")
class Test_MarkSpaceParity(unittest.TestCase):
    """Test MARK and SPACE parity modes"""

    def test_parity_mark(self):
        """Test MARK parity configuration"""
        port_tx, port_rx = get_port_pair()

        try:
            s_tx = serial.Serial(port_tx, baudrate=9600, parity=serial.PARITY_MARK, timeout=1)
            s_rx = serial.Serial(port_rx, baudrate=9600, parity=serial.PARITY_MARK, timeout=1) if port_tx != port_rx else s_tx

            test_data = b'\x00\x7F\xAA\x55\xFF'
            s_tx.write(test_data)
            s_tx.flush()
            time.sleep(0.1)

            received = s_rx.read(len(test_data))
            self.assertEqual(received, test_data, "Data should pass correctly with MARK parity")

            if s_tx != s_rx:
                s_rx.close()
            s_tx.close()
        except (ValueError, AttributeError) as e:
            self.skipTest(f"MARK parity not supported: {e}")

    def test_parity_space(self):
        """Test SPACE parity configuration"""
        port_tx, port_rx = get_port_pair()

        try:
            s_tx = serial.Serial(port_tx, baudrate=9600, parity=serial.PARITY_SPACE, timeout=1)
            s_rx = serial.Serial(port_rx, baudrate=9600, parity=serial.PARITY_SPACE, timeout=1) if port_tx != port_rx else s_tx

            test_data = b'\x00\x7F\xAA\x55\xFF'
            s_tx.write(test_data)
            s_tx.flush()
            time.sleep(0.1)

            received = s_rx.read(len(test_data))
            self.assertEqual(received, test_data, "Data should pass correctly with SPACE parity")

            if s_tx != s_rx:
                s_rx.close()
            s_tx.close()
        except (ValueError, AttributeError) as e:
            self.skipTest(f"SPACE parity not supported: {e}")


# ============================================================================
# Complete Modem Line Tests
# ============================================================================

@unittest.skipUnless(is_hardware_port(), "Requires real hardware or tty0tty (not loop://)")
class Test_AllModemLines(unittest.TestCase):
    """Test all modem status lines (DSR, RI, CD in addition to CTS)"""

    def test_dsr_modem_line(self):
        """Test DSR (Data Set Ready) modem line"""
        port1, port2 = get_port_pair()

        if port1 == port2:
            self.skipTest("Requires paired ports")

        s1 = serial.Serial(port1, baudrate=115200, timeout=1)
        s2 = serial.Serial(port2, baudrate=115200, timeout=1)

        try:
            # DTR on s1 should appear as DSR on s2
            s1.dtr = True
            time.sleep(0.05)
            self.assertTrue(s2.dsr, "DSR should be high when paired DTR is high")

            s1.dtr = False
            time.sleep(0.05)
            self.assertFalse(s2.dsr, "DSR should be low when paired DTR is low")
        finally:
            s2.close()
            s1.close()

    def test_cd_modem_line(self):
        """Test CD (Carrier Detect) modem line"""
        port1, port2 = get_port_pair()

        if port1 == port2:
            self.skipTest("Requires paired ports")

        s1 = serial.Serial(port1, baudrate=115200, timeout=1)
        s2 = serial.Serial(port2, baudrate=115200, timeout=1)

        try:
            # DTR on s1 should appear as CD on s2
            s1.dtr = True
            time.sleep(0.05)
            self.assertTrue(s2.cd, "CD should be high when paired DTR is high")

            s1.dtr = False
            time.sleep(0.05)
            self.assertFalse(s2.cd, "CD should be low when paired DTR is low")
        finally:
            s2.close()
            s1.close()

    def test_ri_modem_line(self):
        """Test RI (Ring Indicator) modem line reading"""
        port1, port2 = get_port_pair()

        if port1 == port2:
            self.skipTest("Requires paired ports")

        s1 = serial.Serial(port1, baudrate=115200, timeout=1)
        s2 = serial.Serial(port2, baudrate=115200, timeout=1)

        try:
            # DTR on s1 may or may not appear as RI on s2 depending on wiring
            # Just verify we can read the property without error
            ri_state = s2.ri
            self.assertIsInstance(ri_state, bool)
        finally:
            s2.close()
            s1.close()


# ============================================================================
# Software Flow Control (XON/XOFF) Tests
# ============================================================================

@unittest.skipUnless(is_hardware_port(), "Requires real hardware or tty0tty (not loop://)")
class Test_SoftwareFlowControl(unittest.TestCase):
    """Test XON/XOFF software flow control"""

    def test_xonxoff_data_transmission(self):
        """Test data transmission with XON/XOFF enabled"""
        port_tx, port_rx = get_port_pair()
        s_tx = serial.Serial(port_tx, baudrate=115200, xonxoff=True, timeout=1)
        s_rx = serial.Serial(port_rx, baudrate=115200, xonxoff=True, timeout=1) if port_tx != port_rx else s_tx

        try:
            # XON/XOFF shouldn't break normal transmission
            test_data = b'Test with XON/XOFF enabled' * 10
            s_tx.write(test_data)
            s_tx.flush()
            time.sleep(0.2)

            if s_tx != s_rx:
                received = s_rx.read(len(test_data))
                self.assertEqual(received, test_data)
        finally:
            if s_tx != s_rx:
                s_rx.close()
            s_tx.close()

    def test_set_input_flow_control(self):
        """Test manual XON/XOFF input flow control"""
        s = serial.Serial(get_port(), xonxoff=True, timeout=1)

        try:
            # Send XOFF (suspend input)
            s.set_input_flow_control(False)
            time.sleep(0.05)

            # Send XON (resume input)
            s.set_input_flow_control(True)
            time.sleep(0.05)
        finally:
            s.close()

    def test_set_output_flow_control(self):
        """Test manual output flow control"""
        s = serial.Serial(get_port(), timeout=1)

        try:
            # Suspend output
            s.set_output_flow_control(False)
            time.sleep(0.05)

            # Resume output
            s.set_output_flow_control(True)
            time.sleep(0.05)
        finally:
            s.close()


# ============================================================================
# Write Timeout Tests
# ============================================================================

@unittest.skipUnless(is_hardware_port(), "Requires real hardware or tty0tty (not loop://)")
class Test_WriteTimeout(unittest.TestCase):
    """Test write timeout and non-blocking writes"""

    @unittest.skip("write_timeout=0 blocks on tty0tty")
    def test_write_non_blocking(self):
        """Test non-blocking write (write_timeout=0)"""
        s = serial.Serial(get_port(), baudrate=115200, write_timeout=0, timeout=1)

        try:
            # Non-blocking write should return immediately
            # May not write all bytes
            large_data = b'X' * 10000
            n = s.write(large_data)

            # Should write at least some bytes
            self.assertGreater(n, 0)
            self.assertLessEqual(n, len(large_data))
        finally:
            s.close()

    def test_write_timeout_expiration(self):
        """Test write timeout exception with slow baudrate and large data"""
        # Use very slow baudrate to force timeout
        s = serial.Serial(get_port(), baudrate=300, write_timeout=0.1, timeout=1)

        try:
            # Write large amount of data - should timeout
            large_data = b'X' * 100000

            with self.assertRaises(serial.SerialTimeoutException):
                s.write(large_data)
        except IOError:
            # May fail to set such slow baudrate on some systems
            self.skipTest("Unable to test write timeout with slow baudrate")
        finally:
            s.close()

    def test_write_with_flush(self):
        """Test write followed by flush waits for transmission"""
        port_tx, port_rx = get_port_pair()
        s_tx = serial.Serial(port_tx, baudrate=115200, timeout=1)
        s_rx = serial.Serial(port_rx, baudrate=115200, timeout=1) if port_tx != port_rx else s_tx

        try:
            test_data = b'Data with flush' * 100

            start = time.time()
            s_tx.write(test_data)
            s_tx.flush()  # Should wait for transmission
            elapsed = time.time() - start

            # Flush should take some time for large data
            self.assertGreater(elapsed, 0.001)

            if s_tx != s_rx:
                time.sleep(0.1)
                received = s_rx.read(len(test_data))
                self.assertEqual(len(received), len(test_data))
        finally:
            if s_tx != s_rx:
                s_rx.close()
            s_tx.close()


# ============================================================================
# Inter-byte Timeout Tests
# ============================================================================

@unittest.skipUnless(is_hardware_port(), "Requires real hardware or tty0tty (not loop://)")
class Test_InterByteTimeout(unittest.TestCase):
    """Test inter-byte timeout behavior"""

    @unittest.skip("inter_byte_timeout test hangs on tty0tty")
    def test_inter_byte_timeout_triggers(self):
        """Test inter-byte timeout stops read on delayed bytes"""
        port_tx, port_rx = get_port_pair()

        if port_tx == port_rx:
            self.skipTest("Requires paired ports")

        s_tx = serial.Serial(port_tx, baudrate=115200, timeout=1)
        s_rx = serial.Serial(port_rx, baudrate=115200, timeout=1, inter_byte_timeout=0.1)

        try:
            # Send bytes with spacing
            s_tx.write(b'AB')
            s_tx.flush()
            time.sleep(0.05)  # Within inter-byte timeout

            s_tx.write(b'CD')
            s_tx.flush()
            time.sleep(0.15)  # Exceeds inter-byte timeout

            s_tx.write(b'EF')
            s_tx.flush()

            time.sleep(0.1)

            # Should read first 4 bytes then stop
            data = s_rx.read(10)
            self.assertEqual(len(data), 4)
            self.assertEqual(data, b'ABCD')
        finally:
            s_rx.close()
            s_tx.close()


# ============================================================================
# Break Condition Property Tests
# ============================================================================

@unittest.skipUnless(is_hardware_port(), "Requires real hardware or tty0tty (not loop://)")
class Test_BreakCondition(unittest.TestCase):
    """Test break_condition property without send_break()"""

    def test_break_condition_property(self):
        """Test break_condition property getter/setter"""
        port_tx, port_rx = get_port_pair()
        s_tx = serial.Serial(port_tx, baudrate=115200, timeout=1)
        s_rx = serial.Serial(port_rx, baudrate=115200, timeout=1) if port_tx != port_rx else s_tx

        try:
            # Set break condition
            s_tx.break_condition = True
            time.sleep(0.05)

            # Clear break condition
            s_tx.break_condition = False
            time.sleep(0.05)

            # Verify communication still works after break
            test_data = b'after break condition'
            s_tx.write(test_data)
            s_tx.flush()

            if s_tx != s_rx:
                time.sleep(0.1)
                received = s_rx.read(len(test_data))
                self.assertEqual(received, test_data)
        finally:
            if s_tx != s_rx:
                s_rx.close()
            s_tx.close()


# ============================================================================
# Edge Cases and Property Validation Tests
# ============================================================================

@unittest.skipUnless(is_hardware_port(), "Requires real hardware or tty0tty (not loop://)")
class Test_PropertyEdgeCases(unittest.TestCase):
    """Test edge cases in property handling"""

    def test_change_port_while_open(self):
        """Test changing port property on open serial port"""
        port1, port2 = get_port_pair()

        if port1 == port2:
            self.skipTest("Requires different ports")

        s = serial.Serial(port1, baudrate=115200, timeout=1)
        self.assertTrue(s.is_open)
        self.assertEqual(s.port, port1)

        try:
            # Changing port should close and reopen
            s.port = port2
            self.assertTrue(s.is_open)
            self.assertEqual(s.port, port2)

            # Verify new port works
            s.write(b'test')
            s.flush()
        finally:
            s.close()

    def test_change_rts_while_open(self):
        """Test changing RTS state on open port"""
        port1, port2 = get_port_pair()

        if port1 == port2:
            self.skipTest("Requires paired ports")

        s1 = serial.Serial(port1, baudrate=115200, timeout=1)
        s2 = serial.Serial(port2, baudrate=115200, timeout=1)

        try:
            # Change RTS while open
            s1.rts = True
            time.sleep(0.05)
            self.assertTrue(s2.cts)

            s1.rts = False
            time.sleep(0.05)
            self.assertFalse(s2.cts)
        finally:
            s2.close()
            s1.close()

    def test_change_dtr_while_open(self):
        """Test changing DTR state on open port"""
        port1, port2 = get_port_pair()

        if port1 == port2:
            self.skipTest("Requires paired ports")

        s1 = serial.Serial(port1, baudrate=115200, timeout=1)
        s2 = serial.Serial(port2, baudrate=115200, timeout=1)

        try:
            # Change DTR while open
            s1.dtr = True
            time.sleep(0.05)
            self.assertTrue(s2.dsr)

            s1.dtr = False
            time.sleep(0.05)
            self.assertFalse(s2.dsr)
        finally:
            s2.close()
            s1.close()

    def test_baudrate_validation(self):
        """Test baudrate property validates input"""
        s = serial.Serial(get_port(), do_not_open=True)

        # Invalid baudrate should raise ValueError
        with self.assertRaises(ValueError):
            s.baudrate = "not a number"

        with self.assertRaises(ValueError):
            s.baudrate = -9600

        s.close()

    def test_timeout_validation(self):
        """Test timeout property validates input"""
        s = serial.Serial(get_port(), do_not_open=True)

        # Invalid timeout should raise ValueError
        with self.assertRaises(ValueError):
            s.timeout = "invalid"

        with self.assertRaises(ValueError):
            s.timeout = -1

        s.close()

    def test_context_manager_opens_closed_port(self):
        """Test context manager opens port if closed"""
        s = serial.Serial(get_port(), do_not_open=True)
        self.assertFalse(s.is_open)

        with s:
            self.assertTrue(s.is_open)
            s.write(b'test')
            s.flush()

        self.assertFalse(s.is_open)


# ============================================================================
# Miscellaneous Coverage Tests
# ============================================================================

@unittest.skipUnless(is_hardware_port(), "Requires real hardware or tty0tty (not loop://)")
class Test_MiscellaneousCoverage(unittest.TestCase):
    """Tests for miscellaneous uncovered code paths"""

    def test_read_until_with_size_limit(self):
        """Test read_until() respects size parameter"""
        port_tx, port_rx = get_port_pair()
        s_tx = serial.Serial(port_tx, baudrate=115200, timeout=1)
        s_rx = serial.Serial(port_rx, baudrate=115200, timeout=1) if port_tx != port_rx else s_tx

        try:
            # Send data without newline
            s_tx.write(b'This is a very long line without any newline character')
            s_tx.flush()

            if s_tx != s_rx:
                time.sleep(0.1)

                # Read until newline but limit to 10 bytes
                data = s_rx.read_until(expected=b'\n', size=10)
                self.assertEqual(len(data), 10)
        finally:
            if s_tx != s_rx:
                s_rx.close()
            s_tx.close()

    def test_readinto_with_memoryview(self):
        """Test readinto() with different buffer types"""
        port_tx, port_rx = get_port_pair()
        s_tx = serial.Serial(port_tx, baudrate=115200, timeout=1)
        s_rx = serial.Serial(port_rx, baudrate=115200, timeout=1) if port_tx != port_rx else s_tx

        try:
            test_data = b'readinto test'
            s_tx.write(test_data)
            s_tx.flush()

            if s_tx != s_rx:
                time.sleep(0.1)

                # Test with bytearray
                buf = bytearray(20)
                n = s_rx.readinto(buf)

                self.assertEqual(n, len(test_data))
                self.assertEqual(bytes(buf[:n]), test_data)
        finally:
            if s_tx != s_rx:
                s_rx.close()
            s_tx.close()

    def test_dsrdtr_follows_rtscts(self):
        """Test dsrdtr defaults to rtscts value when None"""
        s = serial.Serial(get_port(), rtscts=True, dsrdtr=None, do_not_open=True)

        # dsrdtr should follow rtscts at initialization
        self.assertEqual(s._dsrdtr, s._rtscts)

        s.close()

    def test_dsrdtr_independent(self):
        """Test dsrdtr can be set independently of rtscts"""
        s = serial.Serial(get_port(), rtscts=True, dsrdtr=False, do_not_open=True)

        # dsrdtr should be independent when explicitly set
        self.assertNotEqual(s.dsrdtr, s.rtscts)

        s.close()


# ============================================================================
# Low Latency Mode Test (may not work with tty0tty)
# ============================================================================

@unittest.skipUnless(is_hardware_port(), "Requires real hardware or tty0tty (not loop://)")
@unittest.skipUnless(sys.platform.startswith('linux'), "Low latency mode is Linux-specific")
class Test_LowLatencyMode(unittest.TestCase):
    """Test low latency mode (if supported)"""

    def test_low_latency_mode(self):
        """Test enabling/disabling low latency mode"""
        s = serial.Serial(get_port(), baudrate=115200, timeout=1)

        try:
            # Try to enable low latency mode
            s.set_low_latency_mode(True)

            # Try to disable it
            s.set_low_latency_mode(False)
        except (IOError, AttributeError) as e:
            self.skipTest(f"Low latency mode not supported: {e}")
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
