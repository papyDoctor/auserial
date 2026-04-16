import plistlib
import subprocess
from pathlib import Path
from typing import Any

import pytest

import auserial._list_ports as list_ports_module
from auserial import PortInfo, list_ports


def test_unknown_platform_returns_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(list_ports_module.sys, "platform", "win32")
    assert list_ports_module.list_ports() == []


# --- macOS ------------------------------------------------------------------


def _serial_entry(callout: str) -> dict[str, Any]:
    return {
        "IOObjectClass": "IOSerialBSDClient",
        "IOClass": "IOSerialBSDClient",
        "IOCalloutDevice": callout,
        "IODialinDevice": callout.replace("/cu.", "/tty."),
    }


def _usb_dev(name: str, vid: int, pid: int, serial: str | None, *children: dict[str, Any]) -> dict[str, Any]:
    d: dict[str, Any] = {
        "IOObjectClass": "IOUSBHostDevice",
        "IOClass": "IOUSBHostDevice",
        "USB Product Name": name,
        "USB Vendor Name": "ACME",
        "idVendor": vid,
        "idProduct": pid,
        "IORegistryEntryChildren": list(children),
    }
    if serial is not None:
        d["USB Serial Number"] = serial
    return d


def _interface(name: str, vid: int, pid: int, *children: dict[str, Any]) -> dict[str, Any]:
    return {
        "IOObjectClass": "AppleUSBACMData",
        "IOClass": "AppleUSBACMData",
        "idVendor": vid,
        "idProduct": pid,
        "IORegistryEntryChildren": list(children),
    }


def _patch_macos_ioreg(monkeypatch: pytest.MonkeyPatch, serial_entries: list[dict[str, Any]], usb_entries: list[dict[str, Any]]) -> None:
    monkeypatch.setattr(list_ports_module.sys, "platform", "darwin")

    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        if "IOSerialBSDClient" in cmd:
            payload = plistlib.dumps(serial_entries)
        elif "IOUSBHostDevice" in cmd:
            payload = plistlib.dumps(usb_entries)
        else:
            payload = b""
        return subprocess.CompletedProcess(cmd, 0, stdout=payload, stderr=b"")

    monkeypatch.setattr(list_ports_module.subprocess, "run", fake_run)


def test_macos_returns_paths_with_usb_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    callout = "/dev/cu.usbmodem21301"
    serial_entries = [_serial_entry(callout)]
    usb_entries = [
        _usb_dev(
            "Pico",
            0x2E8A,
            0x0008,
            "ABC123",
            _interface("AppleUSBACMData", 0x2E8A, 0x0008, _serial_entry(callout)),
        )
    ]
    _patch_macos_ioreg(monkeypatch, serial_entries, usb_entries)

    ports = list_ports_module.list_ports()
    assert ports == [PortInfo(path=callout, description="ACME Pico", hwid="USB VID:PID=2E8A:0008 SER=ABC123")]


def test_macos_uses_nearest_usb_ancestor_not_outer_hub(monkeypatch: pytest.MonkeyPatch) -> None:
    callout = "/dev/cu.usbmodem21301"
    serial_entries = [_serial_entry(callout)]
    pico = _usb_dev(
        "Pico",
        0x2E8A,
        0x0008,
        None,
        _interface("AppleUSBACMData", 0x2E8A, 0x0008, _serial_entry(callout)),
    )
    hub = _usb_dev("USB Hub", 0x05E3, 0x0610, None, pico)
    _patch_macos_ioreg(monkeypatch, serial_entries, [hub])

    ports = list_ports_module.list_ports()
    assert ports[0].description == "ACME Pico"
    assert ports[0].hwid == "USB VID:PID=2E8A:0008"


def test_macos_filters_bluetooth_and_debug(monkeypatch: pytest.MonkeyPatch) -> None:
    serial_entries = [
        _serial_entry("/dev/cu.Bluetooth-Incoming-Port"),
        _serial_entry("/dev/cu.debug-console"),
        _serial_entry("/dev/cu.usbmodem21301"),
    ]
    _patch_macos_ioreg(monkeypatch, serial_entries, [])

    paths = [p.path for p in list_ports_module.list_ports()]
    assert paths == ["/dev/cu.usbmodem21301"]


def test_macos_keeps_non_usb_path_with_no_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    serial_entries = [_serial_entry("/dev/cu.someserial")]
    _patch_macos_ioreg(monkeypatch, serial_entries, [])

    ports = list_ports_module.list_ports()
    assert ports == [PortInfo(path="/dev/cu.someserial", description=None, hwid=None)]


def test_macos_handles_ioreg_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(list_ports_module.sys, "platform", "darwin")

    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(cmd, 1, stdout=b"", stderr=b"boom")

    monkeypatch.setattr(list_ports_module.subprocess, "run", fake_run)
    assert list_ports_module.list_ports() == []


# --- Linux ------------------------------------------------------------------


def _make_fake_sysfs(tmp_path: Path) -> Path:
    """Build a minimal /sys/class/tty/ttyUSB0 -> USB device structure."""
    sys_root = tmp_path / "sys"
    usb_dev = sys_root / "devices/usb1/1-1"
    usb_dev.mkdir(parents=True)
    (usb_dev / "idVendor").write_text("0403\n")
    (usb_dev / "idProduct").write_text("6001\n")
    (usb_dev / "manufacturer").write_text("FTDI\n")
    (usb_dev / "product").write_text("FT232R USB UART\n")
    (usb_dev / "serial").write_text("AB0CDEF1\n")

    iface = usb_dev / "1-1:1.0/ttyUSB0"
    iface.mkdir(parents=True)

    tty_class = sys_root / "class/tty/ttyUSB0"
    tty_class.parent.mkdir(parents=True)
    (tty_class).symlink_to(iface)

    device_link = tty_class / "device"
    device_link.symlink_to(iface.parent)

    return sys_root


def test_linux_enriches_from_sysfs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    sys_root = _make_fake_sysfs(tmp_path)
    monkeypatch.setattr(list_ports_module.sys, "platform", "linux")
    monkeypatch.setattr(list_ports_module.glob, "glob", lambda pat: ["/dev/ttyUSB0"] if "ttyUSB" in pat else [])

    real_path_cls = list_ports_module.Path

    def patched_path(value: str) -> Path:
        if isinstance(value, str) and value.startswith("/sys/class/tty"):
            return real_path_cls(str(sys_root) + value[len("/sys"):])
        return real_path_cls(value)

    monkeypatch.setattr(list_ports_module, "Path", patched_path)

    ports = list_ports_module.list_ports()
    assert ports == [
        PortInfo(
            path="/dev/ttyUSB0",
            description="FTDI FT232R USB UART",
            hwid="USB VID:PID=0403:6001 SER=AB0CDEF1",
        )
    ]


def test_linux_falls_back_to_path_only_if_no_sysfs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(list_ports_module.sys, "platform", "linux")
    monkeypatch.setattr(list_ports_module.glob, "glob", lambda pat: ["/dev/ttyS0"] if "ttyS" in pat else [])
    monkeypatch.setattr(list_ports_module, "Path", lambda value: tmp_path / "nonexistent")

    ports = list_ports_module.list_ports()
    assert ports == [PortInfo(path="/dev/ttyS0", description=None, hwid=None)]


# --- public surface ---------------------------------------------------------


def test_public_api_exports_list_ports_and_PortInfo() -> None:
    from auserial import PortInfo as ExportedPortInfo
    from auserial import list_ports as exported_list_ports

    assert exported_list_ports is list_ports
    assert ExportedPortInfo is PortInfo
