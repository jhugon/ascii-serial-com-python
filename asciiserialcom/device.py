"""
ASCII Serial Com Python Device

This is probably only used for testing, as a microcontroller is usually the
device.
"""

import sys
import os.path
import argparse
import datetime
import logging
import trio
from .base import Base, convert_to_hex, convert_from_hex
from .errors import *

from typing import Optional, Any, Union


async def deviceLoopOpenFiles(
    finname: str,
    foutname: str,
    registersBitWidth: int,
    nRegisters: int,
    printInterval: float,
) -> None:
    async with await trio.open_file(foutname, "wb", buffering=0) as fout:
        async with await trio.open_file(finname, "rb", buffering=0) as fin:
            async with trio.open_nursery() as nursery:
                dev = Device(
                    nursery, fin, fout, registersBitWidth, nRegisters, printInterval
                )


class Device(Base):
    recv_w: trio.abc.ReceiveChannel
    recv_r: trio.abc.ReceiveChannel

    def __init__(
        self,
        nursery: trio.Nursery,
        fin,
        fout,
        registerBitWidth: int,
        nRegisters: int,
        printRegistersInterval: float = 1,
        asciiSerialComVersion: bytes = b"0",
        appVersion: bytes = b"0",
        ignoreErrors: bool = False,
    ) -> None:
        super().__init__(
            nursery,
            fin,
            fout,
            registerBitWidth,
            asciiSerialComVersion,
            appVersion,
            ignoreErrors,
        )
        self.nRegisters = nRegisters
        self.registers = [0] * self.nRegisters
        nursery.start_soon(self.printRegistersLoop, printRegistersInterval)
        nursery.start_soon(self.handle_r_messages)
        nursery.start_soon(self.handle_w_messages)

        send_r: trio.abc.SendChannel
        send_r, self.recv_r = trio.open_memory_channel(0)
        self.forward_received_r_messages_to(send_r)

        send_w: trio.abc.SendChannel
        send_w, self.recv_w = trio.open_memory_channel(0)
        self.forward_received_w_messages_to(send_w)

    async def printRegistersLoop(self, interval: float) -> None:
        """
        Print the registers every interval seconds
        """

        while True:
            self.printRegisters()
            await trio.sleep(interval)

    async def handle_r_messages(self) -> None:
        async with self.recv_r:
            while True:
                msg = await self.recv_r.receive()
                if not msg:
                    continue
                elif msg.command == b"r":
                    regNum = convert_from_hex(msg.data)
                    if regNum > 0xFFFF:
                        raise BadRegisterNumberError(
                            f"register number, {regNum} = 0x{regNum:04X}, larger than 0xFFFF"
                        )
                    if regNum >= self.nRegisters:
                        raise BadRegisterNumberError(
                            f"Only {self.nRegisters} registers; regNum, {regNum} = 0x{regNum:04X}, too big"
                        )
                    regVal = self.registers[regNum]
                    response = msg.data + b"," + convert_to_hex(regVal)
                    await self.send_message(
                        msg.command, response,
                    )
                    logging.info(
                        f"device Read message received: {regNum} = 0x{regNum:04X} is {regVal}"
                    )
                else:
                    logging.warning(
                        f"device received command '{msg.command}', in read channel"
                    )

    async def handle_w_messages(self) -> None:
        async with self.recv_w:
            while True:
                msg = await self.recv_w.receive()
                if not msg:
                    continue
                elif msg.command == b"w":
                    regNumB, regValB = msg.data.split(b",")
                    regNum = convert_from_hex(regNumB)
                    regVal = convert_from_hex(regValB)
                    regValOld = self.registers[regNum]
                    self.registers[regNum] = regVal
                    await self.send_message(
                        msg.command, regNumB,
                    )
                    logging.info(
                        f"device Write message received: {regNumB} changed from {regValOld:X} to {regValB}"
                    )
                else:
                    logging.warning(
                        f"Warning: device received command '{msg.command}', in write channel"
                    )

    def printRegisters(self) -> None:
        logging.info("printRegisters")
        dtstr = datetime.datetime.now().replace(microsecond=0).isoformat(" ")
        if self.registerBitWidth <= 8:
            logging.info(
                "{0:>8}    {1:>19}    {2}".format("Reg Num", "Register Value", dtstr)
            )
        elif self.registerBitWidth <= 16:
            logging.info(
                "{0:>8}    {1:>31}    {2}".format("Reg Num", "Register Value", dtstr)
            )
        else:
            logging.info(
                "{0:>8}    {1:>21}    {2}".format("Reg Num", "Register Value", dtstr)
            )
        for i in range(self.nRegisters):
            val = self.registers[i]
            if self.registerBitWidth <= 8:
                logging.info(
                    "{0:3d} 0x{0:02X}    {1:3d} 0x{1:02X} {1:#010b}".format(i, val)
                )
            elif self.registerBitWidth <= 16:
                logging.info(
                    "{0:3d} 0x{0:02X}    {1:5d} 0x{1:04X} {1:#018b}".format(i, val)
                )
            else:
                logging.info("{0:3d} 0x{0:02X}    {1:10d} 0x{1:08X}".format(i, val))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="ASCII Serial Com Device. Useful as a test device."
    )
    parser.add_argument("fin", help="Path to tty device file")
    parser.add_argument("fout", help="Path to tty device file")
    parser.add_argument(
        "--registerBitWidth",
        "-r",
        type=int,
        default=32,
        help="Device register bit width (default: 32)",
    )
    parser.add_argument(
        "--nRegisters",
        "-n",
        type=int,
        default=16,
        help="Device number of registers (default: 16)",
    )
    parser.add_argument(
        "--timeBetweenPrint",
        "-t",
        type=float,
        default=2.0,
        help="Time between print statements in seconds (default: 2.)",
    )

    args = parser.parse_args()

    inFname = os.path.abspath(args.fin)
    outFname = os.path.abspath(args.fout)
    print(f"Input file name: {inFname}")
    print(f"outFname file name: {outFname}")
    print(f"N registers: {args.nRegisters}")
    print(f"Time between prints: {args.timeBetweenPrint}")

    trio.run(
        deviceLoopOpenFiles,
        inFname,
        outFname,
        args.registerBitWidth,
        args.nRegisters,
        args.timeBetweenPrint,
    )
