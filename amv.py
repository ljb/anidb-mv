#!/usr/bin/env python3

import argparse
import os
from configparser import ConfigParser
from hashing import ed2k_of_path
from protocol import register_files

def parse_args():
    parser = argparse.ArgumentParser(description='Move and register files on anidb')
    parser.add_argument('-W', '--not-watched', action='store_false', default=True,
                        help='If the files have not been watched')
    parser.add_argument('files', nargs='+', help='The files to move and register')
    parser.add_argument('dir', help='The directory to move the files to')
    return parser.parse_args()

def get_username_and_password():
    parser = ConfigParser()
    parser.read(os.path.expanduser('~/.amvrc'))
    return parser.get('anidb', 'username'), parser.get('anidb', 'password')

def get_files_to_register(files):
    files_to_register = set()
    for arg_file in files:
        if os.path.isdir(arg_file):
            for root, _, files in os.walk(arg_file):
                files_to_register.update([os.path.join(root, fname) for fname in files])
        else:
            files_to_register.add(arg_file)

    return files_to_register

def get_file_infos_iterator(files):
    for fname in files:
        yield {
            'path': fname,
            'size': os.path.getsize(fname),
            'ed2k': ed2k_of_path(fname)
        }

def main():
    args = parse_args()
    files_to_register = get_files_to_register(args.files)
    file_infos_iterator = get_file_infos_iterator(files_to_register)
    username, password = get_username_and_password()
    no_such_files = register_files(username, password, file_infos_iterator)
    print(no_such_files)

if __name__ == '__main__':
    main()
