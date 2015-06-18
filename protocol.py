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
    def __init__(self, username, password, file_infos):
        self.username = username
        self.password = password
        self.no_such_file_infos = []
        self.last_sent_file_info = None
        self.nr_free_packets = 5
        self.start_time = None
        self.file_infos = file_infos
        self.logged_in = False
        self.setTimeout(TIMEOUT)

    def get_delay(self):
        delay = 30 if self.nr_free_packets <= 0 or self.extended_period_of_time() else 0
        self.nr_free_packets -= 1
        print(delay)
        return delay

    def extended_period_of_time(self):
        return time.time() - self.start_time > EXTENDED_PERIOD_OF_TIME

    def send_with_delay(self, datagram):
        print(datagram)
        #pylint: disable=no-member
        reactor.callLater(self.get_delay(), self.transport.write, datagram)

    def connect_and_login(self, ip_address):
        print(ip_address)
        print(ANIDB_PORT)
        self.transport.connect(ip_address, ANIDB_PORT)
        self.send_with_delay(messages.auth_message(self.username, self.password))

    def startProtocol(self):
        print("Start protocol")
        self.start_time = time.time()
        #pylint: disable=no-member
        reactor.resolve(ANIDB_HOST).addCallback(self.connect_and_login)

    def stopProtocol(self):
        print("Shuting down")
        #pylint: disable=no-member
        reactor.stop()

    @staticmethod
    def raise_error(response):
        msg = 'Received unknown response "{number} {string}" in response to login'.format(
            number=response['number'],
            string=response['string']
        )
        raise AnidbProtocolException(msg)

    def verify_logged_in_response(self, response):
        if response['number'] not in [200, 201]:
            self.raise_error(response)
        self.logged_in = True

    def verify_register_file_response(self, response):
        if response['number'] == 320:
            self.no_such_file_infos.append('Hej')
        elif response['number'] == 310:
            print('File already registered')
        elif response['number'] != 210:
            self.raise_error(response)

    def timeoutConnection(self):
        print("Timed out waiting for reply")
        self.transport.loseConnection()

    def datagramReceived(self, datagram, _):
        print("Datagram received")
        self.resetTimeout()
        try:
            pass
            #response = messages.parse_message(datagram)
            #if self.logged_in:
            #    self.verify_logged_in_response(response)
            #else:
            #    self.verify_register_file_response(response)
        except AnidbProtocolException as exception:
            self.transport.loseConnection()
            print(exception)
            #traceback.print_exc()
        else:
            self.register_file_or_shutdown()

    def register_file_or_shutdown(self):
        if self.file_infos:
            file_info = self.file_infos.pop()
            print("Registering file {file}".format(file=file_info['path']))
            self.send_with_delay(messages.mylistadd(
                size=file_info['size'],
                ed2k=file_info['ed2k']
            ))
        else:
            print("Shutting down")
            self.send_with_delay(messages.logout())
            self.transport.loseConnection()

def register_files(username, password, file_infos):
    client = AnidbClientProtocol(username, password, file_infos)
    #pylint: disable=no-member
    reactor.listenUDP(0, client)
    reactor.run()

    return client.no_such_file_infos
