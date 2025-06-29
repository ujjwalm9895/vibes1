# models.py

import sqlite3
from datetime import datetime

DB_NAME = "database.db"

def get_db():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()

    # Users Table
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL
        )
    """)

    # Calls Table
    c.execute("""
        CREATE TABLE IF NOT EXISTS calls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            caller TEXT,
            callee TEXT,
            start_time TEXT,
            end_time TEXT,
            duration INTEGER
        )
    """)

    # Transcripts Table
    c.execute("""
        CREATE TABLE IF NOT EXISTS transcripts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            call_id INTEGER,
            timestamp TEXT,
            text TEXT,
            FOREIGN KEY (call_id) REFERENCES calls(id)
        )
    """)

    # Dreams Table (Generated images)
    c.execute("""
        CREATE TABLE IF NOT EXISTS dreams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            call_id INTEGER,
            prompt TEXT,
            image_url TEXT,
            timestamp TEXT,
            FOREIGN KEY (call_id) REFERENCES calls(id)
        )
    """)

    # Summaries Table (optional but useful)
    c.execute("""
        CREATE TABLE IF NOT EXISTS summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            call_id INTEGER,
            summary TEXT,
            followups TEXT,
            timestamp TEXT,
            FOREIGN KEY (call_id) REFERENCES calls(id)
        )
    """)

    # Optional Indexes
    c.execute("CREATE INDEX IF NOT EXISTS idx_call_id ON transcripts(call_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_dream_call_id ON dreams(call_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_summary_call_id ON summaries(call_id)")

    conn.commit()
    conn.close()
