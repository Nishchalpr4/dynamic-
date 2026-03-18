import logging
from typing import List, Dict, Any
from models import ExtractionPayload, EntityCandidate, RelationCandidate

logger = logging.getLogger(__name__)

class LogicGuard:
    def __init__(self, ontology: Dict[str, Any]):
        self.ontology = ontology
        self.allowed_triples = set()
        for t in ontology.get('allowed_triples', []):
            self.allowed_triples.add((t['source'], t['relation'], t['target']))

    def validate_extraction(self, payload: ExtractionPayload) -> List[str]:
        """Runs all logic guards and returns a list of warning/error messages."""
        flags = []
        
        # 1. Type Guard
        flags.extend(self._check_types(payload.entities, payload.relations))
        
        # 2. Cycle Guard
        flags.extend(self._check_cycles(payload.relations))
        
        # 3. Quant Guard
        flags.extend(self._check_quant(payload.quant_data))
        
        return flags

    def _check_types(self, entities: List[EntityCandidate], relations: List[RelationCandidate]) -> List[str]:
        flags = []
        entity_map = {e.temp_id: e.entity_type for e in entities}
        
        for rel in relations:
            src_type = entity_map.get(rel.source_temp_id)
            tgt_type = entity_map.get(rel.target_temp_id)
            
            if not src_type or not tgt_type:
                continue
                
            # Allow COMPETES_WITH between LegalEntity and Competitors (common discovery case)
            if rel.relation_type == "COMPETES_WITH":
                if src_type in ["LegalEntity", "Competitors"] and tgt_type in ["LegalEntity", "Competitors"]:
                    continue

            triple = (src_type, rel.relation_type, tgt_type)
            if triple not in self.allowed_triples:
                flags.append(f"Type Guard: Relation {rel.relation_type} not allowed between {src_type} and {tgt_type}")
        
        return flags

    def _check_cycles(self, relations: List[RelationCandidate]) -> List[str]:
        flags = []
        # Simple immediate cycle check: A -> B and B -> A
        links = {} # (source, target) -> relation_type
        for rel in relations:
            links[(rel.source_temp_id, rel.target_temp_id)] = rel.relation_type
            
            if (rel.target_temp_id, rel.source_temp_id) in links:
                flags.append(f"Cycle Guard: Potential circular relationship between {rel.source_temp_id} and {rel.target_temp_id}")
                
        # Self-loop check
        for rel in relations:
            if rel.source_temp_id == rel.target_temp_id:
                flags.append(f"Cycle Guard: Self-loop detected for {rel.source_temp_id}")
                
        return flags

    def _check_quant(self, quant_data) -> List[str]:
        flags = []
        for q in quant_data:
            if q.metric.lower() in ['revenue', 'price', 'pat', 'ebitda'] and q.value < 0:
                flags.append(f"Quant Guard: Invalid negative value for {q.metric}: {q.value}")
        return flags
