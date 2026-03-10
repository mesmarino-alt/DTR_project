import psycopg2
import os
from datetime import datetime, timedelta
from psycopg2.extras import RealDictCursor

TESTING_MODE = False

# ---------- Office Hours Config ----------
OFFICE_START_HOUR = 7
OFFICE_END_HOUR = 19


# ---------- Database Connection ----------
def get_db():
    # Prefer a full DATABASE_URL if provided (e.g. from Render or Supabase)
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        conn = psycopg2.connect(db_url, cursor_factory=RealDictCursor)
        return conn

    # Otherwise read individual environment variables with sensible defaults
    conn = psycopg2.connect(
        host=os.environ.get("DB_HOST", "aws-1-ap-northeast-1.pooler.supabase.com"),
        database=os.environ.get("DB_NAME", "postgres"),
        user=os.environ.get("DB_USER", "postgres.gkdbzfrzyalndahgulsm"),
        password=os.environ.get("DB_PASS", "edizonmarino_112717"),
        port=int(os.environ.get("DB_PORT", 6543)),
        cursor_factory=RealDictCursor
    )
    return conn


# ---------- Time Utilities ----------
def get_manila_now():
    """Return current datetime in Asia/Manila (UTC+8)."""
    return datetime.utcnow() + timedelta(hours=8)


def calculate_hours(time_in_str, time_out_str):
    """Calculate total hours between time_in and time_out strings (HH:MM)."""
    try:
        fmt = "%H:%M"
        t_in = datetime.strptime(time_in_str, fmt)
        t_out = datetime.strptime(time_out_str, fmt)
        diff = t_out - t_in

        if diff.total_seconds() < 0:
            return 0.0

        return round(diff.total_seconds() / 3600, 2)

    except (ValueError, TypeError):
        return 0.0


# ---------- Record Checks ----------
def record_exists_for_date(user_id, date_str, is_test=False):
    """Check if a DTR record already exists for a given date."""
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT id FROM dtr WHERE user_id = %s AND date = %s AND is_test = %s",
        (user_id, date_str, is_test)
    )

    row = cur.fetchone()

    cur.close()
    conn.close()

    return row is not None


# ---------- Insert Manual Record ----------
def insert_manual_record(user_id, date_str, time_in, time_out, tasks_list):
    """
    Insert a manual DTR record with associated tasks.
    Returns (success: bool, message: str).
    """

    is_test = True if TESTING_MODE else False

    if record_exists_for_date(user_id, date_str, is_test):
        return False, f"Record for {date_str} already exists."

    hours = calculate_hours(time_in, time_out)

    # Convert HH:MM to 12-hour format
    try:
        time_in_12 = datetime.strptime(time_in, "%H:%M").strftime("%I:%M %p")
        time_out_12 = datetime.strptime(time_out, "%H:%M").strftime("%I:%M %p")
    except ValueError:
        time_in_12 = time_in
        time_out_12 = time_out

    now = get_manila_now()

    conn = get_db()
    cur = conn.cursor()

    try:
        # Check if the employee exists
        cur.execute(
            "SELECT id FROM employees WHERE id = %s",
            (user_id,)
        )
        employee = cur.fetchone()

        if not employee:
            cur.close()
            conn.close()
            return False, f"Employee with ID {user_id} does not exist. Please add the employee first."

        # Insert into dtr_records
        cur.execute(
            """
            INSERT INTO dtr_records
            (employee_id, date, time_in, time_out, hours, is_manual, testing)
            VALUES (%s,%s,%s,%s,%s,TRUE,%s)
            RETURNING id
            """,
            (
                user_id,
                date_str,
                time_in_12,
                time_out_12,
                hours,
                is_test
            )
        )

        rec_row = cur.fetchone()
        record_id = rec_row['id'] if isinstance(rec_row, dict) else rec_row[0]

        # Insert into the DTR table for backward compatibility
        cur.execute(
            """
            INSERT INTO dtr
            (user_id, date, time_in, time_out, total_hours, activities, created_at, is_test, is_manual)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,TRUE)
            RETURNING id
            """,
            (
                user_id,
                date_str,
                time_in_12,
                time_out_12,
                hours,
                "",
                now.strftime("%Y-%m-%d %H:%M:%S"),
                is_test
            )
        )

        # Optionally get the dtr id (not required)
        try:
            dtr_row = cur.fetchone()
            dtr_id = dtr_row['id'] if isinstance(dtr_row, dict) else (dtr_row[0] if dtr_row else None)
        except Exception:
            dtr_id = None

        # Insert tasks
        task_count = 0
        for task in tasks_list:
            task = task.strip()

            if task:
                cur.execute(
                    "INSERT INTO tasks (record_id, task_description) VALUES (%s,%s)",
                    (record_id, task)
                )
                task_count += 1

        # Save tasks as activities (for dtr table)
        activities_text = "\n".join(
            ["• " + t.strip() for t in tasks_list if t.strip()]
        )

        if activities_text and dtr_id:
            cur.execute(
                "UPDATE dtr SET activities = %s WHERE id = %s",
                (activities_text, dtr_id)
            )

        conn.commit()

        cur.close()
        conn.close()

        return True, f"Record for {date_str} saved successfully ({hours} hours, {task_count} tasks)."

    except Exception as e:
        conn.rollback()
        cur.close()
        conn.close()
        return False, f"Error saving record: {str(e)}"


# ---------- Fetch Tasks ----------
def get_tasks_for_record(record_id):
    """Get all tasks for a specific DTR record."""
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT * FROM tasks WHERE record_id = %s ORDER BY id",
        (record_id,)
    )

    tasks = cur.fetchall()

    cur.close()
    conn.close()

    return tasks
