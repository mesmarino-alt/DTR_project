import os
from flask import Flask
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin

from helpers import get_db
from routes import register_blueprints

app = Flask(__name__)
app.secret_key = "supersecretkey"

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
    row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    conn.close()
    if row:
        return User(row["id"], row["username"], row["password"])
    return None


# ---------- Register Blueprints ----------
register_blueprints(app)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
