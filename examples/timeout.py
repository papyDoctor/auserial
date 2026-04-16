"""Reading with a timeout.

`AUSerial.read()` itself has no timeout — it suspends until data arrives. To
bound the wait, wrap the call in `asyncio.wait_for()`, which raises
`TimeoutError` if the coroutine doesn't finish in time. The read is cancelled
cleanly: AUSerial's internal lock and reader registration are released by the
lock's `async with` and the `finally` branch of `read()`.
"""

import asyncio

from auserial import AUSerial


async def main():
    async with AUSerial("/dev/cu.usbmodem21301") as serial:
        await serial.write(b"AT\r\n")
        try:
            data = await asyncio.wait_for(serial.read(), timeout=1.0)
        except TimeoutError:
            print("No response within 1s")
        else:
            print(f"Received: {data!r}")


asyncio.run(main())
