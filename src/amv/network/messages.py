import re
from dataclasses import dataclass
from urllib.parse import urlencode

from ..exceptions import AnidbProtocolException
from ..file_info import FileInfo
from . import codes

PROTOCOL_VERSION = 3
CLIENT_ID = "aregister"
CLIENT_VERSION = 1
MESSAGE_ENCODING = "ascii"


def _create_message(name: str, *parameters: tuple[str, str | int]) -> bytes:
    return f"{name} {urlencode(parameters)}".encode(MESSAGE_ENCODING)


_PASSWORD_PARAMETER = re.compile(rb"(?<=[ &])pass=[^&]*")


def redact(datagram: bytes) -> str:
    """Renders a datagram for printing, with the password in an AUTH message hidden."""
    return str(_PASSWORD_PARAMETER.sub(b"pass=***", datagram))


def auth_message(username: str, password: str) -> bytes:
    return _create_message(
        "AUTH",
        ("user", username),
        ("pass", password),
        ("protover", PROTOCOL_VERSION),
        ("client", CLIENT_ID),
        ("clientver", CLIENT_VERSION),
    )


def mylistadd_message(file_info: FileInfo, session: str, edit: bool = False) -> bytes:
    """With edit, the message updates the file's existing MyList entry instead of adding one."""
    parameters = [
        ("size", file_info.size),
        ("ed2k", file_info.ed2k),
        ("state", 1 if file_info.internal else 2),
        ("viewed", 1 if file_info.watched else 0),
        ("s", session),
    ]
    if file_info.watched:
        parameters.append(("viewdate", int(file_info.view_date)))
    if edit:
        parameters.append(("edit", 1))

    return _create_message("MYLISTADD", *parameters)


def mylist_message(size: int, ed2k: str, session: str) -> bytes:
    return _create_message("MYLIST", ("size", size), ("ed2k", ed2k), ("s", session))


def mylistdel_message(size: int, ed2k: str, session: str) -> bytes:
    return _create_message("MYLISTDEL", ("size", size), ("ed2k", ed2k), ("s", session))


def logout_message() -> bytes:
    return b"LOGOUT"


@dataclass(frozen=True)
class MylistEntry:
    lid: int
    watched: bool
    internal: bool
    view_date: float


# MyList state values from the UDP API: 0 unknown, 1 on HDD, 2 on CD/DVD, 3 deleted, 4 remote.
# amv only distinguishes internal from external, so everything but 2 counts as internal.
_STATE_EXTERNAL = 2


def parse_mylist_entry(data: str) -> MylistEntry:
    """
    Parses the data line of a 221 MYLIST reply:
    lid|fid|eid|aid|gid|date|state|viewdate|storage|source|other|filestate
    """
    fields = data.split("|")
    if len(fields) < 8:
        raise AnidbProtocolException(f'Failed to parse MyList entry: "{data}"')
    view_date = int(fields[7])
    return MylistEntry(
        lid=int(fields[0]),
        watched=view_date != 0,
        internal=int(fields[6]) != _STATE_EXTERNAL,
        view_date=float(view_date),
    )


def parse_message(datagram: bytes) -> dict[str, str | int]:
    parts = datagram.decode(MESSAGE_ENCODING).split(" ", maxsplit=1)
    if len(parts) != 2:
        raise AnidbProtocolException(f'Failed to parse message: "{datagram.decode(MESSAGE_ENCODING)}"')

    number = int(parts[0])
    if number in [codes.LOGIN_ACCEPTED, codes.LOGIN_ACCEPTED_NEW_VERSION]:
        second_parts = parts[1].split(" ", maxsplit=1)
        return {"number": number, "session": second_parts[0], "string": second_parts[1].rstrip()}

    # Replies that carry data put it on the lines after the status line. Every reply ends
    # with a newline, so an empty remainder means there is no data.
    string, _, data = parts[1].partition("\n")
    message: dict[str, str | int] = {"number": number, "string": string.rstrip()}
    if data.strip():
        message["data"] = data.rstrip()
    return message
