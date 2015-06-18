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
    return _create_message('AUTH', ('user', username), ('pass', password))

def mylistadd(size, ed2k):
    return _create_message('MYLISTADD', ('size', size), ('ed2k', ed2k))

def logout():
    return b'LOGOUT'

def parse_message(datagram):
    parts = datagram.decode('ascii').split(' ', maxsplit=1)
    if len(parts) != 2:
        raise AnidbProtocolException('Failed to parse message: "{datagram}"'.format(
            datagram=datagram.decode('ascii')
        ))

    return {'number': int(parts[0]), 'string': parts[1]}
