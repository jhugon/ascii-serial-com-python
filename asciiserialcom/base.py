"""
ASCII Serial Com Python Interface

"""

from __future__ import annotations
import io
import math
import logging
from pathlib import Path
from functools import partial

import trio
from trio._file_io import AsyncIOWrapper  # type: ignore

from .errors import *
from .circularBuffer import Circular_Buffer_Bytes
from .message import ASC_Message

from typing import Union, Optional, Any, Tuple
from collections.abc import Sequence


class Base:
    asciiSerialComVersion: bytes
    appVersion: bytes
    registerBitWidth: int
    ignoreErrors: bool
    send_w: Optional[trio.abc.SendChannel] = None
    send_r: Optional[trio.abc.SendChannel] = None
    send_s: Optional[trio.abc.SendChannel] = None
    write_w: Optional[Any] = None
    write_r: Optional[Any] = None
    write_s: Optional[Any] = None
    send_all_received_channel: Optional[trio.abc.SendChannel] = None
    send_all_received_channel_copy: bool = True
    buf: Circular_Buffer_Bytes = Circular_Buffer_Bytes(128)
    send_stream_frame_counter: int = 0
    receive_stream_frame_counter: Optional[int] = None

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
        if len(asciiSerialComVersion) != 1:
            raise Exception(
                f"asciiSerialComVersion must be a single byte not {asciiSerialComVersion.decode(errors='replace')}"
            )
        if len(appVersion) != 1:
            raise Exception(
                f"appVersion must be a single byte not {appVersion.decode(errors='replace')}"
            )
        self.fin = fin
        self.fout = fout
        self.asciiSerialComVersion = asciiSerialComVersion
        self.appVersion = appVersion
        self.registerBitWidth = registerBitWidth
        self.ignoreErrors = ignoreErrors

        try:
            path = Path(fin.name)
            self.fin_is_fifo = path.is_fifo()
            self.fin_is_char_device = path.is_char_device()
        except Exception:
            self.fin_is_fifo = False
            self.fin_is_char_device = False
        logging.debug(
            f"fin is char device: {self.fin_is_char_device} is FIFO: {self.fin_is_fifo}"
        )

        nursery.start_soon(self._receiver_task)

    async def send_message(self, command: bytes, data: bytes) -> None:
        """
        Low-level message send command
        Does not check if command is defined command or if it was received successfully

        command: single byte lower-case letter command/message type
        data: bytes or None
        """
        msg = ASC_Message(self.asciiSerialComVersion, self.appVersion, command, data)
        message = msg.get_packed()
        logging.debug("sending:          {}".format(msg))
        await self.fout.write(message)
        await self.fout.flush()
        logging.info("sent:          {}".format(msg))

    async def send_stream_message(self, data: bytes) -> None:
        """
        Send a streaming frame containing given data
        Does not check if message was received successfully

        data: bytes
        """

        counter = self.send_stream_frame_counter
        if self.send_stream_frame_counter == 255:
            self.send_stream_frame_counter = 0
        else:
            self.send_stream_frame_counter += 1
        await self.send_message(b"s", convert_to_hex(counter) + b"," + data)

    def forward_received_w_messages_to(
        self, channel: Union[None, trio.abc.SendChannel, io.IOBase, AsyncIOWrapper]
    ) -> None:
        """
        Send all future streaming frame "w" command messages to the given channel.

        If channel is None, then "w" command messages are dropped.
        """
        self.send_w = None
        self.write_w = None
        if channel is None:
            self.send_w = channel
        elif isinstance(channel, trio.abc.SendChannel):
            self.send_w = channel
        elif isinstance(channel, AsyncIOWrapper):
            channel.wrapped.write
            self.write_w = channel
        elif isinstance(channel, io.IOBase):
            self.write_w = trio.wrap_file(channel)
        else:
            raise Exception("Channel wrong type")

    def forward_received_r_messages_to(
        self, channel: Union[None, trio.abc.SendChannel, io.IOBase, AsyncIOWrapper]
    ) -> None:
        """
        Send all future streaming frame "r" command messages to the given channel.

        If channel is None, then "r" command messages are dropped.
        """
        self.send_r = None
        self.write_r = None
        if channel is None:
            self.send_r = channel
        elif isinstance(channel, trio.abc.SendChannel):
            self.send_r = channel
        elif isinstance(channel, AsyncIOWrapper):
            channel.wrapped.write
            self.write_r = channel
        elif isinstance(channel, io.IOBase):
            self.write_r = trio.wrap_file(channel)
        else:
            raise Exception("Channel wrong type")

    def forward_received_s_messages_to(
        self, channel: Union[None, trio.abc.SendChannel, io.IOBase, AsyncIOWrapper]
    ) -> None:
        """
        Send all future streaming frame "s" command messages to the given channel.
        Each message consists of a tuple (nMissed,payload)
        nMissed is the number of missed s messages since the last one received.
        payload is the s message payload data.

        If channel is None, then "s" command messages are dropped.
        """
        self.send_s = None
        self.write_s = None
        if channel is None:
            self.send_s = channel
        elif isinstance(channel, trio.abc.SendChannel):
            self.send_s = channel
        elif isinstance(channel, AsyncIOWrapper):
            channel.wrapped.write
            self.write_s = channel
        elif isinstance(channel, io.IOBase):
            self.write_s = trio.wrap_file(channel)
        else:
            raise Exception("Channel wrong type")

    def forward_all_received_messages_to(
        self, channel: Optional[trio.abc.SendChannel], copy: bool = False
    ) -> None:
        """
        This lets you send all recieved messages to a channel for handling. Useful for testing and debugging.

        If copy is True, then sends each message to channel and also sends them to the channel for each command (if present).

        If copy is False, then sends each message to channel only. This will break some commands like write_register and read_register.

        If channel is None, then resets to normal behavior
        """
        self.send_all_received_channel = channel
        self.send_all_received_channel_copy = copy

    async def _receiver_task(self) -> None:
        """
        This is the task that handles reading from the serial link (self.fin)
        and then puts ASC_Message's in queues
        """
        try:
            while True:
                try:
                    msg = await self._receive_message()
                except ASCErrorBase as e:
                    if isinstance(e, FileReadError) or not self.ignoreErrors:
                        raise e
                    else:
                        logging.error(f"{type(e).__name__}: {e}")
                        # logging.exception(f"{type(e)}: {e}")
                else:
                    if msg:
                        logging.debug(msg)
                        if self.send_all_received_channel:
                            await self.send_all_received_channel.send(msg)
                            if not self.send_all_received_channel_copy:
                                continue  # skip all of the other sends
                        if msg.command == b"w":
                            if self.send_w:
                                await self.send_w.send(msg)
                            elif self.write_w:
                                await self.write_w.write(msg.get_packed())
                        elif msg.command == b"r":
                            if self.send_r:
                                logging.debug(f"Trying to send message to send_r")
                                await self.send_r.send(msg)
                            elif self.write_r:
                                await self.write_r.write(msg.get_packed())
                        elif msg.command == b"s":
                            try:
                                nMissed, payload = self._unpack_received_s_message(msg)
                            except ASCErrorBase as e:
                                if self.ignoreErrors:
                                    logging.error(f"{type(e).__name__}: {e}")
                                    # logging.exception(f"{type(e)}: {e}")
                                else:
                                    raise e
                            else:
                                if self.send_s:
                                    logging.debug(
                                        f"About to send to send_s {(nMissed,payload.decode('ascii','replace'))}"
                                    )
                                    await self.send_s.send((nMissed, payload))
                                elif self.write_s:
                                    line = "{:03n},".format(nMissed).encode() + payload
                                    logging.debug(
                                        f"About to write to write_s {line.decode('ascii','replace')}"
                                    )
                                    await self.write_s.write(line)
                        elif msg.command == b"e":
                            (
                                error_str,
                                error_cause_msg,
                            ) = self._unpack_received_e_message(msg)
                            logging.warning(
                                f'Device sent error message: "{error_str}" about message: {error_cause_msg}'
                            )
                            if error_cause_msg.command == b"w" and self.send_w:
                                await self.send_w.send(msg)
                            elif error_cause_msg.command == b"r" and self.send_r:
                                await self.send_r.send(msg)
                        else:
                            logging.warning(
                                f"Received message with unrecognized command: {msg}"
                            )
        except FileReadError as e:
            logging.debug("FileReadError while reading from serial port")
        except trio.Cancelled as e:
            logging.debug(f"Cancellation happened")
            raise e
        except Exception as e:
            logging.error(f"There as an unhandled exception {type(e)} {e}")
            raise e
        finally:
            ## Closing files causes problems in some tests
            # logging.info("Closing all channels and files")
            # for f in [self.write_w, self.write_r, self.write_s]:
            #    try:
            #        if f:
            #            await f.aclose()
            #    except Exception as e:
            #        logging.exception(e)
            logging.debug("Closing all channels")
            if self.send_all_received_channel:
                await self.send_all_received_channel.aclose()
            if self.send_w:
                await self.send_w.aclose()
            if self.send_r:
                await self.send_r.aclose()
            if self.send_s:
                await self.send_s.aclose()

    async def _receive_message(self) -> Optional[ASC_Message]:
        """
        You usually won't need this, instead use receiver_loop

        fin: file-like object to read from

        uses Circular_Buffer_Bytes to keep track of input within and between invocations of receive_message

        if no frame is received, all members ASC_Message will be None

        """
        frame = await self.frame_from_input_stream()
        if frame is None:
            # logging.debug("received frame is None")
            return None
        logging.debug("received: {!r}".format(frame))
        msg = ASC_Message.unpack(frame)  # type: ignore
        if msg.ascVersion != self.asciiSerialComVersion:
            raise AsciiSerialComVersionMismatchError(
                "Message version: {!r} Expected version: {!r}".format(
                    msg.ascVersion, self.asciiSerialComVersion
                )
            )
        if msg.appVersion != self.appVersion:
            raise ApplicationVersionMismatchError(
                "Message version: {!r} Expected version: {!r}".format(
                    msg.appVersion, self.appVersion
                )
            )
        logging.debug("received: {}".format(msg))
        return msg

    async def frame_from_input_stream(self) -> Optional[Sequence]:
        """
        Reads bytes from file-like object and attempts to identify a message frame.

        returns: frame as bytes; None if no frame found in stream
        """
        try:
            # logging.debug("about to read from fin")
            b = b""
            readfn = self.fin.read
            if self.fin_is_fifo or self.fin_is_char_device:
                b = await self.fin.read(1)
            else:
                b = await self.fin.read()
        except ValueError:
            raise FileReadError
        except IOError:
            raise FileReadError
        else:
            # logging.debug(f"got {len(b)} bytes from fin: {b.decode('ascii','replace')}")
            # if len(b) > 0:
            #     logging.debug(f"got {len(b)} bytes from fin")
            self.buf.push_back(b)
            self.buf.removeFrontTo(b">", inclusive=False)
            if len(self.buf) == 0:
                return None
            iNewline = self.buf.findFirst(b"\n")
            if iNewline is None:
                return None
            logging.debug("have a whole message")
            return self.buf.pop_front(iNewline + 1)

    def _unpack_received_s_message(self, msg: ASC_Message) -> Tuple[int, bytes]:
        """
        Unpacks an s message, dealing with the counter.

        Returns tuple of (payload bytes, number of missed messages)
            where the number of missed messages is determined from the counter
        """
        if len(msg.data) < 3:
            raise BadStreamMsgNumberError(
                f"Message not long enough to contain number and ',' in data '{msg.data.decode('ascii','replace')}'"
            )
        if msg.data[2] != b","[0]:
            raise BadStreamMsgNumberError(
                f"3rd byte must be ',' in data '{msg.data.decode('ascii','replace')}'"
            )
        count_bytes = msg.data[:2]
        count = convert_from_hex(count_bytes)
        last_count = self.receive_stream_frame_counter
        missed_messages = 0
        if not (last_count is None):
            difference = 0
            if count >= last_count:
                difference = count - last_count
            elif count < last_count:
                difference = count + 256 - last_count
            missed_messages = difference - 1
            logging.debug(
                f"count: {count}, last_count: {last_count}, difference: {difference}, missed_messages: {missed_messages}"
            )
        self.receive_stream_frame_counter = count
        payload = msg.data[3:]
        return missed_messages, payload

    def _unpack_received_e_message(self, msg: ASC_Message) -> Tuple[str, ASC_Message]:
        """
        Unpacks an e message.

        Returns tuple of (string description of device error, message that might have caused the
            error with data truncated to 9 bytes)
        """
        try:
            decoded_data = msg.data.decode("ASCII", "replace")
            error_code = int(decoded_data[:2], 16)
            error_message = ERROR_CODE_DICT[error_code]
            result_command = decoded_data[3].encode()
            result_data = msg.data[5:]
            result_msg = ASC_Message(
                msg.ascVersion, msg.appVersion, result_command, result_data
            )
            return error_message, result_msg
        except Exception as e:
            raise EMessageUnpackError(f"{type(e)}: {e}")


