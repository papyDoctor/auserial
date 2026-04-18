"""Reading until a delimiter.

`AUSerial.read_until()` accumulates incoming chunks into a buffer and
returns as soon as the delimiter is found. This is useful when a response
may span multiple kernel-delivered chunks (e.g. an AT command reply
terminated by \r\n).

Note: the returned buffer may include bytes *after* the delimiter if the
delimiter and trailing data arrived in the same chunk. For strict framing,
split on the delimiter and carry the remainder over to the next call
(stateful helper, not shown here).
"""

import asyncio

from auserial import AUSerial


async def main():
    async with AUSerial("/dev/cu.usbmodem21301") as serial:
        await serial.write(b"AT\r\n")
        line = await asyncio.wait_for(serial.read_until(b"\r\n"), timeout=1.0)
        print(f"Line: {line!r}")


asyncio.run(main())
