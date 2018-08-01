#!/usr/bin/env python

import socket
import time

import exceptions
import messages

CLIENT_NAME = 'amv'
EXTENDED_PERIOD_OF_TIME = 60
ANIDB_HOST = 'api.anidb.net'
ANIDB_PORT = 9000
TIMEOUT = 30


class UdpClient:
    # pylint: disable=too-many-instance-attributes
    def __init__(self, shutdown_event, verbose, config, file_info_queue):
        self._verbose = verbose
        self._config = config
        self._shutdown_event = shutdown_event
        self._file_info_queue = file_info_queue
        self._socket = None
        self._nr_free_packets = 5
        self._start_time = None
        self._session_id = None

    def register_file_infos(self):
        no_such_file_infos = []
        while True:
            file_info = self._file_info_queue.get()
            if file_info is None or self._shutdown_event.is_set():
                break
            if not self._register_file(file_info):
                no_such_file_infos.append(file_info)

        return no_such_file_infos

    def _print(self, *args):
        if self._verbose:
            print(*args)

    def __enter__(self):
        self._start_time = time.time()
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.bind(('0.0.0.0', self._config['local_port']))
        self._socket.settimeout(TIMEOUT)
        self._login()
        return self

    def __exit__(self, *_):
        self._shutdown_event.set()
        self._logout()

    def _get_delay_and_decrease_counter(self):
        if self._nr_free_packets > 0:
            self._nr_free_packets -= 1
            return 0
        if self._extended_period_of_time():
            return 4

        return 2

    def _extended_period_of_time(self):
        return time.time() - self._start_time > EXTENDED_PERIOD_OF_TIME

    def _send_with_delay(self, datagram):
        self._print("Sending {}".format(datagram))
        delay = self._get_delay_and_decrease_counter()
        time.sleep(delay)
        self._socket.sendto(datagram, (ANIDB_HOST, ANIDB_PORT))

    def _receive(self):
        datagram, _ = self._socket.recvfrom(4096)
        return messages.parse_message(datagram)

    @staticmethod
    def _raise_error(response):
        raise exceptions.AnidbProtocolException(
            'Received unknown response "{number} {string}" in response to login'.format(
                number=response['number'],
                string=response['string']
            ))

    def _login(self):
        self._send_with_delay(messages.auth_message(
            self._config['username'],
            self._config['password']))
        response = self._receive()
        self._print('Received response', response)
        if response['number'] not in [200, 201]:
            self._raise_error(response)
        self._session_id = response['session']

    def _logout(self):
        self._send_with_delay(messages.logout_message())

    # pylint: disable=inconsistent-return-statements
    def _register_file(self, file_info):
        self._print("Registering file {file}".format(file=file_info['path']))
        self._send_with_delay(messages.mylistadd_message(
            size=file_info['size'],
            ed2k=file_info['ed2k'],
            session=self._session_id
        ))
        datagram, _ = self._socket.recvfrom(4096)
        response = messages.parse_message(datagram)
        if response['number'] == 320:
            print("No such file {}".format(file_info['path']))
            return False
        if response['number'] == 310:
            print('File {} already registered'.format(file_info['path']))
            return True
        if response['number'] == 210:
            print('File {} registered successfully'.format(file_info['path']))
            return True

        self._raise_error(response)
