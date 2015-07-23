#!/usr/bin/env python3

import argparse
import os
import shutil
import signal
import sys
import time
from configparser import ConfigParser
from threading import Event, Thread
from queue import Queue

import database
from hashing import ed2k_of_path
from protocol import UdpClient

def parse_args():
    parser = argparse.ArgumentParser(description='Move and register files on anidb')
    parser.add_argument('-W', '--not-watched', action='store_false', dest='watched', default=True,
                        help='If the files have not been watched')
    parser.add_argument('--external', action='store_true',
                        help='If the files are externally stored')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Print protocol information')
    parser.add_argument('files', nargs='+', help='The files to move and register')
    parser.add_argument('directory', help='The directory to move the files to')

    return parser.parse_args()

def setup_signal_handling(shutdown_event):
    def signal_handler(*_):
        shutdown_event.set()
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

def read_config():
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

def get_files_to_register(files):
    files_to_register = set()
    for arg_file in files:
        if os.path.isdir(arg_file):
            for root, _, files in os.walk(arg_file):
                files_to_register.update([os.path.join(root, fname) for fname in files])
        else:
            files_to_register.add(arg_file)

    return files_to_register

#pylint: disable=too-many-arguments
def process_files(watched_time, watched, internal, shutdown_event, file_info_queue, files):
    try:
        for fname in files:
            if shutdown_event.is_set():
                break

            print("Processing file {}".format(os.path.basename(fname)))
            file_info_queue.put({
                'id': None,
                'view_date': watched_time,
                'internal': internal,
                'watched': watched,
                'path': fname,
                'size': os.path.getsize(fname),
                'ed2k': ed2k_of_path(fname)
            })

        file_info_queue.put(None)
    except Exception as exception:  # pylint: disable=broad-except
        print("Received exception {} while processing files".format(exception))
        shutdown_event.set()

def add_unregistered_files(file_info_queue, unregistered_files):
    for file_info in unregistered_files:
        file_info_queue.add(file_info)

def add_unregistered_files_to_db(cursor, no_such_files):
    if no_such_files:
        print("Adding files that failed to get registered to database")
        database.add_unregistered_files(
            cursor,
            no_such_files
        )

def remove_files_registered_from_db(cursor, unregistered_files, no_such_files):
    files_that_got_registered = list(
        set(unregistered_files) -
        set(no_such_file for no_such_file in no_such_files if no_such_file['id'])
    )

    if files_that_got_registered:
        print("Removing files that got registered from the database")
        database.remove_files(
            cursor,
            [file_info['id'] for file_info in files_that_got_registered]
        )

def move_files(files, directory):
    for fname in files:
        print("Moving {} to {}".format(os.path.basename(fname), directory))
        shutil.move(fname, directory)

def main():
    shutdown_event = Event()
    setup_signal_handling(shutdown_event)

    args = parse_args()
    config = read_config()

    files = get_files_to_register(args.files)
    file_info_queue = Queue()
    Thread(
        target=process_files,
        args=(time.time(), args.watched, not args.external, shutdown_event, file_info_queue, files)
    ).start()

    with database.open_database() as cursor:
        unregistered_files = database.get_unregistered_files(cursor)
        add_unregistered_files(file_info_queue, unregistered_files)
        #pylint: disable=too-many-function-args
        with UdpClient(args.verbose, config, shutdown_event, file_info_queue) as client:
            no_such_files = client.register_files()

        add_unregistered_files_to_db(cursor, no_such_files)
        remove_files_registered_from_db(cursor, unregistered_files, no_such_files)
    move_files(files, args.directory)

if __name__ == '__main__':
    main()
