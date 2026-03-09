import sqlite3
from datetime import datetime, timedelta

TESTING_MODE = True  # Set to True to enable test mode (separate DTR records)

# ---------- Office Hours Config ----------
OFFICE_START_HOUR = 7   # 7:00 AM (early time-in allowed)
OFFICE_END_HOUR = 19    # 7:00 PM (overtime allowed)


def get_db():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn


def get_manila_now():
    """Return current datetime in Asia/Manila (UTC+8)."""
    return datetime.utcnow() + timedelta(hours=8)


def calculate_hours(time_in_str, time_out_str):
    """Calculate total hours between time_in and time_out strings (HH:MM format like 08:00)."""
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


def record_exists_for_date(user_id, date_str, is_test=0):
    """Check if a DTR record already exists for a given date."""
    db = get_db()
    row = db.execute(
        "SELECT id FROM dtr WHERE user_id = ? AND date = ? AND is_test = ?",
        (user_id, date_str, is_test)
    ).fetchone()
    db.close()
    return row is not None


def insert_manual_record(user_id, date_str, time_in, time_out, tasks_list):
    """
    Insert a manual DTR record with associated tasks.
    Returns (success: bool, message: str).
    """
    is_test = 1 if TESTING_MODE else 0

    if record_exists_for_date(user_id, date_str, is_test):
        return False, f"Record for {date_str} already exists."

    hours = calculate_hours(time_in, time_out)

    # Convert HH:MM to 12-hour format (e.g. "08:00" -> "08:00 AM") to match dashboard records
    try:
        time_in_12 = datetime.strptime(time_in, "%H:%M").strftime("%I:%M %p")
        time_out_12 = datetime.strptime(time_out, "%H:%M").strftime("%I:%M %p")
    except ValueError:
        time_in_12 = time_in
        time_out_12 = time_out

    now = get_manila_now()

    db = get_db()
    try:
        cursor = db.execute(
            """INSERT INTO dtr (user_id, date, time_in, time_out, total_hours, activities, created_at, is_test, is_manual)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)""",
            (user_id, date_str, time_in_12, time_out_12, hours,
             "", now.strftime("%Y-%m-%d %H:%M:%S"), is_test)
        )
        record_id = cursor.lastrowid

        # Insert tasks
        task_count = 0
        for task in tasks_list:
            task = task.strip()
            if task:
                db.execute(
                    "INSERT INTO tasks (record_id, task_description) VALUES (?, ?)",
                    (record_id, task)
                )
                task_count += 1

        # Also save tasks as activities text (so weekly/monthly reports pick them up)
        activities_text = "\n".join(["• " + t.strip() for t in tasks_list if t.strip()])
        if activities_text:
            db.execute("UPDATE dtr SET activities = ? WHERE id = ?", (activities_text, record_id))

        db.commit()
        return True, f"Record for {date_str} saved successfully ({hours} hours, {task_count} tasks)."
    except Exception as e:
        db.rollback()
        return False, f"Error saving record: {str(e)}"
    finally:
        db.close()


def get_tasks_for_record(record_id):
    """Get all tasks for a specific DTR record."""
    db = get_db()
    tasks = db.execute(
        "SELECT * FROM tasks WHERE record_id = ? ORDER BY id",
        (record_id,)
    ).fetchall()
    db.close()
    return tasks

#generate_weekly_accomplishment
def generate_weekly_accomplishment(user_id, week_start_date=None):
    """
    Build a weekly accomplishment summary for the given user and week.
    - week_start_date: None (use current Manila week starting Monday) or "YYYY-MM-DD" or datetime.date/datetime.
    - Returns (start_date_str, end_date_str, accomplishment_text)
    """
    is_test = 1 if TESTING_MODE else 0

    # determine week start (Monday) and end (Sunday) in Manila time
    if week_start_date is None:
        now = get_manila_now()
        week_start = (now - timedelta(days=now.weekday())).date()
    elif isinstance(week_start_date, str):
        try:
            week_start = datetime.strptime(week_start_date, "%Y-%m-%d").date()
        except ValueError:
            raise ValueError("week_start_date must be YYYY-MM-DD when passed as string")
    elif isinstance(week_start_date, datetime):
        week_start = week_start_date.date()
    else:
        week_start = week_start_date  # assume date-like

    week_end = week_start + timedelta(days=6)
    start_str = week_start.strftime("%Y-%m-%d")
    end_str = week_end.strftime("%Y-%m-%d")

    db = get_db()
    try:
        rows = db.execute(
            "SELECT * FROM dtr WHERE user_id = ? AND date BETWEEN ? AND ? AND is_test = ? ORDER BY date",
            (user_id, start_str, end_str, is_test)
        ).fetchall()

        if not rows:
            return start_str, end_str, "No records found for this week."

        lines = []
        for r in rows:
            date = r["date"]
            time_in = r.get("time_in") or ""
            time_out = r.get("time_out") or ""
            hours = r.get("total_hours") or 0
            activities = r.get("activities") or ""

            # If activities is empty, pull tasks for the record (keeps older task entries)
            if not activities:
                tasks = get_tasks_for_record(r["id"])
                if tasks:
                    activities = "\n".join("• " + t["task_description"] for t in tasks)

            day_block = f"{date} — {hours}h\n{activities}".strip()
            lines.append(day_block)

        accomplishment_text = "\n\n".join(lines)
        return start_str, end_str, accomplishment_text
    finally:
        db.close()
