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
    parser.add_argument('-W', '--not-watched', action='store_false', default=True,
                        help='If the files have not been watched')
    parser.add_argument('files', nargs='+', help='The files to move and register')
    parser.add_argument('dir', help='The directory to move the files to')

    return parser.parse_args()

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

def setup_signal_handling(shutdown_event):
    def signal_handler(*_):
        shutdown_event.set()
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

def main():
    shutdown_event = Event()
    file_info_queue = Queue()
    setup_signal_handling(shutdown_event)

    args = parse_args()
    config = read_config()

    files = get_files_to_register(args.files)
    Thread(target=process_files, args=(shutdown_event, file_info_queue, files)).start()

    with UdpClient(config, shutdown_event, file_info_queue) as client:
        no_such_files = client.register_files()

    if no_such_files:
        with database.open_database() as cursor:
            database.add_unregistered_files(
                cursor,
                time.time(),
                args.watched,
                args.internal,
                no_such_files
            )
            print("Adding files that failed to get registered to database")

    for fname in files:
        print("Moving {} to {}".format(os.path.basename(fname), args.dir))
        shutil.move(fname, args.dir)

if __name__ == '__main__':
    main()
