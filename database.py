import sqlite3
import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, db_path: str = "graph.db"):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=30.0) # 30 second timeout
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Initializes the 5-table schema for the Investment Intelligence System."""
        with self._get_connection() as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            cursor = conn.cursor()

            # 1. Entity Master (Golden Records)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS entity_master (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    type TEXT NOT NULL,
                    color TEXT,
                    attributes TEXT, -- JSON
                    aliases TEXT,    -- JSON
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 2. Relation Master (Golden Links)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS relation_master (
                    id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    relation TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(source_id) REFERENCES entity_master(id),
                    FOREIGN KEY(target_id) REFERENCES entity_master(id)
                )
            """)

            # 3. Assertions (The Trust Layer / Evidence Trail)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS assertions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    subject_id TEXT NOT NULL, -- master_id of entity or relation
                    subject_type TEXT NOT NULL, -- 'ENTITY' or 'RELATION'
                    source_text TEXT,
                    confidence FLOAT,
                    status TEXT DEFAULT 'PENDING', -- PENDING, VERIFIED, FLAGGED
                    document_name TEXT,
                    section_ref TEXT,
                    source_authority INTEGER DEFAULT 5, -- Authority weight 1-10
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Migration check: add source_authority if missing
            try:
                cursor.execute("ALTER TABLE assertions ADD COLUMN source_authority INTEGER DEFAULT 5")
            except sqlite3.OperationalError:
                pass # Already exists

            # 4. Quant Data (The Financial Metric Layer)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS quant_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    entity_id TEXT NOT NULL,
                    metric TEXT NOT NULL,
                    value REAL,
                    unit TEXT,
                    period TEXT,
                    source_assertion_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(entity_id) REFERENCES entity_master(id),
                    FOREIGN KEY(source_assertion_id) REFERENCES assertions(id)
                )
            """)

            # 5. Ontology Rules (The Brain)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ontology_rules (
                    key TEXT PRIMARY KEY, -- 'entity_types', 'relation_types', 'allowed_triples'
                    data TEXT NOT NULL,   -- JSON blob of the rules
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.commit()
            logger.info(f"Database initialized at {self.db_path}")

    def drop_all_tables(self):
        """Drops all 5 tables in the schema."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DROP TABLE IF EXISTS entity_master")
            cursor.execute("DROP TABLE IF EXISTS relation_master")
            cursor.execute("DROP TABLE IF EXISTS assertions")
            cursor.execute("DROP TABLE IF EXISTS quant_data")
            cursor.execute("DROP TABLE IF EXISTS ontology_rules")
            conn.commit()
            logger.info("All tables dropped from database.")

    # --- Ontology Management ---

    def get_ontology(self):
        """Fetches the current rules from the DB."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT key, data FROM ontology_rules")
            rows = cursor.fetchall()
            return {row['key']: json.loads(row['data']) for row in rows}

    def update_ontology(self, key: str, data: list | dict):
        """Updates or adds new ontology rules."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO ontology_rules (key, data, last_updated)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            """, (key, json.dumps(data)))
            conn.commit()

    # --- Master Ingestion ---

    def upsert_entity(self, entity_id: str, name: str, entity_type: str, color: str = None, attributes: dict = None, aliases: list = None):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO entity_master (id, name, type, color, attributes, aliases, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,
                    type=excluded.type,
                    color=COALESCE(excluded.color, entity_master.color),
                    attributes=excluded.attributes,
                    aliases=excluded.aliases,
                    updated_at=CURRENT_TIMESTAMP
            """, (entity_id, name, entity_type, color, json.dumps(attributes or {}), json.dumps(aliases or [])))
            conn.commit()

    def add_relation(self, rel_id: str, source_id: str, target_id: str, relation: str):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO relation_master (id, source_id, target_id, relation)
                VALUES (?, ?, ?, ?)
            """, (rel_id, source_id, target_id, relation))
            conn.commit()

    def add_assertion(self, subject_id: str, subject_type: str, source_text: str, confidence: float, document_name: str, section_ref: str, status: str = 'PENDING', source_authority: int = 5):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO assertions (subject_id, subject_type, source_text, confidence, status, document_name, section_ref, source_authority)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (subject_id, subject_type, source_text, confidence, status, document_name, section_ref, source_authority))
            conn.commit()
            return cursor.lastrowid

    def add_quant_metric(self, entity_id: str, metric: str, value: float, unit: str, period: str, assertion_id: int = None):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO quant_data (entity_id, metric, value, unit, period, source_assertion_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (entity_id, metric, value, unit, period, assertion_id))
            conn.commit()

    def get_graph_data(self):
        """Retrieves nodes and links with Trust and Quant metadata."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Get Nodes with latest assertion status and quant data
            cursor.execute("SELECT id, name as label, type, color, attributes, aliases FROM entity_master")
            nodes = []
            for row in cursor.fetchall():
                node = dict(row)
                node['attributes'] = json.loads(node['attributes'])
                node['aliases'] = json.loads(node['aliases'])
                
                # Get latest assertion for this entity
                cursor.execute("""
                    SELECT status, confidence, source_text, document_name, section_ref, source_authority 
                    FROM assertions 
                    WHERE subject_id = ? AND subject_type = 'ENTITY' 
                    ORDER BY timestamp DESC LIMIT 3
                """, (node['id'],))
                node['evidence'] = [dict(r) for r in cursor.fetchall()]
                
                # Get quant metrics (WITH WEIGHTED CONSENSUS)
                # We group by metric + period and pick the one with highest authority
                cursor.execute("""
                    SELECT q.metric, q.value, q.unit, q.period, a.source_authority
                    FROM quant_data q
                    JOIN assertions a ON q.source_assertion_id = a.id
                    WHERE q.entity_id = ?
                    ORDER BY a.source_authority DESC, a.timestamp DESC
                """, (node['id'],))
                
                all_metrics = [dict(r) for r in cursor.fetchall()]
                consensus_metrics = {}
                for m in all_metrics:
                    key = f"{m['metric']}_{m['period']}"
                    if key not in consensus_metrics:
                        consensus_metrics[key] = m
                
                node['quant_metrics'] = list(consensus_metrics.values())
                nodes.append(node)

            # Get Links with evidence
            cursor.execute("SELECT id, source_id as source, target_id as target, relation FROM relation_master")
            links = []
            for row in cursor.fetchall():
                link = dict(row)
                # Get latest assertion for this relation
                cursor.execute("""
                    SELECT status, confidence, source_text, document_name, section_ref 
                    FROM assertions 
                    WHERE subject_id = ? AND subject_type = 'RELATION' 
                    ORDER BY timestamp DESC LIMIT 3
                """, (link['id'],))
                link['evidence'] = [dict(r) for r in cursor.fetchall()]
                links.append(link)

            return {"nodes": nodes, "links": links}

    def seed_ontology(self):
        """Standard seed for the Investment Intelligence System ontology."""
        from models import EntityType, RelationType, ALLOWED_RELATION_TRIPLES, ENTITY_TYPE_COLORS
        import json
        
        # 1. Entity Types
        entity_types = [e.value for e in EntityType]
        self.update_ontology("entity_types", entity_types)
        
        # 2. Relation Types
        relation_types = [r.value for r in RelationType]
        self.update_ontology("relation_types", relation_types)
        
        # 3. Allowed Triples
        allowed_triples = [{"source": s.value, "relation": r.value, "target": t.value} for s, r, t in ALLOWED_RELATION_TRIPLES]
        self.update_ontology("allowed_triples", allowed_triples)
        
        # 4. Colors
        self.update_ontology("entity_colors", ENTITY_TYPE_COLORS)
        
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
        self.update_ontology("extraction_rules", rules)
        logger.info("Database ontology seeded successfully.")
