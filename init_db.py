import sqlite3
from flask_bcrypt import generate_password_hash

def init_db():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    # Users table
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )
    """)

    # DTR table — linked to users
    c.execute("""
    CREATE TABLE IF NOT EXISTS dtr (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        date TEXT,
        time_in TEXT,
        time_out TEXT,
        total_hours REAL,
        activities TEXT DEFAULT '',
        created_at TEXT,
        is_test INTEGER DEFAULT 0,
        is_manual INTEGER DEFAULT 0,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    """)

    # Employees table
    c.execute("""
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            position TEXT,
            department TEXT
        )
    """)

    # DTR records table
    c.execute("""
        CREATE TABLE IF NOT EXISTS dtr_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER,
            date TEXT NOT NULL,
            time_in TEXT,
            time_out TEXT,
            hours REAL DEFAULT 0,
            is_manual INTEGER DEFAULT 0,
            testing INTEGER DEFAULT 0,
            FOREIGN KEY (employee_id) REFERENCES employees(id)
        )
    """)

    # Tasks table (multiple tasks per record)
    c.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            record_id INTEGER NOT NULL,
            task_description TEXT NOT NULL,
            FOREIGN KEY (record_id) REFERENCES dtr_records(id)
        )
    """)

    # Preload admin user
    admin_username = "Mark Edizon S. Marino"
    admin_password = "kaiju112717"  # change later for security
    hashed_pw = generate_password_hash(admin_password).decode("utf-8")

    try:
        c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (admin_username, hashed_pw))
        print("Admin user created successfully.")
    except sqlite3.IntegrityError:
        print("Admin user already exists.")

    conn.commit()
    conn.close()
    print("Database initialized successfully.")

if __name__ == "__main__":
    init_db()
