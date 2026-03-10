import io
import calendar
from datetime import datetime, timedelta
from flask import Blueprint, render_template, send_file, request, jsonify
from flask_login import login_required, current_user
from fpdf import FPDF
import psycopg2
import psycopg2.extras

from helpers import get_db, get_manila_now, TESTING_MODE

reports_bp = Blueprint('reports', __name__)


def sanitize_for_pdf(text):
    """Replace Unicode characters that Helvetica cannot render with ASCII equivalents."""
    replacements = {
        "\u2014": "--",
        "\u2013": "-",
        "\u2022": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2026": "...",
        "\u00b7": "-",
    }
    for char, repl in replacements.items():
        text = text.replace(char, repl)
    return text


@reports_bp.route("/weekly-accomplishment-weeks")
@login_required
def weekly_accomplishment_weeks():
    """
    Returns JSON list of weeks (Monday..Sunday) that have DTR rows for current_user.
    Each item: { start: "YYYY-MM-DD", end: "YYYY-MM-DD", label: "Mon DD, YYYY - Sun DD, YYYY" }
    """
    test_flag = 1 if TESTING_MODE else 0
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT MIN(date) AS min_date, MAX(date) AS max_date FROM dtr WHERE user_id = ? AND is_test = ?",
            (current_user.id, test_flag)
        ).fetchone()

        if not row or not row["min_date"]:
            return jsonify([])

        min_date = datetime.strptime(row["min_date"], "%Y-%m-%d").date()
        max_date = datetime.strptime(row["max_date"], "%Y-%m-%d").date()

        first_monday = min_date - timedelta(days=min_date.weekday())
        weeks = []
        cur = first_monday
        while cur <= max_date:
            start = cur
            end = cur + timedelta(days=6)
            label = f"{start.strftime('%b %d, %Y')} - {end.strftime('%b %d, %Y')}"
            weeks.append({
                "start": start.strftime("%Y-%m-%d"),
                "end": end.strftime("%Y-%m-%d"),
                "label": label
            })
            cur += timedelta(days=7)
        return jsonify(weeks)
    finally:
        conn.close()


