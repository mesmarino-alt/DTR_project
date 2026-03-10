from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required

from helpers import get_db

import psycopg2
import psycopg2.extras

auth_bp = Blueprint('auth', __name__)


@auth_bp.route("/")
def landing():
    return render_template("landing.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    from app import bcrypt, User

    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        cur.execute(
            "SELECT * FROM users WHERE username = %s",
            (username,)
        )

        row = cur.fetchone()

        cur.close()
        conn.close()

        if row and bcrypt.check_password_hash(row["password"], password):
            user = User(row["id"], row["username"], row["password"])
            login_user(user)
            return redirect(url_for("dashboard.dashboard"))
        else:
            flash("Invalid credentials")

    return render_template("login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))