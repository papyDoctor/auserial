<p align="center">
  <h1 align="center">🟧 AUSerial</h1>
  <p align="center">
    <strong>Truly async serial port for Linux/macOS using epoll/kqueue</strong><br/>
  </p>
  <p align="center">
    <img src="https://img.shields.io/badge/platform-Linux%20%7C%20macOS-0078D6?style=flat-square&logo=linux&logoColor=white" alt="Platform"/>
    <img src="https://img.shields.io/badge/python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python"/>
    <img src="https://img.shields.io/badge/asyncio-native-4B8BBE?style=flat-square" alt="AsyncIO"/>
    <img src="https://img.shields.io/badge/license-MIT-green?style=flat-square" alt="License"/>
  </p>
</p>

## Why AUSerial?

**AUSerial** (Async Unix Serial) is a minimal, dependency-free async serial port
for `asyncio` applications. It relies only on the standard library (`os`, `termios`,
`asyncio`) and plugs directly into the event loop via `add_reader` / `add_writer` —
which under the hood use **epoll** (Linux) or **kqueue** (macOS).

## Comparison to existing librairies
| Library            | Backend                            | Cost                          |
|--------------------|------------------------------------|-------------------------------|
| `pyserial`         | Blocking reads                     | Freezes the event loop        |
| `aioserial`        | `run_in_executor` around pyserial  | One thread per I/O operation  |
| `pyserial-asyncio` | Transport/Protocol callback API    | Verbose, subclass boilerplate |
| **AUSerial**       | Direct `add_reader` / `add_writer` | Zero threads, zero polling    |

## Features

- 🪶 **~80 lines**, no external dependencies — just the standard library
- ⚡ **Truly non-blocking** — no thread pool, no busy loop
- 🔒 **Concurrency-safe** — internal locks prevent concurrent read/write conflicts
- 🧹 **Clean resource management** — async context manager + idempotent `close()`
- 🧯 **Proper error propagation** through `Future`s (no silent failures)
- 🧵 Pending operations are **cancelled** cleanly on close

## Installation

```bash
pip install auserial
```

Or from source:

```bash
git clone https://github.com/ton-user/auserial.git
cd auserial
pip install -e .
```

## Quick Start

```python
import asyncio
from auserial import AUSerial

async def main():
    async with AUSerial("/dev/ttyUSB0") as serial:
        await serial.write(b"AT\r\n")
        data = await serial.read()
        print(f"Received: {data!r}")

asyncio.run(main())
```

### Custom baudrate

```python
import termios
from auserial import AUSerial

async with AUSerial("/dev/ttyUSB0", baudrate=termios.B9600) as serial:
    ...
```

### Manual open/close

```python
serial = AUSerial("/dev/ttyUSB0")
await serial.open()
try:
    await serial.write(b"ping\n")
    response = await serial.read(n_bytes=128)
finally:
    serial.close()
```

## API

| Method                          | Description                                   |
|---------------------------------|-----------------------------------------------|
| `AUSerial(path, baudrate=...)`  | Opens the tty in non-blocking mode            |
| `await serial.open()`           | Binds the instance to the current event loop  |
| `await serial.read(n_bytes=64)` | Waits until data is available, returns bytes  |
| `await serial.write(data)`      | Waits until writable, returns bytes written   |
| `serial.close()`                | Cancels pending I/O and closes the fd         |

The class also implements `__aenter__` / `__aexit__`, so `async with` is the
recommended usage pattern.

## Limitations

- **Unix-only.** Relies on `termios` and `add_reader`, which require an
  epoll/kqueue-compatible file descriptor. Windows needs a different
  implementation (IOCP).
- A single call to `write()` issues **one** `os.write` — short writes are
  returned as-is (caller retries with the remainder if needed).

## Examples

More usage patterns live in [examples/](examples/).

## License

[MIT](LICENSE)
