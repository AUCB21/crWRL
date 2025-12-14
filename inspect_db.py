import sqlite3
import os
import sys
import argparse

# Parse command line arguments
parser = argparse.ArgumentParser(description='Inspect SQLite database from CRWLR crawler')
parser.add_argument(
    '-d', '--database',
    type=str,
    default=os.path.join("results", "results.db"),
    help='Path to the SQLite database file (default: results/results.db)'
)
args = parser.parse_args()

db_path = args.database
print(f"Looking for DB at: {os.path.abspath(db_path)}")

if not os.path.exists(db_path):
    print(f"Database file not found at {db_path}")
    sys.exit(1)

print(f"File size: {os.path.getsize(db_path)} bytes")

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get list of tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print(f"Tables found: {[t[0] for t in tables]}")
    
    for table in tables:
        table_name = table[0]
        if table_name == "sqlite_sequence":
            continue
            
        print(f"\n--- Table: {table_name} ---")
        # Get row count
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()[0]
        print(f"Row count: {count}")
        
        # Get last 3 rows
        cursor.execute(f"SELECT * FROM {table_name} ORDER BY id DESC LIMIT 3")
        rows = cursor.fetchall()
        if rows:
            # Get column names
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = [col[1] for col in cursor.fetchall()]
            print(f"Columns: {columns}")
            print("Last 3 rows:")
            for row in rows:
                print(row)
        else:
            print("No data.")

    conn.close()

except Exception as e:
    print(f"Error inspecting database: {e}")
