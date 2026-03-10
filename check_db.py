import os
import sys

# Prevent accidental runs in production environments
if os.environ.get("ALLOW_DB_TEST") != "1":
    print("DB diagnostics disabled. Set ALLOW_DB_TEST=1 to run this script.")
    sys.exit(0)

from helpers import get_db
import traceback
from psycopg2 import sql

conn = get_db()
cur = conn.cursor()

print("Connected successfully to:")
try:
    cur.execute("SELECT current_database(), current_user, inet_server_addr();")
    dbinfo = cur.fetchone()
    print("Database info:", dbinfo)
except Exception as e:
    print("Could not fetch DB info:", repr(e))
    print(traceback.format_exc())

print('\nPublic tables:')
try:
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema=%s ORDER BY table_name", ('public',))
    tables_rows = cur.fetchall()
    tables = [row.get('table_name') if isinstance(row, dict) else next(iter(row.values())) for row in tables_rows]
    for t in tables:
        print('-', t)
except Exception as e:
    print('Error listing tables:', repr(e))
    print(traceback.format_exc())

keys = ['users', 'dtr', 'employees', 'dtr_records', 'tasks']
for t in keys:
    try:
        cur.execute(sql.SQL("SELECT COUNT(*) AS cnt FROM {};").format(sql.Identifier(t)))
        row = cur.fetchone()
        # row may be a mapping (RealDictRow) or tuple
        if isinstance(row, dict):
            cnt = row.get('cnt') or next(iter(row.values()))
        else:
            cnt = row[0]
        print(f"{t}: {cnt} rows")
        if cnt and int(cnt) > 0:
            cur.execute(sql.SQL("SELECT * FROM {} ORDER BY id DESC LIMIT 3;").format(sql.Identifier(t)))
            rows = cur.fetchall()
            # normalize rows to dicts for display
            norm = [dict(r) if hasattr(r, 'keys') else r for r in rows]
            print('  sample:', norm)
    except Exception as e:
        print(f"{t}: ERROR -> {repr(e)}")
        print(traceback.format_exc())

cur.close()
conn.close()