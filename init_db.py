import psycopg2
from psycopg2 import sql
from flask_bcrypt import generate_password_hash
import os

def init_db():
    conn = psycopg2.connect(
        host="aws-1-ap-northeast-1.pooler.supabase.com",
        database="postgres",
        user="postgres.gkdbzfrzyalndahgulsm",
        password="edizonmarino_112717",
        port=6543
    )
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
    admin_username = "Mark Edizon S. Marino"
    admin_password = "kaiju112717"  # change later for security
    hashed_pw = generate_password_hash(admin_password).decode("utf-8")

    try:
        cur.execute(
            "INSERT INTO users (username, password) VALUES (%s, %s) ON CONFLICT (username) DO NOTHING",
            (admin_username, hashed_pw)
        )
        print("Admin user created successfully.")
    except Exception as e:
        print(f"Error creating admin user: {e}")

    # Second user
    user2_username = "Nadine B. Vargas"
    user2_password = "nadynevrgs"  # change later for security
    hashed_pw2 = generate_password_hash(user2_password).decode("utf-8")

    try:
        cur.execute(
            "INSERT INTO users (username, password) VALUES (%s, %s) ON CONFLICT (username) DO NOTHING",
            (user2_username, hashed_pw2)
        )
        print(f"User '{user2_username}' created successfully.")
    except Exception as e:
        print(f"Error creating user '{user2_username}': {e}")

    # Add a default employee for testing
    try:
        cur.execute(
            "INSERT INTO employees (id, name, position, department) VALUES (%s, %s, %s, %s) ON CONFLICT (id) DO NOTHING",
            (1, "Default Employee", "Tester", "Development")
        )
        print("Default employee added successfully.")
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
