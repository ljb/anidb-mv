from urllib.parse import urlencode

from . import codes
from ..exceptions import AnidbProtocolException

PROTOCOL_VERSION = 3
CLIENT_ID = 'aregister'
CLIENT_VERSION = 2
MESSAGE_ENCODING = 'ascii'


def _create_message(name, *parameters):
    return f'{name} {urlencode(parameters)}'.encode(MESSAGE_ENCODING)


def auth_message(username, password):
    return _create_message(
        'AUTH',
        ('user', username),
        ('pass', password),
        ('protover', PROTOCOL_VERSION),
        ('client', CLIENT_ID),
        ('clientver', CLIENT_VERSION),
    )


def encrypt(username):
    return _create_message(
        'ENCRYPT',
        ('user', username),
        ('type', 1),
    )


def mylistadd_message(size, ed2k, session):
    return _create_message(
        'MYLISTADD',
        ('size', size),
        ('ed2k', ed2k),
        ('state', 1),
        ('viewed', 1),
        ('s', session)
    )


def logout_message():
    return b'LOGOUT'


def parse_message(datagram):
    parts = datagram.decode(MESSAGE_ENCODING).split(' ', maxsplit=1)
    if len(parts) != 2:
        raise AnidbProtocolException(f'Failed to parse message: "{datagram.decode(MESSAGE_ENCODING)}"')

    number = int(parts[0])
    if number in [codes.LOGIN_ACCEPTED, codes.LOGIN_ACCEPTED_NEW_VERSION]:
        second_parts = parts[1].split(' ', maxsplit=1)
        return {'number': number, 'session': second_parts[0], 'string': second_parts[1].rstrip()}

    return {'number': number, 'string': parts[1].rstrip()}
