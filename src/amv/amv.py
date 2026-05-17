import argparse
import os
import shutil
import signal
import sqlite3
import sys
import time
from configparser import ConfigParser
from queue import Queue
from threading import Event, Thread

from . import database
from .file_info import FileInfo
from .hashing import ed2k_of_path
from .network.client import UdpClient


def main() -> None:
    shutdown_event = setup_shutdown_event()

    args = _parse_args()
    config = read_config()

    files_and_dirs = _remove_duplicates(args.files)
    files = _get_paths_to_register(files_and_dirs)
    file_info_queue = Queue()

    with database.open_database() as cursor:
        unregistered_in_database = database.get_unregistered_files(cursor)
        if args.retry_unregistered:
            _add_unregistered_files(file_info_queue, unregistered_in_database)
            tracked_db_files = unregistered_in_database
        else:
            _report_unregistered_in_database(unregistered_in_database)
            tracked_db_files = []

        thread = _start_worker_thread(shutdown_event, args.watched, args.external, file_info_queue, files)
        with UdpClient(shutdown_event, args.verbose, config, file_info_queue) as client:
            file_infos_not_found = client.register_file_infos()
        thread.join()

        _add_unregistered_files_to_db(cursor, tracked_db_files, file_infos_not_found)
        _remove_registered_files_from_db(cursor, tracked_db_files, file_infos_not_found)

    if args.move:
        _move_files(files_and_dirs, args.directory)


def setup_shutdown_event() -> Event:
    shutdown_event = Event()

    def signal_handler(*_):
        shutdown_event.set()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    return shutdown_event


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Move and register files on AniDB")
    parser.add_argument(
        "--unwatched",
        action="store_false",
        dest="watched",
        default=True,
        help="Mark the files as not watched",
    )
    parser.add_argument("--external", action="store_true", help="Mark the files as stored externally")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print AniDB protocol messages")
    parser.add_argument(
        "-n",
        "--no-move",
        action="store_false",
        default=True,
        dest="move",
        help="Register the files without moving them",
    )
    parser.add_argument(
        "-r",
        "--retry-unregistered",
        action="store_true",
        help="Also retry files saved in the database",
    )
    parser.add_argument("files", nargs="+", help="Files to move and register")
    # Note: this will never match anything and is only here to make the help text look good
    parser.add_argument("directory", help="Destination directory", nargs="?")

    args = parser.parse_args()

    if args.move:
        if len(args.files) < 2:
            print("A destination directory is required (use --no-move to skip moving)")
            sys.exit(1)
        elif not os.path.isdir(args.files[-1]):
            print(f"{args.files[-1]} is not a directory")
            sys.exit(1)
        args.directory = args.files.pop()

    return args


def read_config() -> dict[str, str | int]:
    xdg_config_home = os.getenv("XDG_CONFIG_HOME", "~/.config")
    config_path = os.path.expanduser(os.path.join(xdg_config_home, "amv/config"))
    if not os.path.exists(config_path):
        config_path = os.path.expanduser("~/.amvrc")
        if not os.path.exists(config_path):
            print(
                f"No config file exists at {os.path.join(xdg_config_home, 'amv/config')}.\n"
                "Create one with the following format:\n"
                "[anidb]\n"
                "local_port=9000\n"
                "username=myusername\n"
                "password=mypassword"
            )
            sys.exit(1)

    parser = ConfigParser()
    parser.read(config_path)
    return {
        "username": parser.get("anidb", "username"),
        "password": parser.get("anidb", "password"),
        "local_port": parser.getint("anidb", "local_port"),
    }


def _get_paths_to_register(files: list[str]) -> list[str]:
    files_to_register = []
    for file_ in files:
        if os.path.isdir(file_):
            for root, _, files_in_dir in os.walk(file_):
                files_to_register += [os.path.join(root, file_name) for file_name in files_in_dir]
        else:
            files_to_register.append(file_)

    return files_to_register


def _remove_duplicates(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def _start_worker_thread(
    shutdown_event: Event, watched: bool, external: bool, file_info_queue: Queue, files: list[str]
) -> Thread:
    worker_settings = {
        "watched_time": time.time(),
        "watched": watched,
        "internal": not external,
    }
    thread = Thread(target=_process_files, args=(worker_settings, shutdown_event, file_info_queue, files))
    thread.start()

    return thread


def _process_files(worker_settings: dict, shutdown_event: Event, file_info_queue: Queue, files: list[str]) -> None:
    try:
        for file_name in files:
            if shutdown_event.is_set():
                break

            print(f"Processing file {os.path.basename(file_name)}")
            try:
                file_info_queue.put(
                    FileInfo(
                        view_date=worker_settings["watched_time"],
                        internal=worker_settings["internal"],
                        watched=worker_settings["watched"],
                        path=file_name,
                        size=os.path.getsize(file_name),
                        ed2k=ed2k_of_path(file_name),
                    )
                )
            except IOError as e:
                print(f"Failed to process {file_name}: {e}")
    except Exception as exception:
        print(f"Received exception {exception} while processing files")
        shutdown_event.set()
    finally:
        file_info_queue.put(None)


def _add_unregistered_files(file_info_queue: Queue, unregistered_file_infos: list[FileInfo]) -> None:
    for file_info in unregistered_file_infos:
        file_info_queue.put(file_info)


def register_file_infos(
    shutdown_event: Event, verbose: bool, config: dict, file_infos: list[FileInfo]
) -> list[FileInfo]:
    queue: Queue = Queue()
    for file_info in file_infos:
        queue.put(file_info)
    queue.put(None)
    with UdpClient(shutdown_event, verbose, config, queue) as client:
        return client.register_file_infos()


def _report_unregistered_in_database(unregistered_file_infos: list[FileInfo]) -> None:
    count = len(unregistered_file_infos)
    if count == 0:
        return
    noun = "file" if count == 1 else "files"
    print(
        f"{count} unregistered {noun} in database. "
        "Run `amv-db list` for details or `amv --retry-unregistered ...` to try registering them again."
    )


def _add_unregistered_files_to_db(
    cursor: sqlite3.Cursor, file_infos_from_database: list[FileInfo], file_infos_not_found: list[FileInfo]
) -> None:
    new_file_infos_to_register = [
        file_info for file_info in file_infos_not_found if file_info not in file_infos_from_database
    ]

    if new_file_infos_to_register:
        print("Adding files that failed to get registered to database")
        database.add_unregistered_files(cursor, new_file_infos_to_register)


def _remove_registered_files_from_db(
    cursor: sqlite3.Cursor, file_infos_from_database: list[FileInfo], file_infos_not_found: list[FileInfo]
) -> None:
    ids_to_remove = [file_info.id for file_info in file_infos_from_database if file_info not in file_infos_not_found]

    if ids_to_remove:
        print("Removing files that got registered from the database")
        database.remove_files(cursor, ids_to_remove)


def _move_files(files: list[str], directory: str) -> None:
    for file_name in files:
        print(f"Moving {os.path.basename(file_name)} to {directory}")
        try:
            shutil.move(file_name, directory)
        except (shutil.Error, FileNotFoundError) as e:
            print(f"Failed to move {file_name}: {e}")


if __name__ == "__main__":
    main()
