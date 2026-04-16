"""Discover serial ports available on the current machine.

`list_ports()` returns a list of `PortInfo(path, description, hwid)` —
synchronous, no event loop needed. Useful to enumerate devices before opening
one with AUSerial.
"""

from auserial import list_ports


def main() -> None:
    ports = list_ports()
    if not ports:
        print("No serial ports found.")
        return
    for p in ports:
        print(f"{p.path:30}  {p.description or '(no description)':30}  {p.hwid or ''}")


main()
