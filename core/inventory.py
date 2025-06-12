import sqlite3
from config.settings import DB_PATH

def add_item(name, category, quantity, serial, warranty_date, location):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO items (name, category, quantity, serial, warranty_date, location)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (name, category, quantity, serial, warranty_date, location))
    conn.commit()
    conn.close()
