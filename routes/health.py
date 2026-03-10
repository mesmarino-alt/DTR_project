from flask import Blueprint, jsonify
import psycopg2.extras
from helpers import get_db, TESTING_MODE

health_bp = Blueprint('health', __name__)


@health_bp.route('/health')
def health():
    conn = None
    cur = None
    result = {"db": {"ok": False}, "testing_mode": bool(TESTING_MODE)}
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        # basic connectivity
        cur.execute('SELECT 1 AS ok')
        cur.fetchone()

        # runtime info
        cur.execute('SELECT current_database() AS database, current_user AS user')
        info = cur.fetchone()
        if isinstance(info, dict):
            result['db']['database'] = info.get('database')
            result['db']['user'] = info.get('user')
        else:
            result['db']['database'] = info[0]
            result['db']['user'] = info[1]

        # check essential tables
        essential = ['users','dtr','employees','dtr_records','tasks']
        cur.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema=%s AND table_name = ANY(%s)",
            ('public', essential)
        )
        found = [r['table_name'] if isinstance(r, dict) else r[0] for r in cur.fetchall()]
        result['db']['tables_found'] = found
        result['db']['ok'] = True
        status = 200
    except Exception as e:
        result['error'] = str(e)
        status = 503
    finally:
        if cur:
            try:
                cur.close()
            except Exception:
                pass
        if conn:
            try:
                conn.close()
            except Exception:
                pass
    return jsonify(result), status