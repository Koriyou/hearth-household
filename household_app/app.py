"""Household UI, following Beyond's local Streamlit + SQLite architecture."""
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
import sys
from zoneinfo import ZoneInfo
import sqlite3

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from household_app import store

st.set_page_config(page_title='Hearth · Household', page_icon='🏡', layout='wide')
store.initialize()
TODAY = datetime.now(ZoneInfo('Africa/Casablanca')).date()
st.markdown('''<style>
div.block-container{padding-top:2rem;max-width:1250px}
h1,h2,h3{letter-spacing:-.035em} [data-testid="stMetric"]{background:#fffdf7;border:1px solid #dde3d5;border-radius:14px;padding:18px}
[data-testid="stSidebar"]{border-right:1px solid #d9dfd2}
.eyebrow{font-size:12px;letter-spacing:.16em;color:#648174;font-weight:700}
</style>''', unsafe_allow_html=True)


def commit(table, values, record_id=None):
    try:
        store.save(table, values, record_id)
    except (ValueError, sqlite3.IntegrityError) as exc:
        st.error(str(exc))
        return
    st.rerun()


def remove(table, row):
    with st.popover('Delete', use_container_width=True):
        st.write(f'Delete “{row.get("title", row.get("name"))}” permanently?')
        if st.button('Confirm delete', key=f'del-{table}-{row["id"]}', type='primary'):
            store.delete(table, row['id'])
            st.rerun()


def money(cents):
    return f'{cents / 100:,.2f} {store.setting("currency") or "MAD"}'


def due_label(value):
    days = (date.fromisoformat(value) - TODAY).days
    return 'Overdue' if days < 0 else 'Today' if days == 0 else 'Tomorrow' if days == 1 else value


with st.sidebar:
    st.title('🏡 Hearth')
    st.caption('A little order. More room to live.')
    page = st.radio('Your household', ['Overview', 'Chores', 'Bills', 'Shopping', 'Inventory', 'Notes', 'Household & backups'], label_visibility='collapsed')
    st.divider()
    st.caption(TODAY.strftime('%A, %d %B %Y'))
    st.caption('Saved on this computer · Casablanca time')

tasks = store.records('tasks')
bills = store.records('bills')
shopping = store.records('shopping')
inventory = store.records('inventory')
members = [m['name'] for m in store.records('members')]
st.markdown('<p class="eyebrow">HOUSEHOLD / ' + page.upper() + '</p>', unsafe_allow_html=True)

if page == 'Overview':
    st.title('Home, in good order.')
    st.write('A clear view of what needs a little attention.')
    active = sorted([t for t in tasks if not t['done']], key=lambda t: t['due'])
    unpaid = sorted([b for b in bills if not b['paid']], key=lambda b: b['due'])
    low = [i for i in inventory if i['quantity'] <= i['minimum']]
    cols = st.columns(4)
    cols[0].metric('Chores due', sum(t['due'] <= TODAY.isoformat() for t in active))
    cols[1].metric('Unpaid bills', money(sum(b['cents'] for b in unpaid)))
    cols[2].metric('On the shopping list', sum(not s['done'] for s in shopping))
    cols[3].metric('Supplies running low', len(low))
    left, right = st.columns([1.4, 1], gap='large')
    with left:
        st.subheader('Next up')
        if not active:
            st.info('A fresh start. Add your first chore from Chores.')
        for row in active[:8]:
            with st.container(border=True):
                a, b = st.columns([4, 1])
                a.write(f'**{row["title"]}**')
                a.caption(f'{due_label(row["due"])} · {row["owner"] or "Anyone"}')
                if b.button('Done', key=f'overview-task-{row["id"]}'):
                    store.complete('tasks', row['id'], TODAY)
                    st.rerun()
    with right:
        st.subheader('Coming out of the budget')
        if not unpaid:
            st.info('No unpaid bills. Add upcoming payments in Bills.')
        for row in unpaid[:5]:
            with st.container(border=True):
                st.write(f'**{row["title"]}** · {money(row["cents"])}')
                st.caption(due_label(row['due']))
        st.subheader('Restock soon')
        for row in low[:5]:
            st.write(f'• {row["title"]} — {row["quantity"]:g} {row["unit"]}')
        if not low:
            st.caption('No low-stock supplies.')

