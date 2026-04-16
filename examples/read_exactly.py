"""Reading an exact number of bytes.

`AUSerial.read()` may return fewer bytes than requested (it returns whatever
the kernel has ready). When a protocol has fixed-size frames, you typically
want to block until *exactly* N bytes have been accumulated. We loop and
shrink the remaining count on each read.

An empty chunk means the device went away (e.g. USB unplugged): we raise
`EOFError` rather than loop forever. Pair with `asyncio.wait_for()` if you
also need a timeout.
"""

import asyncio

from auserial import AUSerial


async def read_exactly(fd: AUSerial, n_bytes: int) -> bytes:
    buffer = bytearray()
    while len(buffer) < n_bytes:
        chunk = await fd.read(n_bytes - len(buffer))
        if not chunk:
            raise EOFError(f"Got {len(buffer)} of {n_bytes} bytes before EOF")
        buffer.extend(chunk)
    return bytes(buffer)


async def main():
    async with AUSerial("/dev/cu.usbmodem21301") as serial:
        await serial.write(b"AT\r\n")
        frame = await asyncio.wait_for(read_exactly(serial, 16), timeout=1.0)
        print(f"Frame: {frame!r}")


asyncio.run(main())
