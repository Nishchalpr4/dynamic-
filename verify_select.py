import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()
db_url = os.getenv('DATABASE_URL')
conn = psycopg2.connect(db_url)
cur = conn.cursor()

try:
    cur.execute("SELECT key, data FROM ontology_rules")
    print("SUCCESS: SELECT from ontology_rules worked!")
except Exception as e:
    print(f"FAILED: {e}")

cur.close()
conn.close()