elif page in ('Chores', 'Bills'):
    is_task = page == 'Chores'
    table, flag = ('tasks', 'done') if is_task else ('bills', 'paid')
    st.title('Share the everyday.' if is_task else 'Stay ahead of the bills.')
    st.caption('Assign chores and repeat the routines that keep home running.' if is_task else 'Track payments and monthly reminders. Marking paid records a payment; it does not move money.')

    def editor(row=None):
        row = row or {}
        rid = row.get('id')
        with st.form(f'{table}-form-{rid}'):
            title = st.text_input('Title', value=row.get('title', ''), max_chars=160)
            a, b = st.columns(2)
            due = a.date_input('Due date', value=date.fromisoformat(row['due']) if 'due' in row else TODAY)
            if is_task:
                owners = ['', *members]
                if row.get('owner') and row['owner'] not in owners:
                    owners.append(row['owner'])
                owner = b.selectbox('Assigned to', owners, index=owners.index(row.get('owner', '')), format_func=lambda x: x or 'Anyone')
                repeat = st.number_input('Repeat every (days; 0 = once)', min_value=0, max_value=3650, value=row.get('repeat_days', 0))
            else:
                amount = b.number_input('Amount', min_value=0.0, value=row.get('cents', 0) / 100, step=1.0, format='%.2f')
                monthly = st.checkbox('Repeat monthly after payment', value=bool(row.get('monthly', 0)))
            notes = st.text_area('Notes', value=row.get('notes', ''))
            if st.form_submit_button('Save changes' if rid else 'Add chore' if is_task else 'Add bill', type='primary'):
                values = {'title': title, 'due': due.isoformat(), 'notes': notes}
                values.update({'owner': owner, 'repeat_days': repeat} if is_task else {'cents': int(Decimal(str(amount)).quantize(Decimal('.01')) * 100), 'monthly': int(monthly)})
                commit(table, values, rid)

    with st.expander('＋ Add chore' if is_task else '＋ Add bill'):
        editor()
    a, b = st.columns([3, 1])
    query = a.text_input('Search', placeholder='Find a chore…' if is_task else 'Find a bill…')
    history = b.checkbox('Show completed' if is_task else 'Show paid')
    rows = tasks if is_task else bills
    visible = [r for r in rows if bool(r[flag]) == history and query.casefold() in (r['title'] + r['notes']).casefold()]
    if not visible:
        st.info('No matching entries. Use the add panel above to get started.')
    for row in sorted(visible, key=lambda r: r['due']):
        with st.container(border=True):
            a, b, c = st.columns([5, 1.4, 1])
            a.subheader(row['title'])
            a.caption(f'{due_label(row["due"])} · ' + (row['owner'] or 'Anyone' if is_task else money(row['cents'])))
            if row['notes']:
                a.write(row['notes'])
            if (row.get('repeat_days') or row.get('monthly')):
                a.caption(f'Repeats every {row["repeat_days"]} days' if is_task else 'Repeats monthly')
            if not row[flag] and b.button('✓ Done' if is_task else 'Mark paid', key=f'complete-{table}-{row["id"]}'):
                store.complete(table, row['id'], TODAY)
                st.rerun()
            with c:
                remove(table, row)
            with st.expander('Edit entry'):
                editor(row)

elif page == 'Shopping':
    st.title('One list. Fewer forgotten things.')
    with st.form('new-shopping', clear_on_submit=True):
        a, b, c = st.columns([3, 1, 2])
        title = a.text_input('Item')
        quantity = b.text_input('Quantity', '1')
        category = c.selectbox('Category', ['Produce', 'Dairy', 'Pantry', 'Household', 'Other'])
        if st.form_submit_button('Add to list', type='primary'):
            commit('shopping', {'title': title, 'quantity': quantity, 'category': category})
    show = st.checkbox('Show purchased items')
    rows = [r for r in shopping if bool(r['done']) == show]
    if not rows:
        st.info('Your list is clear.' if not show else 'No purchased items yet.')
    for category in sorted({r['category'] for r in rows}):
        st.subheader(category)
        for row in [r for r in rows if r['category'] == category]:
            a, b, c = st.columns([5, 1.4, 1])
            a.write(f'**{row["title"]}** · {row["quantity"]}')
            if b.button('Put back' if show else 'Purchased', key=f'shop-{row["id"]}'):
                commit('shopping', {'done': int(not row['done'])}, row['id'])
            with c:
                remove('shopping', row)
    if shopping:
        st.download_button('Download shopping list', '\n'.join(f'{r["quantity"]} × {r["title"]} ({r["category"]})' for r in shopping if not r['done']), 'shopping-list.txt')

