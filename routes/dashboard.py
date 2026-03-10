from datetime import datetime, timedelta
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
import psycopg2
import psycopg2.extras

from helpers import get_db, get_manila_now, OFFICE_START_HOUR, OFFICE_END_HOUR, TESTING_MODE

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route("/dashboard")
@login_required
def dashboard():
    now = get_manila_now()
    today_str = now.strftime("%Y-%m-%d")
    test_flag = True if TESTING_MODE else False

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT * FROM dtr WHERE user_id = %s AND date = %s AND is_test = %s",
        (current_user.id, today_str, test_flag)
    )
    today_record = cur.fetchone()

    cur.execute(
        "SELECT * FROM dtr WHERE user_id = %s AND is_test = %s ORDER BY date DESC LIMIT 15",
        (current_user.id, test_flag)
    )
    records = cur.fetchall()

    # --- Normalize dates and weekdays server-side for template rendering ---
    def _normalize_records(records_list):
        processed = []
        for r in records_list:
            # r may be a RealDictCursor row; copy to avoid mutating shared objects
            rec = dict(r)
            d = rec.get("date")
            date_obj = None
            if d is None:
                date_iso = None
            else:
                # date may come as date/datetime or string
                try:
                    # If already a date/datetime
                    if hasattr(d, 'isoformat'):
                        date_obj = d if getattr(d, 'day', None) else None
                        # If it's datetime, convert to date
                        if hasattr(d, 'date') and not isinstance(d, str):
                            try:
                                date_obj = d if isinstance(d, type(d).today()) else d
                            except Exception:
                                date_obj = d
                    # Try parsing string
                    if isinstance(d, str):
                        try:
                            date_obj = datetime.strptime(d, "%Y-%m-%d").date()
                        except Exception:
                            try:
                                date_obj = datetime.strptime(d, "%Y-%m-%d %H:%M:%S").date()
                            except Exception:
                                date_obj = None
                except Exception:
                    date_obj = None

                date_iso = date_obj.isoformat() if date_obj else (d if isinstance(d, str) else None)

            # Build display strings
            if date_iso:
                try:
                    dt = datetime.strptime(date_iso, "%Y-%m-%d")
                    display_date = dt.strftime("%b %d")
                    weekday = dt.strftime("%a")
                except Exception:
                    display_date = date_iso
                    weekday = ""
            else:
                display_date = ""
                weekday = ""

            rec["date"] = date_iso
            rec["display_date"] = display_date
            rec["weekday"] = weekday
            processed.append(rec)
        return processed

    processed_records = _normalize_records(records)

    week_start = now - timedelta(days=now.weekday())
    week_start_str = week_start.strftime("%Y-%m-%d")
    week_end_str = (week_start + timedelta(days=6)).strftime("%Y-%m-%d")

    cur.execute(
        "SELECT * FROM dtr WHERE user_id = %s AND date >= %s AND date <= %s AND is_test = %s ORDER BY date ASC",
        (current_user.id, week_start_str, week_end_str, test_flag)
    )
    weekly_records = cur.fetchall()

    processed_weekly = _normalize_records(weekly_records)

    total_weekly_hours = sum(r["total_hours"] for r in processed_weekly if r["total_hours"])
    days_worked = sum(1 for r in processed_weekly if r["total_hours"])
    avg_hours = round(total_weekly_hours / days_worked, 2) if days_worked > 0 else 0

    cur.close()
    conn.close()

    return render_template("dashboard.html",
        today=today_record,
        records=processed_records,
        weekly_records=processed_weekly,
        total_weekly_hours=round(total_weekly_hours, 2),
        days_worked=days_worked,
        avg_hours=avg_hours,
        now=now,
        today_str=today_str,
        week_start_str=week_start_str,
        week_end_str=week_end_str,
        office_start=OFFICE_START_HOUR,
        office_end=OFFICE_END_HOUR,
        is_weekend=now.weekday() in (5, 6),
        testing_mode=TESTING_MODE
    )


