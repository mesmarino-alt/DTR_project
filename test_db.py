import os
import sys

# Prevent accidental runs in production environments
if os.environ.get("ALLOW_DB_TEST") != "1":
    print("DB test disabled. Set ALLOW_DB_TEST=1 to run this diagnostic.")
    sys.exit(0)

from helpers import get_db

conn = get_db()
print("Connected successfully!")
cur = conn.cursor()

tables = ['users', 'dtr', 'employees', 'dtr_records', 'tasks']
for t in tables:
    try:
        cur.execute('SELECT COUNT(*) FROM ' + t)
        cnt = cur.fetchone()[0]
        print(f"{t}: {cnt} rows")
    except Exception as e:
        print(f"{t}: ERROR -> {e}")

cur.close()
conn.close()