elif page == 'Inventory':
    st.title('Know what’s already at home.')
    st.caption('Track supplies by location and add low-stock items to your shopping list.')

    def stock_editor(row=None):
        row = row or {}
        rid = row.get('id')
        with st.form(f'stock-{rid}'):
            title = st.text_input('Supply', row.get('title', ''))
            a, b, c = st.columns(3)
            quantity = a.number_input('Quantity on hand', min_value=0.0, value=float(row.get('quantity', 0)))
            unit = b.text_input('Unit', row.get('unit', 'items'))
            minimum = c.number_input('Restock at or below', min_value=0.0, value=float(row.get('minimum', 0)))
            location = st.text_input('Location', row.get('location', ''))
            if st.form_submit_button('Save supply', type='primary'):
                commit('inventory', dict(title=title, quantity=quantity, unit=unit, minimum=minimum, location=location), rid)

    with st.expander('＋ Add supply'):
        stock_editor()
    search = st.text_input('Search supplies', placeholder='Name or location')
    low_only = st.checkbox('Only low stock')
    visible = [r for r in inventory if search.casefold() in (r['title'] + r['location']).casefold() and (not low_only or r['quantity'] <= r['minimum'])]
    if not visible:
        st.info('No supplies to show. Add your first supply above.')
    for row in visible:
        with st.expander(f'{"🟠" if row["quantity"] <= row["minimum"] else "🟢"} {row["title"]} · {row["quantity"]:g} {row["unit"]} · {row["location"]}'):
            if st.button('Add to shopping list', key=f'restock-{row["id"]}'):
                if any(s['title'].casefold() == row['title'].casefold() and not s['done'] for s in shopping):
                    st.info('Already on your shopping list.')
                else:
                    commit('shopping', {'title': row['title'], 'quantity': f'1 {row["unit"]}', 'category': 'Household'})
            stock_editor(row)
            remove('inventory', row)

elif page == 'Notes':
    st.title('The things worth remembering.')
    st.caption('House instructions, plans, contacts, and useful details in one place.')

    def note_editor(row=None):
        row = row or {}
        with st.form(f'note-{row.get("id")}'):
            title = st.text_input('Title', row.get('title', ''))
            body = st.text_area('Note', row.get('body', ''), height=200)
            if st.form_submit_button('Save note', type='primary'):
                commit('notes', {'title': title, 'body': body, 'updated': datetime.now(ZoneInfo('Africa/Casablanca')).isoformat(timespec='seconds')}, row.get('id'))
    with st.expander('＋ New note'):
        note_editor()
    query = st.text_input('Search notes')
    rows = [r for r in store.records('notes') if query.casefold() in (r['title'] + r['body']).casefold()]
    if not rows:
        st.info('No notes yet. Make room for the details you want to keep.')
    for row in rows:
        with st.container(border=True):
            st.subheader(row['title'])
            st.text(row['body'])
            st.caption('Updated ' + row['updated'][:16].replace('T', ' '))
            with st.expander('Edit note'):
                note_editor(row)
            remove('notes', row)

else:
    st.title('Make yourself at home.')
    left, right = st.columns(2, gap='large')
    with left:
        st.subheader('Household members')
        with st.form('member', clear_on_submit=True):
            name = st.text_input('Name')
            if st.form_submit_button('Add member'):
                commit('members', {'name': name})
        for row in store.records('members'):
            a, b = st.columns([3, 1])
            a.write(row['name'])
            with b:
                remove('members', row)
        st.caption('Removing a member keeps their name on existing chores.')
    with right:
        st.subheader('Preferences')
        with st.form('preferences'):
            currency = st.text_input('Currency label', store.setting('currency') or 'MAD', max_chars=10)
            if st.form_submit_button('Save preferences'):
                if currency.strip():
                    store.setting('currency', currency.strip())
                    st.rerun()
                st.error('Enter a currency label.')
        st.caption('The label applies to all amounts. It does not convert existing values.')
        st.subheader('Keep a copy')
        st.write('Download a complete database backup, including notes, chores, and payment history.')
        st.download_button('Download database backup', store.backup(), f'household-{TODAY}.sqlite3', 'application/vnd.sqlite3')
        st.caption('Restore instructions are in README.md. Data stays in the data folder on this computer.')
