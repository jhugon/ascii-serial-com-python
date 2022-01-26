from typing import Optional
from pathlib import Path
import logging
from functools import partial
from shutil import get_terminal_size
import math

import typer
import trio
import trio_util  # type: ignore

from ..host import Host
from ..utilities import Tracer
from ..tty_utils import setup_tty
from ..errors import *

DEFAULT_TIMEOUT = 5
DEFAULT_REGISTER_BITS = 8

SERIAL = None
SERIAL_SEND = None
VERBOSE = False
BAUD = None


async def run_send_message(timeout, command, data):
    fin_name = SERIAL
    fout_name = SERIAL
    if SERIAL_SEND:
        fout_name = SERIAL_SEND
    logging.debug(f"fin_name: {fin_name}")
    logging.debug(f"fout_name: {fout_name}")
    result = None
    if fin_name.is_char_device():
        setup_tty(fin_name, BAUD)
    with trio.move_on_after(timeout) as cancel_scope:
        async with trio.open_nursery() as nursery:
            async with await trio.open_file(fin_name, "br") as fin:
                async with await trio.open_file(fout_name, "bw") as fout:
                    logging.debug("Opened files and nursery")
                    host = Host(
                        nursery, fin, fout, DEFAULT_REGISTER_BITS, ignoreErrors=True
                    )
                    await host.send_message(command, data)
    return result


async def run_read(timeout, reg_num, reg_bits):
    fin_name = SERIAL
    fout_name = SERIAL
    if SERIAL_SEND:
        fout_name = SERIAL_SEND
    logging.debug(f"fin_name: {fin_name}")
    logging.debug(f"fout_name: {fout_name}")
    result = None
    if fin_name.is_char_device():
        setup_tty(fin_name, BAUD)
    with trio.move_on_after(timeout) as cancel_scope:
        async with trio.open_nursery() as nursery:
            async with await trio.open_file(fin_name, "br") as fin:
                async with await trio.open_file(fout_name, "bw") as fout:
                    logging.debug("Opened files and nursery")
                    host = Host(nursery, fin, fout, reg_bits, ignoreErrors=True)
                    result = await host.read_register(reg_num)
    return result


async def run_write(timeout, reg_num, reg_val, reg_bits):
    fin_name = SERIAL
    fout_name = SERIAL
    if SERIAL_SEND:
        fout_name = SERIAL_SEND
    logging.debug(f"fin_name: {fin_name}")
    logging.debug(f"fout_name: {fout_name}")
    result = False
    if fin_name.is_char_device():
        setup_tty(fin_name, BAUD)
    with trio.move_on_after(timeout) as cancel_scope:
        async with trio.open_nursery() as nursery:
            async with await trio.open_file(fin_name, "br") as fin:
                async with await trio.open_file(fout_name, "bw") as fout:
                    logging.debug("Opened files and nursery")
                    host = Host(nursery, fin, fout, reg_bits, ignoreErrors=True)
                    await host.write_register(reg_num, reg_val)
                result = True
    return result


async def forward_received_messages_to_print(
    ch,
    outfile,
    stop_messages,
    stop_bytes,
    stop_seperators,
    stop_event,
    split_seperators_newlines,
    decode_hex_to_dec,
):
    logging.debug("Started")
    totalMessages = 0
    totalBytes = 0
    totalSeperators = 0
    totalMissedMessages = 0
    f = None
    try:
        if outfile:
            f = await trio.open_file(outfile, "w")
        while True:
            try:
                nMissed, payload = await ch.receive()
            except trio.EndOfChannel:
                break
            else:
                out_text = ""
                totalMessages += 1
                totalBytes += len(payload)
                totalSeperators += payload.count(b" ")
                msg_text = payload.decode("ascii", "replace")
                if split_seperators_newlines or decode_hex_to_dec:
                    for x in msg_text.split(" "):
                        if decode_hex_to_dec:
                            out_text += str(int(msg_text, 16)) + "\n"
                        else:
                            out_text += msg_text + "\n"
                else:
                    out_text += msg_text + "\n"
                if f:
                    await f.write(out_text)
                else:
                    typer.echo(out_text, nl=False)
                if stop_messages and totalMessages >= stop_messages:
                    stop_event.set()
                    break
                elif stop_bytes and totalBytes >= stop_bytes:
                    stop_event.set()
                    break
                elif stop_seperators and totalSeperators >= stop_seperators:
                    stop_event.set()
                    break
            finally:
                if totalMissedMessages > 0:
                    logging.warning(
                        f"Receiver missed a total of {totalMissedMessages} messages"
                    )
    except Exception as e:
        raise e
    finally:
        if f:
            await f.aclose()


