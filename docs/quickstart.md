# Quick start

## Install

```bash
pip install auserial
```

Requires Python 3.10+ on Linux or macOS. Windows is not supported (different
I/O primitives — see [Limitations](#limitations)).

## Discover available ports

```python
from auserial import list_ports

for p in list_ports():
    print(p.path, p.description, p.hwid)
# /dev/cu.usbmodem21301  Raspberry Pi Pico  USB VID:PID=2E8A:0008 SER=E660B4400765AB25
```

`list_ports()` is synchronous and returns `list[PortInfo]`. On Linux it reads
USB metadata from `/sys/class/tty/<name>/device/`. On macOS it parses `ioreg`
output and links each `/dev/cu.*` to its USB ancestor (Bluetooth and debug
consoles are filtered out).

## Open a port and send a command

```python
import asyncio
from auserial import AUSerial

async def main():
    async with AUSerial("/dev/cu.usbmodem21301") as serial:
        await serial.write(b"AT\r\n")
        data = await serial.read()
        print(f"Received: {data!r}")

asyncio.run(main())
```

The `async with` block opens the port, configures termios in raw mode, flushes
stale bytes, then closes the fd on exit (even if an exception is raised).

## Read a complete line

```python
async with AUSerial("/dev/cu.usbmodem21301") as serial:
    await serial.write(b"AT\r\n")
    line = await serial.read_until(b"\r\n")
    print(f"Line: {line!r}")
```

`read_until()` accumulates incoming chunks until the terminator appears, then
returns the line including the terminator. Bytes that arrived after the
terminator are kept in an internal buffer for the next read.

## Read with a timeout

`AUSerial.read()` and `read_until()` have no native timeout — they suspend
until data arrives. To bound the wait, wrap with `asyncio.wait_for`:

```python
try:
    data = await asyncio.wait_for(serial.read(), timeout=1.0)
except TimeoutError:
    print("No response within 1s")
```

Cancellation cleans up the internal state — a subsequent `read()` works
normally.

## Configure baudrate, parity, flow control

```python
import termios
from auserial import AUSerial

serial = AUSerial(
    "/dev/ttyUSB0",
    baudrate=termios.B9600,
    bytesize=8,
    parity="N",       # "N" (none), "E" (even), "O" (odd)
    stopbits=1,
    xonxoff=False,
    rtscts=False,
)
```

Defaults are sensible for typical use: 115200 baud, 8N1, no flow control.

## Concurrent read + write

The whole point of `auserial`: one coroutine waits on incoming data while
another sends periodically — no threads involved.

```python
import asyncio
from auserial import AUSerial

async def reader(serial):
    while True:
        data = await serial.read()
        print(f"<- {data!r}")

async def sender(serial):
    while True:
        await serial.write(b"AT\r\n")
        await asyncio.sleep(1)

async def main():
    async with AUSerial("/dev/ttyUSB0") as serial:
        await asyncio.gather(reader(serial), sender(serial))

asyncio.run(main())
```

Internal locks serialize reads among themselves and writes among themselves —
a concurrent `read()` and `write()` are safe and proceed in parallel.

## Limitations

- **Unix-only.** Relies on `termios` and `add_reader`, which require an
  epoll/kqueue-compatible file descriptor. Windows needs a different
  implementation (IOCP) and is out of scope.
- A single `write()` issues **one** `os.write` — short writes are returned
  as-is (caller retries with the remainder if needed).
