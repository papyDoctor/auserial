"""Discover available serial ports on Linux and macOS.

Stdlib only. On Linux: globs `/dev/tty{USB,ACM,S}*` and enriches each entry
with USB metadata read from `/sys/class/tty/<name>/device/`. On macOS: parses
`ioreg` plist output to list every `IOSerialBSDClient` and links each one to
its USB ancestor (when applicable).

Other platforms (Windows, BSD, etc.) currently return an empty list.
"""

import glob
import os
import plistlib
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, NamedTuple


class PortInfo(NamedTuple):
    path: str
    description: str | None
    hwid: str | None


_MACOS_SKIP = re.compile(r"^/dev/cu\.(Bluetooth|debug-console|wlan-debug)")


def list_ports() -> list[PortInfo]:
    if sys.platform.startswith("linux"):
        return _list_linux()
    if sys.platform == "darwin":
        return _list_darwin()
    return []


# --- Linux ------------------------------------------------------------------


def _list_linux() -> list[PortInfo]:
    paths = sorted(
        set(
            glob.glob("/dev/ttyUSB*")
            + glob.glob("/dev/ttyACM*")
            + glob.glob("/dev/ttyS*")
        )
    )
    return [_describe_linux(p) for p in paths]


def _describe_linux(path: str) -> PortInfo:
    name = os.path.basename(path)
    sysfs = Path(f"/sys/class/tty/{name}/device")
    if not sysfs.exists():
        return PortInfo(path=path, description=None, hwid=None)

    # Walk up the device tree until we find a USB device (has idVendor file).
    real = sysfs.resolve()
    usb_dir: Path | None = None
    candidate = real
    for _ in range(6):
        if (candidate / "idVendor").exists():
            usb_dir = candidate
            break
        if candidate.parent == candidate:
            break
        candidate = candidate.parent

    if usb_dir is None:
        return PortInfo(path=path, description=None, hwid=None)

    def read(fname: str) -> str | None:
        f = usb_dir / fname
        try:
            return f.read_text().strip() or None
        except OSError:
            return None

    vid = read("idVendor")
    pid = read("idProduct")
    product = read("product")
    manufacturer = read("manufacturer")
    serial = read("serial")

    description = " ".join(p for p in (manufacturer, product) if p) or None
    hwid_parts: list[str] = []
    if vid and pid:
        hwid_parts.append(f"USB VID:PID={vid.upper()}:{pid.upper()}")
    if serial:
        hwid_parts.append(f"SER={serial}")
    hwid = " ".join(hwid_parts) or None

    return PortInfo(path=path, description=description, hwid=hwid)


# --- macOS ------------------------------------------------------------------


def _list_darwin() -> list[PortInfo]:
    serial_paths = _macos_serial_paths()
    usb_map = _macos_usb_map()
    result: list[PortInfo] = []
    for path in serial_paths:
        if _MACOS_SKIP.match(path):
            continue
        info = usb_map.get(path, (None, None))
        result.append(PortInfo(path=path, description=info[0], hwid=info[1]))
    return sorted(result, key=lambda p: p.path)


def _ioreg_plist(class_name: str) -> list[dict[str, Any]]:
    try:
        out = subprocess.run(
            ["ioreg", "-arc", class_name, "-l", "-w", "0"],
            capture_output=True,
            check=False,
        )
    except (FileNotFoundError, OSError):
        return []
    if out.returncode != 0 or not out.stdout:
        return []
    try:
        entries = plistlib.loads(out.stdout)
    except Exception:
        return []
    return entries if isinstance(entries, list) else []


def _macos_serial_paths() -> list[str]:
    return [
        e["IOCalloutDevice"]
        for e in _ioreg_plist("IOSerialBSDClient")
        if isinstance(e.get("IOCalloutDevice"), str)
    ]


def _macos_usb_map() -> dict[str, tuple[str | None, str | None]]:
    """Map each /dev/cu.* path to the description/hwid of its NEAREST USB ancestor.

    The IOUSBHostDevice tree contains hubs whose children may be other USB
    devices. A serial endpoint should be described by the device it physically
    plugs into, not by an upstream hub.
    """
    result: dict[str, tuple[str | None, str | None]] = {}
    for usb_dev in _ioreg_plist("IOUSBHostDevice"):
        _collect_callouts_with_nearest_usb(usb_dev, result)
    return result


def _is_usb_device(d: dict[str, Any]) -> bool:
    """A real USB device, not a driver/interface that just inherits VID/PID."""
    return d.get("IOObjectClass") == "IOUSBHostDevice"


def _collect_callouts_with_nearest_usb(
    node: dict[str, Any],
    out: dict[str, tuple[str | None, str | None]],
    current_usb: dict[str, Any] | None = None,
    depth: int = 0,
) -> None:
    if depth > 16:
        return
    if _is_usb_device(node):
        current_usb = node
    if node.get("IOClass") == "IOSerialBSDClient":
        callout = node.get("IOCalloutDevice")
        if isinstance(callout, str) and current_usb is not None:
            out[callout] = _macos_usb_info(current_usb)
    children = node.get("IORegistryEntryChildren")
    if isinstance(children, list):
        for child in children:
            if isinstance(child, dict):
                _collect_callouts_with_nearest_usb(child, out, current_usb, depth + 1)


def _macos_usb_info(d: dict[str, Any]) -> tuple[str | None, str | None]:
    vendor = d.get("USB Vendor Name")
    product = d.get("USB Product Name")
    vid = d.get("idVendor")
    pid = d.get("idProduct")
    serial = d.get("USB Serial Number")

    description = " ".join(p for p in (vendor, product) if isinstance(p, str)) or None
    hwid_parts: list[str] = []
    if isinstance(vid, int) and isinstance(pid, int):
        hwid_parts.append(f"USB VID:PID={vid:04X}:{pid:04X}")
    if isinstance(serial, str) and serial:
        hwid_parts.append(f"SER={serial}")
    hwid = " ".join(hwid_parts) or None
    return description, hwid