def check_register_number(num: Union[int, str, bytes, bytearray]) -> bytes:
    """
    Checks register number passed to read_register/write_register matches format specification

    returns properly formatted content

    raises BadRegisterNumberError if not fomatted correctly or incorrect bit width
    """
    if isinstance(num, int):
        if num < 0:
            raise BadRegisterNumberError(f"register number, {num}, must be positive")
        if num.bit_length() > 16:
            raise BadRegisterNumberError(
                f"register number {num} = 0x{num:X} requires {num.bit_length()} bits which is > 16"
            )
        num = b"%04X" % num
    if isinstance(num, str):
        num = num.encode("ascii")
    if not (isinstance(num, bytes) or isinstance(num, bytearray)):
        raise BadRegisterNumberError(
            f"register number {num} isn't bytes or bytearray type or int is {type(num)}"
        )
    if len(num) < 4:
        num = b"0" * (4 - len(num)) + num
    if len(num) != 4:
        raise BadRegisterNumberError(
            f"register number {num!r} should be 4 bytes, but is {len(num)} bytes"
        )
    if not num.isalnum():
        raise BadRegisterNumberError(
            f"register number must be ASCII letters and numbers not: {num!r}"
        )
    try:
        int(num, 16)
    except:
        raise BadRegisterNumberError(
            f"register number, {num!r},must be convertible to hexadecimal number"
        )
    if int(num, 16).bit_length() > 16:  # in case num is bytes so missed earlier check
        raise BadRegisterNumberError(
            f"register number, {num!r}, requires more than 16 bits"
        )
    return num.upper()


