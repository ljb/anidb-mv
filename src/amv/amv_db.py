import argparse
from datetime import datetime

from . import database
from .amv import read_config, register_file_infos, setup_shutdown_event
from .file_info import FileInfo


def main() -> None:
    args = _parse_args()
    match args.action:
        case "list":
            _handle_list()
        case "remove":
            _handle_remove(args.ids)
        case "clear":
            _handle_clear()
        case "retry":
            _handle_retry(args.verbose)


def _parse_args() -> argparse.Namespace:
    # Shared so that -v works both before and after the subcommand. SUPPRESS keeps the
    # subparser from writing its own default over a -v that was given ahead of it.
    verbose = argparse.ArgumentParser(add_help=False)
    verbose.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Print AniDB protocol messages",
    )

    parser = argparse.ArgumentParser(description="Manage files that failed to register with AniDB", parents=[verbose])

    subparsers = parser.add_subparsers(dest="action", required=True, metavar="action")
    subparsers.add_parser("list", help="List the files that failed to register")
    subparsers.add_parser("clear", help="Remove every file from the database")
    remove_parser = subparsers.add_parser("remove", help="Remove individual files from the database by id")
    remove_parser.add_argument("ids", nargs="+", type=int, help="Ids as shown by amv-db list")
    subparsers.add_parser("retry", parents=[verbose], help="Try registering the files with AniDB again")

    args = parser.parse_args()
    # SUPPRESS leaves the attribute off entirely unless -v was given somewhere. Note that
    # parser.set_defaults() cannot be used instead: it mutates the shared action object,
    # which would put the default back on the subparsers and undo the whole arrangement.
    args.verbose = getattr(args, "verbose", False)
    return args


def _format_with_unit(number: float, unit: str) -> str:
    return f"{number:.1f}{unit}B"


def _format_size(number: float) -> str:
    for unit in ["", "Ki", "Mi", "Gi"]:
        if abs(number) < 1024:
            return _format_with_unit(number, unit)
        number /= 1024
    return _format_with_unit(number, "Ti")


def _format_timestamp(view_date: float) -> str:
    return datetime.fromtimestamp(view_date).strftime("%Y-%m-%d %H:%M:%S")


def _handle_list() -> None:
    with database.open_database() as cursor:
        file_infos = database.get_unregistered_files(cursor)
        if file_infos:
            _print_list_header()
            for file_info in file_infos:
                print_list_line(file_info)


def _print_list_header() -> None:
    print(f"{'Id':10}{'Size':10}{'ed2k':34}{'Internal':10}{'Watched':9}{'Viewed':21}{'Path'}")
    print("-" * 120)


def print_list_line(file_info: FileInfo) -> None:
    print(
        "{id:<10}{size:<10}{ed2k:34}{internal:<10}{watched:<9}{view_date:21}{path}".format(
            id=file_info.id,
            path=file_info.path,
            size=_format_size(file_info.size),
            ed2k=file_info.ed2k,
            internal=file_info.internal,
            watched=file_info.watched,
            view_date=_format_timestamp(file_info.view_date),
        )
    )


def _handle_clear() -> None:
    with database.open_database() as cursor:
        database.clear(cursor)


def _handle_remove(ids: list[int]) -> None:
    with database.open_database() as cursor:
        database.remove_files(cursor, ids)


def _handle_retry(verbose: bool) -> None:
    shutdown_event = setup_shutdown_event()
    config = read_config()
    with database.open_database() as cursor:
        file_infos = database.get_unregistered_files(cursor)
        if not file_infos:
            print("No unregistered files in database")
            return

        file_infos_not_found = register_file_infos(shutdown_event, verbose, config, file_infos)
        ids_to_remove = [fi.id for fi in file_infos if fi not in file_infos_not_found]
        if ids_to_remove:
            print("Removing files that got registered from the database")
            database.remove_files(cursor, ids_to_remove)


if __name__ == "__main__":
    main()
