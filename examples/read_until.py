"""Reading until a delimiter.

`AUSerial.read()` returns whatever chunk the kernel hands over (up to
`n_bytes`). A line or framed message may span several chunks, so we
accumulate into a buffer and stop as soon as the delimiter appears.

Note: the returned buffer may include bytes *after* the delimiter if the
delimiter and some trailing data arrived in the same chunk. If you need
strict framing, split on the delimiter and keep the remainder for the next
call (stateful helper, not shown here).
"""

import asyncio

from auserial import AUSerial


async def read_until(serial: AUSerial, delimiter: bytes = b"\n") -> bytes:
    buffer = b""
    while delimiter not in buffer:
        chunk = await serial.read(64)
        if not chunk:
            break
        buffer += chunk
    return buffer


async def main():
    async with AUSerial("/dev/cu.usbmodem21301") as serial:
        await serial.write(b"AT\r\n")
        line = await asyncio.wait_for(read_until(serial, b"\r\n"), timeout=1.0)
        print(f"Line: {line!r}")


asyncio.run(main())
