"""
ASCII Serial Com Python Interface

"""

from __future__ import annotations
import logging

import trio

from .errors import *
from .message import ASC_Message
from .base import Base, check_register_content, check_register_number, convert_from_hex

from typing import cast, Union, Optional


class Host(Base):
    def __init__(
        self,
        nursery: trio.Nursery,
        fin,
        fout,
        registerBitWidth: int,
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

    async def read_register(self, regnum: int) -> int:
        """
        Read register on device

        Probably want a timeout on this just in case the device never replies (or it gets garbled)

        regnum: an integer register number from 0 to 0xFFFF

        returns register content as int
        """

        regnum_hex = check_register_number(regnum)
        await self.send_message(b"r", regnum_hex)
        send_r: trio.abc.SendChannel
        send_r, recv_r = trio.open_memory_channel(0)
        self.forward_received_r_messages_to(send_r)
        result: Optional[int] = None
        async with send_r:
            # read all messages in queue until one is correct or get cancelled or send_r closes
            while True:
                logging.debug(f"Trying to receive message from recv_r")
                msg_raw = await recv_r.receive()
                msg = cast(ASC_Message, msg_raw)
                if msg is None:
                    continue
                if msg.command == b"r":
                    logging.debug(f"Received message: {msg}")
                    splitdata = msg.data.split(b",")
                    try:
                        rec_regnum, rec_value = splitdata
                    except ValueError:
                        logging.warning(
                            f"Read response data, {msg.data.decode('ascii','replace')}, can't be split into a reg num and reg val (no comma!)"
                        )
                    else:
                        if int(rec_regnum, 16) == int(regnum_hex, 16):
                            result = convert_from_hex(rec_value)
                            break
                elif msg.command == b"e":
                    error_str, error_cause_msg = self._unpack_received_e_message(msg)
                    if error_cause_msg.command == b"r":
                        if error_cause_msg.data == regnum_hex:
                            raise DeviceError(
                                f'Device returned error while trying to read register: "{error_str}"'
                            )
                    else:
                        raise Exception(
                            f"read_register function somehow received: {msg}"
                        )
                else:
                    raise Exception(f"read_register function somehow received: {msg}")
        self.forward_received_r_messages_to(None)
        return result

    async def write_register(self, regnum: int, content: Union[bytes, int]) -> None:
        """
        write register on device

        Probably want a timeout on this just in case the device never replies (or it gets garbled)

        regnum: an integer register number

        content: bytes to write to the regnum or an integer.
            The integer is converted to little-endian bytes,
            and negative integers aren't allowed.
        """
        regnum_hex = check_register_number(regnum)
        content_hex = check_register_content(content, self.registerBitWidth)
        data = regnum_hex + b"," + content_hex
        await self.send_message(b"w", data)
        send_w: trio.abc.SendChannel
        send_w, recv_w = trio.open_memory_channel(0)
        self.forward_received_w_messages_to(send_w)
        async with send_w:
            # read all messages in queue until one is correct or get cancelled
            while True:
                msg_raw = await recv_w.receive()
                msg = cast(ASC_Message, msg_raw)
                if msg.command == b"w":
                    try:
                        msg_regnum = int(msg.data, 16)
                    except ValueError:
                        logging.warning(
                            f"Write response data, {msg.data.decode('ascii','replace')}, isn't a valid register number"
                        )
                    else:
                        if msg_regnum == int(regnum_hex, 16):
                            break
                elif msg.command == b"e":
                    error_str, error_cause_msg = self._unpack_received_e_message(msg)
                    if error_cause_msg.command == b"w":
                        if error_cause_msg.data.split(b",")[0] == data.split(b",")[0]:
                            raise DeviceError(
                                f'Device returned error while trying to write register: "{error_str}"'
                            )
                        else:
                            logging.debug(
                                f"write_register received error message caused by original message {error_cause_msg} not matching this message's data {data.decode('ascii','replace')} with error: {error_str}"
                            )
                    else:
                        raise Exception(
                            f"read_register function somehow received: {msg}"
                        )
                else:
                    raise Exception(f"read_register function somehow received: {msg}")
        self.forward_received_w_messages_to(None)
        return

    async def start_streaming(self) -> None:
        """
        Send command to start streaming from device to host (if supported on device)
        """

        await self.send_message(b"n", b"")

    async def stop_streaming(self) -> None:
        """
        Send command to stop streaming from device to host (if supported on device)
        """

        await self.send_message(b"f", b"")

    async def send_noop(self) -> None:
        """
        Send noop command
        """

        await self.send_message(b"z", b"")
