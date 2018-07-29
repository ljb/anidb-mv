#!/usr/bin/env python3

import argparse
import os
import shutil
import signal
import sys
import time
from configparser import ConfigParser
from queue import Queue
from threading import Event, Thread

import database
from hashing import ed2k_of_path
from protocol import UdpClient


def main():
    shutdown_event = Event()
    _setup_signal_handling(shutdown_event)

    args = _parse_args()
    config = _read_config()

    files = _get_files_to_register(args.files)
    file_info_queue = Queue()
    _start_worker_thread(args.watched, args.external, file_info_queue, files, shutdown_event)

    with database.open_database() as cursor:
        unregistered_files = database.get_unregistered_files(cursor)
        _add_unregistered_files(file_info_queue, unregistered_files)
        with UdpClient(args.verbose, config, shutdown_event, file_info_queue) as client:
            no_such_files = client.register_files()

        _add_unregistered_files_to_db(cursor, no_such_files)
        _remove_files_registered_from_db(cursor, unregistered_files, no_such_files)
    _move_files(files, args.directory)


def _start_worker_thread(watched, external, file_info_queue, files, shutdown_event):
    Thread(
        target=_process_files,
        args=(time.time(), watched, not external, shutdown_event, file_info_queue, files)
    ).start()


def _parse_args():
    parser = argparse.ArgumentParser(description='Move and register files on anidb')
    parser.add_argument('-W', '--not-watched', action='store_false', dest='watched', default=True,
                        help='If the files have not been watched')
    parser.add_argument('--external', action='store_true',
                        help='If the files are externally stored')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Print protocol information')
    parser.add_argument('-n', '--no-move', action='store_false', default=True, dest='move',
                        help='Do not move the files, only register them')
    parser.add_argument('-i', '--no-old-report',
                        help='Do not try to report old files')
    parser.add_argument('files', nargs='*', help='The files to move and register')
    parser.add_argument('directory', help='The directory to move the files to')

    args = parser.parse_args()

    if args.move:
        if not args.directory:
            print("A directory argument is required when not using the --no-move flag")
            sys.exit(1)
        elif not os.path.isdir(args.directory):
            print("{} is not a directory".format(args.directory))
            sys.exit(1)

    return args


def _setup_signal_handling(shutdown_event):
    def signal_handler(*_):
        shutdown_event.set()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


def _read_config():
    config_path = os.path.expanduser('~/.amvrc')
    if not os.path.exists(config_path):
        print("No config file exists at {}.\n"
              "Create one with the following format:\n"
              "[anidb]\n"
              "local_port=9000\n"
              "username=myusername\n"
              "password=mypassword".format(config_path))
        sys.exit(1)

    parser = ConfigParser()
    parser.read(config_path)
    return {
        'username': parser.get('anidb', 'username'),
        'password': parser.get('anidb', 'password'),
        'local_port': parser.getint('anidb', 'local_port')
    }


def _get_files_to_register(files):
    files_to_register = set()
    for arg_file in files:
        if os.path.isdir(arg_file):
            for root, _, files in os.walk(arg_file):
                files_to_register.update([os.path.join(root, file_name) for file_name in files])
        else:
            files_to_register.add(arg_file)

    return files_to_register


# pylint: disable=too-many-arguments
def _process_files(watched_time, watched, internal, shutdown_event, file_info_queue, files):
    try:
        for file_name in files:
            if shutdown_event.is_set():
                break

            print("Processing file {}".format(os.path.basename(file_name)))
            file_info_queue.put({
                'id': None,
                'view_date': watched_time,
                'internal': internal,
                'watched': watched,
                'path': file_name,
                'size': os.path.getsize(file_name),
                'ed2k': ed2k_of_path(file_name)
            })

        file_info_queue.put(None)
    except Exception as exception:  # pylint: disable=broad-except
        print("Received exception {} while processing files".format(exception))
        shutdown_event.set()


def _add_unregistered_files(file_info_queue, unregistered_files):
    for file_info in unregistered_files:
        file_info_queue.put(file_info)


def _add_unregistered_files_to_db(cursor, no_such_files):
    if no_such_files:
        print("Adding files that failed to get registered to database")
        database.add_unregistered_files(
            cursor,
            no_such_files
        )


def _remove_files_registered_from_db(cursor, unregistered_files, no_such_files):
    file_ids_that_got_registered = list(
        set(unregistered_file['id'] for unregistered_file in unregistered_files) -
        set(no_such_file['id'] for no_such_file in no_such_files if no_such_file['id'])
    )

    if file_ids_that_got_registered:
        print("Removing files that got registered from the database")
        database.remove_files(
            cursor,
            file_ids_that_got_registered
        )


def _move_files(files, directory):
    for file_name in files:
        print("Moving {} to {}".format(os.path.basename(file_name), directory))
        shutil.move(file_name, directory)


if __name__ == '__main__':
    main()
