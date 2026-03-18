import json
from database import DatabaseManager
from models import EntityType, RelationType, ALLOWED_RELATION_TRIPLES, ENTITY_TYPE_COLORS

def seed():
    db = DatabaseManager()
    
    # 1. Entity Types
    entity_types = [e.value for e in EntityType]
    db.update_ontology("entity_types", entity_types)
    
    # 2. Relation Types
    relation_types = [r.value for r in RelationType]
    db.update_ontology("relation_types", relation_types)
    
    # 3. Allowed Triples (Serialize to strings for JSON)
    allowed_triples = []
    for s, r, t in ALLOWED_RELATION_TRIPLES:
        allowed_triples.append({
            "source": s.value,
            "relation": r.value,
            "target": t.value
        })
    db.update_ontology("allowed_triples", allowed_triples)
    
    # 4. Colors
    db.update_ontology("entity_colors", ENTITY_TYPE_COLORS)
    
    # 5. Extraction Rules (Initial Set)
    rules = [
        "ROOT ENTITY: identify the primary company as LegalEntity (ROOT).",
        "NO ORPHANS: Every node must connect to ROOT directly or indirectly.",
        "MANAGEMENT CHAIN: LegalEntity -> HAS_MANAGEMENT -> Management -> HAS_ROLE -> Role -> HELD_BY -> Person.",
        "SUCCESSION: If one Person replaces another, use [Person A] -> SUCCEEDS -> [Person B].",
        "GEOGRAPHY: Region -> Country -> Site hierarchy.",
        "QUANT DATA: DO NOT create nodes for Revenue, PAT, Assets, etc. These MUST only be in 'quant_data'.",
        "BUSINESS UNITS: Key divisions (e.g. Wealth Management) are BusinessUnit nodes."
    ]
    db.update_ontology("extraction_rules", rules)

    print("Database seeded successfully with ontology from models.py")

if __name__ == "__main__":
    seed()
