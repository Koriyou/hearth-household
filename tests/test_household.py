import os
from datetime import date
from pathlib import Path
import sqlite3
import tempfile
import unittest

from household_app import store
from streamlit.testing.v1 import AppTest


class HouseholdTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'home.sqlite3'
        self.previous = os.environ.get('HOUSEHOLD_DB')
        os.environ['HOUSEHOLD_DB'] = str(self.path)
        store.initialize()

    def tearDown(self):
        if self.previous is None:
            os.environ.pop('HOUSEHOLD_DB', None)
        else:
            os.environ['HOUSEHOLD_DB'] = self.previous
        self.temp.cleanup()

    def test_recurring_chore_skips_missed_days_and_is_idempotent(self):
        rid = store.save('tasks', dict(title='Laundry', due='2026-11-01', repeat_days=7))
        store.complete('tasks', rid, date(2026, 11, 12))
        store.complete('tasks', rid, date(2026, 11, 12))
        rows = store.records('tasks')
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['due'], '2026-11-15')
        self.assertEqual(rows[1]['done'], 1)

    def test_monthly_bill_and_backup(self):
        rid = store.save('bills', dict(title='Utilities', cents=12345, due='2026-01-31', monthly=1))
        store.complete('bills', rid)
        rows = store.records('bills')
        self.assertEqual(rows[0]['due'], '2026-02-28')
        self.assertEqual(rows[0]['cents'], 12345)
        snapshot = Path(self.temp.name) / 'backup.sqlite3'
        snapshot.write_bytes(store.backup())
        with sqlite3.connect(snapshot) as db:
            self.assertEqual(db.execute('SELECT SUM(paid) FROM bills').fetchone()[0], 1)

    def test_validation_and_persistence(self):
        with self.assertRaises(ValueError):
            store.save('notes', dict(title='  ', body=''))
        with self.assertRaises(sqlite3.IntegrityError):
            store.save('inventory', dict(title='Soap', quantity=-1))
        rid = store.save('shopping', dict(title='Milk', quantity='2 litres'))
        store.save('shopping', {'done': 1}, rid)
        self.assertEqual(store.records('shopping')[0]['done'], 1)
        store.delete('shopping', rid)
        self.assertEqual(store.records('shopping'), [])

    def test_all_pages_and_add_complete_chore(self):
        app = AppTest.from_file('household_app/app.py').run()
        self.assertFalse(app.exception)

    def test_populated_pages(self):
        store.save('members', {'name': 'Alex'})
        store.save('tasks', dict(title='Dishes', owner='Alex', due='2026-11-12', repeat_days=1))
        store.save('bills', dict(title='Rent', cents=400000, due='2026-12-01', monthly=1))
        store.save('inventory', dict(title='Soap', quantity=1, minimum=2, location='Bathroom'))
        store.save('shopping', dict(title='Milk', quantity='2', category='Dairy'))
        store.save('notes', dict(title='House guide', body='Water plants weekly', updated='2026-11-12T12:00:00'))
        app = AppTest.from_file('household_app/app.py').run()
        for page in ['Overview', 'Chores', 'Bills', 'Shopping', 'Inventory', 'Notes', 'Household & backups']:
            app.sidebar.radio[0].set_value(page).run()
            self.assertFalse(app.exception, page)
        for page in ['Chores', 'Bills', 'Shopping', 'Inventory', 'Notes', 'Household & backups', 'Overview']:
            app.sidebar.radio[0].set_value(page).run()
            self.assertFalse(app.exception, page)
        app.sidebar.radio[0].set_value('Chores').run()
        app.text_input[0].set_value('Clean kitchen')
        app.button[0].click().run()
        self.assertFalse(app.exception)
        self.assertEqual(store.records('tasks')[0]['title'], 'Clean kitchen')
        done = next(b for b in app.button if b.key == f'complete-tasks-{store.records("tasks")[0]["id"]}')
        done.click().run()
        self.assertEqual(next(row for row in store.records('tasks') if row['title'] == 'Clean kitchen')['done'], 1)
        self.assertFalse(app.exception)


if __name__ == '__main__':
    unittest.main()