async def run_stream(
    timeout,
    outfile,
    stop_messages,
    stop_bytes,
    stop_seperators,
    split_seperators_newlines,
    decode_hex_to_dec,
):
    fin_name = SERIAL
    fout_name = SERIAL
    if SERIAL_SEND:
        fout_name = SERIAL_SEND
    logging.debug(f"fin_name: {fin_name}")
    logging.debug(f"fout_name: {fout_name}")
    logging.debug(f"timeout: {timeout}")
    send_ch, recv_ch = trio.open_memory_channel(0)
    if timeout is None:
        timeout = float("inf")
    timeout_cancel = timeout + 0.5
    if fin_name.is_char_device():
        setup_tty(fin_name, BAUD)
    with trio.move_on_after(timeout_cancel) as cancel_scope:
        async with trio.open_nursery() as nursery:
            logging.debug(f"About to open files")
            async with await trio.open_file(fin_name, "br") as fin:
                async with await trio.open_file(fout_name, "bw") as fout:
                    try:
                        logging.debug(f"Files open!")
                        host = Host(nursery, fin, fout, 8, ignoreErrors=True)
                        stop_event = trio.Event()
                        nursery.start_soon(
                            forward_received_messages_to_print,
                            recv_ch,
                            outfile,
                            stop_messages,
                            stop_bytes,
                            stop_seperators,
                            stop_event,
                            split_seperators_newlines,
                            decode_hex_to_dec,
                        )
                        host.forward_received_s_messages_to(send_ch)
                        await host.start_streaming()
                        await trio_util.wait_any(
                            partial(trio.sleep, timeout), stop_event.wait
                        )
                    except BaseException as e:
                        logging.debug(
                            f"Caught exception while receiving stream: {e.__class__.__name__} {e}"
                        )
                        if not isinstance(e, KeyboardInterrupt):
                            raise e
                    finally:
                        await host.stop_streaming()


async def run_stream_text_graph(
    minimum_value, maximum_value, timeout, stop_messages, stop_bytes, stop_lines,
):
    fin_name = SERIAL
    fout_name = SERIAL
    if SERIAL_SEND:
        fout_name = SERIAL_SEND
    logging.debug(f"fin_name: {fin_name}")
    logging.debug(f"fout_name: {fout_name}")
    logging.debug(f"timeout: {timeout}")
    send_ch, recv_ch = trio.open_memory_channel(0)
    if timeout is None:
        timeout = float("inf")
    timeout_cancel = timeout + 0.5
    if fin_name.is_char_device():
        setup_tty(fin_name, BAUD)
    with trio.move_on_after(timeout_cancel) as cancel_scope:
        async with trio.open_nursery() as nursery:
            logging.debug(f"About to open files")
            async with await trio.open_file(fin_name, "br") as fin:
                async with await trio.open_file(fout_name, "bw") as fout:
                    try:
                        logging.debug(f"Files open!")
                        host = Host(nursery, fin, fout, 8, ignoreErrors=True)
                        stop_event = trio.Event()
                        nursery.start_soon(
                            forward_received_messages_to_text_graph,
                            recv_ch,
                            minimum_value,
                            maximum_value,
                            stop_messages,
                            stop_bytes,
                            stop_lines,
                            stop_event,
                        )
                        host.forward_received_s_messages_to(send_ch)
                        await host.start_streaming()
                        await trio_util.wait_any(
                            partial(trio.sleep, timeout), stop_event.wait
                        )
                    except BaseException as e:
                        logging.debug(
                            f"Caught exception while receiving stream: {e.__class__.__name__} {e}"
                        )
                        if not isinstance(e, KeyboardInterrupt):
                            raise e
                    finally:
                        await host.stop_streaming()


