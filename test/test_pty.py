#!/usr/bin/env python
#
# This file is part of pySerial - Cross platform serial port support for Python
# (C) 2016 Chris Liechti <cliechti@gmx.net>
#
# SPDX-License-Identifier:    BSD-3-Clause
"""
Test PTY related functionality.
"""

import os
import sys

try:
    import pty
except ImportError:
    pty = None
import unittest
import serial

DATA = b'Hello\n'

@unittest.skipIf(pty is None, "pty module not supported on platform")
class Test_Pty_Serial_Open(unittest.TestCase):
    """Test PTY serial open"""

    def setUp(self):
        # Open PTY
        self.master, self.slave = pty.openpty()

    def tearDown(self):
        # Close PTY file descriptors if they haven't been closed yet
        try:
            os.close(self.master)
        except OSError:
            pass  # Already closed by fdopen
        try:
            os.close(self.slave)
        except OSError:
            pass  # Already closed

    def test_pty_serial_open_slave(self):
        with serial.Serial(os.ttyname(self.slave), timeout=1) as slave_ser:
            slave_ser.reset_input_buffer()
            slave_ser.reset_output_buffer()

    def test_pty_serial_write(self):
        with serial.Serial(os.ttyname(self.slave), timeout=1) as slave_ser:
            # Duplicate the master fd so fdopen doesn't close it
            master_dup = os.dup(self.master)
            with os.fdopen(master_dup, "wb") as fd:
                fd.write(DATA)
                fd.flush()
                out = slave_ser.read(len(DATA))
                self.assertEqual(DATA, out)
                slave_ser.reset_input_buffer()
                slave_ser.reset_output_buffer()

    def test_pty_serial_read(self):
        with serial.Serial(os.ttyname(self.slave), timeout=1) as slave_ser:
            # Duplicate the master fd so fdopen doesn't close it
            master_dup = os.dup(self.master)
            with os.fdopen(master_dup, "rb") as fd:
                slave_ser.write(DATA)
                # Don't call flush() - tcdrain() blocks on macOS PTYs
                out = fd.read(len(DATA))
                self.assertEqual(DATA, out)
                slave_ser.reset_input_buffer()
                slave_ser.reset_output_buffer()

if __name__ == '__main__':
    sys.stdout.write(__doc__)
    # When this module is executed from the command-line, it runs all its tests
    unittest.main()
