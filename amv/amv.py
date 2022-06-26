import argparse
import os
import shutil
import signal
import sys
import time
from collections import OrderedDict
from configparser import ConfigParser
from queue import Queue
from threading import Event, Thread

from . import database
from .hashing import ed2k_of_path
from .network.client import UdpClient


def main():
    shutdown_event = _setup_shutdown_event()

    args_files, args_directory, args = _parse_args()
    config = _read_config()

    files_and_dirs = _remove_duplicates(args_files)
    files = _get_paths_to_register(files_and_dirs)
    file_info_queue = Queue()

    with database.open_database() as cursor:
        if args.db_report:
            file_infos_from_database = database.get_unregistered_files(cursor)
            _add_unregistered_files(file_info_queue, file_infos_from_database)
        else:
            file_infos_from_database = []

        thread = _start_worker_thread(shutdown_event, args.watched, args.external, file_info_queue, files)
        with UdpClient(shutdown_event, args.verbose, config, file_info_queue) as client:
            file_infos_not_found = client.register_file_infos()
        thread.join()

        _add_unregistered_files_to_db(cursor, file_infos_from_database, file_infos_not_found)
        _remove_registered_files_from_db(cursor, file_infos_from_database, file_infos_not_found)

    if args.move:
        _move_files(files_and_dirs, args_directory)


def _setup_shutdown_event():
    shutdown_event = Event()

    def signal_handler(*_):
        shutdown_event.set()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    return shutdown_event


def _parse_args():
    parser = argparse.ArgumentParser(description='Move and register files on AniDB')
    parser.add_argument('-W', '--not-watched', action='store_false', dest='watched', default=True,
                        help='If the files have not been watched')
    parser.add_argument('--external', action='store_true',
                        help='If the files are externally stored')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Print protocol information')
    parser.add_argument('-n', '--no-move', action='store_false', default=True, dest='move',
                        help='Do not move the files, only register them')
    parser.add_argument('--no-db-report', action='store_false', dest='db_report',
                        help='Ignore old files from the database when doing the reporting')
    parser.add_argument('files', nargs='+', help='The files to move and register')
    # Note: this will never match anything and is only here to make the help text look good
    parser.add_argument('directory', help='The directory to move the files to', nargs='?')

    args = parser.parse_args()

    if args.move:
        if len(args.files) < 2:
            print("A directory argument is required when not using the --no-move flag")
            sys.exit(1)
        elif not os.path.isdir(args.files[-1]):
            print(f"{args.files[-1]} is not a directory")
            sys.exit(1)

    args_files = args.files[:-1] if args.move else args.files
    args_directory = args.files[-1] if args.move else None

    return args_files, args_directory, args


def _read_config():
    xdg_config_home = os.getenv('XDG_CONFIG_HOME', '~/.config')
    config_path = os.path.expanduser(os.path.join(xdg_config_home, 'amv/config'))
    if not os.path.exists(config_path):
        config_path = os.path.expanduser('~/.amvrc')
        if not os.path.exists(config_path):
            print(f"No config file exists at {os.path.join(xdg_config_home, 'amv/config')}.\n"
                  "Create one with the following format:\n"
                  "[anidb]\n"
                  "local_port=9000\n"
                  "username=myusername\n"
                  "password=mypassword\n"
                  "# This is optional and used for encryption\n"
                  "api_key=")
            sys.exit(1)

    parser = ConfigParser()
    parser.read(config_path)
    return {
        'username': parser.get('anidb', 'username'),
        'password': parser.get('anidb', 'password'),
        'local_port': parser.getint('anidb', 'local_port'),
        'api_key': parser.get('anidb', 'api_key')
    }


def _get_paths_to_register(files):
    files_to_register = []
    for file_ in files:
        if os.path.isdir(file_):
            for root, _, files_in_dir in os.walk(file_):
                files_to_register += [os.path.join(root, file_name) for file_name in files_in_dir]
        else:
            files_to_register.append(file_)

    return files_to_register


def _remove_duplicates(items):
    return list(OrderedDict.fromkeys(items))


def _start_worker_thread(shutdown_event, watched, external, file_info_queue, files):
    thread = Thread(
        target=_process_files,
        args=(time.time(), watched, not external, shutdown_event, file_info_queue, files))
    thread.start()

    return thread


# pylint: disable=too-many-arguments
def _process_files(watched_time, watched, internal, shutdown_event, file_info_queue, files):
    try:
        for file_name in files:
            if shutdown_event.is_set():
                break

            print(f"Processing file {os.path.basename(file_name)}")
            try:
                file_info_queue.put({
                    'id': None,
                    'view_date': watched_time,
                    'internal': internal,
                    'watched': watched,
                    'path': file_name,
                    'size': os.path.getsize(file_name),
                    'ed2k': ed2k_of_path(file_name)
                })
            except IOError as e:
                print(f"Failed to process {file_name}: {e}")

        file_info_queue.put(None)
    except Exception as exception:  # pylint: disable=broad-except
        print(f"Received exception {exception} while processing files")
        shutdown_event.set()


def _add_unregistered_files(file_info_queue, unregistered_file_infos):
    for file_info in unregistered_file_infos:
        file_info_queue.put(file_info)


def _add_unregistered_files_to_db(cursor, file_infos_from_database, file_infos_not_found):
    new_file_infos_to_register = [
        file_info for file_info in file_infos_not_found if file_info not in file_infos_from_database
    ]

    if new_file_infos_to_register:
        print("Adding files that failed to get registered to database")
        database.add_unregistered_files(
            cursor,
            new_file_infos_to_register
        )


def _remove_registered_files_from_db(cursor, file_infos_from_database, file_infos_not_found):
    ids_to_remove = [
        file_info['id']
        for file_info in file_infos_from_database
        if file_info not in file_infos_not_found
    ]

    if ids_to_remove:
        print("Removing files that got registered from the database")
        database.remove_files(
            cursor,
            ids_to_remove
        )


def _move_files(files, directory):
    for file_name in files:
        print(f"Moving {os.path.basename(file_name)} to {directory}")
        try:
            shutil.move(file_name, directory)
        except (shutil.Error, FileNotFoundError) as e:
            print(f"Failed to move {file_name}: {e}")


if __name__ == '__main__':
    main()