async def forward_received_messages_to_text_graph(
    ch, minimum_value, maximum_value, stop_messages, stop_bytes, stop_lines, stop_event,
):
    logging.debug("Started")
    totalMessages = 0
    totalBytes = 0
    totalLines = 0
    totalMissedMessages = 0
    value_span = maximum_value - minimum_value
    minimum_value_str_width = len(str(minimum_value))
    maximum_value_str_width = len(str(maximum_value))
    term_width = get_terminal_size()[0]
    space_width = term_width - minimum_value_str_width - maximum_value_str_width
    typer.echo("=" * term_width)
    typer.echo(str(minimum_value) + " " * space_width + str(maximum_value))
    typer.echo("-" * term_width)
    try:
        while True:
            try:
                nMissed, payload = await ch.receive()
            except trio.EndOfChannel:
                break
            else:
                out_text = ""
                totalMessages += 1
                totalBytes += len(payload)
                msg_text = payload.decode("ascii", "replace")
                logging.debug(f"term_width: {term_width} value_span: {value_span}")
                for x in msg_text.split(" "):
                    totalLines += 1
                    msg_value = int(msg_text, 16)
                    pos = (msg_value - minimum_value) / value_span * term_width
                    pos_int = int(math.ceil(pos))
                    pos_int = max(pos_int, 0)
                    pos_int = min(pos_int, term_width - 1)
                    logging.debug(f"value: {msg_value} pos: {pos} pos_int: {pos_int}")
                    out_text += " " * pos_int + "o\n"
                typer.echo(out_text, nl=False)
                if stop_messages and totalMessages >= stop_messages:
                    stop_event.set()
                    break
                elif stop_bytes and totalBytes >= stop_bytes:
                    stop_event.set()
                    break
                elif stop_lines and totalLines >= stop_lines:
                    stop_event.set()
                    break
            finally:
                if totalMissedMessages > 0:
                    logging.warning(
                        f"Receiver missed a total of {totalMissedMessages} messages"
                    )
        term_width = get_terminal_size()[0]
        space_width = term_width - minimum_value_str_width - maximum_value_str_width
        typer.echo("-" * term_width)
        typer.echo(str(minimum_value) + " " * space_width + str(maximum_value))
        typer.echo("=" * term_width)
    except Exception as e:
        raise e


app = typer.Typer()


