
from typing import List, Dict, Any, Set
import logging

logger = logging.getLogger(__name__)

class GraphInference:
    """
    Automated Logic Inference Engine for Knowledge Graphs.
    Derives hidden relationships based on transitive paths.
    """
    
    def __init__(self, nodes: List[Dict], links: List[Dict]):
        self.nodes = {n['id']: n for n in nodes}
        self.links = links
        
        # Build adjacency maps for traversal
        self.adj = {} # source -> list of (relation, target)
        for rel in links:
            s, r, t = rel['source'], rel['relation'], rel['target']
            if s not in self.adj: self.adj[s] = []
            self.adj[s].append((r, t))

    def infer_all(self) -> List[Dict]:
        """Runs all inference rules and returns a list of virtual/inferred links."""
        inferred = []
        inferred.extend(self._infer_indirect_presence())
        inferred.extend(self._infer_sector_inheritance())
        return inferred

    def _infer_indirect_presence(self) -> List[Dict]:
        """Rule: LegalEntity -> HAS_BUSINESS_UNIT -> BusinessUnit -> OPERATES_SITE -> Site"""
        inferred = []
        for root_id, node in self.nodes.items():
            if node['type'] != 'LegalEntity': continue
            
            # Find all Business Units
            for rel, target_id in self.adj.get(root_id, []):
                if rel == 'HAS_BUSINESS_UNIT' and self.nodes.get(target_id, {}).get('type') == 'BusinessUnit':
                    # Check if this BU operates a site
                    for bu_rel, site_id in self.adj.get(target_id, []):
                        if bu_rel in ['OPERATES_SITE', 'OWNS_SITE', 'LOCATED_IN']:
                            inferred.append({
                                "id": f"inf_site_{root_id}_{site_id}",
                                "source": root_id,
                                "target": site_id,
                                "relation": "INDIRECT_PRESENCE",
                                "is_inferred": True,
                                "evidence": [{"status": "INFERRED", "source_text": f"Inferred via BusinessUnit {target_id}"}]
                            })
        return inferred

    def _infer_sector_inheritance(self) -> List[Dict]:
        """Rule: BusinessUnit -> BELONGS_TO_SECTOR -> Sector  => LegalEntity -> SHARES_SECTOR -> Sector"""
        inferred = []
        for root_id, node in self.nodes.items():
            if node['type'] != 'LegalEntity': continue
            
            for rel, bu_id in self.adj.get(root_id, []):
                if rel == 'HAS_BUSINESS_UNIT':
                    for bu_rel, sector_id in self.adj.get(bu_id, []):
                        if bu_rel == 'BELONGS_TO_SECTOR':
                            inferred.append({
                                "id": f"inf_sec_{root_id}_{sector_id}",
                                "source": root_id,
                                "target": sector_id,
                                "relation": "SHARES_SECTOR",
                                "is_inferred": True,
                                "evidence": [{"status": "INFERRED", "source_text": f"Inferred via BusinessUnit {bu_id}"}]
                            })
        return inferred
