#!/usr/bin/env python3
"""List available serial ports for testing.

Usage:
    python test/list_available_ports.py                    # List all ports
    python test/list_available_ports.py --by-id            # Show by-id paths
    python test/list_available_ports.py --first            # Return first USB port
    python test/list_available_ports.py --select           # Interactive selection
"""
import sys
import serial.tools.list_ports


def list_ports(by_id=False, first=False, select_mode=False):
    """List available serial ports."""
    ports = list(serial.tools.list_ports.comports())
    
    # Filter to USB ports (more likely to be test hardware)
    usb_ports = [p for p in ports if 'USB' in p.description.upper() or '/dev/ttyACM' in p.device or '/dev/ttyUSB' in p.device]
    
    if not usb_ports:
        if not first:
            print("No USB serial ports found", file=sys.stderr)
            print("\nAvailable ports (may be built-in):", file=sys.stderr)
            for p in ports[:5]:  # Show first 5
                print(f"  {p.device} - {p.description}", file=sys.stderr)
        sys.exit(1)
    
    if first:
        # Return first USB port, prefer by-id path
        port = usb_ports[0]
        if by_id and hasattr(port, 'hwid'):
            # Try to find by-id path
            import os
            by_id_dir = '/dev/serial/by-id'
            if os.path.exists(by_id_dir):
                for name in os.listdir(by_id_dir):
                    path = os.path.join(by_id_dir, name)
                    if os.path.realpath(path) == port.device:
                        print(path)
                        return
        print(port.device)
        return
    
    if select_mode:
        print("Available serial ports:", file=sys.stderr)
        for i, p in enumerate(usb_ports, 1):
            device = p.device
            if by_id and hasattr(p, 'hwid'):
                import os
                by_id_dir = '/dev/serial/by-id'
                if os.path.exists(by_id_dir):
                    for name in os.listdir(by_id_dir):
                        path = os.path.join(by_id_dir, name)
                        if os.path.realpath(path) == p.device:
                            device = path
                            break
            print(f"  {i}. {device}", file=sys.stderr)
            print(f"     {p.description}", file=sys.stderr)
        
        try:
            choice = input("\nSelect port number (1-{}): ".format(len(usb_ports)))
            idx = int(choice) - 1
            if 0 <= idx < len(usb_ports):
                port = usb_ports[idx]
                device = port.device
                if by_id and hasattr(port, 'hwid'):
                    import os
                    by_id_dir = '/dev/serial/by-id'
                    if os.path.exists(by_id_dir):
                        for name in os.listdir(by_id_dir):
                            path = os.path.join(by_id_dir, name)
                            if os.path.realpath(path) == port.device:
                                device = path
                                break
                print(device)
                return
        except (ValueError, KeyboardInterrupt):
            sys.exit(1)
        
        print("Invalid selection", file=sys.stderr)
        sys.exit(1)
    
    # List all USB ports
    print("Available serial ports:")
    for p in usb_ports:
        device = p.device
        if by_id and hasattr(p, 'hwid'):
            import os
            by_id_dir = '/dev/serial/by-id'
            if os.path.exists(by_id_dir):
                for name in os.listdir(by_id_dir):
                    path = os.path.join(by_id_dir, name)
                    if os.path.realpath(path) == p.device:
                        device = path
                        break
        print(f"  {device}")
        print(f"    {p.description}")
        if hasattr(p, 'hwid'):
            print(f"    {p.hwid}")


if __name__ == '__main__':
    by_id = '--by-id' in sys.argv
    first = '--first' in sys.argv
    select_mode = '--select' in sys.argv
    
    if '--help' in sys.argv or '-h' in sys.argv:
        print(__doc__)
        sys.exit(0)
    
    list_ports(by_id=by_id, first=first, select_mode=select_mode)