@reports_bp.route("/weekly-accomplishment-pdf")
@login_required
def weekly_accomplishment_pdf():
    """
    Generate weekly accomplishment PDF for an optional week_start query param (YYYY-MM-DD).
    If week_start is not provided or invalid, use current Manila week.
    """
    now = get_manila_now()

    week_param = request.args.get('week_start')
    if week_param:
        try:
            parsed = datetime.strptime(week_param, "%Y-%m-%d")
            week_start = parsed - timedelta(days=parsed.weekday())
        except Exception:
            week_start = now - timedelta(days=now.weekday())
    else:
        week_start = now - timedelta(days=now.weekday())

    week_end = week_start + timedelta(days=6)
    week_start_str = week_start.strftime("%Y-%m-%d")
    week_end_str = week_end.strftime("%Y-%m-%d")
    test_flag = True if TESTING_MODE else False

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cur.execute(
        "SELECT * FROM dtr WHERE user_id = %s AND date >= %s AND date <= %s AND is_test = %s ORDER BY date ASC",
        (current_user.id, week_start_str, week_end_str, test_flag)
    )
    records = cur.fetchall()

    cur.close()
    conn.close()

    # Build the PDF (reuse existing layout)
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=20)

    page_w = pdf.w - 30  # usable width (15mm margin each side)

    # ---- Header ----
    pdf.set_fill_color(30, 58, 138)
    pdf.rect(0, 0, 210, 42, 'F')
    pdf.set_fill_color(37, 99, 235)
    pdf.rect(0, 42, 210, 3, 'F')

    pdf.set_y(10)
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(255, 255, 255)
    title_text = "Weekly Accomplishment Report"
    if TESTING_MODE:
        title_text += "  [TEST]"
    pdf.cell(0, 10, title_text, align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(191, 219, 254)
    pdf.cell(0, 7, f"{week_start.strftime('%B %d, %Y')}  -  {week_end.strftime('%B %d, %Y')}", align="C", new_x="LMARGIN", new_y="NEXT")

    # ---- Employee Info Box ----
    pdf.set_y(52)
    pdf.set_fill_color(248, 250, 252)
    pdf.set_draw_color(229, 231, 235)
    pdf.rect(15, 52, page_w, 22, 'DF')

    pdf.set_xy(20, 55)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(156, 163, 175)
    pdf.cell(40, 5, "EMPLOYEE NAME", new_x="LMARGIN", new_y="NEXT")
    pdf.set_xy(20, 60)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(17, 24, 39)
    pdf.cell(80, 7, current_user.username)

    pdf.set_xy(120, 55)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(156, 163, 175)
    pdf.cell(40, 5, "DATE GENERATED", new_x="LMARGIN", new_y="NEXT")
    pdf.set_xy(120, 60)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(17, 24, 39)
    pdf.cell(60, 7, now.strftime("%B %d, %Y  %I:%M %p"))

    # ---- Daily Entries ----
    pdf.set_y(82)

    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    for i in range(7):
        day_date = week_start + timedelta(days=i)
        day_str = day_date.strftime("%Y-%m-%d")
        day_name = day_names[i]
        day_display = day_date.strftime("%B %d, %Y")

        record = None
        for r in records:
            if r["date"] == day_str:
                record = r
                break

        activities_text = ""
        time_in_val = ""
        time_out_val = ""
        total_hrs = ""

        if record:
            activities_text = record["activities"] if record["activities"] else ""
            time_in_val = record["time_in"] if record["time_in"] else ""
            time_out_val = record["time_out"] if record["time_out"] else ""
            if record["total_hours"]:
                total_hrs = f"{record['total_hours']:.2f} hrs"

        if i >= 5 and not activities_text and not time_in_val:
            continue

        if pdf.get_y() > 245:
            pdf.add_page()
            pdf.set_y(15)

        y_start = pdf.get_y()

        if i < 5:
            pdf.set_fill_color(239, 246, 255)
            pdf.set_draw_color(191, 219, 254)
        else:
            pdf.set_fill_color(254, 243, 199)
            pdf.set_draw_color(253, 224, 71)

        pdf.rect(15, y_start, page_w, 10, 'DF')

        pdf.set_xy(18, y_start + 2)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(30, 64, 175)
        pdf.cell(70, 6, f"{day_name}")

        pdf.set_xy(90, y_start + 2)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(75, 85, 99)
        pdf.cell(40, 6, day_display)

        if time_in_val or time_out_val:
            time_info = ""
            if time_in_val:
                time_info += f"In: {time_in_val}"
            if time_out_val:
                time_info += f"  |  Out: {time_out_val}"
            if total_hrs:
                time_info += f"  |  {total_hrs}"
            pdf.set_xy(15, y_start + 2)
            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(107, 114, 128)
            pdf.cell(page_w - 3, 6, time_info, align="R")

        pdf.set_y(y_start + 10)

        if activities_text:
            pdf.set_fill_color(255, 255, 255)
            pdf.set_draw_color(229, 231, 235)

            pdf.set_font("Helvetica", "", 9.5)
            lines = activities_text.split("\n")
            content_lines = []
            for line in lines:
                stripped = line.strip()
                if stripped:
                    content_lines.append(stripped)

            if not content_lines:
                content_lines = [activities_text.strip()]

            line_h = 5.5
            box_padding = 4
            box_h = len(content_lines) * line_h + box_padding * 2
            box_y = pdf.get_y()

            if box_y + box_h > 275:
                pdf.add_page()
                pdf.set_y(15)
                box_y = 15

            pdf.rect(15, box_y, page_w, box_h, 'DF')

            pdf.set_fill_color(37, 99, 235)
            pdf.rect(15, box_y, 2.5, box_h, 'F')

            pdf.set_xy(21, box_y + box_padding)
            pdf.set_text_color(51, 65, 85)

            for cl in content_lines:
                if cl.startswith(("\u2022", "-", "*", ">")):
                    for prefix in ("\u2022", "-", "*", ">"):
                        if cl.startswith(prefix):
                            cl = cl[len(prefix):].strip()
                            break
                    display_line = f"-  {cl}"
                else:
                    display_line = f"-  {cl}"
                pdf.set_x(21)
                pdf.cell(page_w - 10, line_h, sanitize_for_pdf(display_line), new_x="LMARGIN", new_y="NEXT")

            pdf.set_y(box_y + box_h + 3)
        else:
            pdf.set_fill_color(249, 250, 251)
            pdf.set_draw_color(229, 231, 235)
            no_y = pdf.get_y()
            pdf.rect(15, no_y, page_w, 10, 'DF')
            pdf.set_xy(18, no_y + 2)
            pdf.set_font("Helvetica", "I", 9)
            pdf.set_text_color(156, 163, 175)
            if time_in_val:
                pdf.cell(page_w - 6, 6, "No activities recorded for this day.")
            else:
                pdf.cell(page_w - 6, 6, "No attendance / No activities recorded.")
            pdf.set_y(no_y + 13)

    # ---- Summary Footer ----
    if pdf.get_y() > 250:
        pdf.add_page()
        pdf.set_y(15)

    total_hours = sum(r["total_hours"] for r in records if r["total_hours"]) if records else 0
    days_with_activities = sum(1 for r in records if r["activities"] and r["activities"].strip()) if records else 0
    days_worked = sum(1 for r in records if r["total_hours"]) if records else 0

    pdf.set_y(pdf.get_y() + 5)
    summary_y = pdf.get_y()
    pdf.set_fill_color(248, 250, 252)
    pdf.set_draw_color(229, 231, 235)
    pdf.rect(15, summary_y, page_w, 20, 'DF')

    col_w = page_w / 3

    pdf.set_xy(15, summary_y + 3)
    pdf.set_font("Helvetica", "", 7.5)
    pdf.set_text_color(156, 163, 175)
    pdf.cell(col_w, 4, "TOTAL HOURS", align="C")
    pdf.cell(col_w, 4, "DAYS WORKED", align="C")
    pdf.cell(col_w, 4, "DAYS WITH ACTIVITIES", align="C")

    pdf.set_xy(15, summary_y + 8)
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(17, 24, 39)
    pdf.cell(col_w, 9, f"{total_hours:.2f}", align="C")
    pdf.cell(col_w, 9, str(days_worked), align="C")
    pdf.cell(col_w, 9, str(days_with_activities), align="C")

    # ---- Bottom Footer ----
    pdf.set_y(pdf.get_y() + 28)
    if pdf.get_y() > 270:
        pdf.add_page()
        pdf.set_y(260)

    foot_y = max(pdf.get_y(), 265)
    pdf.set_y(foot_y)
    pdf.set_font("Helvetica", "I", 7.5)
    pdf.set_text_color(156, 163, 175)
    footer_text = f"Generated by DTR Automate  |  {now.strftime('%B %d, %Y %I:%M %p')}"
    if TESTING_MODE:
        footer_text += "  |  TEST DATA -- NOT FOR SUBMISSION"
    pdf.cell(0, 5, sanitize_for_pdf(footer_text), align="C")

    pdf_bytes = pdf.output()
    buffer = io.BytesIO(pdf_bytes)

    prefix = "TEST_" if TESTING_MODE else ""
    filename = f"{prefix}Weekly_Accomplishment_{week_start.strftime('%b%d')}_{week_end.strftime('%b%d_%Y')}_{current_user.username.replace(' ', '_')}.pdf"

    return send_file(
        buffer,
        as_attachment=True,
        download_name=filename,
        mimetype='application/pdf'
    )


<<<<<<< Updated upstream
@reports_bp.route("/weekly-accomplishment")
@login_required
def weekly_accomplishment():
    """
    Page with dropdown / prev-next and Generate PDF button to download any week's PDF (including past records).
    """
    return render_template("weekly_accomplishment.html")


=======
>>>>>>> Stashed changes
@reports_bp.route("/monthly-dtr")
@reports_bp.route("/monthly-dtr/<int:year>/<int:month>")
@login_required
def monthly_dtr(year=None, month=None):
    now = get_manila_now()
    if year is None or month is None:
        year = now.year
        month = now.month

    if month < 1:
        month = 12
        year -= 1
    elif month > 12:
        month = 1
        year += 1

    days_in_month = calendar.monthrange(year, month)[1]
    month_name = calendar.month_name[month]

    prev_month = month - 1
    prev_year = year
    if prev_month < 1:
        prev_month = 12
        prev_year -= 1

    next_month = month + 1
    next_year = year
    if next_month > 12:
        next_month = 1
        next_year += 1

    start_date = f"{year}-{month:02d}-01"
    end_date = f"{year}-{month:02d}-{days_in_month:02d}"
    test_flag = True if TESTING_MODE else False

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cur.execute(
        "SELECT * FROM dtr WHERE user_id = %s AND date >= %s AND date <= %s AND is_test = %s ORDER BY date ASC",
        (current_user.id, start_date, end_date, test_flag)
    )
    rows = cur.fetchall()

    cur.close()
    conn.close()

    weekdays = {}
    for d in range(1, days_in_month + 1):
        dt = datetime(year, month, d)
        weekdays[d] = calendar.day_abbr[dt.weekday()]

    STANDARD_MINUTES = 8 * 60
    NOON = 12 * 60

    def parse_time_minutes(t_str):
        try:
            dt = datetime.strptime(t_str.strip(), "%I:%M %p")
            return dt.hour * 60 + dt.minute
        except Exception:
            return None

    records_by_day = {}
    total_ut_minutes = 0

    for row in rows:
        day_num = int(row["date"].split("-")[2])
        time_in_val = row["time_in"]
        time_out_val = row["time_out"]
        total_hours = row["total_hours"]

        am_arrival = ""
        am_departure = ""
        pm_arrival = ""
        pm_departure = ""
        ut_hours = ""
        ut_minutes = ""

        if time_in_val:
            t_in_min = parse_time_minutes(time_in_val)
            if t_in_min is not None:
                if t_in_min < NOON:
                    am_arrival = time_in_val.strip()
                else:
                    pm_arrival = time_in_val.strip()

        if time_out_val:
            t_out_min = parse_time_minutes(time_out_val)
            if t_out_min is not None:
                if t_out_min <= NOON + 30:
                    am_departure = time_out_val.strip()
                else:
                    pm_departure = time_out_val.strip()

        if am_arrival and pm_departure and not am_departure:
            am_departure = "12:00 PM"
        if am_arrival and pm_departure and not pm_arrival:
            pm_arrival = "01:00 PM"

        if total_hours is not None and total_hours > 0:
            worked_minutes = int(round(total_hours * 60))
            if worked_minutes > 300:
                worked_minutes -= 60
            undertime = max(STANDARD_MINUTES - worked_minutes, 0)
            if undertime > 0:
                ut_hours = str(undertime // 60) if undertime // 60 > 0 else ""
                ut_minutes = str(undertime % 60) if undertime % 60 > 0 else ""
                total_ut_minutes += undertime

        class DayRecord:
            pass

        rec = DayRecord()
        rec.am_arrival = am_arrival
        rec.am_departure = am_departure
        rec.pm_arrival = pm_arrival
        rec.pm_departure = pm_departure
        rec.undertime_hours = ut_hours
        rec.undertime_minutes = ut_minutes
        records_by_day[day_num] = rec

    total_undertime_hours = str(total_ut_minutes // 60) if total_ut_minutes > 0 else ""
    total_undertime_minutes = str(total_ut_minutes % 60) if total_ut_minutes % 60 > 0 else ""

    return render_template("monthly_dtr.html",
        employee_name=current_user.username,
        month_name=month_name,
        year=year,
        days_in_month=days_in_month,
        records_by_day=records_by_day,
        weekdays=weekdays,
        total_undertime_hours=total_undertime_hours,
        total_undertime_minutes=total_undertime_minutes,
        regular_hours="8:00AM - 5:00PM",
        saturday_hours="",
        prev_year=prev_year,
        prev_month=prev_month,
        next_year=next_year,
        next_month=next_month,
        testing_mode=TESTING_MODE
    )
