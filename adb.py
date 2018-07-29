#!/usr/bin/env python3

import argparse
from datetime import datetime

import database


def main():
    args = parse_args()
    if args.action == 'list':
        handle_list()
    elif args.action == 'remove':
        handle_remove(args)
    elif args.action == 'clear':
        handle_clear()


def parse_args():
    parser = argparse.ArgumentParser(description='Handle unregister files on anidb')
    subparsers = parser.add_subparsers(dest='action')
    subparsers.add_parser('list')
    subparsers.add_parser('clear')
    remove_parser = subparsers.add_parser('remove')
    remove_parser.add_argument('ids', nargs='+', type=int)

    return parser.parse_args()


def sizeof_format(num, suffix='B'):
    for unit in ['', 'Ki', 'Mi', 'Gi', 'Ti', 'Pi', 'Ei', 'Zi']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)


def handle_list():
    with database.open_database() as cursor:
        file_infos = database.get_unregistered_files(cursor)
        if file_infos:
            print_list_header()
            for file_info in file_infos:
                print_list_line(file_info)


def print_list_header():
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
        size=sizeof_format(file_info['size']),
        ed2k=file_info['ed2k'],
        internal=file_info['internal'],
        watched=file_info['watched'],
        view_date=datetime.fromtimestamp(
            file_info['view_date']
        ).strftime('%Y-%m-%d %H:%M:%S')
    ))


def handle_clear():
    with database.open_database() as cursor:
        database.clear(cursor)


def handle_remove(args):
    with database.open_database() as cursor:
        database.remove_files(cursor, args.ids)


if __name__ == '__main__':
    main()
