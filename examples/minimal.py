import asyncio

from auserial import AUSerial


async def main():
    async with AUSerial("/dev/cu.usbmodem21301") as serial:
        await serial.write(b"AT\r\n")
        data = await serial.read()
        print(f"Received: {data!r}")


asyncio.run(main())
