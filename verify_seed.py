
from database import DatabaseManager
from seed_db import seed
import json

print("Starting manual seed...")
try:
    seed()
    print("Seed function completed.")
    db = DatabaseManager()
    ontology = db.get_ontology()
    print("Current Ontology Keys:", ontology.keys())
    if 'SUCCEEDS' in ontology.get('relation_types', []):
        print("SUCCESS: 'SUCCEEDS' relation found in database.")
    else:
        print("FAILURE: 'SUCCEEDS' relation NOT found.")
    
    extraction_rules = ontology.get('extraction_rules', [])
    print("Extraction Rules Count:", len(extraction_rules))
    for rule in extraction_rules:
        if "SUCCESSION" in rule:
            print(f"SUCCESS: Rule found: {rule}")
except Exception as e:
    print(f"ERROR: {e}")
