import psycopg2
from psycopg2 import sql
from flask_bcrypt import generate_password_hash
import os


def init_db():
    # Prefer DATABASE_URL if provided
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        print("Initializing DB using DATABASE_URL from environment")
        conn = psycopg2.connect(db_url)
    else:
        host = os.environ.get("DB_HOST", "aws-1-ap-northeast-1.pooler.supabase.com")
        database = os.environ.get("DB_NAME", "postgres")
        user = os.environ.get("DB_USER", "postgres.gkdbzfrzyalndahgulsm")
        password = os.environ.get("DB_PASS", "edizonmarino_112717")
        port = int(os.environ.get("DB_PORT", 6543))
        print(f"Initializing DB using host={host} port={port}")
        conn = psycopg2.connect(host=host, database=database, user=user, password=password, port=port)

    cur = conn.cursor()

    # Users table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        username VARCHAR(255) UNIQUE NOT NULL,
        password VARCHAR(255) NOT NULL
    )
    """)

    # DTR table — linked to users
    cur.execute("""
    CREATE TABLE IF NOT EXISTS dtr (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL,
        date DATE,
        time_in TIME,
        time_out TIME,
        total_hours REAL,
        activities TEXT DEFAULT '',
        created_at TIMESTAMP,
        is_test BOOLEAN DEFAULT FALSE,
        is_manual BOOLEAN DEFAULT FALSE,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    """)

    # Employees table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS employees (
        id SERIAL PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        position VARCHAR(255),
        department VARCHAR(255)
    )
    """)

    # DTR records table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS dtr_records (
        id SERIAL PRIMARY KEY,
        employee_id INTEGER,
        date DATE NOT NULL,
        time_in TIME,
        time_out TIME,
        hours REAL DEFAULT 0,
        is_manual BOOLEAN DEFAULT FALSE,
        testing BOOLEAN DEFAULT FALSE,
        FOREIGN KEY (employee_id) REFERENCES employees(id)
    )
    """)

    # Tasks table (multiple tasks per record)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        id SERIAL PRIMARY KEY,
        record_id INTEGER NOT NULL,
        task_description TEXT NOT NULL,
        FOREIGN KEY (record_id) REFERENCES dtr_records(id)
    )
    """)

    # Preload admin user
    admin_username = os.environ.get("INIT_ADMIN_USER", "Mark Edizon S. Marino")
    admin_password = os.environ.get("INIT_ADMIN_PASS", "kaiju112717")  # recommend override via env
    hashed_pw = generate_password_hash(admin_password).decode("utf-8")

    try:
        cur.execute(
            "INSERT INTO users (username, password) VALUES (%s, %s) ON CONFLICT (username) DO NOTHING",
            (admin_username, hashed_pw)
        )
        print("Admin user created successfully (or already existed).")
    except Exception as e:
        print(f"Error creating admin user: {e}")

    # Second user
    user2_username = os.environ.get("INIT_USER2", "Nadine B. Vargas")
    user2_password = os.environ.get("INIT_USER2_PASS", "nadynevrgs")
    hashed_pw2 = generate_password_hash(user2_password).decode("utf-8")

    try:
        cur.execute(
            "INSERT INTO users (username, password) VALUES (%s, %s) ON CONFLICT (username) DO NOTHING",
            (user2_username, hashed_pw2)
        )
        print(f"User '{user2_username}' created successfully (or already existed).")
    except Exception as e:
        print(f"Error creating user '{user2_username}': {e}")

    # Add a default employee for testing
    try:
        cur.execute(
            "INSERT INTO employees (id, name, position, department) VALUES (%s, %s, %s, %s) ON CONFLICT (id) DO NOTHING",
            (1, os.environ.get("INIT_EMP_NAME", "Default Employee"), os.environ.get("INIT_EMP_POS", "Tester"), os.environ.get("INIT_EMP_DEPT", "Development"))
        )
        print("Default employee added successfully (or already existed).")
    except Exception as e:
        print(f"Error adding default employee: {e}")

    conn.commit()
    cur.close()
    conn.close()
    print("Database initialized successfully.")


if __name__ == "__main__":
    if os.environ.get("RUN_INIT_DB") == "1":
        init_db()
    else:
        print("RUN_INIT_DB not set — skipping DB initialization.")
