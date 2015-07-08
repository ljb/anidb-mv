#!/usr/bin/env python

import os
import signal
import socket
import time
from threading import Event, Thread
from queue import Queue

from hashing import ed2k_of_path
import messages
import exceptions

CLIENT_NAME = 'amv'
EXTENDED_PERIOD_OF_TIME = 60
ANIDB_HOST = 'api.anidb.net'
ANIDB_PORT = 9000
TIMEOUT = 30

class UdpClient(object):
    def __init__(self, config, shutdown_event, file_info_queue):
        self._config = config
        self._shutdown_event = shutdown_event
        self._file_info_queue = file_info_queue
        self._socket = None
        self._nr_free_packets = 5
        self._start_time = None
        self._session_id = None

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
        elif self._extended_period_of_time():
            return 4
        else:
            return 2

    def _extended_period_of_time(self):
        return time.time() - self._start_time > EXTENDED_PERIOD_OF_TIME

    def _send_with_delay(self, datagram):
        print("Sending {}".format(datagram))
        delay = self._get_delay_and_decrease_counter()
        time.sleep(delay)
        self._socket.sendto(datagram, (ANIDB_HOST, ANIDB_PORT))

    def _receive(self):
        datagram, _ = self._socket.recvfrom(4096)
        print(datagram)
        return messages.parse_message(datagram)

    @staticmethod
    def _raise_error(response):
        msg = 'Received unknown response "{number} {string}" in response to login'.format(
            number=response['number'],
            string=response['string']
        )
        raise exceptions.AnidbProtocolException(msg)

    def _login(self):
        self._send_with_delay(messages.auth_message(
            self._config['username'],
            self._config['password']))
        response = self._receive()
        print('Received response', response)
        if response['number'] not in [200, 201]:
            self._raise_error(response)
        self._session_id = response['session']

    def _logout(self):
        self._send_with_delay(messages.logout())

    def register_file(self, file_info):
        print("Registering file {file}".format(file=file_info['path']))
        self._send_with_delay(messages.mylistadd(
            size=file_info['size'],
            ed2k=file_info['ed2k'],
            session=self._session_id
        ))
        datagram, _ = self._socket.recvfrom(4096)
        response = messages.parse_message(datagram)
        if response['number'] == 320:
            print("No such file")
            return False
        elif response['number'] == 310:
            print('File {} already registered'.format(file_info['fname']))
            return True
        elif response['number'] == 210:
            print('File {} registered successfully'.format(file_info['path']))
            return True
        else:
            self._raise_error(response)

    def register_files(self):
        no_such_file_infos = []
        while True:
            file_info = self._file_info_queue.get()
            if file_info is None or self._shutdown_event.is_set():
                return
            if not self.register_file(file_info):
                no_such_file_infos.append(file_info)

        self._logout()
        return no_such_file_infos

def process_files(shutdown_event, file_info_queue, files):
    try:
        for fname in files:
            if shutdown_event.is_set():
                break

            print("Processing file {}".format(os.path.basename(fname)))
            file_info_queue.put({
                'path': fname,
                'size': os.path.getsize(fname),
                'ed2k': ed2k_of_path(fname)
            })
            print("Done processing file")

        file_info_queue.put(None)
    except: #pylint: disable=bare-except
        print("Hej")

def register_files(config, files):
    shutdown_event = Event()
    file_info_queue = Queue()

    def signal_handler(*_):
        shutdown_event.set()
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    Thread(target=process_files, args=(shutdown_event, file_info_queue, files)).start()
    with UdpClient(config, shutdown_event, file_info_queue) as client:
        return client.register_files()
