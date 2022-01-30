import argparse
import trio
from asciiserialcom.tty_utils import setup_tty

BAUD = 19200


async def print_fin(fin):
    while True:
        data = await fin.read()
        text = data.decode("ASCII", errors="replace")
        if len(text) > 0:
            print(text, end="", flush=True)


async def run(serial, firmware):
    timeout = 10
    setup_tty(serial, BAUD, arduino_dont_hup=False)
    with trio.move_on_after(timeout) as cancel_scope:
        async with trio.open_nursery() as nursery:
            async with await trio.open_file(serial, "br") as fin:
                async with await trio.open_file(serial, "bw") as fout:
                    async with await trio.open_file(firmware, "br") as fw_file:
                        nursery.start_soon(print_fin, fin)
                        await trio.sleep(1)
                        await fout.write(b"u")
                        await trio.sleep(0.5)
                        await fout.write(b"u")
                        await trio.sleep(0.5)
                        data = await fw_file.read()
                        await fout.write(data)
                        await trio.sleep(0.5)
                        await fout.write(b"e")
                        await trio.sleep(2)
                        nursery.cancel_scope.cancel()


def main():

    parser = argparse.ArgumentParser(
        description="Uploads firmware to NeoRV32 cores over UART. The user should run this right after resetting the core."
    )
    parser.add_argument(
        "tty", help="Location of tty to use, e.g. /dev/ttyUSB0",
    )
    parser.add_argument(
        "firmware", help="Location of firmware file to upload",
    )
    args = parser.parse_args()

    serial_location = args.tty
    firmware = args.firmware

    trio.run(run, serial_location, firmware)
