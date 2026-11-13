"""SQLite domain layer. No UI dependencies; money is stored as integer cents."""
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path
import calendar
import os
import sqlite3
import tempfile

DEFAULT_PATH = Path(__file__).resolve().parents[1] / 'data' / 'household.sqlite3'


@contextmanager
def connect(path=None):
    target = Path(path or os.environ.get('HOUSEHOLD_DB', DEFAULT_PATH))
    target.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(target)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def initialize(path=None):
    with connect(path) as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS members(id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE);
        CREATE TABLE IF NOT EXISTS tasks(id INTEGER PRIMARY KEY, title TEXT NOT NULL,
          owner TEXT NOT NULL DEFAULT '', due TEXT NOT NULL, repeat_days INTEGER NOT NULL DEFAULT 0,
          done INTEGER NOT NULL DEFAULT 0, notes TEXT NOT NULL DEFAULT '');
        CREATE TABLE IF NOT EXISTS bills(id INTEGER PRIMARY KEY, title TEXT NOT NULL,
          cents INTEGER NOT NULL CHECK(cents>=0), due TEXT NOT NULL, monthly INTEGER NOT NULL DEFAULT 0,
          paid INTEGER NOT NULL DEFAULT 0, notes TEXT NOT NULL DEFAULT '');
        CREATE TABLE IF NOT EXISTS shopping(id INTEGER PRIMARY KEY, title TEXT NOT NULL,
          quantity TEXT NOT NULL DEFAULT '1', category TEXT NOT NULL DEFAULT 'Other',
          done INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS inventory(id INTEGER PRIMARY KEY, title TEXT NOT NULL,
          quantity REAL NOT NULL CHECK(quantity>=0), unit TEXT NOT NULL DEFAULT 'items',
          location TEXT NOT NULL DEFAULT '', minimum REAL NOT NULL DEFAULT 0 CHECK(minimum>=0));
        CREATE TABLE IF NOT EXISTS notes(id INTEGER PRIMARY KEY, title TEXT NOT NULL,
          body TEXT NOT NULL DEFAULT '', updated TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        ''')


FIELDS = {
    'members': {'name'},
    'tasks': {'title', 'owner', 'due', 'repeat_days', 'done', 'notes'},
    'bills': {'title', 'cents', 'due', 'monthly', 'paid', 'notes'},
    'shopping': {'title', 'quantity', 'category', 'done'},
    'inventory': {'title', 'quantity', 'unit', 'location', 'minimum'},
    'notes': {'title', 'body', 'updated'},
}


def records(table, path=None):
    if table not in FIELDS:
        raise ValueError('Unknown record type')
    with connect(path) as db:
        return [dict(row) for row in db.execute(f'SELECT * FROM {table} ORDER BY id DESC')]


def save(table, values, record_id=None, path=None):
    if table not in FIELDS or not values or not set(values) <= FIELDS[table]:
        raise ValueError('Invalid fields')
    values = dict(values)
    for field in ('title', 'name'):
        if field in values:
            values[field] = values[field].strip()
            if not values[field]:
                raise ValueError('A name or title is required.')
    if 'due' in values:
        date.fromisoformat(values['due'])
    if values.get('repeat_days', 0) < 0:
        raise ValueError('Repeat interval must be positive.')
    with connect(path) as db:
        if record_id is None:
            cols = ','.join(values)
            marks = ','.join('?' for _ in values)
            return db.execute(f'INSERT INTO {table} ({cols}) VALUES ({marks})', list(values.values())).lastrowid
        db.execute(f'UPDATE {table} SET ' + ','.join(f'{k}=?' for k in values) + ' WHERE id=?', [*values.values(), record_id])
        return record_id


def delete(table, record_id, path=None):
    if table not in FIELDS:
        raise ValueError('Unknown record type')
    with connect(path) as db:
        db.execute(f'DELETE FROM {table} WHERE id=?', (record_id,))


def complete(table, record_id, today=None, path=None):
    """Complete once and create the next occurrence in the same transaction."""
    if table not in ('tasks', 'bills'):
        raise ValueError('Only chores and bills recur')
    today = today or date.today()
    flag = 'done' if table == 'tasks' else 'paid'
    with connect(path) as db:
        row = db.execute(f'SELECT * FROM {table} WHERE id=?', (record_id,)).fetchone()
        if row is None or row[flag]:
            return
        db.execute(f'UPDATE {table} SET {flag}=1 WHERE id=?', (record_id,))
        values = dict(row)
        values.pop('id')
        due = date.fromisoformat(row['due'])
        if table == 'tasks' and row['repeat_days']:
            # Skip missed occurrences instead of generating a backlog.
            step = timedelta(days=row['repeat_days'])
            due += step * max(1, (today - due).days // row['repeat_days'] + 1)
        elif table == 'bills' and row['monthly']:
            month = due.month % 12 + 1
            year = due.year + (due.month == 12)
            due = date(year, month, min(due.day, calendar.monthrange(year, month)[1]))
        else:
            return
        values['due'] = due.isoformat()
        values[flag] = 0
        db.execute(f'INSERT INTO {table} ({",".join(values)}) VALUES ({",".join("?" for _ in values)})', list(values.values()))


def setting(key, value=None, path=None):
    with connect(path) as db:
        if value is not None:
            db.execute('INSERT INTO settings VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', (key, value))
        row = db.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
        return row[0] if row else None


def backup(path=None):
    """Return a consistent SQLite snapshot even when the app is running."""
    with tempfile.TemporaryDirectory() as folder:
        snapshot = Path(folder) / 'backup.sqlite3'
        with connect(path) as source:
            destination = sqlite3.connect(snapshot)
            try:
                source.backup(destination)
            finally:
                destination.close()
        return snapshot.read_bytes()
