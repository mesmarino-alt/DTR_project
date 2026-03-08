from datetime import datetime, timedelta
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user

from helpers import get_db, get_manila_now, OFFICE_START_HOUR, OFFICE_END_HOUR, TESTING_MODE

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route("/dashboard")
@login_required
def dashboard():
    now = get_manila_now()
    today_str = now.strftime("%Y-%m-%d")
    test_flag = 1 if TESTING_MODE else 0

    conn = get_db()

    today_record = conn.execute(
        "SELECT * FROM dtr WHERE user_id=? AND date=? AND is_test=?",
        (current_user.id, today_str, test_flag)
    ).fetchone()

    records = conn.execute(
        "SELECT * FROM dtr WHERE user_id=? AND is_test=? ORDER BY date DESC LIMIT 15",
        (current_user.id, test_flag)
    ).fetchall()

    week_start = now - timedelta(days=now.weekday())
    week_start_str = week_start.strftime("%Y-%m-%d")
    week_end_str = (week_start + timedelta(days=6)).strftime("%Y-%m-%d")

    weekly_records = conn.execute(
        "SELECT * FROM dtr WHERE user_id=? AND date >= ? AND date <= ? AND is_test=? ORDER BY date ASC",
        (current_user.id, week_start_str, week_end_str, test_flag)
    ).fetchall()

    total_weekly_hours = sum(r["total_hours"] for r in weekly_records if r["total_hours"])
    days_worked = sum(1 for r in weekly_records if r["total_hours"])
    avg_hours = round(total_weekly_hours / days_worked, 2) if days_worked > 0 else 0

    conn.close()

    return render_template("dashboard.html",
        today=today_record,
        records=records,
        weekly_records=weekly_records,
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
    existing = conn.execute(
        "SELECT * FROM dtr WHERE user_id=? AND date=? AND is_test=?",
        (current_user.id, today_str, test_flag)
    ).fetchone()

    if existing:
        flash("⚠️ You have already timed in today. You cannot time in twice.")
    else:
        conn.execute(
            "INSERT INTO dtr (user_id, date, time_in, created_at, is_test) VALUES (?, ?, ?, ?, ?)",
            (current_user.id, today_str, time_str, now.strftime("%Y-%m-%d %H:%M:%S"), test_flag)
        )
        conn.commit()
        prefix = "🧪 [TEST] " if TESTING_MODE else ""
        flash(f"✅ {prefix}Time In recorded successfully at {time_str}")

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
    existing = conn.execute(
        "SELECT * FROM dtr WHERE user_id=? AND date=? AND is_test=?",
        (current_user.id, today_str, test_flag)
    ).fetchone()

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

        conn.execute(
            "UPDATE dtr SET time_out=?, total_hours=? WHERE id=?",
            (time_str, total, existing["id"])
        )
        conn.commit()
        prefix = "🧪 [TEST] " if TESTING_MODE else ""
        flash(f"✅ {prefix}Time Out recorded successfully at {time_str}. Total: {total} hrs")

    conn.close()
    return redirect(url_for("dashboard.dashboard"))


@dashboard_bp.route("/delete-record/<int:record_id>", methods=["POST"])
@login_required
def delete_record(record_id):
    conn = get_db()
    record = conn.execute(
        "SELECT * FROM dtr WHERE id=? AND user_id=?",
        (record_id, current_user.id)
    ).fetchone()

    if record:
        conn.execute("DELETE FROM dtr WHERE id=? AND user_id=?", (record_id, current_user.id))
        conn.commit()
        flash("Record deleted successfully!")
    else:
        flash("Record not found.")

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
    existing = conn.execute(
        "SELECT * FROM dtr WHERE user_id=? AND date=? AND is_test=?",
        (current_user.id, today_str, test_flag)
    ).fetchone()

    if existing:
        conn.execute(
            "UPDATE dtr SET activities=? WHERE id=?",
            (activities, existing["id"])
        )
        conn.commit()
        flash("✅ Activities saved successfully!")
    else:
        flash("⚠️ No DTR record found for today. Please Time In first.")

    conn.close()
    return redirect(url_for("dashboard.dashboard"))
