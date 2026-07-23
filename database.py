import sqlite3
from contextlib import contextmanager

DB_NAME = "orders.db"

@contextmanager
def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    with get_db() as conn:
        # 1. Products Table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                price INTEGER NOT NULL,
                product_image_file_id TEXT
            )
        """)
        
        # 2. Users Table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                name TEXT,
                phone TEXT,
                state_province TEXT,
                address TEXT
            )
        """)
        
        # 3. Orders Table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                product_id INTEGER,
                amount INTEGER,
                status TEXT DEFAULT 'pending',
                payment_image_file_id TEXT,
                locked_by INTEGER,
                locked_until TEXT,
                accepted_at TEXT,
                FOREIGN KEY(user_id) REFERENCES users(user_id),
                FOREIGN KEY(product_id) REFERENCES products(id)
            )
        """)
        conn.commit()
