from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from helpers import (
    get_manila_now, insert_manual_record, TESTING_MODE,
    get_db, get_tasks_for_record
)
import psycopg2
import psycopg2.extras

manual_entry_bp = Blueprint("manual_entry", __name__, url_prefix="/dashboard")


@manual_entry_bp.route("/manual-entry", methods=["GET"])
@login_required
def manual_entry_form():
    """Redirect to dashboard where the modal lives."""
    return redirect(url_for("dashboard.dashboard"))


@manual_entry_bp.route("/manual-entry", methods=["POST"])
@login_required
def manual_entry_submit():
    """Process the manual record entry form."""
    user_id = current_user.id
    date_str = request.form.get("date", "").strip()
    time_in = request.form.get("time_in", "").strip()
    time_out = request.form.get("time_out", "").strip()
    tasks_list = request.form.getlist("tasks")

    # Validation
    if not date_str:
        flash("Date is required.", "danger")
        return redirect(url_for("dashboard.dashboard"))

    if not time_in or not time_out:
        flash("Both Time In and Time Out are required.", "danger")
        return redirect(url_for("dashboard.dashboard"))

    # Prevent future dates
    today = get_manila_now().strftime("%Y-%m-%d")
    if date_str > today:
        flash("Manual entry is only for past dates. Use Time In/Out for today.", "warning")
        return redirect(url_for("dashboard.dashboard"))

    success, message = insert_manual_record(user_id, date_str, time_in, time_out, tasks_list)

    if success:
        flash(message, "success")
    else:
        flash(message, "danger")

    return redirect(url_for("dashboard.dashboard"))


@manual_entry_bp.route("/manual-entry/history")
@login_required
def manual_entry_history():
    """Show all manual entries."""
    user_id = current_user.id
    is_test = 1 if TESTING_MODE else 0

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """SELECT * FROM dtr
           WHERE user_id = %s AND is_manual = 1 AND is_test = %s
           ORDER BY date DESC""",
        (user_id, is_test)
    )
    records = cur.fetchall()

    cur.close()
    conn.close()

    # Attach tasks to each record
    records_with_tasks = []
    for record in records:
        tasks = get_tasks_for_record(record["id"])
        records_with_tasks.append({
            "record": record,
            "tasks": tasks
        })

    return render_template("history.html", records=records_with_tasks)