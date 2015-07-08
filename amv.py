#!/usr/bin/env python3

import argparse
import os
import shutil
import sys
import time
from configparser import ConfigParser

import database
from protocol import register_files

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

def main():
    args = parse_args()
    files = get_files_to_register(args.files)
    config = read_config()
    no_such_files = register_files(config, files)

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
