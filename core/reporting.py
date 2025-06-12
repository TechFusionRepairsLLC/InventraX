import pandas as pd
import sqlite3
from config.settings import DB_PATH

def export_inventory_to_csv(output_file):
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM items", conn)
    df.to_csv(output_file, index=False)
    conn.close()
