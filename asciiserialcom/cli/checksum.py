from typing import Optional
from pathlib import Path
import logging
from functools import partial

import typer
import trio
import trio_util  # type: ignore

from ..message import ASC_Message
from ..errors import *

app = typer.Typer()


@app.command()
def compute_checksum(
    message: str = typer.Argument(
        ..., help='Message from > to . not including checksum. Example: ">00r001F."',
    ),
) -> None:
    """
    Computes and prints the checksum for the given message
    """
    message_bytes = message.encode("ASCII", "replace")
    try:
        checksum = ASC_Message.compute_checksum(message_bytes)
    except MalformedFrameError as e:
        typer.echo(f"Couldn't decode message: {e}")
        raise typer.Abort()
    whole_message = message_bytes + checksum + b"\n"
    typer.echo(checksum.decode("ASCII", "replace"))
    typer.echo(whole_message.decode("ASCII", "replace")[:-1] + "\\n")
    try:
        message_obj = ASC_Message.unpack(whole_message)
    except Exception as e:
        typer.echo("Couldn't decode message, there may be something wrong with it")
        print(type(e))
        print(e)


def main():
    logging.basicConfig(
        # filename="test_hostiiSerialCom.log",
        # level=logging.INFO,
        # level=logging.DEBUG,
        format="%(levelname)s L%(lineno)d %(funcName)s: %(message)s",
    )

    app()
