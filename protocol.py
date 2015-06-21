#!/usr/bin/env python

import os
import time
import messages
from exceptions import AnidbProtocolException
from hashing import ed2k_of_path

from twisted.internet.protocol import DatagramProtocol
from twisted.internet import reactor
from twisted.protocols.policies import TimeoutMixin
from twisted.internet.defer import DeferredQueue, inlineCallbacks

EXTENDED_PERIOD_OF_TIME = 30
#ANIDB_HOST = 'api.anidb.net'
ANIDB_HOST = 'localhost'
ANIDB_PORT = 9000
TIMEOUT = 120

#pylint: disable=no-member
class AnidbClientProtocol(DatagramProtocol, TimeoutMixin):
    def __init__(self, username, password):
        self._username = username
        self._password = password
        self._nr_free_packets = 5
        self._start_time = None
        self._logged_in = False
        self.setTimeout(TIMEOUT)

    def _get_delay_and_decrease_counter(self):
        delay = 30 if self._nr_free_packets <= 0 or self._extended_period_of_time() else 0
        self._nr_free_packets -= 1
        print(delay)
        return delay

    def _extended_period_of_time(self):
        return time.time() - self._start_time > EXTENDED_PERIOD_OF_TIME

    def _verify_logged_in_response(self, response):
        if response['number'] not in [200, 201]:
            self.raise_error(response)
        self._logged_in = True

    @inlineCallbacks
    def _shutdown(self):
        yield self.transport.loseConnection()
        reactor.stop()

    @inlineCallbacks
    def timeoutConnection(self):
        print("Timed out waiting for reply")
        yield self._shutdown()

    @inlineCallbacks
    def stopProtocol(self):
        print("Shuting down")
        yield self._shutdown()

    @inlineCallbacks
    def startProtocol(self):
        print("Start protocol")
        self._start_time = time.time()
        ip_address = yield reactor.resolve(ANIDB_HOST)
        print(ip_address)
        print(ANIDB_PORT)
        self.transport.connect(ip_address, ANIDB_PORT)
        yield self.send_with_delay(messages.auth_message(self._username, self._password))

    @inlineCallbacks
    def datagramReceived(self, datagram, _):
        print("Datagram received")
        self.resetTimeout()
        try:
            response = messages.parse_message(datagram)
            if self._logged_in:
                self._verify_logged_in_response(response)
            else:
                yield self.handle_response(response)
        except AnidbProtocolException as exception:
            print(exception)
            yield self._shutdown()

    @inlineCallbacks
    def send_with_delay(self, datagram):
        print(datagram)
        yield reactor.callLater(
            self._get_delay_and_decrease_counter(),
            self.transport.write,
            datagram
        )

    @staticmethod
    def raise_error(response):
        msg = 'Received unknown response "{number} {string}" in response to login'.format(
            number=response['number'],
            string=response['string']
        )
        raise AnidbProtocolException(msg)

    @inlineCallbacks
    def log_out(self):
        if self._logged_in:
            print("Logging out")
            yield self.send_with_delay(messages.logout())
        print("Shutting down")
        yield self._shutdown()

    def handle_response(self, message):
        raise NotImplementedError()

class AmvProtocol(AnidbClientProtocol):
    def __init__(self, username, password, file_info_queue):
        super().__init__(username, password)
        self.no_such_file_infos = []
        self._last_sent_file_info = None
        self._file_info_queue = file_info_queue

    def verify_file_registered_response(self, response):
        if not self._last_sent_file_info:
            self.raise_error(response)
        elif response['number'] == 320:
            self.no_such_file_infos.append(self._last_sent_file_info)
        elif response['number'] == 310:
            print('File {} already registered'.format(self._last_sent_file_info['fname']))
        elif response['number'] == 210:
            print('File {} registered successfully')
        else:
            self.raise_error(response)

    @inlineCallbacks
    def handle_response(self, response):
        self.verify_file_registered_response(response)

        file_info = yield self._file_info_queue.get()
        if file_info is None:
            yield self._log_out()
        else:
            print("Registering file {file}".format(file=file_info['path']))
            yield self.send_with_delay(messages.mylistadd(
                size=file_info['size'],
                ed2k=file_info['ed2k']
            ))
            self._last_sent_file_info = file_info

def process_files(file_info_queue, files):
    for fname in files:
        print("Processing file {}".format(fname))
        reactor.callFromThread(file_info_queue.put, {
            'path': fname,
            'size': os.path.getsize(fname),
            'ed2k': ed2k_of_path(fname)
        })

        reactor.callFromThread(file_info_queue.put, None)

def register_files(username, password, files):
    file_info_queue = DeferredQueue()
    client = AmvProtocol(username, password, file_info_queue)
    reactor.callInThread(process_files, file_info_queue, files)
    reactor.listenUDP(0, client)
    reactor.run()

    return client.no_such_file_infos
