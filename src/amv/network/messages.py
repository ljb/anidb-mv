from urllib.parse import urlencode

from . import codes
from ..exceptions import AnidbProtocolException

PROTOCOL_VERSION = 3
CLIENT_ID = 'aregister'
CLIENT_VERSION = 1
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


def mylistadd_message(file_info, session):
    parameters = [
        ('size', file_info['size']),
        ('ed2k', file_info['ed2k']),
        ('state', 1 if file_info['internal'] else 2),
        ('viewed', 1 if file_info['watched'] else 0),
        ('s', session),
    ]
    if file_info['watched']:
        parameters.append(('viewdate', int(file_info['view_date'])))

    return _create_message('MYLISTADD', *parameters)


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
