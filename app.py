import os
from flask import Flask
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin
import psycopg2
import psycopg2.extras

from helpers import get_db
from routes import register_blueprints
from routes.health import health_bp

app = Flask(__name__)
# DATABASE CONFIGURATION

app.secret_key = os.environ.get("APP_SECRET", "supersecretkey")

# Log DB source at startup for clarity in deployment logs
_db_url = os.environ.get("DATABASE_URL")
_db_host = os.environ.get("DB_HOST")
if _db_url:
    print("Startup: using DATABASE_URL (external Postgres/Supabase)")
elif _db_host:
    print(f"Startup: using DB_HOST={_db_host} (external Postgres)")
elif os.path.exists("database.db"):
    print("Startup: no DATABASE_URL/DB_* found — database.db exists, app may use local SQLite")
else:
    print("Startup: no DB configuration found in env — app will attempt default connection settings")

bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = "auth.login"


# ---------- User model ----------
class User(UserMixin):
    def __init__(self, id, username, password):
        self.id = id
        self.username = username
        self.password = password


@login_manager.user_loader
def load_user(user_id):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    row = cur.fetchone()

    cur.close()
    conn.close()

    if row:
        return User(row["id"], row["username"], row["password"])
    return None


# ---------- Register Blueprints ----------
register_blueprints(app)
app.register_blueprint(health_bp)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
