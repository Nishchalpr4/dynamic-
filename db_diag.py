
import os
import sys
import time

print("DIAGNOSTIC START")
print(f"Current PID: {os.getpid()}")
print(f"Checking if graph.db exists: {os.path.exists('graph.db')}")

try:
    print("Attempting to import models...")
    import models
    print("Models imported successfully.")
except Exception as e:
    print(f"FAILED to import models: {e}")

try:
    print("Attempting to import database...")
    import database
    print("Database module imported successfully.")
except Exception as e:
    print(f"FAILED to import database: {e}")

try:
    print("Attempting connection via sqlite3 directly...")
    import sqlite3
    # Try with a very short timeout to avoid long hangs here
    conn = sqlite3.connect("graph.db", timeout=1.0)
    print("Sqlite3 connection object created.")
    cursor = conn.cursor()
    print("Attempting a simple SELECT...")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print(f"Connected! Tables in DB: {[t[0] for t in tables]}")
    conn.close()
except Exception as e:
    print(f"FAILED to connect: {e}")

print("DIAGNOSTIC END")
