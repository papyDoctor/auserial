"""Concurrent reader + periodic writer — the whole point of AUSerial.

Two tasks run on the same event loop:

- `reader` blocks on `serial.read()` waiting for incoming bytes. Because
  AUSerial uses the kernel's epoll/kqueue (via `loop.add_reader`), this wait
  does NOT block the thread — it just suspends the coroutine until the fd is
  readable.

- `sender` wakes up every second to push `AT\r\n`, then goes back to sleep.

While `reader` is parked in `await serial.read()`, `sender` keeps running:
it sleeps, writes, sleeps, writes… A synchronous serial library (pyserial)
or a thread-backed one (aioserial) could not do this without extra threads.

Ctrl+C → `KeyboardInterrupt` cancels both tasks, the `async with` closes the
port, `AUSerial.close()` cancels any pending read/write future.
"""

import asyncio

from auserial import AUSerial


async def reader(serial: AUSerial) -> None:
    while True:
        data = await serial.read()
        print(f"<- {data!r}")


async def sender(serial: AUSerial, interval: float = 1.0) -> None:
    while True:
        await serial.write(b"AT\r\n")
        print("-> AT")
        await asyncio.sleep(interval)


async def main() -> None:
    async with AUSerial("/dev/cu.usbmodem21301") as serial:
        await asyncio.gather(reader(serial), sender(serial))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
