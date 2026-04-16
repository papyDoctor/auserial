"""Minimal AUSerial example: open a port, send a command, read the reply.

The `async with` block calls `open()` on entry and `close()` on exit, so the
file descriptor is released even if an exception is raised inside. `write()`
and `read()` both suspend the coroutine (not the whole thread) until the
kernel reports the fd as writable / readable — so other asyncio tasks keep
running while we wait.

Adjust the device path below to match your hardware (e.g. `/dev/ttyUSB0` on
Linux, `/dev/cu.usbmodem*` on macOS).
"""

import asyncio

from auserial import AUSerial


async def main():
    async with AUSerial("/dev/cu.usbmodem21301") as serial:
        await serial.write(b"AT\r\n")
        data = await serial.read()
        print(f"Received: {data!r}")


asyncio.run(main())
