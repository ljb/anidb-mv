#!/usr/bin/env python

import time
import messages
from exceptions import AnidbProtocolException

from twisted.internet.protocol import DatagramProtocol
from twisted.internet import reactor
from twisted.protocols.policies import TimeoutMixin

EXTENDED_PERIOD_OF_TIME = 30
#ANIDB_HOST = 'api.anidb.net'
ANIDB_HOST = 'localhost'
ANIDB_PORT = 9000
TIMEOUT = 60

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

    def send_with_delay(self, datagram):
        print(datagram)
        #pylint: disable=no-member
        reactor.callLater(
            self._get_delay_and_decrease_counter(),
            self.transport.write,
            datagram
        )

    def _connect_and_login(self, ip_address):
        print(ip_address)
        print(ANIDB_PORT)
        self.transport.connect(ip_address, ANIDB_PORT)
        self.send_with_delay(messages.auth_message(self._username, self._password))

    def _verify_logged_in_response(self, response):
        if response['number'] not in [200, 201]:
            self.raise_error(response)
        self._logged_in = True

    def timeoutConnection(self):
        print("Timed out waiting for reply")
        self.transport.loseConnection()

    def startProtocol(self):
        print("Start protocol")
        self._start_time = time.time()
        #pylint: disable=no-member
        reactor.resolve(ANIDB_HOST).addCallback(self._connect_and_login)

    def stopProtocol(self):
        print("Shuting down")
        #pylint: disable=no-member
        reactor.stop()

    def datagramReceived(self, datagram, _):
        print("Datagram received")
        self.resetTimeout()
        try:
            self.handle_response(datagram)
            response = messages.parse_message(datagram)
            if self._logged_in:
                self._verify_logged_in_response(response)
            elif self.handle_response(response):
                print("Shutting down")
                self.send_with_delay(messages.logout())
                self.transport.loseConnection()

        except AnidbProtocolException as exception:
            self.transport.loseConnection()
            print(exception)

    @staticmethod
    def raise_error(response):
        msg = 'Received unknown response "{number} {string}" in response to login'.format(
            number=response['number'],
            string=response['string']
        )
        raise AnidbProtocolException(msg)

    def handle_response(self, message):
        raise NotImplementedError()

class AmvProtocol(AnidbClientProtocol):
    def __init__(self, username, password, file_infos):
        super().__init__(username, password)
        self.no_such_file_infos = []
        self._last_sent_file_info = None
        self._file_infos = file_infos

    def handle_response(self, response):
        self.verify_file_registered_response(response)
        return self.register_file_or_shutdown()

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

    def register_file_or_shutdown(self):
        if not self._file_infos:
            return True

        file_info = self._file_infos.pop()
        print("Registering file {file}".format(file=file_info['path']))
        self.send_with_delay(messages.mylistadd(
            size=file_info['size'],
            ed2k=file_info['ed2k']
        ))
        self._last_sent_file_info = file_info

        return False

def register_files(username, password, file_infos):
    client = AmvProtocol(username, password, file_infos)
    #pylint: disable=no-member
    reactor.listenUDP(0, client)
    reactor.run()

    return client.no_such_file_infos
