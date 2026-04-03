import socket
import time
from queue import Queue
from threading import Event
from typing import Self

from .. import exceptions
from ..file_info import FileInfo
from . import messages
from . import codes

SOFTWARE_URL = "https://github.com/ljb/anidb-mv"

EXTENDED_PERIOD_OF_TIME = 60
ANIDB_HOST = 'api.anidb.net'
ANIDB_PORT = 9000
TIMEOUT = 30
MAX_DATAGRAM_SIZE = 1400
MAX_OUTSTANDING_PACKAGES = 5
LOCAL_BIND_ADDRESS = '0.0.0.0'

SMALL_DELAY = 2
LARGE_DELAY = 4


class UdpClient:
    # pylint: disable=too-many-instance-attributes
    def __init__(self, shutdown_event: Event, verbose: bool, config: dict, file_info_queue: Queue) -> None:
        self._verbose = verbose
        self._config = config
        self._shutdown_event = shutdown_event
        self._file_info_queue = file_info_queue
        self._socket = None
        self._nr_free_packets = MAX_OUTSTANDING_PACKAGES
        self._start_time = None
        self._session_id = None

    def register_file_infos(self) -> list[FileInfo]:
        no_such_file_infos: list[FileInfo] = []
        while True:
            file_info = self._file_info_queue.get()
            if file_info is None or self._shutdown_event.is_set():
                break
            if not self._register_file(file_info):
                no_such_file_infos.append(file_info)

        return no_such_file_infos

    def _print_if_verbose_mode(self, *args: object) -> None:
        if self._verbose:
            print(*args)

    def __enter__(self) -> Self:
        self._start_time = time.time()
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.bind((LOCAL_BIND_ADDRESS, self._config['local_port']))
        self._socket.settimeout(TIMEOUT)
        self._login()
        return self

    def __exit__(self, *_: object) -> None:
        self._shutdown_event.set()
        self._logout()

    def _get_delay_and_decrease_counter(self) -> int:
        if self._nr_free_packets > 0:
            self._nr_free_packets -= 1
            return 0
        if self._extended_period_of_time():
            return LARGE_DELAY

        return SMALL_DELAY

    def _extended_period_of_time(self) -> bool:
        return time.time() - self._start_time > EXTENDED_PERIOD_OF_TIME

    def _send_with_delay(self, datagram: bytes) -> None:
        self._print_if_verbose_mode(f"Sending {datagram}")
        delay = self._get_delay_and_decrease_counter()
        time.sleep(delay)
        self._socket.sendto(datagram, (ANIDB_HOST, ANIDB_PORT))

    def _receive(self) -> dict[str, str | int]:
        datagram, _ = self._socket.recvfrom(MAX_DATAGRAM_SIZE)
        return messages.parse_message(datagram)

    @staticmethod
    def _raise_error(response: dict[str, str | int]) -> None:
        raise exceptions.AnidbProtocolException(
            f'Received unknown response "{response["number"]} {response["string"]}" in response to message')

    def _login(self) -> None:
        self._send_with_delay(messages.auth_message(
            self._config['username'],
            self._config['password']))
        response = self._receive()
        self._print_if_verbose_mode('Received response', response)
        match response['number']:
            case codes.LOGIN_ACCEPTED:
                pass
            case codes.LOGIN_ACCEPTED_NEW_VERSION:
                print("This program uses an outdated version of the AniDB UDP protocol."
                      f"Please download a new version of it from {SOFTWARE_URL}")
            case _:
                self._raise_error(response)
        self._session_id = response['session']

    def _logout(self) -> None:
        self._send_with_delay(messages.logout_message())

    def _register_file(self, file_info: FileInfo) -> bool:
        self._print_if_verbose_mode(f"Registering file {file_info.path}")
        self._send_with_delay(messages.mylistadd_message(file_info, self._session_id))
        datagram, _ = self._socket.recvfrom(MAX_DATAGRAM_SIZE)
        response = messages.parse_message(datagram)
        match response['number']:
            case codes.NO_SUCH_FILE_CODE:
                print(f"No such file {file_info.path}")
                return False
            case codes.FILE_ALREADY_IN_MYLIST:
                print(f'File {file_info.path} already registered')
                return True
            case codes.MYLIST_ENTRY_ADDED:
                print(f'File {file_info.path} registered successfully')
                return True
            case _:
                self._raise_error(response)
