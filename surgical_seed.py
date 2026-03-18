
import sqlite3
import json
from models import EntityType, RelationType, ALLOWED_RELATION_TRIPLES, ENTITY_TYPE_COLORS

def surgical_seed():
    db_path = "graph.db"
    print(f"Opening {db_path} surgically...")
    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
    cursor = conn.cursor()

    try:
        # 1. Entity Types
        entity_types = [e.value for e in EntityType]
        cursor.execute("INSERT OR REPLACE INTO ontology_rules (key, data, last_updated) VALUES (?, ?, CURRENT_TIMESTAMP)", 
                       ("entity_types", json.dumps(entity_types)))
        
        # 2. Relation Types
        relation_types = [r.value for r in RelationType]
        cursor.execute("INSERT OR REPLACE INTO ontology_rules (key, data, last_updated) VALUES (?, ?, CURRENT_TIMESTAMP)", 
                       ("relation_types", json.dumps(relation_types)))
        
        # 3. Allowed Triples
        allowed_triples = [{"source": s.value, "relation": r.value, "target": t.value} for s, r, t in ALLOWED_RELATION_TRIPLES]
        cursor.execute("INSERT OR REPLACE INTO ontology_rules (key, data, last_updated) VALUES (?, ?, CURRENT_TIMESTAMP)", 
                       ("allowed_triples", json.dumps(allowed_triples)))
        
        # 4. Colors
        cursor.execute("INSERT OR REPLACE INTO ontology_rules (key, data, last_updated) VALUES (?, ?, CURRENT_TIMESTAMP)", 
                       ("entity_colors", json.dumps(ENTITY_TYPE_COLORS)))
        
        # 5. Extraction Rules
        rules = [
            "ROOT ENTITY: identify the primary company as LegalEntity (ROOT).",
            "NO ORPHANS: Every node must connect to ROOT directly or indirectly.",
            "MANAGEMENT CHAIN: LegalEntity -> HAS_MANAGEMENT -> Management -> HAS_ROLE -> Role -> HELD_BY -> Person.",
            "SUCCESSION: If one Person replaces another, use [Person A] -> SUCCEEDS -> [Person B].",
            "GEOGRAPHY: Region -> Country -> Site hierarchy.",
            "QUANT DATA: DO NOT create nodes for Revenue, PAT, Assets, etc. These MUST only be in 'quant_data'.",
            "BUSINESS UNITS: Key divisions (e.g. Wealth Management) are BusinessUnit nodes."
        ]
        cursor.execute("INSERT OR REPLACE INTO ontology_rules (key, data, last_updated) VALUES (?, ?, CURRENT_TIMESTAMP)", 
                       ("extraction_rules", json.dumps(rules)))
        
        conn.commit()
        print("Surgical seed successful. Ontology updated in database.")
    except Exception as e:
        print(f"Surgical seed failed: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    surgical_seed()
