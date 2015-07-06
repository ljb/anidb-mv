from exceptions import AnidbProtocolException

def _create_message(name, *parameters):
    return '{name} {parameters}'.format(
        name=name,
        parameters='&'.join('{key}={value}'.format(
            key=key,
            value=value
        ) for key, value in parameters)
    ).encode('ascii')

def auth_message(username, password):
    return _create_message(
        'AUTH',
        ('user', username),
        ('pass', password),
        ('protover', 3),
        ('client', 'aregister'),
        ('clientver', 1),
    )

def mylistadd(size, ed2k, session):
    return _create_message(
        'MYLISTADD',
        ('size', size),
        ('ed2k', ed2k),
        ('state', 1),
        ('viewed', 1),
        ('s', session)
    )

def logout():
    return b'LOGOUT'

def parse_message(datagram):
    parts = datagram.decode('ascii').split(' ', maxsplit=1)
    if len(parts) != 2:
        raise AnidbProtocolException('Failed to parse message: "{datagram}"'.format(
            datagram=datagram.decode('ascii')
        ))

    number = int(parts[0])
    if number in [200, 201]:
        second_parts = parts[1].split(' ', maxsplit=1)
        return {'number': number, 'session': second_parts[0], 'string': second_parts[1].rstrip()}
    else:
        return {'number': number, 'string': parts[1].rstrip()}
