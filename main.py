"""
Zone 1 Entity Graph Explorer — FastAPI Server
===============================================
Serves the API (extraction, graph state, reset) and static frontend files.

Run:
  uvicorn main:app --reload --port 8000

Environment variables:
  LLM_API_KEY   — Your API key (Groq / OpenAI / etc.)
  LLM_BASE_URL  — API base URL (default: https://api.groq.com/openai/v1)
  LLM_MODEL     — Model name (default: llama-3.3-70b-versatile)
"""

from __future__ import annotations

import os
import traceback
from dotenv import load_dotenv

load_dotenv()  # Load .env before other imports that read env vars

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from graph_store import GraphStore
from extraction import call_llm

# ────────────────────────────────────────────────────────────────────────
# APP SETUP
# ────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Zone 1 Entity Graph Explorer",
    description="Interactive Zone 1 (Entity Zone) knowledge graph builder for investment analysis",
    version="1.0.0",
)

# ── GLOBAL STATE ──
# The 'store' is the brain of the app, coordinating database and LLM-driven ingestion.
store = GraphStore()

# ── STARTUP SEQUENCE ──
# Ensures the ontology is alive and the LogicGuard is ready to validate incoming extractions.
@app.on_event("startup")
def startup_seed():
    print("SERVER STARTUP: Checking ontology updates...")
    try:
        # Initial seed if empty
        store.db.seed_ontology()
        store.ontology = store.db.get_ontology()
        from validators import LogicGuard
        store.guard = LogicGuard(store.ontology)
        print("SERVER STARTUP: Ontology updated successfully.")
    except Exception as e:
        print(f"SERVER STARTUP ERROR: {e}")

@app.post("/api/admin/reseed")
async def reseed_ontology():
    """Administrative endpoint to force refresh the ontology without restarting."""
    try:
        store.db.seed_ontology()
        store.ontology = store.db.get_ontology()
        from validators import LogicGuard
        store.guard = LogicGuard(store.ontology)
        return {"success": True, "message": "Ontology re-seeded successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ────────────────────────────────────────────────────────────────────────
# REQUEST / RESPONSE MODELS
# ────────────────────────────────────────────────────────────────────────

class ExtractRequest(BaseModel):
    text: str
    document_name: str = "User Input"
    section_ref: str = "chunk"
    source_authority: int = 5
    metadata: dict = {}


# ── EXTRACTION & INGESTION ──
# This is the primary endpoint that accepts raw text and turns it into graph nodes.
@app.post("/api/extract")
async def extract_entities(req: ExtractRequest):
    """
    Accept a text chunk, extract Zone 1 entities/relations via LLM,
    ingest into graph store, and return the diff + full graph.
    """
    api_key = os.getenv("LLM_API_KEY", "")
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="LLM_API_KEY not configured. Set it in your .env file."
        )

    try:
        # Call LLM for extraction
        payload = await call_llm(
            text=req.text,
            document_name=req.document_name,
            section_ref=req.section_ref,
            metadata=req.metadata
        )

        # Ingest into graph store
        diff = store.ingest_extraction(payload, source_authority=req.source_authority)

        # Return diff + full graph state
        full_graph = store.get_full_graph()
        return {
            "success": True,
            "diff": {
                "new_entities": [e.canonical_name for e in payload.entities],  # Simple proxy for 'newness' for UI
                "total_entities": full_graph['stats']['total_entities'],
                "total_relations": full_graph['stats']['total_relations']
            },
            "graph": full_graph,
            "extraction": {
                "entities_extracted": len(payload.entities),
                "relations_extracted": len(payload.relations),
                "thought_process": payload.thought_process,
                "llm_analysis_summary": payload.llm_analysis_summary,
                "analysis_attributes": payload.analysis_attributes.dict() if payload.analysis_attributes else None,
                "abstentions": payload.abstentions,
                "discoveries": [d.dict() for d in payload.discoveries],
            },
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/graph")
async def get_graph():
    """Return the current full graph state."""
    return store.get_full_graph()


@app.get("/api/log")
async def get_log():
    """Return the extraction history log."""
    return store.get_extraction_log()


@app.delete("/api/graph")
async def reset_graph():
    """Clear the entire graph store."""
    store.reset()
    return {"success": True, "message": "Graph reset successfully."}


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "llm_configured": bool(os.getenv("LLM_API_KEY")),
        "llm_model": os.getenv("LLM_MODEL", "llama-3.3-70b-versatile"),
        "llm_base_url": os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1"),
    }

@app.get("/api/ontology")
async def get_ontology():
    """Returns the current ontology rules (entity types, relations, colors)."""
    return store.db.get_ontology()


# ────────────────────────────────────────────────────────────────────────
# STATIC FILES — serve the frontend
# ────────────────────────────────────────────────────────────────────────

@app.get("/")
async def serve_index():
    return FileResponse("static/index.html")

from fastapi import Request
from fastapi.responses import JSONResponse
import traceback

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    print(f"GLOBAL ERROR: {exc}")
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error", "message": str(exc)},
    )

# Mount static files AFTER specific routes
app.mount("/static", StaticFiles(directory="static"), name="static")