def check_register_content(
    content: Union[int, str, bytes, bytearray], registerBitWidth: int
) -> bytes:
    """
    Checks register content passed to write_register matches format specification and register width

    returns properly formatted content

    raises BadRegisterContentError if not fomatted correctly or incorrect bit width
    """
    registerByteWidth = int(math.ceil(registerBitWidth / 8))
    if isinstance(content, int):
        if content < 0:
            raise BadRegisterContentError(
                "content argument", content, "must be positive"
            )
        if content.bit_length() > registerBitWidth:
            raise BadRegisterContentError(
                f"content argument {content} = 0x{content:X} requires {content.bit_length()} bits which is > registerBitWidth = {registerBitWidth}"
            )
        content = b"%0X" % content
    if isinstance(content, str):
        content = content.encode("ascii")
    if not (isinstance(content, bytes) or isinstance(content, bytearray)):
        raise BadRegisterContentError(
            "content argument", content, "isn't bytes or bytearray type or int"
        )
    if len(content) < registerByteWidth * 2:
        content = b"0" * (registerByteWidth * 2 - len(content)) + content
    if len(content) != registerByteWidth * 2:
        raise BadRegisterContentError(
            "content argument ",
            content,
            "should be len ",
            registerByteWidth * 2,
            ", is len ",
            len(content),
        )
    if not content.isalnum():
        raise BadRegisterContentError(
            "content argument must be ASCII letters and numbers not: ", content
        )
    try:
        int(content, 16)
    except:
        raise BadRegisterContentError(
            "content argument must be convertible to hexadecimal number"
        )
    if (
        int(content, 16).bit_length() > registerBitWidth
    ):  # in case content is bytes so missed earlier check
        raise BadRegisterContentError(
            "content argument", content, "requires more bits than registerBitWidth"
        )
    return content.upper()


def convert_to_hex(num: Union[bytes, bytearray, str, int], N: int = 2) -> bytes:
    """
    Converts integer to hexadecimal number as bytes

    num: integer. If str, bytes, or bytearray just converts to bytes
    N: (optional) amount to zero pad (but will use more if necessary). Default: 2

    returns bytes
    """

    result = None
    if isinstance(num, bytearray):
        result = bytes(num)
    elif isinstance(num, str):
        result = num.encode("ascii")
    elif isinstance(num, bytes):
        result = num
    else:
        formatstr = b"%0" + str(N).encode("ascii") + b"X"
        result = formatstr % (num)
    result = result.upper()
    if len(result) == 0:
        raise ValueError("num is a zero length bytes, not valid hex")
    lendiff = N - len(result)
    if lendiff > 0:
        result = b"0" * lendiff + result
    return result


def convert_from_hex(num: Union[bytes, bytearray, str, int]) -> int:
    if isinstance(num, int):
        return num
    else:
        if len(num) == 0:
            raise ValueError("num is a zero length bytes, can't convert to int")
        return int(num, 16)
