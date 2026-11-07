"""Delete local test runtime for this addon only.

Reads disposable_databases.txt in this directory. A name is removed only when
it is listed there and starts with cpla_. Other PostgreSQL databases are left
untouched.
"""
import configparser
import os
import shutil
import sys

import psycopg2
from psycopg2 import sql

ADDON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
LIST_PATH = os.path.join(HERE, 'disposable_databases.txt')
CONF_PATH = r'C:\PycharmProjects\odoo19\odoo-19.0\odoo.conf'
FILESTORE = os.path.join(
    os.environ.get('LOCALAPPDATA', ''),
    'OpenERP S.A.',
    'Odoo',
    'filestore',
)
KEEP = {
    'free_space.py',
    'disposable_databases.txt',
    'PUBLISH_OMIT.txt',
}


def _names():
    names = []
    with open(LIST_PATH, encoding='utf-8') as handle:
        for line in handle:
            name = line.strip()
            if not name or name.startswith('#'):
                continue
            if not name.startswith('cpla_') or any(char in name for char in '/\\.'):
                raise SystemExit('Refusing name that is not a cpla_ test database: %s' % name)
            names.append(name)
    return names


def _conf():
    parser = configparser.ConfigParser(interpolation=None)
    parser.read(CONF_PATH)
    return parser['options']


def _drop_databases(names):
    opt = _conf()
    connection = psycopg2.connect(
        host=opt.get('db_host', 'localhost'),
        port=opt.get('db_port', '5432'),
        user=opt.get('db_user'),
        password=opt.get('db_password'),
        dbname='postgres',
        connect_timeout=8,
    )
    connection.autocommit = True
    cursor = connection.cursor()
    for name in names:
        cursor.execute(
            'SELECT pg_terminate_backend(pid) FROM pg_stat_activity '
            'WHERE datname = %s AND pid <> pg_backend_pid()',
            (name,),
        )
        cursor.execute(sql.SQL('DROP DATABASE IF EXISTS {}').format(sql.Identifier(name)))
        print('dropped database %s' % name)
    cursor.close()
    connection.close()


def _remove_filestore(names):
    root = os.path.abspath(FILESTORE)
    if not os.path.isdir(root):
        print('filestore directory not found')
        return
    for name in names:
        path = os.path.abspath(os.path.join(root, name))
        if os.path.dirname(path) != root or not path.startswith(root + os.sep):
            raise SystemExit('Refusing filestore path %s' % path)
        if os.path.isdir(path):
            shutil.rmtree(path)
            print('removed filestore %s' % path)
        else:
            print('no filestore %s' % name)


def _remove_pycache():
    for dirpath, dirnames, _filenames in os.walk(ADDON):
        for dirname in list(dirnames):
            if dirname == '__pycache__':
                path = os.path.join(dirpath, dirname)
                shutil.rmtree(path)
                print('removed %s' % path)
                dirnames.remove(dirname)


def _clear_publish_scratch():
    for entry in os.listdir(HERE):
        if entry in KEEP:
            continue
        path = os.path.join(HERE, entry)
        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(path)
        print('removed local scratch %s' % path)


def main():
    names = _names()
    _drop_databases(names)
    _remove_filestore(names)
    _remove_pycache()
    if '--publish' in sys.argv:
        _clear_publish_scratch()
    print('local test space cleared for %d cpla databases' % len(names))


if __name__ == '__main__':
    main()
