def assign_asset(item_id, assigned_to, department, location, assigned_date):
    import sqlite3
    from config.settings import DB_PATH

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO assets (item_id, assigned_to, department, location, assigned_date)
        VALUES (?, ?, ?, ?, ?)
    """, (item_id, assigned_to, department, location, assigned_date))
    conn.commit()
    conn.close()
