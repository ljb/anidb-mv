import argparse
from datetime import datetime

from . import database


def main():
    args = _parse_args()
    if args.action == 'list':
        _handle_list()
    elif args.action == 'remove':
        _handle_remove(args.ids)
    elif args.action == 'clear':
        _handle_clear()


def _parse_args():
    parser = argparse.ArgumentParser(description='Handle unregistered files on anidb')
    subparsers = parser.add_subparsers(dest='action')
    subparsers.add_parser('list')
    subparsers.add_parser('clear')
    remove_parser = subparsers.add_parser('remove')
    remove_parser.add_argument('ids', nargs='+', type=int)

    return parser.parse_args()


def _format_with_unit(number, unit):
    return "{:.1f}{}B".format(number, unit)


def _format_size(number):
    for unit in ['', 'Ki', 'Mi', 'Gi']:
        if abs(number) < 1024:
            return _format_with_unit(number, unit)
        number /= 1024
    return _format_with_unit(number, 'Ti')


def _format_timestamp(view_date):
    return datetime.fromtimestamp(view_date).strftime('%Y-%m-%d %H:%M:%S')


def _handle_list():
    with database.open_database() as cursor:
        file_infos = database.get_unregistered_files(cursor)
        if file_infos:
            _print_list_header()
            for file_info in file_infos:
                print_list_line(file_info)


def _print_list_header():
    print('{id:10}{size:10}{ed2k:34}{internal:10}{watched:9}{view_date:21}{path}'.format(
        id='Id',
        path='Path',
        size='Size',
        ed2k='ed2k',
        internal='Internal',
        watched='Watched',
        view_date='Viewed',
    ))
    print('-' * 120)


def print_list_line(file_info):
    print('{id:<10}{size:<10}{ed2k:34}{internal:<10}{watched:<9}{view_date:21}{path}'.format(
        id=file_info['id'],
        path=file_info['path'],
        size=_format_size(file_info['size']),
        ed2k=file_info['ed2k'],
        internal=file_info['internal'],
        watched=file_info['watched'],
        view_date=_format_timestamp(file_info['view_date'])
    ))


def _handle_clear():
    with database.open_database() as cursor:
        database.clear(cursor)


def _handle_remove(ids):
    with database.open_database() as cursor:
        database.remove_files(cursor, ids)


if __name__ == '__main__':
    main()