@app.callback()
def callback(
    serial: Path = typer.Argument(
        ...,
        help="Filename of the serial device",
        exists=True,
        writable=True,
        readable=True,
    ),
    serial_send: Optional[Path] = typer.Option(
        None,
        help="Filename of the serial device to write to. If present, SERIAL is only read from",
        exists=True,
        writable=True,
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
    baud: int = typer.Option(9600, "--baud", "-b", help="Serial baud rate",),
) -> None:
    """
    Communicate with a device with ASCII-Serial-Com

    There are two levels of options: those before the serial device and those after. They are seperate groups.
    """
    global SERIAL
    global SERIAL_SEND
    global VERBOSE
    global BAUD
    SERIAL = serial
    SERIAL_SEND = serial_send
    VERBOSE = verbose
    BAUD = baud
    level = logging.WARNING
    if verbose:
        level = logging.DEBUG
    logging.basicConfig(
        level=level, format="%(levelname)s L%(lineno)d %(funcName)s: %(message)s",
    )
    logging.debug(f"SERIAL: {SERIAL}, SERIAL_SEND: {SERIAL_SEND}, VERBOSE: {VERBOSE}")


@app.command()
def send_message(
    command: str = typer.Argument(..., help="command, should be a lowercase letter"),
    data: str = typer.Argument(..., help="data string"),
    timeout: float = typer.Option(
        DEFAULT_TIMEOUT, "--timeout", "-t", help="Timeout in seconds", min=0.0
    ),
) -> None:
    """
    Low-level message send command
    """
    if SERIAL_SEND:
        typer.echo(
            f"Sending command '{command}' data '{data}' on send device {SERIAL_SEND} and read device {SERIAL}"
        )
    else:
        typer.echo(f"Sending command '{command}' data '{data}' on device {SERIAL}")
    try:
        trio.run(
            run_send_message, timeout, command.encode("ASCII"), data.encode("ASCII")
        )
    except Exception as e:
        typer.echo(f"Error: unhandled exception: {e.__class__.__name__}: {e}", err=True)


@app.command()
def read(
    register_number: int = typer.Argument(..., help="Register number", min=0),
    timeout: float = typer.Option(
        DEFAULT_TIMEOUT, "--timeout", "-t", help="Timeout in seconds", min=0.0
    ),
    register_bits: int = typer.Option(
        DEFAULT_REGISTER_BITS,
        "--register-bits",
        "-b",
        help="Register bit width (typically 8,16,32)",
        min=1,
    ),
) -> None:
    """
    Read a register
    """
    if SERIAL_SEND:
        typer.echo(
            f"Reading register {register_number} on send device {SERIAL_SEND} and read device {SERIAL}"
        )
    else:
        typer.echo(f"Reading register {register_number} on device {SERIAL}")
    try:
        result = trio.run(run_read, timeout, register_number, register_bits)
        if result is None:
            typer.echo(
                f"Error: read reply not received and timeout expired after {timeout} s",
                err=True,
            )
        else:
            if register_bits == 8:
                typer.echo(
                    f'Register {register_number} value is {result:3} = 0x{result:02x} = 0b{result:08b} = UTF-8: "{chr(result)}"'
                )
            else:
                typer.echo(
                    f"Register {register_number} value is {result:10} = 0x{result:08x} = 0b{result:032b}"
                )
    except Exception as e:
        typer.echo(f"Error: unhandled exception: {e.__class__.__name__}: {e}", err=True)


@app.command()
def write(
    register_number: int = typer.Argument(..., help="Register number", min=0),
    register_value: str = typer.Argument(
        ...,
        help="Register value to write to device in decimal, hex, octal, or binary with prefix (15,0xF,0o17,0b1111)",
    ),
    timeout: float = typer.Option(
        DEFAULT_TIMEOUT, "--timeout", "-t", help="Timeout in seconds", min=0.0
    ),
    register_bits: int = typer.Option(
        DEFAULT_REGISTER_BITS,
        "--register-bits",
        "-b",
        help="Register bit width (typically 8,16,32)",
        min=1,
    ),
) -> None:
    """
    Write to a register
    """
    register_value_int = None
    try:
        register_value_int = int(register_value, 0)
    except ValueError:
        typer.echo(
            f'Error: couldn\'t convert REGISTER_VALUE "{register_value}" to int',
            err=True,
        )
        raise typer.Exit(code=1)
    if SERIAL_SEND:
        typer.echo(
            f"Writing {register_value_int} (0x{register_value_int:02x}) to register {register_number} on send device {SERIAL_SEND} and read device {SERIAL}"
        )
    else:
        typer.echo(
            f"Writing {register_value_int} (0x{register_value_int:02x}) to register {register_number} on device {SERIAL}"
        )
    try:
        result = trio.run(
            run_write, timeout, register_number, register_value_int, register_bits
        )
        if result:
            typer.echo(f"Success")
        else:
            typer.echo(
                f"Error: write reply not received and timeout expired after {timeout} s",
                err=True,
            )
    except Exception as e:
        typer.echo(f"Error: unhandled exception: {e.__class__.__name__}: {e}", err=True)


@app.command()
def stream(
    outfile: Optional[Path] = typer.Option(
        None,
        help="Filename to write received data to instead of printing to stdout",
        writable=True,
    ),
    stop_seconds: Optional[float] = typer.Option(
        None, "--stop-seconds", "-t", help="Stop after this many seconds"
    ),
    stop_messages: Optional[int] = typer.Option(
        None,
        "--stop-messages",
        "-m",
        help="Stop after this many messages have been received",
    ),
    stop_bytes: Optional[int] = typer.Option(
        None, "--stop-bytes", "-b", help="Stop after this many bytes have been received"
    ),
    stop_datasep: Optional[int] = typer.Option(
        None,
        "--stop-datasep",
        "-d",
        help="Stop after this many data-seperater characters have been received (spaces in the data field)",
    ),
    split_seperators_newlines: Optional[bool] = typer.Option(
        False,
        "--split_seperators_newlines",
        "-n",
        help="In addition to a newline for every message, there is a newline for every seperator",
    ),
    decode_hex_to_dec: Optional[bool] = typer.Option(
        False,
        "--decode-hex-to-dec",
        "-x",
        help="Convert each message (or seperated chunk of data) from hexadecimal to decimal integer. Implies --split-seperators-newlines",
    ),
) -> None:
    """
    Either prints message data to the screen, one message per line, or writes the same to OUTFILE

    With all the stop arguments and hitting Ctrl-C: whichever happens first will stop streaming.
    """
    if SERIAL_SEND:
        typer.echo(
            f"Receive streaming data with send device {SERIAL_SEND} and read device {SERIAL}"
        )
    else:
        typer.echo(f"Receive streaming data with device {SERIAL}")
    try:
        trio.run(
            run_stream,
            stop_seconds,
            outfile,
            stop_messages,
            stop_bytes,
            stop_datasep,
            split_seperators_newlines,
            decode_hex_to_dec,
        )  # ,instruments=[Tracer()])
    except Exception as e:
        typer.echo(f"Error: unhandled exception: {e.__class__.__name__}: {e}", err=True)


@app.command()
def stream_text_graph(
    minimum: int = typer.Argument(
        ..., help="Minimum expected value for setting graph limits.", min=0
    ),
    maximum: int = typer.Argument(
        ..., help="Maximum expected value for setting graph limits.", min=1
    ),
    stop_seconds: Optional[float] = typer.Option(
        None, "--stop-seconds", "-t", help="Stop after this many seconds"
    ),
    stop_messages: Optional[int] = typer.Option(
        None,
        "--stop-messages",
        "-m",
        help="Stop after this many messages have been received",
    ),
    stop_bytes: Optional[int] = typer.Option(
        None, "--stop-bytes", "-b", help="Stop after this many bytes have been received"
    ),
    stop_lines: Optional[int] = typer.Option(
        None,
        "--stop-lines",
        "-l",
        help="Stop after this many lines (could differ from --stop-messages due to data seperators within messages)",
    ),
) -> None:
    """
    Converts each message (or part of one due to seperators) into an int and then plots them in the terminal in real time.
    Each sample (or part of one) gets a new line and a symbol is placed the appropriate position between MINIMUM and MAXIMUM.

    With all the stop arguments and hitting Ctrl-C: whichever happens first will stop streaming.
    """
    if SERIAL_SEND:
        typer.echo(
            f"Receive streaming data with send device {SERIAL_SEND} and read device {SERIAL}"
        )
    else:
        typer.echo(f"Receive streaming data with device {SERIAL}")
    try:
        trio.run(
            run_stream_text_graph,
            minimum,
            maximum,
            stop_seconds,
            stop_messages,
            stop_bytes,
            stop_lines,
        )  # ,instruments=[Tracer()])
    except Exception as e:
        typer.echo(f"Error: unhandled exception: {e.__class__.__name__}: {e}", err=True)


@app.command()
def start_streaming(
    timeout: float = typer.Option(
        DEFAULT_TIMEOUT, "--timeout", "-t", help="Timeout in seconds", min=0.0
    ),
) -> None:
    """
    Low-level send device start streaming command
    """
    command = "n"
    data = ""
    if SERIAL_SEND:
        typer.echo(
            f"Sending command '{command}' data '{data}' on send device {SERIAL_SEND} and read device {SERIAL}"
        )
    else:
        typer.echo(f"Sending command '{command}' data '{data}' on device {SERIAL}")
    try:
        trio.run(
            run_send_message, timeout, command.encode("ASCII"), data.encode("ASCII")
        )
    except Exception as e:
        typer.echo(f"Error: unhandled exception: {e.__class__.__name__}: {e}", err=True)


@app.command()
def stop_streaming(
    timeout: float = typer.Option(
        DEFAULT_TIMEOUT, "--timeout", "-t", help="Timeout in seconds", min=0.0
    ),
) -> None:
    """
    Low-level send device stop streaming command
    """
    command = "f"
    data = ""
    if SERIAL_SEND:
        typer.echo(
            f"Sending command '{command}' data '{data}' on send device {SERIAL_SEND} and read device {SERIAL}"
        )
    else:
        typer.echo(f"Sending command '{command}' data '{data}' on device {SERIAL}")
    try:
        trio.run(
            run_send_message, timeout, command.encode("ASCII"), data.encode("ASCII")
        )
    except Exception as e:
        typer.echo(f"Error: unhandled exception: {e.__class__.__name__}: {e}", err=True)


@app.command()
def noop(
    timeout: float = typer.Option(
        DEFAULT_TIMEOUT, "--timeout", "-t", help="Timeout in seconds", min=0.0
    ),
) -> None:
    """
    Low-level send no-op command
    """
    command = "z"
    data = ""
    if SERIAL_SEND:
        typer.echo(
            f"Sending command '{command}' data '{data}' on send device {SERIAL_SEND} and read device {SERIAL}"
        )
    else:
        typer.echo(f"Sending command '{command}' data '{data}' on device {SERIAL}")
    try:
        trio.run(
            run_send_message, timeout, command.encode("ASCII"), data.encode("ASCII")
        )
    except Exception as e:
        typer.echo(f"Error: unhandled exception: {e.__class__.__name__}: {e}", err=True)


@app.command()
def dump(
    timeout: float = typer.Option(
        DEFAULT_TIMEOUT, "--timeout", "-t", help="Timeout in seconds", min=0.0
    ),
    register_bits: int = typer.Option(
        DEFAULT_REGISTER_BITS,
        "--register-bits",
        "-b",
        help="Register bit width (typically 8,16,32)",
        min=1,
    ),
) -> None:
    """
    Read registers starting from 0 until receive "register number out of bounds" error from device
    """
    if SERIAL_SEND:
        typer.echo(
            f"Dumping registers on send device {SERIAL_SEND} and read device {SERIAL}"
        )
    else:
        typer.echo(f"Dumping registers on device {SERIAL}")

    logging.basicConfig(
        level=logging.ERROR,
        format="%(levelname)s L%(lineno)d %(funcName)s: %(message)s",
    )
    register_number = 0
    while True:
        try:
            result = trio.run(run_read, timeout, register_number, register_bits)
            if result is None:
                typer.echo(
                    f"Error: read reply not received and timeout expired after {timeout} s",
                    err=True,
                )
                break
            else:
                if register_bits == 8:
                    typer.echo(
                        f"{register_number}: {result:3} = 0x{result:02x} = 0b{result:08b}"
                    )
                else:
                    typer.echo(
                        f"{register_number}: {result:10} = 0x{result:08x} = 0b{result:032b}"
                    )
                register_number += 1
        except DeviceError as e:
            if not ("Register number out of bounds" in str(e)):
                typer.echo(
                    f"Error: unhandled exception: {e.__class__.__name__}: {e}", err=True
                )
            break
        except Exception as e:
            typer.echo(
                f"Error: unhandled exception: {e.__class__.__name__}: {e}", err=True
            )
            break


def main():
    app()
