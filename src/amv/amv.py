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

    if args.replace:
        _replace(shutdown_event, args.existing, args.new, args.verbose, config)
        return

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
        "-u",
        "--unwatched",
        action="store_false",
        dest="watched",
        default=True,
        help="Mark the files as not watched",
    )
    parser.add_argument("-e", "--external", action="store_true", help="Mark the files as stored externally")
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
        "-R",
        "--retry-unregistered",
        action="store_true",
        help="Also retry files saved in the database",
    )
    parser.add_argument(
        "-r",
        "--replace",
        action="store_true",
        help="Replace a file with another, in mv's order (amv -r NEW EXISTING): register NEW with EXISTING's "
        "watch date and flags, drop EXISTING from MyList, and move NEW into EXISTING's place",
    )
    parser.add_argument("files", nargs="+", help="Files to move and register")
    # Note: this will never match anything and is only here to make the help text look good
    parser.add_argument("directory", help="Destination directory", nargs="?")

    args = parser.parse_args()

    if args.replace:
        if len(args.files) != 2:
            print("--replace takes exactly two files: the new one and the one it replaces", file=sys.stderr)
            sys.exit(1)
        given = {
            "-u": not args.watched,
            "-e": args.external,
            "-n": not args.move,
            "-R": args.retry_unregistered,
        }
        incompatible = [flag for flag, is_given in given.items() if is_given]
        if incompatible:
            print(f"--replace cannot be combined with {', '.join(incompatible)}", file=sys.stderr)
            sys.exit(1)
        args.new, args.existing = args.files
    elif args.move:
        if len(args.files) < 2:
            print("A destination directory is required (use --no-move to skip moving)", file=sys.stderr)
            sys.exit(1)
        elif not os.path.isdir(args.files[-1]):
            print(f"{args.files[-1]} is not a directory", file=sys.stderr)
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
                "password=mypassword",
                file=sys.stderr,
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
                print(f"Failed to process {file_name}: {e}", file=sys.stderr)
    except Exception as exception:
        print(f"Received exception {exception} while processing files", file=sys.stderr)
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


def _replace(shutdown_event: Event, existing_path: str, new_path: str, verbose: bool, config: dict) -> None:
    """
    Swaps existing_path for new_path on AniDB and on disk.

    The existing file is looked up in the database of unregistered files first, since that
    is free and works offline, and in MyList otherwise. The new file is registered with the
    watch date and flags found there, the old entry is dropped, and only then is anything
    moved or removed on disk, so a failed registration leaves everything as it was.
    """
    if not os.path.isfile(existing_path):
        print(f"{existing_path} is not a file", file=sys.stderr)
        sys.exit(1)
    if not os.path.isfile(new_path):
        print(f"{new_path} is not a file", file=sys.stderr)
        sys.exit(1)
    if os.path.abspath(existing_path) == os.path.abspath(new_path):
        print("existing and new must be different files", file=sys.stderr)
        sys.exit(1)

    print(f"Hashing {os.path.basename(existing_path)}")
    existing_size = os.path.getsize(existing_path)
    existing_ed2k = ed2k_of_path(existing_path)
    print(f"Hashing {os.path.basename(new_path)}")
    new_size = os.path.getsize(new_path)
    new_ed2k = ed2k_of_path(new_path)

    with database.open_database() as cursor:
        in_database = [
            fi
            for fi in database.get_unregistered_files(cursor)
            if fi.ed2k == existing_ed2k and fi.size == existing_size
        ]

        with UdpClient(shutdown_event, verbose, config, Queue()) as client:
            if in_database:
                old_entry = in_database[0]
            else:
                old_entry = client.get_mylist_entry(existing_path, existing_size, existing_ed2k)
                if old_entry is None:
                    print(
                        f"{existing_path} is neither in the database nor in MyList; nothing to replace",
                        file=sys.stderr,
                    )
                    sys.exit(1)

            new_file_info = FileInfo(
                path=new_path,
                size=new_size,
                ed2k=new_ed2k,
                watched=old_entry.watched,
                internal=old_entry.internal,
                view_date=old_entry.view_date,
            )
            # A Ctrl-C during registration may still let the reply through, so the shutdown
            # event is checked as well before anything is removed.
            if not client.register_replacement(new_file_info) or shutdown_event.is_set():
                print("Registration of new file failed; leaving everything unchanged", file=sys.stderr)
                sys.exit(1)

            if in_database:
                database.remove_files(cursor, [old_entry.id])
            elif not client.delete_mylist_entry(existing_path, existing_size, existing_ed2k):
                print(f"Could not remove {existing_path} from MyList; remove it by hand", file=sys.stderr)

    new_destination = os.path.join(os.path.dirname(existing_path), os.path.basename(new_path))
    print(f"Moving {os.path.basename(new_path)} to {os.path.dirname(existing_path) or '.'}")
    shutil.move(new_path, new_destination)
    if os.path.abspath(existing_path) != os.path.abspath(new_destination):
        print(f"Removing {existing_path}")
        os.remove(existing_path)


def _report_unregistered_in_database(unregistered_file_infos: list[FileInfo]) -> None:
    count = len(unregistered_file_infos)
    if count == 0:
        return
    noun = "file" if count == 1 else "files"
    print(f"{count} unregistered {noun} in database:")
    for file_info in unregistered_file_infos:
        print(f"  {file_info.path}")
    print()
    print("Run amv-db retry to try registering them again.")
    print()


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
            print(f"Failed to move {file_name}: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
