# AUSerial

**Truly async serial port for Linux/macOS using epoll/kqueue.**

`auserial` is a minimal, dependency-free async serial port for `asyncio`
applications. It relies only on the standard library (`os`, `termios`,
`asyncio`) and plugs directly into the event loop via `add_reader` /
`add_writer` — which under the hood use **epoll** on Linux and **kqueue**
on macOS.

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

## Why AUSerial?

| Library            | Backend                            | Cost                          |
|--------------------|------------------------------------|-------------------------------|
| `pyserial`         | Blocking reads                     | Freezes the event loop        |
| `aioserial`        | `run_in_executor` around pyserial  | One thread per I/O operation  |
| `pyserial-asyncio` | Transport/Protocol callback API    | Verbose, subclass boilerplate |
| **AUSerial**       | Direct `add_reader` / `add_writer` | Zero threads, zero polling    |

## Features

- **Stdlib only** — no external dependencies
- **Truly non-blocking** — no thread pool, no busy loop
- **Concurrency-safe** — internal locks serialize read/write across coroutines
- **`read_until()`** preserves surplus bytes for the next call
- **Port discovery** with USB metadata enrichment
- **PEP 561 typed** — full type info propagated to consumers
- **Tested via PTY** — no hardware needed to run the test suite

## Next steps

- [Quick start](quickstart.md) — install and first example
- [Examples](examples.md) — concurrent readers, timeouts, framing
- [API reference](api.md) — generated from the source
