# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] — 2026-04-28

First stable release. Public API is now considered stable; breaking changes
will require a 2.0.0 bump.

### Added
- Buffer flush on construct (`tcflush(TCIFLUSH)`) to discard stale bytes from
  a previous session ([#4](https://github.com/papyDoctor/auserial/pull/4)).
- Test that verifies stale bytes are dropped at construction time.

### Changed
- `Development Status` classifier promoted to `5 - Production/Stable`.

## [0.4.2] — 2026-04-18

### Changed
- Updated `examples/read_until.py` to use the native `AUSerial.read_until()`
  instead of a hand-rolled accumulator
  ([#2](https://github.com/papyDoctor/auserial/pull/2)).

## [0.4.1] — 2026-04-17

### Added
- `maintainers` field in `pyproject.toml` (Louis Travaux).

### Changed
- `Development Status` classifier promoted to `4 - Beta`.

## [0.4.0] — 2026-04-17

### Added
- `AUSerial.read_until(terminator, size=None)` — accumulates bytes until a
  delimiter is found, with EOF and `size` cap handling
  ([#1](https://github.com/papyDoctor/auserial/pull/1)).
- Internal `_read_buf` shared between `read()` and `read_until()` so bytes
  arriving after a terminator are preserved for the next call.
- 18 new tests covering `read_until` semantics and read/write lock
  serialization across concurrent callers.

## [0.3.0] — 2026-04-17

### Added
- Full constructor configuration: `bytesize` (5/6/7/8), `parity` (`"N"`/`"E"`/`"O"`),
  `stopbits` (1/2), `xonxoff`, `rtscts` — with validation.
- Explicit raw mode (clears `iflag`/`oflag`/`lflag`) and explicit
  `VMIN=0`/`VTIME=0` for non-blocking reads.

## [0.2.0] — 2026-04-16

### Added
- `list_ports()` and `PortInfo(path, description, hwid)` for discovering
  available serial ports.
- Linux: enriches via `/sys/class/tty/<name>/device/`.
- macOS: parses `ioreg` plist output and links each `/dev/cu.*` to its
  nearest USB ancestor; filters out Bluetooth and debug consoles.
- Pure stdlib — no extra dependency.

## [0.1.0] — 2026-04-16

Initial public release.

### Added
- `AUSerial` async context manager with `read()`, `write()`, `close()`
  built on `asyncio.add_reader` / `add_writer` (epoll on Linux, kqueue on
  macOS).
- PTY-based test suite — no hardware required.
- PEP 561 `py.typed` marker so consumers get type info.
- Examples: `minimal.py`, `timeout.py`, `read_until.py`, `read_exactly.py`,
  `good_way_to_use.py`.

[1.0.0]: https://github.com/papyDoctor/auserial/releases/tag/v1.0.0
[0.4.2]: https://github.com/papyDoctor/auserial/releases/tag/v0.4.2
[0.4.1]: https://github.com/papyDoctor/auserial/releases/tag/v0.4.1
[0.4.0]: https://github.com/papyDoctor/auserial/releases/tag/v0.4.0
[0.3.0]: https://github.com/papyDoctor/auserial/releases/tag/v0.3.0
[0.2.0]: https://github.com/papyDoctor/auserial/releases/tag/v0.2.0
[0.1.0]: https://github.com/papyDoctor/auserial/releases/tag/v0.1.0