@dashboard_bp.route("/time-in", methods=["POST"])
@login_required
def time_in():
    now = get_manila_now()
    today_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%I:%M %p")
    test_flag = 1 if TESTING_MODE else 0

    # Only enforce restrictions in production mode
    if not TESTING_MODE:
        if now.weekday() in (5, 6):
            day_name = "Saturday" if now.weekday() == 5 else "Sunday"
            flash(f"⚠️ Time In is disabled on {day_name}. Office is closed on weekends.")
            return redirect(url_for("dashboard.dashboard"))

        if now.hour < OFFICE_START_HOUR or now.hour >= OFFICE_END_HOUR:
            flash("⚠️ Time In is only allowed between 7:00 AM – 7:00 PM.")
            return redirect(url_for("dashboard.dashboard"))

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute(
        "SELECT * FROM dtr WHERE user_id = %s AND date = %s AND is_test = %s",
        (current_user.id, today_str, test_flag)
    )
    existing = cur.fetchone()

    if existing:
        flash("⚠️ You have already timed in today. You cannot time in twice.")
    else:
        cur.execute(
            "INSERT INTO dtr (user_id, date, time_in, created_at, is_test) VALUES (%s, %s, %s, %s, %s)",
            (current_user.id, today_str, time_str, now.strftime("%Y-%m-%d %H:%M:%S"), test_flag)
        )
        conn.commit()

    cur.close()
    conn.close()
    return redirect(url_for("dashboard.dashboard"))


@dashboard_bp.route("/time-out", methods=["POST"])
@login_required
def time_out():
    now = get_manila_now()
    today_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%I:%M %p")
    test_flag = 1 if TESTING_MODE else 0

    # Only enforce restrictions in production mode
    if not TESTING_MODE:
        if now.weekday() in (5, 6):
            day_name = "Saturday" if now.weekday() == 5 else "Sunday"
            flash(f"⚠️ Time Out is disabled on {day_name}. Office is closed on weekends.")
            return redirect(url_for("dashboard.dashboard"))

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute(
        "SELECT * FROM dtr WHERE user_id = %s AND date = %s AND is_test = %s",
        (current_user.id, today_str, test_flag)
    )
    existing = cur.fetchone()

    if not existing or not existing["time_in"]:
        flash("⚠️ You must Time In first before Timing Out.")
    elif existing["time_out"]:
        flash("⚠️ You have already timed out today. You cannot time out twice.")
    else:
        fmt = "%I:%M %p"
        t_in = datetime.strptime(existing["time_in"], fmt)
        t_out = datetime.strptime(time_str, fmt)
        diff = (t_out - t_in).total_seconds() / 3600
        total = round(max(diff, 0), 2)

        cur.execute(
            "UPDATE dtr SET time_out = %s, total_hours = %s WHERE id = %s",
            (time_str, total, existing["id"])
        )
        conn.commit()

    cur.close()
    conn.close()
    return redirect(url_for("dashboard.dashboard"))


@dashboard_bp.route("/delete-record/<int:record_id>", methods=["POST"])
@login_required
def delete_record(record_id):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute(
        "SELECT * FROM dtr WHERE id = %s AND user_id = %s",
        (record_id, current_user.id)
    )
    record = cur.fetchone()

    if record:
        cur.execute("DELETE FROM dtr WHERE id = %s AND user_id = %s", (record_id, current_user.id))
        conn.commit()
        flash("Record deleted successfully!")
    else:
        flash("Record not found.")

    cur.close()
    conn.close()
    return redirect(url_for("dashboard.dashboard"))


@dashboard_bp.route("/save-activities", methods=["POST"])
@login_required
def save_activities():
    now = get_manila_now()
    today_str = now.strftime("%Y-%m-%d")
    activities = request.form.get("activities", "").strip()
    test_flag = 1 if TESTING_MODE else 0

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute(
        "SELECT * FROM dtr WHERE user_id = %s AND date = %s AND is_test = %s",
        (current_user.id, today_str, test_flag)
    )
    existing = cur.fetchone()

    if existing:
        cur.execute(
            "UPDATE dtr SET activities = %s WHERE id = %s",
            (activities, existing["id"])
        )
        conn.commit()
        flash("✅ Activities saved successfully!")
    else:
        flash("⚠️ No DTR record found for today. Please Time In first.")

    cur.close()
    conn.close()
    return redirect(url_for("dashboard.dashboard"))
